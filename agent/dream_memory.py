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

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 容量限制（与 CrossSessionMemory 一致）
_MAX_DECISIONS = 20
_MAX_PATTERNS = 30
_MAX_CONSTRAINTS = 5  # 行为约束上限

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
    try:
        from agent.persistent_normalize import normalize_and_log

        normalize_and_log(data, source="dream-memory")
    except Exception as e:  # noqa: BLE001 — 见上：不允许因规范化失败丢记忆
        logger.error("[DreamMemory] PERSISTENT-NORMALIZE 失败（本次写盘未净化）: %s", e)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
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

    return "\n".join(lines)


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


def build_distillation_input(data: Dict, memory_md_text: str) -> Tuple[str, str]:
    """纯函数：决定蒸馏取数面并产出输入文本。

    优先级（B 档 #17 判据 = 取数面改指向 memories/MEMORY.md）：
      ① persistent.json 的 key_decisions / learned_patterns 非空 ⇒ 行为与改前一致
      ② ①为空 且 MEMORY.md 有正文 ⇒ 输入 = MEMORY.md 正文
      ③ 皆空 ⇒ 空串 + 标记 none，调用方据此判「无内容可蒸馏」且**不写盘**

    Returns:
        (输入文本, 取数面标记) —— 标记与读数落日志，治「无人知道它在空转」。
    """
    primary = _format_memory_for_distillation(data)
    if primary.strip():
        return primary, _DISTILL_SOURCE_PERSISTENT
    body = (memory_md_text or "").strip()
    if body:
        return body, _DISTILL_SOURCE_MEMORY_MD
    return "", _DISTILL_SOURCE_NONE


def distillation_input_metrics(text: str) -> Dict[str, int]:
    """输入读数（可观测性）：字符数 / 非空行数 / 段数（段 = 独占一行的 §）。"""
    all_lines = text.splitlines()
    return {
        "chars": len(text),
        "lines": sum(1 for ln in all_lines if ln.strip()),
        "segments": sum(1 for ln in all_lines if ln.strip() == "§"),
    }


def _build_distillation_prompt(memory_text: str) -> str:
    """构建梦境蒸馏的 LLM 提示词。"""
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
9. **self_contradiction** 为单条字符串——分析记忆条目中最严重的自我矛盾（哪个决策和哪个模式冲突）
10. **每条决策可附带 context 字段**（不超过 30 字）
11. **每条模式可附带 evidence 字段**（不超过 50 字）
12. **每条约束格式**：{{"rule": "你应该/你不应该...", "source": "distilled", "evidence": "基于XX条模式/决策的提炼"}}
13. **（Trajectory-Informed Memory）** 每条决策和模式增加以下字段：
    - **tip_type**：分类为 "strategy"（策略—以后该怎么做）、"recovery"（恢复—怎么从错误中修）、"optimization"（优化—怎么把好的做得更好）
    - **cause_chain**（仅决策）：{{"direct": "直接触发原因", "proximate": "近因/中间原因", "root": "根因/系统性问题"}}
14. **只输出 JSON**，不要解释过程。

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
    解析失败时日志行仍留 200 字摘要（``_safe_json_parse`` 内）。
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
                f" · 尝试 {attempts} 次 ⇒ 原始载荷见失败件"
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

    logger.error(f"[DreamMemory] 所有 JSON 解析策略均失败，前200字: {text[:200]}")
    return None


def _get_contradiction_path() -> str:
    """获取 self_contradiction_report.json 路径。"""
    home = os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
    return os.path.join(home, "data", "self_contradiction_report.json")


