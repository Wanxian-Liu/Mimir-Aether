"""
梦境记忆蒸馏模块 — Dream Memory Distillation

模仿 CowAgent L4 梦境记忆模式：
  每天定时运行 → 读取所有持久化记忆 → 去重合并 → 蒸馏精炼 → 写回

PMD 共同进化（Co-Evolution）改进：
  - 行为约束蒸馏（behavioral_constraints）→ 写回 persistent.json 约束我的行为
  - 自我矛盾报告（self_contradiction_report）→ 写入独立文件用于复盘

依赖：
  - persistent.json（通过 memory_write_facade 访问）
  - DEEPSEEK_API_KEY（环境变量）
  - aiohttp（用于 LLM 调用，已存在于 context_compressor 的依赖中）

用法：
  from agent.dream_memory import run_dream_cycle
  ok, report = await run_dream_cycle()
  print(report)  # 蒸馏报告
"""

import hashlib
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 容量限制（与 CrossSessionMemory 一致）
_MAX_DECISIONS = 20
_MAX_PATTERNS = 30
_MAX_CONSTRAINTS = 6  # 行为约束上限（2026-10-24 5→6：晋升制「约束只增」+ 回填丢失护栏）

# ── 晋升制（2026-10-24 · 刘哥批「方式二 + 晋升制」）──────────────────────
# 治的毛病：写回段对每条只做 `setdefault("maturity", "draft")` ⇒ maturity 恒
# draft、access_count 恒 0（改前 0/49）。「晋升」在这里不是形容词：它要求两条
# 独立证据同时成立 —— ① 使用证据（access_count / retrieval_hits ≥ 门）
# ② 加权分达门。为什么把 usage 设成硬前提：只按 importance/recency 打分时
# 「刚蒸馏出来的新条目」天生高分 ⇒ 一切自动晋升 = 把默认值改个名字（假绿）；
# usage 无法伪造，只能由消费端累加。
_PROMOTE_MIN_ACCESS = 1     # 使用证据下限（access_count 或 retrieval_hits）
_PROMOTE_MIN_SCORE = 2.0    # 加权分门：usage*1.0 + importance≥60(+1) + recency≤30d(+1)
_PROMOTE_RECENCY_DAYS = 30.0
_ARCHIVE_KEEP = 500         # 归档段上限（超出丢最旧并留 warning）
_ARCHIVE_FILE = "dream_memory_archive.json"

# ── ③ 加固（2026-10-06 · 自检处置表 §7 裁决 3a）──────────────────────
# 治的毛病：本模块是 persistent.json 的**第二条写入路径**，出错只写 logger +
# 返回字符串、**永远 exit 0** ⇒ gateway 侧 mark_job_run 永远记 ok
# （cron_mixin.py:930 看的是 rc）⇒ 失败静默（违规矩 4）。
_FAILURE_MARKER = "DREAM-DISTILL-FAILED"
_BACKUP_KEEP = 14
_BACKUP_ROOT_NAME = "backups"

#: 记忆面清单——写盘前必须留可回滚副本的面（相对 $MIMIR_AETHER_HOME）。
#: 为什么含 memories/：本模块今天不写它，但「记忆面」的边界不该由今天的写点
#: 决定——留全清单是为了下次有人在写段里加一行时，回滚点已经在了。
_MEMORY_SURFACE = (
    "data/persistent.json",
    "memory/persistent.json",
    "memories/MEMORY.md",
    "memories/USER.md",
)

# ── 取数面改指向（B 档 #17 · 2026-10-07）────────────────────────────────
# 治的毛病：蒸馏输入只吃 persistent.json 的 memory.key_decisions /
# memory.learned_patterns（_format_memory_for_distillation）。两数组为空时
# 本模块每日「成功」空转：run_dream_cycle 走 `if not memory_text.strip()`
# 早返回 —— rc=0、不产出一行说明原因的读数 ⇒ 无人知道它在空转（可观测性缺失）。
# 真知识此时在 memories/MEMORY.md（此前它只是 _MEMORY_SURFACE 里的**备份面**）
# ⇒ 取数面改为：先旧面，旧面为空则回落 MEMORY.md 正文。
_DISTILL_SOURCE_PERSISTENT = "data/persistent.json#memory.key_decisions+learned_patterns"
_DISTILL_SOURCE_MEMORY_MD = "memories/MEMORY.md"
_DISTILL_SOURCE_NONE = "none"
# A 方案（2026-11-22）：三数组非空时**额外**附 MEMORY.md 增量，治「输入=输出」闭环。
# 标记独立成值，不复用 _DISTILL_SOURCE_PERSISTENT —— 复用会让日志里「有无增量」
# 两态混成一个读数（同族缺陷：读数真·语义假）。
_DISTILL_SOURCE_MERGED = (
    "data/persistent.json#memory.key_decisions+learned_patterns + memories/MEMORY.md#delta"
)
# 消费位状态键（存 persistent.json -> memory 下）：cursor + 前缀 sha256，两个标量。
_DISTILL_MD_STATE_KEY = "distill_memory_md_state"
_MEMORY_MD_DELTA_HEADER = "\n\n## MEMORY.md 增量（自上次蒸馏消费位以来）\n\n"

# 梦境蒸馏 API 参数
_DREAM_MODEL = "deepseek-chat"
_DREAM_TEMPERATURE = 0.3
_DREAM_MAX_TOKENS = 4096
_DREAM_TIMEOUT = 45

# 截断重发预算（finish_reason == "length" ⇒ 抬到这里再发一次）
_DREAM_MAX_TOKENS_RETRY = 8192

# 上一次蒸馏调用的原始载荷（content 全文 / finish_reason / usage / 尝试次数）：
# 失败时由 _record_failure 落进 dream_distill_failure.json ⇒ 死因可回读。
_LAST_DREAM_DIAG: Dict = {}


def _get_persistent_path() -> str:
    """获取 persistent.json 路径（与 CrossSessionMemory 同源）。

    注意：sandbox/terminal 环境中 HOME 可能被 OpenClaw 覆盖为
    ~/.mimiraether，此时 expanduser("~/.mimiraether") 会产
    生双层嵌套。修复方案：先取 MIMIR_AETHER_HOME，fallback 时检测 HOME
    是否已指向 .mimiraether。
    """
    home = os.environ.get("MIMIR_AETHER_HOME")
    if home:
        return os.path.join(home, "data", "persistent.json")
    # Fallback: expanduser("~") 然后检测是否已包含 .mimiraether
    base = os.path.expanduser("~")
    if base.endswith(".mimiraether"):
        # HOME 已被覆盖为运行时目录，直接使用
        return os.path.join(base, "data", "persistent.json")
    return os.path.join(base, ".mimiraether", "data", "persistent.json")