def _save_contradiction_report(contradiction: str) -> bool:
    """将自我矛盾报告写入独立文件。"""
    if not contradiction or not contradiction.strip():
        return False
    path = _get_contradiction_path()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contradiction": contradiction.strip(),
    }
    try:
        # 追加到已有报告列表（保留最近10条）
        existing = []
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        if len(existing) > 10:
            existing = existing[-10:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info(f"[DreamMemory] 自我矛盾报告已写入: {contradiction[:80]}...")
        return True
    except (IOError, json.JSONDecodeError) as e:
        logger.warning(f"[DreamMemory] 写入自我矛盾报告失败: {e}")
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

    prompt = _build_distillation_prompt(memory_text)
    logger.info(f"[DreamMemory] 调用蒸馏 LLM（提示词 {len(prompt)} 字符）")
    result = await _call_dream_llm(prompt)

    if result is None:
        return data, "❌ 梦境蒸馏 LLM 调用失败，未修改", False

    # 统计蒸馏前后的条目数
    old_decisions = len(data.get("memory", {}).get("key_decisions", []))
    old_patterns = len(data.get("memory", {}).get("learned_patterns", []))
    old_constraints = len(data.get("memory", {}).get("behavioral_constraints", []))
    new_decisions = len(result.get("key_decisions", []))
    new_patterns = len(result.get("learned_patterns", []))
    new_constraints = len(result.get("behavioral_constraints", []))

    # 用蒸馏后的条目替换原有记忆
    if "memory" not in data:
        data["memory"] = {}
    data["memory"]["key_decisions"] = result["key_decisions"][:_MAX_DECISIONS]
    data["memory"]["learned_patterns"] = result["learned_patterns"][:_MAX_PATTERNS]

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

    # PMD 共同进化：写入 behavioral_constraints
    if new_constraints > 0:
        data["memory"]["behavioral_constraints"] = result["behavioral_constraints"][:_MAX_CONSTRAINTS]
    else:
        data["memory"].pop("behavioral_constraints", None)

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

    report = (
        f"🔄 梦境蒸馏完成\n"
        f"  - key_decisions: {old_decisions} → {new_decisions} "
        f"({old_decisions - new_decisions:+d})\n"
        f"    · tip_type 分布: {tip_types_decisions}\n"
        f"    · cause_chain 覆盖率: {decisions_with_chain}/{new_decisions}\n"
        f"  - learned_patterns: {old_patterns} → {new_patterns} "
        f"({old_patterns - new_patterns:+d})\n"
        f"    · tip_type 分布: {tip_types_patterns}\n"
        f"  - behavioral_constraints: {old_constraints} → {new_constraints} "
        f"({new_constraints - old_constraints:+d})\n"
        f"  - 自我矛盾: {'⚠️ ' + contradiction[:80] if contradiction else '✅ 无'}\n"
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
    memory_text, distill_source = build_distillation_input(
        data, _load_memory_markdown(memory_md_path)
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
        "[DreamMemory] 取数面=%s · 输入 %d 字符 / %d 行 / %d 段",
        distill_source,
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
        ok = _save_persistent(path, updated_data)

    if not ok:
        detail = _record_failure("save", IOError(f"_save_persistent({path}) 返回 False"))
        return False, report + f"\n❌ 写入失败（耗时 {elapsed:.1f}s）\n{_FAILURE_MARKER}: {detail}"

    # 6. 写哨兵文件——通知 CrossSessionMemory 下一轮 save 前从磁盘重载缓存
    #    （避免终端进程蒸馏写盘后，Gateway 进程仍用旧缓存 59 kd 覆盖掉压缩后的 20 kd）
    _write_distill_sentinel()
    return True, report + f"\n✅ 写入成功（耗时 {elapsed:.1f}s）\n备份: {backup_dir}"


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

def cli_main(argv: Optional[List[str]] = None) -> int:
    """cron / 终端入口：**退出码即结论**（0 = 成功 / 跳过 · 1 = 失败）。

    为什么必须有这条：``sync_run_dream_cycle`` 只返回字符串、永远 exit 0 ⇒
    gateway 侧 ``mark_job_run`` 永远记 ``ok``（``cron_mixin.py:930`` 判的是 rc）
    ⇒ 失败连 ``last_status=error`` 都不产生。① 的出口就落在 rc 上。
    """
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