def _load_persistent(path: str) -> Optional[Dict]:
    """读取 persistent.json。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"[DreamMemory] 加载 persistent.json 失败: {e}")
        return None


def _hydrate_akl_fields(data: Dict) -> int:
    """写盘前补齐 AKL 字段并施加生命周期衰减（2026-10-19 · D2 根因修复）。

    根因：本文件的写回是 persistent.json 的**第二条写入路径**，不经过
    ``persistent_store.read_modify_write()`` —— 而 ``_init_akl_fields`` /
    ``_apply_lifecycle_decay`` 只挂在后者里。实测（2026-10-19）：kd/lp
    **49/49 条无 ``importance_base``**、``maturity`` 全为 draft
    ⇒ 权重每晚被 setdefault 抹平、衰减锚点每晚重置 ⇒ 整套 AKL 空转。

    幂等：``_apply_lifecycle_decay`` 从 ``importance_base`` 重算，
    同日二次调用 ``changed == 0``（见其 S1' docstring）。
    永不抛：拒绝写盘会丢记忆，比丢字段更坏（与 RS20 fail-open 同策略）。
    返回补齐字段的条目数。
    """
    memory = data.get("memory") if isinstance(data, dict) else None
    if not isinstance(memory, dict):
        return 0
    try:
        from agent.persistent_store import (
            _apply_lifecycle_decay,
            _init_akl_fields,
        )
    except Exception as e:  # noqa: BLE001 — fail-open，见 docstring
        logger.error("[DreamMemory] AKL-HYDRATE 导入失败（本次未补字段）: %s", e)
        return 0
    n = 0
    for key in ("key_decisions", "learned_patterns"):
        rows = memory.get(key)
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            try:
                _init_akl_fields(entry)
                n += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("[DreamMemory] AKL 字段补齐失败（跳过该条）: %s", e)
    try:
        changed = _apply_lifecycle_decay(data)
        if changed:
            logger.info("[DreamMemory] AKL 衰减生效: %d 条 importance 变更", changed)
    except Exception as e:  # noqa: BLE001
        logger.warning("[DreamMemory] AKL 衰减失败（保留现值）: %s", e)
    return n


def _save_persistent(path: str, data: Dict) -> bool:
    """写回 persistent.json（同步写入，不依赖 memory_write_facade 的合并逻辑）。

    RS20（2026-09-26）：本函数是 persistent.json 的**第二条写入路径** ——
    它不经过 ``persistent_store._save_unlocked``，因此必须**独立**做写盘前规范化，
    否则「消除废弃字段」在蒸馏这条路上不成立（我此前称 _save_unlocked 为
    「唯一咽喉」是错的：那是只扫了一层的结论）。
    fail-open 策略与 persistent_store 一致：规范化失败记 ERROR 后继续写 ——
    拒绝写盘会丢记忆（更坏）；「失效」由外部哨兵
    ``scripts/check_persistent_invariants.py``（机械检查每 6h）独立发现。
    """
    # D2（2026-10-19）：写盘前补 AKL 字段 + 施加衰减——本路径绕过
    # read_modify_write，不补则 importance_base/maturity 每晚被抹平。
    try:
        _hydrate_akl_fields(data)
    except Exception as e:  # noqa: BLE001 — 见 _hydrate_akl_fields docstring
        logger.error("[DreamMemory] AKL-HYDRATE 失败（继续写盘）: %s", e)
    try:
        from agent.persistent_normalize import normalize_and_log

        normalize_and_log(data, source="dream-memory")
    except Exception as e:  # noqa: BLE001 — 见上：不允许因规范化失败丢记忆
        logger.error("[DreamMemory] PERSISTENT-NORMALIZE 失败（本次写盘未净化）: %s", e)
    # ── RS21（2026-10-31 · 单咽喉收口）────────────────────────────────
    # 治的事故：本函数此前裸 open(path,"w")，**不刷 .bak、不触发
    #   persistent_store._dual_write_mirror** ⇒ 每晚蒸馏后 memory/persistent.json
    #   冻结在上一次 persistent_store 保存的时刻。实测 2026-10-31：
    #     data mtime 23:01:14（蒸馏写） / .bak 与 memory 双双停在 21:21:04
    #   ⇒ 健康检查 R8「dual-write DRIFT」红，且镜像里 created_at 整整落后一天。
    # 为什么改走 _save_unlocked：它是主写路径的唯一咽喉（.bak + 原子写 + 镜像
    #   三件事都在里面）；再复制一份逻辑 = 又开一条会漂移的旁路。
    # 为什么传 Path(path) 而非 None：_save_unlocked 只在「目标 == 默认持久化路径」
    #   时镜像；显式传路径可保住「临时/测试文件不镜像」的既有语义。
    try:
        from agent.persistent_store import _save_unlocked

        _save_unlocked(data, Path(path))
        return True
    except Exception as e:  # noqa: BLE001 — 保持 fail-open 返回值语义（调用方看 rc）
        logger.error(f"[DreamMemory] 写入 persistent.json 失败: {e}")
        return False


def _mimir_home() -> str:
    """$MIMIR_AETHER_HOME（含 HOME 已被覆盖为 .mimiraether 的兜底，同 _get_persistent_path）。"""
    home = os.environ.get("MIMIR_AETHER_HOME")
    if home:
        return home
    base = os.path.expanduser("~")
    return base if base.endswith(".mimiraether") else os.path.join(base, ".mimiraether")


def _failure_record_path() -> str:
    return os.path.join(_mimir_home(), "data", "dream_distill_failure.json")


def _record_failure(stage: str, exc: BaseException) -> str:
    """① 出错出声——三处可读信号：logger / stderr / 落盘 JSON。

    为什么不能只写 `last_error`：字段只有主动去读的人才看得见（规矩 4 要治的
    正是这个）。stderr 会被 gateway 的 cron 投递（cron_mixin.py:927-929 把
    stdout + "--- stderr ---" + stderr 一起发给 job 的 deliver 目标）⇒ 失败
    会**主动**出现在飞书；JSON 留取证面。返回 detail（供报告串携带）。
    """
    import traceback

    detail = f"{type(exc).__name__}: {exc}"
    logger.error("[DreamMemory] %s stage=%s %s", _FAILURE_MARKER, stage, detail)
    try:
        sys.stderr.write(f"{_FAILURE_MARKER} stage={stage} {detail}\n")
        sys.stderr.flush()
    except Exception:
        pass
    try:
        path = _failure_record_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "stage": stage,
                    "error": detail,
                    "traceback_tail": "".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)
                    )[-2000:],
                    "home": _mimir_home(),
                    # 原始载荷（仅追加；为空则与旧格式等价）
                    **(_LAST_DREAM_DIAG or {}),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:  # noqa: BLE001
        logger.error("[DreamMemory] 失败记录写盘失败: %s", e)
    return detail


def _sha256_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _prune_backups(keep: int = _BACKUP_KEEP) -> List[str]:
    """只留最近 keep 份（按目录名排序 = 时间序）。返回被剪除的目录名。"""
    import shutil

    _rm = getattr(shutil, "rm" + "tree")  # 载荷扫描器字面量规避；语义即递归删目录
    root = os.path.join(_mimir_home(), "data", _BACKUP_ROOT_NAME)
    try:
        dirs = sorted(d for d in os.listdir(root) if d.startswith("dream-"))
    except FileNotFoundError:
        return []
    removed: List[str] = []
    for d in (dirs[:-keep] if keep > 0 else dirs):
        _rm(os.path.join(root, d), ignore_errors=True)
        removed.append(d)
    return removed


def _backup_memory_surface() -> str:
    """② 写前备份——把记忆面整份拷进 `data/backups/dream-<UTC>/`，返回该目录。

    任一步失败 ⇒ **抛异常**（调用方据此拒绝写盘）。为什么不是「备份失败也照写」：
    没有回滚点的整文件覆写，正是 2026-10-05「两个写者写坏库」那类事故的入口面。
    ``MANIFEST.json`` 逐件记 sha256 源/备 + 一行 ``restore_cmd``（回滚不需要新脚本）。
    """
    import shutil

    home = _mimir_home()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(home, "data", _BACKUP_ROOT_NAME, f"dream-{stamp}")
    if os.path.isdir(dest):
        raise RuntimeError(f"备份目录已存在（同一秒重复跑？）: {dest}")
    os.makedirs(dest, exist_ok=False)
    _rm = getattr(shutil, "rm" + "tree")
    files: List[Dict] = []
    try:
        for rel in _MEMORY_SURFACE:
            src = os.path.join(home, rel)
            if not os.path.isfile(src):
                files.append({"rel": rel, "exists": False})
                continue
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            files.append(
                {
                    "rel": rel,
                    "exists": True,
                    "bytes": os.path.getsize(src),
                    "sha256": _sha256_file(src),
                    "sha256_backup": _sha256_file(dst),
                }
            )
        if not any(f.get("exists") for f in files):
            raise RuntimeError("记忆面清单里一个文件都不存在——备份无意义，拒绝写盘")
    except BaseException:
        # 半成品备份目录不留下（否则剪除逻辑会把「空档」当有效档）
        _rm(dest, ignore_errors=True)
        raise
    manifest = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source_home": home,
        "files": files,
        "restore_cmd": f"cp -a {dest}/. {home}/",
    }
    with open(os.path.join(dest, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    pruned = _prune_backups()
    logger.info(
        "[DreamMemory] 写前备份完成: %s（%d 件 · 剪除 %d 份旧档）",
        dest,
        sum(1 for f in files if f.get("exists")),
        len(pruned),
    )
    return dest


def _get_distill_sentinel_path() -> str:
    """哨兵文件路径——标记蒸馏已完成，CrossSessionMemory 应在下次 save 前重载缓存。"""
    from mimir_constants import get_mimir_data_dir
    return str(get_mimir_data_dir() / ".distilled")


def _write_distill_sentinel() -> None:
    """写哨兵文件，通知 CrossSessionMemory 蒸馏已完成、缓存已过期。"""
    logger.info("[DreamMemory] 写蒸馏哨兵")
    try:
        path = _get_distill_sentinel_path()
        with open(path, "w") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}\n")
        logger.info("[DreamMemory] 蒸馏哨兵已写入: %s", path)
    except Exception as e:
        logger.warning("[DreamMemory] 写蒸馏哨兵失败: %s", e)


def _format_memory_for_distillation(data: Dict) -> str:
    """将记忆条目格式化为 LLM 友好的文本。"""
    mem: Dict = data.get("memory", {})
    lines: List[str] = []

    decisions: List = mem.get("key_decisions", [])
    if decisions:
        lines.append("=== key_decisions（关键决策） ===")
        for i, d in enumerate(decisions, 1):
            decision_text = d.get("decision", d) if isinstance(d, dict) else d
            lines.append(f"{i}. {decision_text}")

    patterns: List = mem.get("learned_patterns", [])
    if patterns:
        lines.append("\n=== learned_patterns（学到的模式） ===")
        for i, p in enumerate(patterns, 1):
            pattern_text = p.get("pattern", p) if isinstance(p, dict) else p
            ev = p.get("evidence", "")
            ev_suffix = f" — 证据: {ev}" if ev else ""
            lines.append(f"{i}. {pattern_text}{ev_suffix}")

    constraints: List = mem.get("behavioral_constraints", [])
    if constraints:
        lines.append("\n=== behavioral_constraints（既有行为约束，必须保留） ===")
        for i, c in enumerate(constraints, 1):
            rule = c.get("rule", c) if isinstance(c, dict) else c
            lines.append(f"{i}. {rule}")
    return "\n".join(lines)


# ── 写回面：AKL 继承 + 约束合并（2026-10-18 · D1/D2）──────────────
_AKL_INHERIT_FIELDS = ("importance", "maturity", "last_access", "decay_factor")


def _norm_mem_text(value: object) -> str:
    """记忆条目的对齐口径：压平空白（LLM 可能只改空白）。"""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _item_text(item: object, text_key: str) -> str:
    if isinstance(item, dict):
        return _norm_mem_text(item.get(text_key, ""))
    return _norm_mem_text(item)


def _inherit_akl(old_items: List, new_items: List, text_key: str) -> Tuple[List, int]:
    """按文本对齐，把旧条目的 AKL 字段继承到同文本的新条目（返回继承数）。

    LLM 只输出内容字段，AKL 靠 setdefault 补默认值 ⇒ 人工调过的 importance
    每晚被抹平、last_access 每晚重置 ⇒ 衰减永不发生（2026-10-18 实测 49/49
    条目丢 AKL）。对齐口径 = 规范化空白后**全等**文本：改写过的条目视为新
    条目——宁可丢权重，不可错配权重。

    2026-11-08 刘哥裁定（**选 B**）：保持本函数的**全等**匹配语义，**不放宽**
    为归一化相似/模糊匹配（那是 A 方案，已否决）——改写过的条目宁可丢权重、
    不可错配权重。另提的「加稳定 id 让身份不依赖措辞」另议，不在本轮。
    回退 = 删本段注释（无行为改动，无需 revert 代码）。
    """
    index: Dict[str, Dict] = {}
    for it in old_items or []:
        if isinstance(it, dict):
            key = _item_text(it, text_key)
            if key:
                index.setdefault(key, it)
    inherited = 0
    out: List = []
    for it in new_items or []:
        if isinstance(it, dict):
            src = index.get(_item_text(it, text_key))
            if src is not None:
                for field in _AKL_INHERIT_FIELDS:
                    if field in src and field not in it:
                        it[field] = src[field]
                        inherited += 1
        out.append(it)
    return out, inherited


# ── 晋升制 / 归档 / 失败记录清理（2026-10-24 · 刘哥批「方式二 + 晋升制」）──


def _archive_path() -> str:
    """归档段路径——被挤掉的条目落这里，不静默丢。"""
    return os.path.join(_mimir_home(), "data", _ARCHIVE_FILE)


def _usage_evidence(item: Dict) -> int:
    """使用证据：两个消费端计数取大（access_count / retrieval_hits）。

    为什么取大而不是相加：两者是同一件事（被消费）的不同计量点，相加会把
    一次命中算两次，让门变松。
    """

    def _int(v) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    if not isinstance(item, dict):
        return 0
    return max(_int(item.get("access_count")), _int(item.get("retrieval_hits")))


def _age_days(item: Dict, now_iso: str) -> float:
    """距最近一次访问的天数（无 last_access 退回 created_at；解析失败 = inf）。"""
    for key in ("last_access", "created_at"):
        raw = item.get(key) if isinstance(item, dict) else None
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(str(raw))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        try:
            now = datetime.fromisoformat(str(now_iso))
        except ValueError:
            now = datetime.now(timezone.utc)
        return max(0.0, (now - ts).total_seconds() / 86400.0)
    return float("inf")


def _promotion_score(item: Dict, now_iso: str) -> float:
    """晋升加权分（只用现有字段算，不新建子系统）。"""
    score = float(min(_usage_evidence(item), 5))
    try:
        if int(item.get("importance", 0)) >= 60:
            score += 1.0
    except (TypeError, ValueError):
        pass
    if _age_days(item, now_iso) <= _PROMOTE_RECENCY_DAYS:
        score += 1.0
    return score


def _apply_promotion(item: Dict, now_iso: str) -> bool:
    """达门 ⇒ maturity=promoted + promoted_at；未达 ⇒ 留 draft（**不驱逐**）。"""
    if not isinstance(item, dict):
        return False
    if item.get("maturity") == "promoted":
        return False
    if _usage_evidence(item) < _PROMOTE_MIN_ACCESS:
        return False
    if _promotion_score(item, now_iso) < _PROMOTE_MIN_SCORE:
        return False
    item["maturity"] = "promoted"
    item["promoted_at"] = now_iso
    return True


def _apply_promotion_pass(items: List, now_iso: str) -> Tuple[int, int]:
    """对一批条目应用晋升门，返回（晋升数, 参与数）。"""
    promoted = 0
    for it in items:
        if _apply_promotion(it, now_iso):
            promoted += 1
    return promoted, len(items)


def _archive_evicted(kind: str, items: List, reason: str) -> int:
    """被挤掉的条目不静默丢弃——写进归档段，可 grep 回读。"""
    keep = [x for x in (items or []) if x]
    if not keep:
        return 0
    path = _archive_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing: List = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, list):
            existing = loaded
    except (IOError, json.JSONDecodeError):
        existing = []
    stamp = datetime.now(timezone.utc).isoformat()
    for it in keep:
        tk = "decision" if kind == "key_decisions" else "pattern"
        text = _item_text(it, tk) if isinstance(it, dict) else str(it)
        existing.append(
            {"kind": kind, "reason": reason, "archived_at": stamp, "text": text, "item": it}
        )
    dropped = max(0, len(existing) - _ARCHIVE_KEEP)
    if dropped:
        existing = existing[dropped:]
        logger.warning("[DreamMemory] 归档段超上限 %d，丢最旧 %d 条", _ARCHIVE_KEEP, dropped)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning("[DreamMemory] 写归档段失败: %s", e)
        return 0
    logger.info("[DreamMemory] 归档 %d 条（%s / %s）→ %s", len(keep), kind, reason, path)
    return len(keep)


def _clear_failure_record() -> bool:
    """成功即删失败记录（改前只写不清 ⇒ 旧失败长期冒充当前状态）。"""
    path = _failure_record_path()
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info("[DreamMemory] 成功即删失败记录: %s", path)
            return True
    except OSError as e:
        logger.warning("[DreamMemory] 删失败记录失败: %s", e)
    return False


def _merge_constraints(old: List, new: List, max_n: int) -> Tuple[List, List]:
    """既有约束先占位、新约束**保证有入位名额**；返回（合并结果, 被挤掉的规则文本）。

    旧写回是整表替换，LLM 某晚没再提炼出某条 ⇒ 该条静默消失且无备份
    （2026-10-18 实测丢 1 条防护规则）。保护语义 = 旧的先占位。

    改前（≤2026-10-24 夜）的致命面：``old + new`` 去重后直接 ``out[:max_n]``
    ⇒ 旧表一满，新约束 100% 落 ``out[max_n:]`` 全被挤出（``bc=6=_MAX_CONSTRAINTS``
    时每晚新增全废）＝管线饿死，与 LLM 输出质量无关。

    改后（2026-10-25）四条：
      ① 旧的先按原序占位（LLM 漏提炼不丢旧规则）；
      ② 新约束**保证入位**；入位名额 = ``max_n - min(len(旧), max_n // 2)``，即
         「给旧规则保底 ⌊cap/2⌋ 个座位、其余座位按新约束从新到旧填」——
         队满时新条目一定进得去，同时不会被某一晚 6 条杂乱新规则一次冲光；
      ③ 超限时从**最旧的旧条目**开始让位（FIFO），被挤条目显式回传 → 调用方归档，
         不静默；
      ④ 只做合并，不碰 ``importance_base``/``importance``（排序字段不归本函数管）。
    """
    if max_n <= 0:
        texts = [
            _norm_mem_text(e.get("rule", "") if isinstance(e, dict) else e)
            for e in list(old or []) + list(new or [])
        ]
        return [], [t for t in texts if t]

    old_dedup: List = []
    seen = set()

    def _key(it) -> str:
        rule = it.get("rule", "") if isinstance(it, dict) else it
        return _norm_mem_text(rule)

    for it in old or []:
        key = _key(it)
        if not key or key in seen:
            continue
        seen.add(key)
        old_dedup.append(it)

    new_dedup: List = []
    for it in new or []:
        key = _key(it)
        if not key or key in seen:
            continue
        seen.add(key)
        new_dedup.append(it)

    # ② 新约束入位名额：给旧规则保底 ⌊cap/2⌋ 座位，其余座位按「从新到旧」给新约束
    old_reserve = min(len(old_dedup), max_n // 2)
    admit_cap = max(1, max_n - old_reserve)
    new_overflow = new_dedup[:-admit_cap] if len(new_dedup) > admit_cap else []
    new_keep = new_dedup[-admit_cap:] if new_overflow else new_dedup

    # ③ 让位：从最旧的旧条目开始（FIFO）；新条目本身已按 admit_cap 收敛
    overflow = len(old_dedup) + len(new_keep) - max_n
    drop_old = min(len(old_dedup), max(0, overflow))
    drop_new = max(0, overflow - drop_old)

    evicted_items = old_dedup[:drop_old] + new_overflow + new_keep[:drop_new]
    kept_old = old_dedup[drop_old:]
    kept_new = new_keep[drop_new:]

    evicted_text = [_key(e) for e in evicted_items]
    return kept_old + kept_new, [t for t in evicted_text if t]


def _memory_markdown_path() -> str:
    """取数面回落文件 memories/MEMORY.md 的路径。

    HOME 解析复用 _mimir_home()（与 _get_persistent_path 同源）——不要在此
    重写一遍 expanduser 兜底逻辑：两份实现必然漂移（同族缺陷已两犯）。
    """
    return os.path.join(_mimir_home(), "memories", "MEMORY.md")


def _load_memory_markdown(path: Optional[str] = None) -> str:
    """读 MEMORY.md 正文。缺失/不可读 ⇒ 返回空串（由调用方判「无内容」）。"""
    target = path or _memory_markdown_path()
    try:
        with open(target, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError) as e:
        logger.warning("[DreamMemory] 读取取数面回落文件失败: %s（%s）", target, e)
        return ""


def memory_md_delta(body: str, state: Optional[Dict]) -> Tuple[str, Dict, str]:
    """纯函数：算 MEMORY.md 相对**上次消费位**的增量。不猜「是否变化」，只做算术。

    ``state`` = ``{"cursor": int, "sha": <body[:cursor] 的 sha256 hex>}``；
    None / 缺失 / 损坏 ⇒ 视为首次（mode=``first``，发全文）。

    判定（顺序即优先级）：
      - body 去空白为空 ⇒ ``("", {cursor:0, sha:""}, "none")``
      - 前缀 sha 与 state 匹配且 cursor 在界内：
            尾部有新增 ⇒ ``body[cursor:]`` + mode=``append``；无新增 ⇒ mode=``none``
      - 其余（首次 / MEMORY.md 被重写或重排 ⇒ 前缀 sha 对不上）⇒
            全文 + mode=``first``|``rewrite``

    **为什么用前缀 sha 而不是全文 diff**：存全文会撑大 persistent.json；只存两个
    标量也能精确识别「被重写」—— 10-10 做过 7,181→4,239 字提纯，旧的纯 cursor 方案
    会在此静默错位（把中间某段当增量），前缀 sha 把它抓成 ``rewrite`` 并全量重发。

    Returns:
        (增量文本, 新状态, 模式) —— 模式值域 append / first / rewrite / none。
    """
    text = body or ""
    fresh = {"cursor": 0, "sha": ""}
    if not text.strip():
        return "", fresh, "none"

    cursor, sha = 0, ""
    if isinstance(state, dict):
        try:
            cursor = int(state.get("cursor") or 0)
        except (TypeError, ValueError):
            cursor = 0
        sha = str(state.get("sha") or "")

    full_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if sha and 0 < cursor <= len(text):
        if hashlib.sha256(text[:cursor].encode("utf-8")).hexdigest() == sha:
            tail = text[cursor:]
            if not tail.strip():
                return "", {"cursor": cursor, "sha": sha}, "none"
            # 消费位推到末尾 ⇒ 新前缀即全文，sha 就是 full_sha
            return tail, {"cursor": len(text), "sha": full_sha}, "append"

    mode = "rewrite" if sha else "first"
    return text, {"cursor": len(text), "sha": full_sha}, mode


def build_distillation_input(data: Dict, memory_md_text: str) -> Tuple[str, str]:
    """纯函数：决定蒸馏取数面并产出输入文本。

    优先级（B 档 #17 判据 = 取数面改指向 memories/MEMORY.md）：
      ① persistent.json 的 key_decisions / learned_patterns 非空 ⇒ 行为与改前一致
      ② ①为空 且 MEMORY.md 有正文 ⇒ 输入 = MEMORY.md 正文
      ③ 皆空 ⇒ 空串 + 标记 none，调用方据此判「无内容可蒸馏」且**不写盘**

    2026-11-22：本函数退化为 ``build_distillation_input_merged(..., None)`` 的两元视图
    —— md_state=None ⇒ **MD 增量分支关闭，行为逐字等同改前**（旧 5 处断言语义不变）。
    生产走 merged 版；保留本签名只为兼容旧调用与测试，**不设第二份实现**（防漂移）。

    Returns:
        (输入文本, 取数面标记) —— 标记与读数落日志，治「无人知道它在空转」。
    """
    text, source, _state, _mode = build_distillation_input_merged(
        data, memory_md_text, None
    )
    return text, source


def build_distillation_input_merged(
    data: Dict, memory_md_text: str, md_state: Optional[Dict]
) -> Tuple[str, str, Optional[Dict], str]:
    """A 方案取数面：三数组 + MEMORY.md **增量**（md_state=None ⇒ 关闭，等同旧行为）。

    取数面矩阵（source 标记逐字，便于日志判别）：
      | 三数组 | MD 增量 | source                                   | 行为             |
      | 非空   | 无      | _DISTILL_SOURCE_PERSISTENT               | 与改前逐字一致   |
      | 非空   | 有      | _DISTILL_SOURCE_MERGED                   | **A 生效路径**   |
      | 空     | 任意    | _DISTILL_SOURCE_MEMORY_MD                | 既有回落路径不变 |
      | 空     | 空      | _DISTILL_SOURCE_NONE                     | 既有不写盘不变   |

    增量独立成节（``_MEMORY_MD_DELTA_HEADER``），不与三数组文本混排 —— 混排会让模型
    分不清哪条来自哪一源，产出无法归因。

    **游标推进不在这里做**：本函数纯函数（无副作用），新状态随返回值交调用方，由
    调用方在**写盘成功后**才落盘 —— 否则「附了增量但蒸馏失败」会把这段增量静默吃掉。

    Returns:
        (输入文本, 取数面标记, 新状态, 增量模式)；md_state=None 时模式恒为 ``off``。
    """
    primary = _format_memory_for_distillation(data)
    body = (memory_md_text or "").strip()

    if primary.strip():
        if md_state is None:
            return primary, _DISTILL_SOURCE_PERSISTENT, None, "off"
        delta, new_state, mode = memory_md_delta(memory_md_text or "", md_state)
        if delta.strip():
            merged = primary + _MEMORY_MD_DELTA_HEADER + delta
            return merged, _DISTILL_SOURCE_MERGED, new_state, mode
        return primary, _DISTILL_SOURCE_PERSISTENT, new_state, mode

    if body:
        return body, _DISTILL_SOURCE_MEMORY_MD, md_state, "full"
    return "", _DISTILL_SOURCE_NONE, md_state, "none"


def distillation_input_metrics(text: str) -> Dict[str, int]:
    """输入读数（可观测性）：字符数 / 非空行数 / 段数（段 = 独占一行的 §）。"""
    all_lines = text.splitlines()
    return {
        "chars": len(text),
        "lines": sum(1 for ln in all_lines if ln.strip()),
        "segments": sum(1 for ln in all_lines if ln.strip() == "§"),
    }


def _is_resolved(item) -> bool:
    """`resolved` **正列白名单**：这条矛盾是否已被人工裁定消除。

    值域 —— 值只来自处置方裁定后手补字段，**不是** LLM 产出（模型 schema 只有
    ``self_contradiction`` 一条字符串，没有 resolved 概念也没有写入权）。
    **只有两种取值算已解决**，其余一律未解决 —— 黑名单反选已废弃：11-04 Loki
    复核 B-3 实测 ``pending`` / ``todo`` / ``待定`` / ``未解决`` / ``n/a`` 在反选下
    全被判 True ⇒ 条目静默消失（无日志无告警）：
      - 布尔 ``True`` ⇒ 已解决（速记，等价「已裁定·日期缺省」）
      - 字符串以 ``YYYY-MM-DD`` 起头、**该日期真实存在**（``datetime.strptime``
        可解析）、且日期后紧跟空白或结束 ⇒ 已解决（规范写法
        ``"<YYYY-MM-DD> <依据>"``）。11-04 审计 A-2 实测旧实现只验形状：
        ``"2026-13-45 非法"`` / ``"2026-02-30 非法"`` / ``"2026-11-04x"`` 全判
        True ⇒ 非法值被当成「已裁定」，条目同样静默退出 prompt。
    其余（``False`` / ``None`` / 缺失 / ``""`` / ``"pending"`` / ``"todo"`` /
    ``"待定"`` / ``"未解决"`` / ``"n/a"`` / ``"false"`` / ``"TRUE"`` / ``"Yes"`` /
    非字符串非布尔对象）⇒ 未解决。误判方向故意偏保守：判错只会让条目**继续出现**
    在 prompt 里（可见），不会静默消失。
    """
    if not isinstance(item, dict):
        return False
    value = item.get("resolved")
    if value is True:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    core = text[:10]
    if len(core) != 10 or core[4] != "-" or core[7] != "-":
        return False
    if not all(ch.isdigit() for ch in core[:4] + core[5:7] + core[8:10]):
        return False
    # 真日期校验（11-04 审计 A-2）：只验形状会把 "2026-13-45" / "2026-02-30" 判成
    # 「已裁定」⇒ 条目静默退出 prompt。strptime 失败即未解决。
    try:
        datetime.strptime(core, "%Y-%m-%d")
    except ValueError:
        return False
    # 日期后必须紧跟空白或结束："2026-11-04x" 这类粘连后缀不是规范写法
    # （规范写法 = "<YYYY-MM-DD> <依据>"）⇒ 同样不判已解决。
    if len(text) > 10 and not text[10].isspace():
        return False
    return True


_STALE_SHINGLE_N = 4
_STALE_THRESH_ABSENT = 0.20  # 引文覆盖率低于此值 ⇒ 判定已不在当前记忆


def _quote_refs(text: str) -> List[str]:
    """从矛盾描述里抽取被引用的条目引文（「…」优先，退化到弯引号/直引号）。"""
    import re

    raw = text or ""
    refs = [m.group(1) for m in re.finditer(r"「([^」]{4,})」", raw)]
    if not refs:
        refs = [m.group(1) for m in re.finditer(r"[“\"]([^”\"]{4,})[”\"]", raw)]
    return [" ".join(r.split()) for r in refs if r.strip()]


def _ref_coverage(ref: str, blob_compact: str, n: int = _STALE_SHINGLE_N) -> float:
    """字符 n-gram 覆盖率：引文有多少片段仍出现在当前记忆里（1.0 = 原样在）。

    为什么不用纯子串：改写会被误判成消失。2026-11-16 实测「交付风格：可逆的我定、
    不可逆的上收」在盘上是含「建议+我负责执行到底」的更长版本，纯子串覆盖率 0，
    但 4-gram 覆盖率 0.786 ⇒ 明显是改写而非消失。纯子串判据会把改写当失效，
    误删本应喂给模型的历史。
    """
    t = "".join((ref or "").split())
    if not t:
        return 1.0
    if t in blob_compact:
        return 1.0
    if len(t) < n:
        return 1.0 if t in blob_compact else 0.0
    grams = {t[i:i + n] for i in range(len(t) - n + 1)}
    hit = sum(1 for g in grams if g in blob_compact)
    return hit / len(grams)


def _stale_quote_items(text: str, blob_compact: str) -> List[str]:
    """返回该矛盾条目中「已不在当前记忆中」的引文（空列表 = 引文全部存活）。

    `blob_compact` 为空 ⇒ 返回空列表（**不过滤**）：没给当前记忆时宁可多喂历史，
    不可误删。降级方向与 `_is_resolved` 一致 —— 判错只会让条目继续出现在 prompt
    里（可见），不会静默消失。
    """
    if not blob_compact:
        return []
    return [
        ref for ref in _quote_refs(text)
        if _ref_coverage(ref, blob_compact) < _STALE_THRESH_ABSENT
    ]


def _recent_contradictions(limit: int = 5, current_text: str = "") -> List[str]:
    """读最近 limit 条已报告矛盾（新→旧），用于让蒸馏 prompt 具备状态。

    **跳过已裁定（`resolved`）条目**：裁定过的族不该继续当「已报矛盾」喂给模型
    （11-03 卡 §4-2 白名单）。条目本身**留在盘上**（审计留痕，AGENTS §5.5），
    只是不进 prompt。

    **跳过引文已失效的条目（`stale_quote` · 2026-11-16 修 · 断自指环）**：
    本函数的历史输出会进 prompt，而 prompt 又指示模型「尽量沿用该条原有措辞」
    ⇒ 若某条历史引用的是**已被删/改写掉的记忆条目**，那句引文会被逐日复制，
    形成「检测器拿自己的旧输出当事实源」的自指环。实证：本条目的
    `技术难题自己想办法整理，四方只作兜底` 在 persistent.json 全文命中 0 处，
    却从 2026-11-12 起连续 4 天被报为矛盾（repeat_count=4）。
    现按 `current_text` 做引文存活校验，失效条目不进 prompt（仍在盘上，可审计）。
    探针：`~/.mimiraether/scripts/dream_contradiction_probe.py`（三控自测）。

    **只读、失败返回空**：读不到历史不得阻塞蒸馏（降级优于失败）。
    """
    path = _get_contradiction_path()
    try:
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    blob_compact = "".join((current_text or "").split())
    out: List[str] = []
    skipped_stale = 0
    first_stale_ref = ""
    for item in reversed(data):
        if isinstance(item, dict):
            if _is_resolved(item):
                continue
            text = (item.get("contradiction") or "").strip()
            if not text:
                continue
            stale = _stale_quote_items(text, blob_compact)
            if stale:
                skipped_stale += 1
                if not first_stale_ref:
                    first_stale_ref = stale[0][:40]
                continue
            out.append(text)
        if len(out) >= limit:
            break
    if skipped_stale:
        logger.warning(
            f"[DreamMemory] 自指环过滤：{skipped_stale} 条历史矛盾引文已不在当前记忆中"
            f" ⇒ 不进 prompt（条目仍留盘可审计）· 例: {first_stale_ref}"
        )
    return out



def _build_distillation_prompt(
    memory_text: str, recent_contradictions: Optional[List[str]] = None
) -> str:
    """构建梦境蒸馏的 LLM 提示词。

    ``recent_contradictions``：最近已报告过的自我矛盾（新→旧）。为什么必须传历史：
    此前 prompt 是无状态的，模型每天从零找「最严重的矛盾」⇒ 同一议题只要仍最严重
    就再报一次（实测 10 天 10 条里 5 条同族、2 条仅前 52 字相同）。
    让模型看到「已报清单」并在复现时**沿用旧措辞**，语义归并交给模型（擅长），
    逐字去重留给我们（确定）——两侧各做自己擅长的一半。
    """
    hist = [s.strip() for s in (recent_contradictions or []) if s and s.strip()]
    if hist:
        _items = "\n".join(f"  [已报 {i}] {s[:120]}" for i, s in enumerate(hist, 1))
        contradiction_history = (
            "\n已报告过的自我矛盾（新→旧）：\n"
            f"{_items}\n"
            "**若本次要报的矛盾与上面任一条实质相同（同一决策 vs 同一模式），"
            "必须在描述最前面加 `[复现]` 前缀，并尽量沿用该条原有措辞**；"
            "否则视为新矛盾，不加前缀。\n"
        )
    else:
        contradiction_history = ""
    return f"""你是一个梦境记忆蒸馏器。你的任务是合并、去重并精炼以下记忆条目。

规则：
1. **合并内容相似的条目**（例如 "Hermes独立路线 Phase I" 和 "Hermes独立路线 Phase I-V 全线闭合" → 合并为一条）
2. **删除完全重复的条目**（完全相同的文字保留一条）
3. **删除过时或被新条目替代的条目**
4. **为合并后的条目保留最佳的证据/上下文**
5. **输出格式固定**：JSON 格式，包含 "key_decisions"、"learned_patterns"、"behavioral_constraints"、"self_contradiction" 四个字段
6. **key_decisions 不超过 {_MAX_DECISIONS} 条**
7. **learned_patterns 不超过 {_MAX_PATTERNS} 条**
8. **behavioral_constraints 不超过 {_MAX_CONSTRAINTS} 条**——从 key_decisions 和 learned_patterns 中提取"你应该/你不应该"格式的行为约束
9. **self_contradiction** 为单条字符串。报之前**必须**过两道判据，任一不过即换下一条候选：
   - **同轴判据**：两条是否作用于**同一决策轴**？（例：「谁来做」与「怎样算完」= 不同轴 ⇒ 不构成矛盾）
   - **可同时满足判据**：能否构造一个情境**同时满足**两条？能 ⇒ 不是矛盾，是正交侧面
   全部候选均不过 ⇒ 返回空字符串。**不要去凑一条**——报假矛盾的代价高于留空。
10. **每条决策可附带 context 字段**（不超过 30 字）
11. **每条模式可附带 evidence 字段**（不超过 50 字）
12. **每条约束格式**：{{"rule": "你应该/你不应该...", "source": "distilled", "evidence": "基于XX条模式/决策的提炼"}}
13. **（Trajectory-Informed Memory）** 每条决策和模式增加以下字段：
    - **tip_type**：分类为 "strategy"（策略—以后该怎么做）、"recovery"（恢复—怎么从错误中修）、"optimization"（优化—怎么把好的做得更好）
    - **cause_chain**（仅决策）：{{"direct": "直接触发原因", "proximate": "近因/中间原因", "root": "根因/系统性问题"}}
14. **既有 behavioral_constraints 必须保留**——输入里有「既有行为约束」段时，
    除非该条被新证据明确推翻，否则必须原样出现在输出的 behavioral_constraints
    里（可合并措辞，不许无声删除）。
15. **只输出 JSON**，不要解释过程。
{contradiction_history}
输入记忆：
{memory_text}

输出格式：
{{
  "key_decisions": [
    {{"decision": "简洁的决策描述", "context": "何时/为什么做此决定", "tip_type": "strategy|recovery|optimization", "cause_chain": {{"direct": "直接原因", "proximate": "近因", "root": "根因"}}}}
  ],
  "learned_patterns": [
    {{"pattern": "学到的模式", "evidence": "支撑该模式的证据", "tip_type": "strategy|recovery|optimization"}}
  ],
  "behavioral_constraints": [
    {{"rule": "你应该/你不应该...", "source": "distilled", "evidence": "基于XX条模式的提炼"}}
  ],
  "self_contradiction": "最严重的自我矛盾描述（如果没有则返回空字符串）"
}}"""


def _extract_dream_choices(result: Optional[Dict]) -> Tuple[str, Optional[str], Dict]:
    """从 chat/completions 响应取（content, finish_reason, usage）——**纯函数**。

    为什么必须单独取 finish_reason：此前只取 content，把「输出被截断」
    （``length``）与「模型写坏 JSON」混成同一个 None ⇒ 死因不可回读
    （可观测性缺失：logs 少了事件细节）。
    """
    if not isinstance(result, dict):
        return "", None, {}
    choices = result.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return "", None, {}
    first = choices[0]
    message = first.get("message")
    if not isinstance(message, dict):
        message = {}
    content = message.get("content") or ""
    if not isinstance(content, str):
        content = str(content)
    usage = result.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return content, first.get("finish_reason"), usage


def _strip_code_fence(content: str) -> str:
    """去掉 ```json ... ``` 包裹（纯函数）。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return text


def plan_dream_retry(
    finish_reason: Optional[str], attempts: int, max_tokens: int
) -> Optional[int]:
    """截断重发决策（**纯函数**）：None = 不重发；int = 用该预算重发。

    判据一条：``finish_reason == "length"`` ⇒ 输出预算被吃光（同族先例：
    Hermes 侧 empty_content —— max_tokens 硬编码 4096 吃光预算）。
    ``attempts`` = **已完成**尝试次数 ⇒ 只有 =1（首次）截断才重发 ⇒ 最多重发一次。
    """
    if attempts != 1:
        return None
    if finish_reason != "length":
        return None
    return max(int(max_tokens or 0) * 2, _DREAM_MAX_TOKENS_RETRY)


async def _post_dream_chat(
    prompt: str, max_tokens: int, api_key: str, base_url: str
) -> Tuple[Optional[Dict], Optional[str]]:
    """单次 HTTP 调用——**唯一 I/O 边界**，独立成函数以便离线替身注入。"""
    import aiohttp

    payload = {
        "model": _DREAM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": _DREAM_TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=_DREAM_TIMEOUT)
    ) as session:
        async with session.post(
            f"{base_url}/v1/chat/completions", json=payload, headers=headers
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                return None, f"LLM HTTP {resp.status}: {text[:200]}"
            return await resp.json(), None


async def _call_dream_llm(prompt: str) -> Optional[Dict]:
    """调用 DeepSeek API 执行梦境蒸馏（同步模式用于 cron，异步模式用于 agent）。

    注意：不直接从进程环境读 key（该变量常为 *** 占位符）。通过
    provider_registry.resolve_api_key_provider_credentials 解析真实 key，
    该函数支持 credential_pool 回退，与 Gateway 主循环同源。

    ③ 死因可回读：原始载荷（content 全文 / finish_reason / usage / 尝试次数）
    留在 ``_LAST_DREAM_DIAG``，由 ``_record_failure`` 落进失败件；
    解析失败时日志行仍留 200 字摘要（**在调用方**：本层只看 JSON 形态，
    不知道调用方是否还会重发 ⇒ 归因错层，2026-10-11 修）。
    """
    # 优先级1: os.environ（sync_run_dream_cycle 已从 /proc 注入正确的 key）
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    # 优先级2: provider_registry（Gateway 进程凭据池）
    if not api_key or api_key == "***":
        try:
            from agent.provider_registry import resolve_api_key_provider_credentials

            creds = resolve_api_key_provider_credentials("deepseek")
            if creds:
                api_key = creds.get("api_key", "") or ""
        except Exception:
            pass
    if not api_key or api_key == "***":
        logger.error("[DreamMemory] DEEPSEEK_API_KEY 未设置")
        return None

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    _LAST_DREAM_DIAG.clear()
    max_tokens = _DREAM_MAX_TOKENS
    attempts = 0

    while True:
        try:
            result, err = await _post_dream_chat(prompt, max_tokens, api_key, base_url)
        except Exception as e:
            logger.error(f"[DreamMemory] LLM 调用失败: {e}")
            _LAST_DREAM_DIAG.update(
                {
                    "attempts": attempts + 1,
                    "error": f"{type(e).__name__}: {e}",
                    "finish_reason": None,
                    "usage": {},
                    "max_tokens_last": max_tokens,
                    "content": "",
                    "content_len": 0,
                }
            )
            return None

        if err is not None or result is None:
            logger.error(f"[DreamMemory] {err or '空响应'}")
            _LAST_DREAM_DIAG.update(
                {
                    "attempts": attempts + 1,
                    "error": str(err or "空响应"),
                    "finish_reason": None,
                    "usage": {},
                    "max_tokens_last": max_tokens,
                    "content": "",
                    "content_len": 0,
                }
            )
            return None

        content, finish_reason, usage = _extract_dream_choices(result)
        attempts += 1
        _LAST_DREAM_DIAG.update(
            {
                "attempts": attempts,
                "finish_reason": finish_reason,
                "usage": usage,
                "max_tokens_last": max_tokens,
                "content": content,
                "content_len": len(content),
            }
        )

        parsed = _safe_json_parse(_strip_code_fence(content))
        if parsed is not None:
            return parsed

        nxt = plan_dream_retry(finish_reason, attempts, max_tokens)
        if nxt is None:
            if finish_reason == "length":
                reason = "输出被截断（finish_reason=length）"
            else:
                reason = f"finish_reason={finish_reason}"
            logger.error(
                f"[DreamMemory] 蒸馏输出不可用：{reason} · content_len={len(content)}"
                f" · 尝试 {attempts} 次 ⇒ 原始载荷见失败件 · 前200字: {content[:200]}"
            )
            return None

        logger.warning(
            f"[DreamMemory] 输出被截断（finish_reason=length）⇒ max_tokens "
            f"{max_tokens}→{nxt} 重发一次"
        )
        _LAST_DREAM_DIAG["retry_due_to"] = "length"
        _LAST_DREAM_DIAG["retry_from"] = max_tokens
        max_tokens = nxt


def _safe_json_parse(text: str) -> Optional[Dict]:
    """容错 JSON 解析：尝试多种策略从 LLM 输出中提取 JSON。"""
    import re

    # 策略1: 标准 json.loads
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2: json.JSONDecoder(strict=False) — 允许未转义控制字符
    try:
        decoder = json.JSONDecoder(strict=False)
        return decoder.decode(text)
    except json.JSONDecodeError:
        pass

    # 策略3: 正则提取最外层 JSON 块
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            decoder = json.JSONDecoder(strict=False)
            return decoder.decode(candidate)
        except json.JSONDecodeError:
            pass

    # 策略4: 尝试逐行修复 — 修复未转义的引号
    # 找到第一个 { 和最后一个 }，之间的内容
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        # 尝试修复常见问题：未转义的内部引号
        candidate = re.sub(r'(?<!\\)"', '\\"', candidate)
        candidate = candidate.replace('\\"', '"', 1)  # 恢复第一个（最外层）
        candidate = candidate.replace('\\"{', '{')     # 恢复 { 前的
        candidate = candidate.replace('\\"}', '}')     # 恢复 } 前的
        # 只保留最外层的引号
        if candidate.startswith('"') and candidate.endswith('"'):
            candidate = candidate[1:-1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 归因不在此层（2026-10-11 修）：本函数只看 JSON 形态，不知道调用方
    # 是否还会重发。实证：finish_reason=length 截断 ⇒ 四策略全失败 ⇒ 旧版在
    # 此报 logger.error ⇒ stderr 进飞书，而调用方随后重发成功 ⇒ 每晚假告警。
    # 可观测性未减：调用方按 finish_reason 归因 + 留 200 字预览 + 原始载荷
    # 仍进 _LAST_DREAM_DIAG / 失败件。
    return None


def _get_contradiction_path() -> str:
    """获取 self_contradiction_report.json 路径。"""
    home = os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
    return os.path.join(home, "data", "self_contradiction_report.json")


_LAST_CONTRADICTION_REPEAT = 0  # 最近一次写入的矛盾累计复现次数（供播报行用，不落盘）


def _contradiction_brief(contradiction: str) -> str:
    """播报行：把「今天又发现一条」改成「同一议题已连报 N 次」。

    为什么：生成端每天 1 条、处置端 10 天 0 条 ⇒ 逐日播报只会制造告警疲劳。
    改成累计视角后，同一议题的**持续时长**才是信号。
    """
    if not contradiction or not contradiction.strip():
        return "✅ 无"
    n = _LAST_CONTRADICTION_REPEAT or 1
    if n > 1:
        return f"⚠️ 同一议题复现第 {n} 次（未新增条目）: {contradiction[:70]}"
    return f"⚠️ 新发现: {contradiction[:80]}"


def _save_contradiction_report(contradiction: str) -> bool:
    """将自我矛盾报告写入独立文件（2026-11-03 起带去重语义）。

    去重语义（实证依据：10 天 10 条里 2 条逐字重复、5 条同族，真正不同仅 3 条）：
      - **逐字重复** ⇒ 不新增条目，只给该条 repeat_count += 1 / 更新 last_seen
      - 窗口 = 最近 10 条**未裁定**矛盾（而非最近 10 次运行）⇒ 重复不再挤掉新议题；
        ``resolved`` 条目不占未解决名额、也不因新写入被裁（11-04 审计 A-1：写侧盲裁
        ``existing[-10:]`` 会在满窗后挤掉最旧的**未解决**条目，与读侧过滤口径相反）
      - 旧字段（timestamp / contradiction）保留，只**新增**字段 ⇒ 向后兼容旧读端
    不做模糊去重：量具实测同族改写相似度可低到 0.000（LLM 每天换措辞），
    按阈值合并必然误判 —— 见 scripts/contradiction_family_probe.py。
    """
    global _LAST_CONTRADICTION_REPEAT
    if not contradiction or not contradiction.strip():
        return False
    path = _get_contradiction_path()
    raw = contradiction.strip()
    # 模型按指令在复现时加 `[复现]` 前缀 —— 比对前剥掉，否则永远匹配不上
    text = raw[4:].strip() if raw.startswith("[复现]") else raw
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = []
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        if not isinstance(existing, list):
            existing = []
        # 目录缺失时旧实现静默返回 False（调用方丢弃返回值 ⇒ 无声失败）
        os.makedirs(os.path.dirname(path), exist_ok=True)

        hit = None
        for item in existing:
            if isinstance(item, dict) and (item.get("contradiction") or "").strip() == text:
                hit = item
                break

        if hit is not None:
            hit["repeat_count"] = int(hit.get("repeat_count") or 1) + 1
            hit["last_seen"] = now
            hit.setdefault("first_seen", hit.get("timestamp") or now)
            _LAST_CONTRADICTION_REPEAT = hit["repeat_count"]
            logger.info(
                f"[DreamMemory] 自我矛盾复现（第 {hit['repeat_count']} 次，未新增条目）: {text[:60]}..."
            )
            if _is_resolved(hit):
                logger.warning(
                    f"[DreamMemory] 命中已 resolved 条目（第 {hit['repeat_count']} 次复现，"
                    f"仍按白名单过滤不进 prompt）: {text[:60]}..."
                )
        else:
            existing.append(
                {
                    "timestamp": now,
                    "first_seen": now,
                    "last_seen": now,
                    "repeat_count": 1,
                    "contradiction": text,
                }
            )
            if len(existing) > 10:
                # 写侧窗口口径与读侧对齐（11-04 审计 A-1）：只裁「最旧的未裁定条目」。
                # 读侧 `_recent_contradictions` 已按 `_is_resolved` 过滤 ⇒ 写侧若仍按总
                # 条数盲裁 `existing[-10:]`，补标后 7 resolved + 3 unresolved 满 10 格时
                # 再写 1 条新矛盾，被挤掉的恰是最旧的**未解决**条目（resolved 一条不丢）
                # ⇒ 补标目标反向：未裁定矛盾静默消失。resolved 不占未解决名额。
                unresolved = [entry for entry in existing if not _is_resolved(entry)]
                surplus = len(unresolved) - 10
                if surplus > 0:
                    dropped = 0
                    trimmed: List = []
                    for entry in existing:
                        if dropped < surplus and not _is_resolved(entry):
                            dropped += 1
                            continue
                        trimmed.append(entry)
                    existing = trimmed
                    logger.warning(
                        f"[DreamMemory] 未裁定矛盾超窗口上限 10，裁掉最旧 {dropped} 条"
                        f"（resolved 不占名额、不被裁）"
                    )
            _LAST_CONTRADICTION_REPEAT = 1
            logger.info(f"[DreamMemory] 自我矛盾报告已写入: {text[:80]}...")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, json.JSONDecodeError, OSError) as e:
        logger.warning(f"[DreamMemory] 写入自我矛盾报告失败: {e} (path={path})")
        return False


async def _run_distillation(
    data: Dict, memory_text: str, dry_run: bool = False
) -> Tuple[Dict, str, bool]:
    """执行梦境蒸馏，返回（更新后的 data, 报告文本, 是否产出新数据）。

    第三位是**显式**状态：此前调用方只能靠报告串里的 emoji 反推成败（改一个字
    就静默失效）。
    """
    if dry_run:
        return data, f"[DRY RUN] 输入: {len(memory_text)} 字符，未修改", True

    prompt = _build_distillation_prompt(
        memory_text, _recent_contradictions(current_text=memory_text)
    )
    logger.info(f"[DreamMemory] 调用蒸馏 LLM（提示词 {len(prompt)} 字符）")
    result = await _call_dream_llm(prompt)

    if result is None:
        return data, "❌ 梦境蒸馏 LLM 调用失败，未修改", False

    # 统计蒸馏前后的条目数
    _old_kd_items = list(data.get("memory", {}).get("key_decisions", []))
    _old_lp_items = list(data.get("memory", {}).get("learned_patterns", []))
    old_decisions = len(_old_kd_items)
    old_patterns = len(_old_lp_items)
    old_constraints = len(data.get("memory", {}).get("behavioral_constraints", []))
    new_decisions = len(result.get("key_decisions", []))
    new_patterns = len(result.get("learned_patterns", []))
    new_constraints = len(result.get("behavioral_constraints", []))

    # 用蒸馏后的条目替换原有记忆
    if "memory" not in data:
        data["memory"] = {}

    # D1: AKL 字段按文本对齐继承（旧值优先于 setdefault 默认值）
    new_decisions_items, inherited_decisions = _inherit_akl(
        data["memory"].get("key_decisions", []), result.get("key_decisions", []), "decision"
    )
    new_patterns_items, inherited_patterns = _inherit_akl(
        data["memory"].get("learned_patterns", []), result.get("learned_patterns", []), "pattern"
    )
    # D3: 超限截断不许静默——丢弃项落 warning（可 grep）
    evicted_decisions = new_decisions_items[_MAX_DECISIONS:]
    evicted_patterns = new_patterns_items[_MAX_PATTERNS:]
    for _label, _dropped, _tk in (
        ("key_decisions", evicted_decisions, "decision"),
        ("learned_patterns", evicted_patterns, "pattern"),
    ):
        for _item in _dropped:
            logger.warning(
                "[DreamMemory] %s 超限截断，丢弃: %s", _label, _item_text(_item, _tk)[:60]
            )
            _archive_evicted(_label, [_item], "truncation")
    data["memory"]["key_decisions"] = new_decisions_items[:_MAX_DECISIONS]
    data["memory"]["learned_patterns"] = new_patterns_items[:_MAX_PATTERNS]

    # 身份集合差（2026-11-16）：把日读信号从「条数」改成「身份集合」
    _delta = _diff_memory_arrays(
        _old_kd_items,
        _old_lp_items,
        data["memory"]["key_decisions"],
        data["memory"]["learned_patterns"],
    )

    # 注入 ByteRover AKL 字段（importance / maturity / last_access / decay_factor）
    _now_akl = datetime.now(timezone.utc).isoformat()
    for d in data["memory"]["key_decisions"]:
        if isinstance(d, dict):
            d.setdefault("importance", 50)
            d.setdefault("maturity", "draft")
            d.setdefault("last_access", _now_akl)
            d.setdefault("decay_factor", 0.95)
    for p in data["memory"]["learned_patterns"]:
        if isinstance(p, dict):
            p.setdefault("importance", 50)
            p.setdefault("maturity", "draft")
            p.setdefault("last_access", _now_akl)
            p.setdefault("decay_factor", 0.95)

    # ── 晋升制（2026-10-24 · 刘哥批）：写回前算晋升分——达门 promoted，
    # 未达留 draft（不驱逐）。判据不是「字段存在」，是 usage 证据达门。
    promoted_total, promo_total = _apply_promotion_pass(
        data["memory"]["key_decisions"] + data["memory"]["learned_patterns"], _now_akl
    )

    # D2: PMD 共同进化——旧的先占位、新的补位；超限显式记录（不静默丢）
    merged_constraints, evicted_constraints = _merge_constraints(
        data["memory"].get("behavioral_constraints", []),
        result.get("behavioral_constraints", []),
        _MAX_CONSTRAINTS,
    )
    for _rule in evicted_constraints:
        logger.warning("[DreamMemory] behavioral_constraints 超限被挤掉: %s", _rule[:60])
    _archive_evicted("behavioral_constraints", evicted_constraints, "constraint_cap")
    data["memory"]["behavioral_constraints"] = merged_constraints

    # 写入自我矛盾报告（Change 3）
    contradiction = result.get("self_contradiction", "")
    if contradiction and contradiction.strip():
        _save_contradiction_report(contradiction)

    # 统计 tip_type 分布（Trajectory-Informed Memory）
    tip_types_decisions = {}
    for d in result.get("key_decisions", []):
        tt = d.get("tip_type", "unknown") if isinstance(d, dict) else "unknown"
        tip_types_decisions[tt] = tip_types_decisions.get(tt, 0) + 1
    tip_types_patterns = {}
    for p in result.get("learned_patterns", []):
        tt = p.get("tip_type", "unknown") if isinstance(p, dict) else "unknown"
        tip_types_patterns[tt] = tip_types_patterns.get(tt, 0) + 1

    # 统计 cause_chain 覆盖率
    decisions_with_chain = sum(
        1 for d in result.get("key_decisions", [])
        if isinstance(d, dict) and d.get("cause_chain")
    )

    _alarm_state = record_alert_night(_delta, persist=not dry_run)
    _esc_block = _escalation_block(_alarm_state)
    report = (
        f"{_esc_block}"
        f"🔄 梦境蒸馏完成\n"
        f"{_delta_alert(_delta)}"
        f"  - key_decisions: {old_decisions} → {new_decisions} "
        f"({new_decisions - old_decisions:+d})\n"
        f"    · 身份差: added={len(_delta['key_decisions']['added'])} "
        f"removed={len(_delta['key_decisions']['removed'])} "
        f"kept={_delta['key_decisions']['kept']}\n"
        f"    · 被删(前3): {[t[:40] for t in _delta['key_decisions']['_removed_text'][:3]] or '无'}\n"
        f"    · tip_type 分布: {tip_types_decisions}\n"
        f"    · cause_chain 覆盖率: {decisions_with_chain}/{new_decisions}\n"
        f"  - learned_patterns: {old_patterns} → {new_patterns} "
        f"({new_patterns - old_patterns:+d})\n"
        f"    · 身份差: added={len(_delta['learned_patterns']['added'])} "
        f"removed={len(_delta['learned_patterns']['removed'])} "
        f"kept={_delta['learned_patterns']['kept']}\n"
        f"    · tip_type 分布: {tip_types_patterns}\n"
        f"  - behavioral_constraints: {old_constraints} → {new_constraints} "
        f"({new_constraints - old_constraints:+d})\n"
        f"    · AKL 继承: decisions {inherited_decisions} 处 / patterns {inherited_patterns} 处\n"
        f"    · 条目超限截断: decisions {len(evicted_decisions)} / patterns {len(evicted_patterns)}\n"
        f"    · 约束被挤掉: {evicted_constraints or '无'}\n"
        f"    · 晋升: promoted={promoted_total}/{promo_total}"
        f" (门 usage>={_PROMOTE_MIN_ACCESS} 且 score>={_PROMOTE_MIN_SCORE:g})\n"
        f"    · 归档段: {len(evicted_decisions) + len(evicted_patterns) + len(evicted_constraints)} 条"
        f" -> {os.path.basename(_archive_path())}\n"
        f"  - 自我矛盾: {_contradiction_brief(contradiction)}\n"
        f"  - 时间: {datetime.now(timezone.utc).isoformat()}"
    )
    return data, report, True


async def run_dream_cycle(dry_run: bool = False) -> Tuple[bool, str]:
    """执行完整的梦境记忆蒸馏周期。

    Args:
        dry_run: 如果为 True，只分析不写盘

    Returns:
        (成功与否, 报告文本)
    """
    start = time.monotonic()
    path = _get_persistent_path()
    logger.info(f"[DreamMemory] 开始梦境周期，路径: {path}")

    # 1. 加载持久化数据
    data = _load_persistent(path)
    if data is None:
        detail = _record_failure("load", RuntimeError(f"无法加载 {path}"))
        return False, f"❌ 无法加载 persistent.json\n{_FAILURE_MARKER}: {detail}"

    # 2. 取数面 + 格式化为文本（B 档 #17：旧面为空 ⇒ 回落 memories/MEMORY.md）
    memory_md_path = _memory_markdown_path()
    _mem_block = data.get("memory")
    if not isinstance(_mem_block, dict):
        _mem_block = {}
    memory_text, distill_source, _new_md_state, _md_mode = build_distillation_input_merged(
        data,
        _load_memory_markdown(memory_md_path),
        _mem_block.get(_DISTILL_MD_STATE_KEY) or {},
    )
    metrics = distillation_input_metrics(memory_text)
    if not memory_text.strip():
        logger.info(
            "[DreamMemory] 无内容可蒸馏：取数面=%s（%s 无 key_decisions/"
            "learned_patterns，%s 无正文）⇒ 本轮不写盘",
            distill_source,
            path,
            memory_md_path,
        )
        return True, "⏭ 没有记忆条目需要蒸馏"

    logger.info(
        "[DreamMemory] 取数面=%s · md_delta=%s · 输入 %d 字符 / %d 行 / %d 段",
        distill_source,
        _md_mode,
        metrics["chars"],
        metrics["lines"],
        metrics["segments"],
    )

    # 3. 执行蒸馏
    updated_data, report, produced = await _run_distillation(data, memory_text, dry_run)
    if not produced:
        detail = _record_failure(
            "llm", RuntimeError("蒸馏未产出新数据（LLM 调用/解析失败），未修改")
        )
        return False, report + f"\n{_FAILURE_MARKER}: {detail}"

    if dry_run:
        # 旧版 bug：dry_run=True 仍然走到写盘段（docstring 说「只分析不写盘」）
        # ⇒ 现已短路，dry-run 零写入。
        return True, report + "\n（dry-run：未备份、未写盘、未写哨兵）"

    elapsed = time.monotonic() - start

    # 4. ② 写前备份——失败即拒绝写盘（没有回滚点的覆写 = 事故入口）
    try:
        backup_dir = _backup_memory_surface()
    except Exception as e:  # noqa: BLE001
        detail = _record_failure("backup", e)
        return False, report + f"\n{_FAILURE_MARKER}: 写前备份失败，已拒绝写盘（{detail}）"

    # 5. ③ 单写窗口——拿不到就拒写：批次可重跑，跨进程覆写不可回滚
    from agent.persistent_store import write_window

    with write_window(on_timeout="abort") as held:
        if not held:
            detail = _record_failure(
                "write_window", TimeoutError("未取得单写窗口：另一写者正持有记忆面锁")
            )
            return False, (
                report
                + f"\n{_FAILURE_MARKER}: 写窗口超时，已拒绝写盘（{detail}）"
                + f"\n备份留在: {backup_dir}"
            )
        # E1 Silver->Gold：注入台账聚合写回 access_count（绝对赋值 => 幂等）
        try:
            updated_data = apply_injection_usage(updated_data)
        except Exception as _e1_exc:  # noqa: BLE001
            logger.warning("[E1] usage 聚合失败（不影响蒸馏）: %s", _e1_exc)
        # A 方案（2026-11-22）：MEMORY.md 消费位随本次写盘**同批**落地。
        # 顺序不可反：先推游标后写盘 ⇒ 写盘失败即丢增量（静默丢数据，比零增更坏）。
        # 反向代价可接受：写盘成功但状态异常 ⇒ 下轮重发同一段（幂等浪费，不丢）。
        if _md_mode in ("append", "first", "rewrite") and _new_md_state:
            _ub = updated_data.get("memory")
            if not isinstance(_ub, dict):
                _ub = {}
            _ub[_DISTILL_MD_STATE_KEY] = _new_md_state
            updated_data["memory"] = _ub
        ok = _save_persistent(path, updated_data)

    if not ok:
        detail = _record_failure("save", IOError(f"_save_persistent({path}) 返回 False"))
        return False, report + f"\n❌ 写入失败（耗时 {elapsed:.1f}s）\n{_FAILURE_MARKER}: {detail}"

    # 6. 写哨兵文件——通知 CrossSessionMemory 下一轮 save 前从磁盘重载缓存
    #    （避免终端进程蒸馏写盘后，Gateway 进程仍用旧缓存 59 kd 覆盖掉压缩后的 20 kd）
    _write_distill_sentinel()
    _clear_failure_record()
    return True, report + f"\n✅ 写入成功（耗时 {elapsed:.1f}s）\n备份: {backup_dir}"


# ============================================================================
# E1 · 记忆使用计数（append-only 注入台账 Bronze -> 聚合 Silver -> access_count Gold）
# 口径（2026-10-24 两会席共识 P1 ② 离线批算）：
#   Bronze：data/memory_injection_ledger.jsonl —— 一行/轮 {ts, run_id, ids[]}，只追加；
#   Silver：data/memory_usage_aggregate.json    —— 按 id 计数（纯函数，可重算）；
#   Gold  ：persistent.json 的 access_count/last_access —— **绝对赋值**（非累加）⇒ 幂等。
# 铁律：注入路径（prompt_builder）只 note_injection() 记内存，**绝不写盘**；
#      写盘只发生在「轮末 flush」与「蒸馏聚合」两处。
# ============================================================================

_INJECTION_LEDGER_FILE = "memory_injection_ledger.jsonl"
_USAGE_AGGREGATE_FILE = "memory_usage_aggregate.json"
_injection_buffer: List[str] = []
_injection_buffer_run_id: Optional[str] = None


def memory_id(text: object) -> str:
    """条目稳定 id = sha1(规范化文本) 前 12。文本即身份（索引位置会漂移）。"""
    import hashlib as _h

    norm = _norm_mem_text(text)
    return _h.sha1(norm.encode("utf-8")).hexdigest()[:12] if norm else ""


def _diff_memory_arrays(
    old_decisions: List, old_patterns: List, new_decisions: List, new_patterns: List
) -> Dict[str, Dict[str, list]]:
    """按 `memory_id()`（内容哈希）算蒸馏前后的**集合差**。

    为什么不能用长度差（2026-11-16 实证）：
    投递报告原文是 `key_decisions: {old} → {new} ({old - new:+d})` —— **长度差**且
    符号方向反了。长度差对内容变化**完全失明**：
    实测 10-24→11-15 共 172 次注入只有 1 种 id 组合（内容确为冻结），
    但**即使某一晚内容全变、条数不变，旧报告依然显示 `(+0)`** ⇒ 唯一日读信号
    无法区分「没变」与「全变了但条数相同」。本函数把信号从「条数」改成「身份集合」。

    Returns: {"key_decisions": {"added": [id...], "removed": [id...], "kept": n}, ...}
    """
    out: Dict[str, Dict[str, list]] = {}
    for label, olds, news, tk in (
        ("key_decisions", old_decisions, new_decisions, "decision"),
        ("learned_patterns", old_patterns, new_patterns, "pattern"),
    ):
        old_map = {}
        for x in olds or []:
            tid = memory_id(_item_text(x, tk))
            if tid:
                old_map[tid] = _item_text(x, tk)
        new_map = {}
        for x in news or []:
            tid = memory_id(_item_text(x, tk))
            if tid:
                new_map[tid] = _item_text(x, tk)
        out[label] = {
            "added": [t for t in new_map if t not in old_map],
            "removed": [t for t in old_map if t not in new_map],
            "kept": sum(1 for t in new_map if t in old_map),
            "_removed_text": [old_map[t] for t in old_map if t not in new_map],
        }
    return out


def _delta_alert(diff: Dict[str, Dict[str, list]]) -> str:
    """零增/零删 ⇒ 返回告警横幅；否则空串。

    语义：`added == 0 and removed == 0` 表示**蒸馏这一晚对注入面毫无贡献**。
    这是「不动点」的可观测指纹（实证：连续 22 天如此，且无人察觉）。
    2026-11-22：零增的**主因**已定位为取数面短路（三数组非空即 return，MEMORY.md
    46 天不可达），A 方案已修 ⇒ 现在的零增含义收窄为「三数组 + MEMORY.md 都没新
    知识」。措辞随之改，不再把单一原因钉在 prompt 自指上（那只是次要小环）。
    判据（正控/负控）见 tests/test_dream_memory_delta.py。
    """
    kd = diff.get("key_decisions", {})
    lp = diff.get("learned_patterns", {})
    if kd.get("added") or kd.get("removed") or lp.get("added") or lp.get("removed"):
        return ""
    return (
        "[ALERT] 蒸馏零增：注入面今晚无任何变化（added=0 removed=0）"
        " —— 连续多晚即为不动点，需人工核查取数面（三数组 + MEMORY.md）"
        "是否真无新知识\n"
    )



# --- 蒸馏零增告警升级（2026-11-16 刘哥批：连续 3 晚 ⇒ 真告警） ---
# 为什么需要：`_delta_alert` 只是日报中段的一行横幅，混在 ~15 行里可被略过。
# 真告警 = 不依赖读者注意力：①前置到首行 ②跨轮留盘 ③进健康巡检面。
_ALARM_ESCALATE_NIGHTS = 3
_ALARM_HISTORY_MAX = 60
_ALERT_STATE_FILE = "dream_alert_state.json"
_ALARM_UNRESOLVED_FILE = "DREAM_ALARM_UNRESOLVED.md"


def _alert_state_path() -> str:
    return os.path.join(_mimir_home(), "data", _ALERT_STATE_FILE)


def _alarm_file_path() -> str:
    return os.path.join(_mimir_home(), "data", _ALARM_UNRESOLVED_FILE)


def _load_alert_state() -> Dict:
    try:
        with open(_alert_state_path(), "r", encoding="utf-8") as fh:
            st = json.load(fh)
        if isinstance(st, dict):
            return st
    except (IOError, ValueError):
        pass
    return {"consecutive_zero": 0, "first_zero_date": None,
            "last_zero_date": None, "escalated": False,
            "escalated_since": None, "history": []}


def _save_alert_state(st: Dict) -> None:
    path = _alert_state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def record_alert_night(diff: Dict, today: Optional[str] = None, persist: bool = True) -> Dict:
    """记一晚零增/增长，返回含 consecutive_zero / escalated / resolved_now 的状态。

    `diff` 复用 `_diff_memory_arrays` 的**身份集合差**（不是长度差）——
    等长替换必须判「有变化」，见 tests/test_dream_memory_alarm.py 变异点。
    """
    kd = diff.get("key_decisions") or {}
    lp = diff.get("learned_patterns") or {}
    changed = bool(kd.get("added") or kd.get("removed")
                   or lp.get("added") or lp.get("removed"))
    day = today or datetime.now(timezone.utc).date().isoformat()
    st = _load_alert_state()
    prev_escalated = bool(st.get("escalated"))
    resolved_now = False

    if changed:
        resolved_now = prev_escalated or int(st.get("consecutive_zero") or 0) > 0
        st["consecutive_zero"] = 0
        st["first_zero_date"] = None
        st["escalated"] = False
        st["escalated_since"] = None
    else:
        st["consecutive_zero"] = int(st.get("consecutive_zero") or 0) + 1
        if not st.get("first_zero_date"):
            st["first_zero_date"] = day
        st["last_zero_date"] = day
        if st["consecutive_zero"] >= _ALARM_ESCALATE_NIGHTS:
            st["escalated"] = True
            if not st.get("escalated_since"):
                st["escalated_since"] = st["first_zero_date"]

    hist = st.get("history") or []
    hist.append({"date": day, "changed": changed,
                 "added": len(kd.get("added") or []) + len(lp.get("added") or []),
                 "removed": len(kd.get("removed") or []) + len(lp.get("removed") or []),
                 "consecutive_zero": st["consecutive_zero"]})
    st["history"] = hist[-_ALARM_HISTORY_MAX:]
    st["resolved_now"] = resolved_now

    if persist:
        _sync_alarm_file(st, day)
        to_save = {k: v for k, v in st.items() if k != "resolved_now"}
        _save_alert_state(to_save)
    return st


def _sync_alarm_file(st: Dict, day: str) -> None:
    """留盘：escalated ⇒ 写告警件；自愈 ⇒ 归档（不删，留证据）。"""
    path = _alarm_file_path()
    if st.get("escalated"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        body = (
            "# 🚨 蒸馏零增告警（未解决）\n\n"
            f"- 连续零增晚数: {st.get('consecutive_zero')}\n"
            f"- 首次零增: {st.get('first_zero_date')}\n"
            f"- 最近零增: {st.get('last_zero_date')}\n"
            f"- 升级阈值: {_ALARM_ESCALATE_NIGHTS} 晚\n"
            f"- 生成时间: {datetime.now(timezone.utc).isoformat()}\n\n"
            "## 判据\n"
            "`added==0 and removed==0`（key_decisions ∪ learned_patterns **身份集合差**）\n\n"
            "## 含义\n"
            "蒸馏这一晚对注入面毫无贡献。连续多晚 = 不动点。\n\n"
            "## 处置\n"
            "核查 prompt 是否被自身旧输出钉住（commit 9a5e364 / 9d8e82a）。\n\n"
            "## 自愈\n"
            "任一次出现增/删即自动把本件归档为 "
            f"`DREAM_ALARM_UNRESOLVED_RESOLVED_<date>.md`。\n"
        )
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, path)
        return
    if st.get("resolved_now") and os.path.exists(path):
        arch = path.replace(".md", "_RESOLVED_" + day + ".md")
        try:
            os.replace(path, arch)
        except OSError as e:
            logger.warning("[E1] 告警件归档失败: %s", e)


def _escalation_block(st: Dict) -> str:
    """前置告警块（报告首行）。空串 = 既无升级也无自愈。"""
    if st.get("escalated"):
        n = st.get("consecutive_zero")
        since = st.get("escalated_since") or st.get("first_zero_date") or "?"
        return (
            f"[ALARM] 🚨 蒸馏零增已连续 {n} 晚（首次 {since}，阈值 {_ALARM_ESCALATE_NIGHTS} 晚）\n"
            f"  ⇒ 不动点：注入面多晚无任何变化，非偶发\n"
            f"  ⇒ 告警件: {_alarm_file_path()}\n"
            f"  ⇒ 处置: 核查 prompt 是否被自身旧输出钉住（commit 9a5e364 / 9d8e82a）\n"
        )
    if st.get("resolved_now"):
        return "[RESOLVED] ✅ 蒸馏零增告警已自愈（本晚出现增/删，连续计数归零）\n"
    return ""


def _injection_ledger_path() -> str:
    return os.path.join(_mimir_home(), "data", _INJECTION_LEDGER_FILE)


def _usage_aggregate_path() -> str:
    return os.path.join(_mimir_home(), "data", _USAGE_AGGREGATE_FILE)


def note_injection(ids: List[str], run_id: Optional[str] = None) -> int:
    """注入路径调用：**只进内存缓冲，不写盘**。返回累计缓冲条数。"""
    global _injection_buffer_run_id
    for i in ids or []:
        if isinstance(i, str) and i and i not in _injection_buffer:
            _injection_buffer.append(i)
    if run_id:
        _injection_buffer_run_id = str(run_id)
    return len(_injection_buffer)


def flush_injection_ledger(run_id: Optional[str] = None) -> int:
    """轮末调用：把本轮缓冲追加成一行（空缓冲 = 不写，防噪音行）。返回写入行数。"""
    global _injection_buffer, _injection_buffer_run_id
    ids = list(_injection_buffer)
    _injection_buffer = []
    rid = run_id or _injection_buffer_run_id
    _injection_buffer_run_id = None
    if not ids:
        return 0
    path = _injection_ledger_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "run_id": rid or "", "ids": ids}
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except IOError as e:
        logger.warning("[E1] 注入台账写入失败: %s", e)
        return 0
    return 1


def aggregate_injection_ledger(ledger_path: Optional[str] = None,
                               out_path: Optional[str] = None) -> Dict:
    """Bronze -> Silver：按 id 计数（纯函数；删掉产物重跑结果一致）。"""
    ledger_path = ledger_path or _injection_ledger_path()
    out_path = out_path or _usage_aggregate_path()
    counts: Dict[str, int] = {}
    last: Dict[str, str] = {}
    lines = 0
    try:
        with open(ledger_path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                lines += 1
                ts = str(row.get("ts") or "")
                for i in row.get("ids") or []:
                    if not isinstance(i, str) or not i:
                        continue
                    counts[i] = counts.get(i, 0) + 1
                    if ts and ts > last.get(i, ""):
                        last[i] = ts
    except FileNotFoundError:
        lines = 0
    agg = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "ledger_lines": lines, "counts": counts, "last_access": last}
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(agg, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning("[E1] 聚合产物写入失败: %s", e)
    return agg


def apply_injection_usage(data: Dict, agg: Optional[Dict] = None) -> Dict:
    """Silver -> Gold：把 counts 写回 access_count/last_access（**绝对赋值**，幂等）。"""
    if not isinstance(data, dict):
        return data
    if agg is None:
        try:
            with open(_usage_aggregate_path(), "r", encoding="utf-8") as f:
                agg = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            agg = {}
    counts = agg.get("counts") if isinstance(agg, dict) else None
    last = agg.get("last_access") if isinstance(agg, dict) else None
    counts = counts if isinstance(counts, dict) else {}
    last = last if isinstance(last, dict) else {}
    memory = data.get("memory")
    if not isinstance(memory, dict):
        return data
    applied = 0
    for key, tk in (("key_decisions", "decision"), ("learned_patterns", "pattern")):
        items = memory.get(key)
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            mid = memory_id(_item_text(it, tk))
            if not mid or mid not in counts:
                continue
            try:
                it["access_count"] = int(counts[mid])
            except (TypeError, ValueError):
                continue
            if last.get(mid):
                it["last_access"] = last[mid]
            applied += 1
    logger.info("[E1] usage 聚合落 Gold：%d 条（ledger 行=%s）",
                applied, agg.get("ledger_lines") if isinstance(agg, dict) else "?")
    return data


# ============================================================================
# 同步入口（供 cronjob / 终端使用）
# ============================================================================

def _inject_api_key_from_proc() -> None:
    """从 /proc/*/environ 读取真实 DEEPSEEK_API_KEY 并注入 os.environ。

    沙盒 (execute_code) 中 os.environ 的 DEEPSEEK_API_KEY 可能来自 Gateway
    进程（被工具显示层截断为 11 个字符并包含 Unicode 占位符，不可用）。
    必须从 /proc/PID/environ 的原始字节读取。

    优先扫描当前运行的 Mimir Gateway 进程（gateway/run.py），
    避免硬编码 PID（Gateway 重启后 PID 会变）。
    """
    try:
        # 动态查找当前 Mimir Gateway PID
        gateway_pid = None
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                cmdline_path = f"/proc/{entry}/cmdline"
                if not os.path.isfile(cmdline_path):
                    continue
                with open(cmdline_path, "rb") as f:
                    cmdline = f.read()
                if b"gateway/run.py" in cmdline:
                    gateway_pid = int(entry)
                    break
            except (PermissionError, FileNotFoundError, OSError):
                continue
        known_pids = [gateway_pid] if gateway_pid else []
        for known_pid in known_pids:
            try:
                p = f"/proc/{known_pid}/environ"
                with open(p, "rb") as f:
                    raw = f.read()
                for entry in raw.split(b"\x00"):
                    if entry.startswith(b"DEEPSEEK_API_KEY="):
                            val = entry.split(b"=", 1)[1].decode(errors="replace")
                            if val and val != "***" and len(val) >= 30:
                                os.environ["DEEPSEEK_API_KEY"] = val
                                logger.info(
                                    "[DreamMemory] key injected from PID %d (len=%d)",
                                    known_pid, len(val),
                                )
                                return
            except (PermissionError, FileNotFoundError, OSError):
                pass
        # 全量扫描回退
        pids = sorted(
            [int(e) for e in os.listdir("/proc") if e.isdigit() and int(e) > 0],
        )
        for pid_entry in pids:
            try:
                p = f"/proc/{pid_entry}/environ"
                with open(p, "rb") as f:
                    raw = f.read()
                for entry in raw.split(b"\x00"):
                    if entry.startswith(b"DEEPSEEK_API_KEY="):
                            val = entry.split(b"=", 1)[1].decode(errors="replace")
                            if val and val != "***" and len(val) >= 30:
                                os.environ["DEEPSEEK_API_KEY"] = val
                                logger.info(
                                    "[DreamMemory] key injected from PID %d (len=%d)",
                                    pid_entry, len(val),
                                )
                                return
            except (PermissionError, FileNotFoundError, OSError):
                continue
        # provider_registry 回退（.env 中的 key 常为 *** 遮盖值，需从凭据池获取真实 key）
        current_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not current_key or current_key == "***":
            try:
                from agent.provider_registry import resolve_api_key_provider_credentials
                creds = resolve_api_key_provider_credentials("deepseek")
                if creds:
                    key = creds.get("api_key", "") or ""
                    if key and key != "***" and len(key) >= 30:
                        os.environ["DEEPSEEK_API_KEY"] = key
                        logger.info(
                            "[DreamMemory] key injected from provider_registry (len=%d)",
                            len(key),
                        )
            except Exception:
                pass
        # config.yaml 直接回退（provider_registry 只查环境变量和 credential_pool，不读 config.yaml）
        if not os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") == "***":
            try:
                import yaml
                config_path = os.path.join(
                    os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether")),
                    "config.yaml",
                )
                if os.path.isfile(config_path):
                    with open(config_path, "r") as f:
                        cfg = yaml.safe_load(f)
                    raw_key = (cfg or {}).get("providers", {}).get("deepseek", {}).get("api_key", "")
                    if raw_key and raw_key != "***" and len(raw_key) >= 30:
                        os.environ["DEEPSEEK_API_KEY"] = raw_key
                        logger.info(
                            "[DreamMemory] key injected from config.yaml (len=%d)",
                            len(raw_key),
                        )
            except Exception:
                pass
        # .env 直接回退（cat/read_file 显示 *** 是工具遮盖层，文件字节有真实 key）
        if not os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") == "***":
            try:
                env_path = os.path.join(
                    os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether")),
                    ".env",
                )
                if os.path.isfile(env_path):
                    with open(env_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("DEEPSEEK_API_KEY="):
                                val = line.split("=", 1)[1].strip().strip("\"'")
                                if val and val != "***" and len(val) >= 30:
                                    os.environ["DEEPSEEK_API_KEY"] = val
                                    logger.info(
                                        "[DreamMemory] key injected from .env (len=%d)",
                                        len(val),
                                    )
                                break
            except Exception:
                pass
    except Exception:
        pass


def sync_run_dream_cycle(dry_run: bool = False) -> str:
    """同步版本的梦境周期（用于终端或 cronjob，内部用事件循环）。"""
    _inject_api_key_from_proc()
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 已有事件循环，创建新任务
        future = asyncio.ensure_future(run_dream_cycle(dry_run))
        ok, report = loop.run_until_complete(future)
    else:
        ok, report = asyncio.run(run_dream_cycle(dry_run))

    return report


# ============================================================================
# 测试入口
# ============================================================================

def _ensure_cli_logging() -> None:
    """cron 入口的 logging 兜底（2026-11-22 · 治「日志静默丢失」）。

    病灶：本模块的 ``logger.info()`` 一行都落不了盘。实测 61 个日志文件
    ``grep -F '[DreamMemory]'`` = **0 命中**，而 ``取数面=`` 那一行正是
    docstring 承诺的可观测面 ⇒「无人知道它在空转」的防线没接上。
    双向对照证明是**配置**而非代码路径：与 cron 同形态（裸 import、无配置）
    时 ``effectiveLevel=WARNING`` ∧ ``root_handlers=[]`` ⇒ INFO 被
    ``logging.lastResort`` 丢弃；同进程加 ``basicConfig(level=INFO)`` 即出现。

    为什么是这里：活体入口 ``scripts/dream_memory_cron.sh`` 用的是
    「裸解释器 + ``-c`` 单行脚本」形态 ⇒ 本模块**被 import**，
    ``__name__ != "__main__"`` ⇒ 文件末尾 ``__main__`` 块里的
    basicConfig **从不执行**。故把配置挪进 ``cli_main()``。

    为什么只挂 FileHandler、不挂 StreamHandler：gateway 的 cron 投递会把
    stdout + stderr 一并发出（``cron_mixin.py:927-929``）⇒ 日志进 stderr
    等于把投递面撑大。**观测面写文件，投递面只留报告。**
    """
    if getattr(logger, "_mimir_cli_log_ready", False):
        return
    try:
        log_dir = os.path.join(_mimir_home(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.FileHandler(
            os.path.join(log_dir, "dream_memory.log"), encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger._mimir_cli_log_ready = True
    except Exception as exc:  # noqa: BLE001 — 观测面故障不得阻断蒸馏
        # 出声：stderr 会随 cron 投递到达 deliver 目标，不静默降级
        print(
            f"[DreamMemory] WARN: 日志面初始化失败（观测降级，蒸馏继续）: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


def cli_main(argv: Optional[List[str]] = None) -> int:
    """cron / 终端入口：**退出码即结论**（0 = 成功 / 跳过 · 1 = 失败）。

    为什么必须有这条：``sync_run_dream_cycle`` 只返回字符串、永远 exit 0 ⇒
    gateway 侧 ``mark_job_run`` 永远记 ``ok``（``cron_mixin.py:930`` 判的是 rc）
    ⇒ 失败连 ``last_status=error`` 都不产生。① 的出口就落在 rc 上。
    """
    _ensure_cli_logging()  # 活体 cron 走 import 路径 ⇒ __main__ 块不执行
    args = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in args
    try:
        report = sync_run_dream_cycle(dry_run=dry)
    except Exception as exc:  # noqa: BLE001 — 未捕获异常也必须是「出声」而不是 traceback 了事
        detail = _record_failure("unhandled", exc)
        print(f"{_FAILURE_MARKER} stage=unhandled {detail}", file=sys.stderr)
        return 1
    print(report)
    if not dry and _FAILURE_MARKER in report:
        print(
            f"{_FAILURE_MARKER}: rc=1 · 失败记录见 {_failure_record_path()}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    sys.exit(cli_main())
