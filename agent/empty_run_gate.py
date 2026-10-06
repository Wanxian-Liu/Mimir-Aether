"""空跑闸门（empty-run gate）——2026-09-28 · 第 3 次空跑实证后机制化。

## 病灶（盘上实证）
- run be1eb421e3a066cf（2026-09-27T19:48:24→19:49:53 · 89.75s · 10 步）：
  **10/10 只读**（skill_view 1 + execute_code 5 + read_file 4），**0 写交付物**，
  最终 content 空 ⇒ exit_reason=empty_content ⇒ 静默退出，任务书五问一句没答。
- run d85a4c1097d19fb4（第 2 次 · 8 步）：7 只读 + 1 次 execute_code 写**中转草稿**
  （mimir home 的 tmp/b2/src.md）⇒ 材料读齐、草稿在盘，但交付物没写 ⇒ 同样空跑。
- 批 1 立的「单轮只读 ≤3 转写」只有**提示词载体**：一轮上下文变长就被稀释。
  **约束是概率，机制才是保证。**

## 闸门形态（两段式）
- **A 止血 · exit 前 flush**：`empty_content` 出口前，若本 run 有 staging 写（tmp 草稿）
  且交付物未写 ⇒ 把草稿落进目标卡（追加 `半段` 标记）⇒ 把「静默退出」变「带伤交付」。
  落盘后**给模型一次补写机会**（注入硬指令 + continue），预算 MIMIR_EMPTY_RUN_MAX_FORCE（默认 2）。
- **B 预防 · 只读预算硬限**：每轮统计只读连续轮数，达 MIMIR_READONLY_TURN_LIMIT（默认 4）
  ⇒ 经既有**安全通道**（_read_gate_directive，序列合法）注入硬指令「本轮到写」。

## 判据（纯函数 · 可离线测）
本模块**不依赖** _check_has_written（它只认 write_file/patch，execute_code 写盘不计 —— 第 2 次
被读成 has_written=False 的量具缺口），独立实现 staging 判定 ⇒ 量具与闸门解耦。

## 回滚
MIMIR_EMPTY_RUN_GATE=0 ⇒ 全部退化为现状（只有 empty_content，不 flush 不注入）。
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 工具分类 ────────────────────────────────────────────────────────────────
WRITE_TOOLS = {"write_file", "patch", "create_file", "edit", "write"}
# 能写盘的「非写工具」——内容级判定（否则第 2 次的草稿会被读成「从未动笔」）
EXEC_TOOLS = {"execute_code", "terminal"}

# staging 判据：中转目录（写了不算交付）
STAGING_MARKERS = (
    "/.mimiraether/tmp/",
    "/tmp/",
    "/.mimir-inbox/tmp/",
)
# P0-3（2026-10-07 · Hermes 复核 #12 补刀）：临时目录**禁字面量**。
#   病灶：TMPDIR 非 /tmp 时（Hermes 会话默认 ~/.hermes/cache/scratch），写进临时目录的
#   草稿不算 staging ⇒ 反被判「写了交付物」⇒ 只读计数清零（P0-2 的病换路径复发）。
#   修法：临时目录标记运行期由 tempfile.gettempdir() 展开；保留 "/tmp/" 字面量 = 兼容。
#   同族口径：本文件 `_HOME = os.path.expanduser("~")`（家路径禁字面量 · pre-push A6）。
# 交付物排除项（工作记忆/运行日志 —— 同 _check_has_written 口径）
# P0-1（2026-09-28 · probe_p5 5a 实证）：补 "logs/" / ".log" / ".jsonl" ——
#   运行日志被读成「交付物」⇒ deliverable_written() 误真 ⇒ B 段掩护被误关（静默空跑）。
WORK_MEMORY_KEYS = ("search-notes.md", "PROGRESS.md", "/tmp/", "run-log/",
                    "logs/", ".log", ".jsonl")


def _tempdir_markers() -> Tuple[str, ...]:
    """运行期临时目录标记（带尾斜杠）——TMPDIR=/tmp 时返回空元组（静态标记已覆盖）。

    `tempfile.gettempdir()` = 本进程临时目录唯一真源（已含 TMPDIR 语义）；不用 realpath
    （TMPDIR 为符号链接时会与模型实际写下的路径字面量不符）。异常/根目录兜底返回空 ⇒
    退化为静态标记，绝不因取目录失败把 staging 误判成交付物。
    """
    try:
        d = tempfile.gettempdir()
    except Exception:
        return ()
    if not d:
        return ()
    m = str(d).replace("\\", "/").rstrip("/") + "/"
    if len(m) <= 1 or m == "/tmp/":     # "/" ⇒ 全部路径皆临时目录 ⇒ 拒绝放大
        return ()
    return (m,)


def staging_markers() -> Tuple[str, ...]:
    """staging 判据全集（静态 + 运行期临时目录）——分类判定唯一入口。"""
    return STAGING_MARKERS + _tempdir_markers()


def work_memory_keys() -> Tuple[str, ...]:
    """交付物排除项全集（静态 + 运行期临时目录）。"""
    return WORK_MEMORY_KEYS + _tempdir_markers()


_PATH_RE = re.compile(r"[\w./~-]+\.(?:md|py|json|txt|yaml|yml|sh|log|html)")
_OPEN_W_RE = re.compile(r"open\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][wax]")
_WRITE_TEXT_RE = re.compile(r"write_text\(|Path\(\s*['\"]([^'\"]+)['\"]\s*\)")
_HEREDOC_RE = re.compile(r">\s*(?:[\w./~-]+\.(?:md|txt|json))")
# 家路径禁字面量（pre-push A6 闸）：运行期展开；HOME=/home/<user> 时与硬编码逐字等价。
_HOME = os.path.expanduser("~")
_CARD_HINTS = re.compile(r"(?:wiki/(?:discussions|concepts|raw)|" + re.escape(_HOME) + r"/wiki)/[^\s'\"`)]+\.md")

# ── P0-1（2026-09-28）：写动作 × 目标路径 **配对**的取路径正则 ──
# 只有写在**写动作参数位**上的路径才算「写目标」；注释/字符串里「提及」的不算。
_PATH_WRITE_RE = re.compile(r"Path\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.\s*(?:write_text|write_bytes|open)\s*\(")
_PATH_OPEN_MODE_RE = re.compile(r"\.\s*open\(\s*['\"][wax]")
_SHELL_REDIRECT_RE = re.compile(r">>?\s*['\"]?([\w./~-]+\.(?:md|py|json|jsonl|txt|yaml|yml|sh|log|html))")
_TEE_RE = re.compile(r"\btee\s+(?:-a\s+)?['\"]?([\w./~-]+\.\w+)")


# ── 别名路径（P0-2 · 2026-10-07）：变量化写路径识别 ──
# 病灶：p = Path("<card>.md"); p.write_text(...) —— 「写动作 × 目标路径」正则只认
#   Path('字面量').write_*，变量形态 ⇒ write_targets() 返回 [] ⇒ deliverable_written()
#   恒 False（而 classify_tool 因 ".write_text(" 命中仍判 write）⇒ 计数口径分裂。
_ALIAS_PATH_RE = re.compile(
    r"""(\w+)\s*=\s*(?:pathlib\.)?Path\(\s*['"]([^'"]+)['"]\s*\)""")


def _alias_write_paths(raw):
    """别名变量 → 真实路径：`v = Path(p)` 且 `v.write_text(`/`v.open('w'`。"""
    out = []
    for var, path in _ALIAS_PATH_RE.findall(raw or ""):
        hit = (re.search(re.escape(var) + r"""\s*\.\s*(?:write_text|write_bytes)\s*\(""", raw or "")
               or re.search(re.escape(var) + r"""\s*\.\s*open\s*\(\s*['"][wax]""", raw or ""))
        if hit and path not in out:
            out.append(path)
    return out


def gate_enabled() -> bool:
    """总开关（回滚用）。"""
    return os.environ.get("MIMIR_EMPTY_RUN_GATE", "1").strip().lower() not in ("0", "false", "no")


def readonly_turn_limit() -> int:
    try:
        return max(1, int(os.environ.get("MIMIR_READONLY_TURN_LIMIT", "4") or "4"))
    except Exception:
        return 4


def readonly_hard_limit() -> int:
    """硬限（机制，非提醒）：连续未交付轮数 ≥ 此值 ⇒ 只读工具被 agent_loop 拒发。

    默认 = readonly_turn_limit() * 3（限 4 ⇒ 硬限 12）；显式设 0 关闭（回滚）。
    为什么需要它（盘上实证 run 337cb513 · 2026-09-30 13:42→13:44）：闸门自 turn 5 起
    **每轮**注入强制落盘指令（streak 4→15，连续 12 轮），模型全部忽略 ⇒ 纯提醒在长回环
    里饱和。硬限把「提醒」升级为「工具面拒绝」= 有可观察后果。
    """
    raw = os.environ.get("MIMIR_READONLY_HARD_LIMIT")
    if raw is None or str(raw).strip() == "":
        return readonly_turn_limit() * 3
    try:
        return max(0, int(raw))
    except Exception:
        return readonly_turn_limit() * 3


def build_blocked_result(name: str, streak: int, hard_limit: int) -> str:
    """被硬限拒发的只读调用所返回的**替代工具结果**（保持 API 消息序列合法）。"""
    return (
        f"[空跑闸门·硬限] 已连续 {streak} 轮未产出交付物（硬限 {hard_limit}）；"
        f"只读调用 `{name}` 已被拒绝。本轮**只能**写：用 write_file/patch 落**半段**"
        f"交付物（骨架 + 已确证结论 + 待补清单），写完再补证。"
    )


def max_force_writes() -> int:
    try:
        return max(0, int(os.environ.get("MIMIR_EMPTY_RUN_MAX_FORCE", "2") or "2"))
    except Exception:
        return 2


def _tc_name(tc: Any) -> str:
    if isinstance(tc, dict):
        fn = tc.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            return str(fn["name"])
        return str(tc.get("name") or "")
    fn = getattr(tc, "function", None)
    if fn is not None:
        return str(getattr(fn, "name", "") or "")
    return str(getattr(tc, "name", "") or "")


def _tc_args(tc: Any) -> str:
    if isinstance(tc, dict):
        fn = tc.get("function")
        args = fn.get("arguments") if isinstance(fn, dict) else tc.get("arguments")
    else:
        fn = getattr(tc, "function", None)
        args = getattr(fn, "arguments", None) if fn is not None else getattr(tc, "arguments", None)
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args or {}, ensure_ascii=False)
    except Exception:
        return str(args or "")


def classify_tool(name: str, args_raw: str = "") -> str:
    """单个工具调用归类：write / readonly。

    execute_code / terminal 需**内容级**判据（写了文件才算 write）——这是第 2 次空跑
    被误读成「从未动笔」的根因。判据：open(...,'w'/'a') / write_text( / shell 重定向。
    """
    n = (name or "").strip()
    if n in WRITE_TOOLS:
        return "write"
    if n in EXEC_TOOLS:
        s = args_raw or ""
        # P0-1（2026-09-28）：判据收紧到**真写形态** —— `Path(p)` 单独出现（只读）不再误判 write；
        #   写动作清单 = open(p,'w'|'a'|'x') / Path(p).write_text|write_bytes|open('w') / .write*() /
        #   shell 重定向 & tee / heredoc / 显式委托 write_file·patch。
        if (_OPEN_W_RE.search(s) or _PATH_WRITE_RE.search(s) or _PATH_OPEN_MODE_RE.search(s)
                or ".write_text(" in s or ".write_bytes(" in s or ".write(" in s
                or _SHELL_REDIRECT_RE.search(s) or _TEE_RE.search(s)
                or _HEREDOC_RE.search(s)):
            return "write"
        if "write_file" in s or "patch(" in s:
            return "write"
    return "readonly"


def turn_kind(tool_names: List[str]) -> str:
    """一轮的性质：write（含写）/ readonly（全只读）/ none（无工具调用）。"""
    if not tool_names:
        return "none"
    return "write" if any(classify_tool(n) == "write" for n in tool_names) else "readonly"


def turn_deliverable_written(tcs):
    """该轮是否**真写交付物**（写动作 × 交付物路径 配对）。"""
    for tc in (tcs or []):
        name = _tc_name(tc); raw = _tc_args(tc)
        if classify_tool(name, raw) != "write":
            continue
        if any(is_deliverable_path(q) for q in write_targets(name, raw)):
            return True
    return False


def readonly_streak(messages: List[Dict[str, Any]], max_scan: int = 40) -> int:
    """从尾往前数**连续「未产出交付物」轮数**（assistant 带 tool_calls 的轮次）。

    ★ P0-2（2026-10-07 · 治 10-05 审计 E4「阈值 4 · 实测 15」）计数语义修复：
      - 旧版：命中**任意 write** 即清零 ⇒ staging 草稿 / logs 写同样退还预算，而
        deliverable_written() 仍为 False ⇒ **闸门在它自己要防的死法里被自己关掉**
        （d85a4c10：写 tmp 草稿 → 继续只读 → 空正文退出）。
      - 新版：**只有真写交付物才清零**；非交付写与只读写同计（都 = 没交付）。
      - 判据（受控差分）：scripts/probes/empty_run_gate_budget_differential.py
        —— 旧版 staging 写后**静默 4 轮**，新版下一轮即再触发。
    - 「无工具调用的 assistant 轮」不计入也不打断（那是模型在说话，不是只读回环）。
    """
    streak = 0
    scanned = 0
    for m in reversed(messages or []):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        scanned += 1
        if scanned > max_scan:
            break
        tcs = m.get("tool_calls") or []
        if not tcs:
            continue
        if turn_deliverable_written(tcs):
            break
        streak += 1
    return streak


def _norm_paths(raw: str) -> List[str]:
    out: List[str] = []
    for q in _PATH_RE.findall(raw or ""):
        if q and q not in out:
            out.append(q)
    return out


def _expand(q: str) -> str:
    return q.replace("~", str(Path.home()))


def is_staging_path(q: str) -> bool:
    return any(k in _expand(q) for k in staging_markers())


def is_deliverable_path(q: str) -> bool:
    if not q:
        return False
    if is_staging_path(q):
        return False
    return not any(k in _expand(q) for k in work_memory_keys())


def write_targets(name: str, args_raw: str = "") -> List[str]:
    """该工具调用的**写目标**路径 —— 「写动作 × 目标路径」配对的唯一取路径入口。

    与 `_norm_paths()`（扫**整串** args）的区别：只认**写动作参数位**上的路径。
    病灶（probe_p5 5a 实证）：
        open('<tmp 草稿>','a').write('x')  # log=<MIMIR_HOME>/logs/agent.log
    旧口径把**注释里提及**的 agent.log 读成交付物 ⇒ deliverable_written() 误真
    ⇒ tick() 不注入 + flush() 直接 return [] ⇒ **B 段掩护被误关**（静默空跑）。
    """
    n = (name or "").strip()
    raw = args_raw or ""
    out: List[str] = []

    def _add(q: str) -> None:
        if q and q not in out:
            out.append(q)

    if n in WRITE_TOOLS:
        d = None
        if raw.strip().startswith("{"):
            try:
                d = json.loads(raw)
            except Exception:
                d = None
        if isinstance(d, dict):
            for k in ("path", "file_path", "filepath", "filename", "target",
                      "target_path", "notebook_path"):
                v = d.get(k)
                if isinstance(v, str):
                    _add(v)
        else:
            # 非 JSON 形态：参数本身即路径（保守回退，仍不含注释/无关串）
            for q in _norm_paths(raw):
                _add(q)
        return out

    if n in EXEC_TOOLS:
        for q in _OPEN_W_RE.findall(raw):       # open('p', 'w'|'a'|'x')
            _add(q)
        for q in _PATH_WRITE_RE.findall(raw):   # Path('p').write_text(... / .open('w')
            _add(q)
        for q in _SHELL_REDIRECT_RE.findall(raw):  # > p / >> p
            _add(q)
        for q in _alias_write_paths(raw):   # v = Path('p'); v.write_text(...)
            _add(q)
        for q in _TEE_RE.findall(raw):          # tee [-a] p
            _add(q)
    return out


def staging_writes(messages: List[Dict[str, Any]]) -> List[str]:
    """本 run 里**真实发生**的 staging 写盘路径（execute_code/terminal 内容级 + write_file/patch）。"""
    found: List[str] = []
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        for tc in (m.get("tool_calls") or []):
            name = _tc_name(tc)
            raw = _tc_args(tc)
            if classify_tool(name, raw) == "write":
                # P0-1：路径取「写动作 × 目标路径」配对结果（禁扫整串 args）
                for q in write_targets(name, raw):
                    if is_staging_path(q) and q not in found:
                        found.append(q)
    return found


def deliverable_written(messages: List[Dict[str, Any]]) -> bool:
    """本 run 是否写过交付物（非 staging、非工作记忆）。"""
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        for tc in (m.get("tool_calls") or []):
            name = _tc_name(tc)
            raw = _tc_args(tc)
            if classify_tool(name, raw) == "write":
                # P0-1：配对取路径 —— 代码里「提及」的路径不算交付物写入
                if any(is_deliverable_path(q) for q in write_targets(name, raw)):
                    return True
    return False


def infer_target(messages: List[Dict[str, Any]]) -> Optional[str]:
    """从任务书（首条含卡路径的 user 消息）推断交付物目标卡——讨论卡优先。"""
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        c = m.get("content")
        if not isinstance(c, str):
            continue
        hits = _CARD_HINTS.findall(c)
        if hits:
            q = hits[0]
            if q.startswith("/"):
                return q          # 已是绝对路径（测试/自定义 hint 也走这条）
            return _HOME + "/" + q.lstrip("/")
    return None


def build_directive(streak: int, limit: int, staging: List[str], turn: int = 0,
                    ignored: int = 0) -> str:
    """只读预算用尽时的硬指令（经 _read_gate_directive 安全通道注入）。

    ignored = 连续被忽略的指令数（P0-2）：达硬限后只读工具会被**拒发**，故此处必须
    把「还剩几轮就硬拒」讲清楚——否则模型只会看到工具突然报错却不知为何。
    """
    where = ("\n已读材料的中转草稿在：" + "、".join(staging)) if staging else ""
    _hl = readonly_hard_limit()
    _esc = ""
    if _hl > 0:
        _left = max(0, _hl - streak)
        _esc = (f"\n⚠️ 硬限 {_hl}：再连续只读 {_left} 轮，只读工具将被**直接拒绝**"
                f"（机制，不是提醒）。本指令已被忽略 {ignored} 次。")
    return (
        f"【空跑闸门】本 run 已连续 {streak} 轮只读（预算 {limit}）且**交付物未写**——"
        f"本轮**必须**先落盘再继续：用 write_file/patch 把已读材料落成**半段**交付物"
        f"（骨架 + 已确证部分 + 待补清单），写完再补证。只读=不合格。{where}{_esc}"
    )


HALF_MARK = "<!-- 半段·未完成（empty-run gate flush） -->"


def _safe_id(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", task_id or "run")[:40]


def flush_draft(draft_path: str, target_path: Optional[str], task_id: str,
                turn: int = 0, reason: str = "") -> Dict[str, Any]:
    """把 staging 草稿落成**半段交付物**（幂等：同一草稿第二次调用不重复追加）。

    目标缺失/卡内已有本段标记 ⇒ 走 fallback（mimir home 的 data/half_drafts/）。
    """
    out: Dict[str, Any] = {"flushed": False, "target": "", "chars": 0, "reason": ""}
    src = Path(_expand(draft_path))
    if not src.exists() or not src.is_file():
        out["reason"] = "draft_missing"
        return out
    body = src.read_text(encoding="utf-8", errors="replace").strip()
    if not body:
        out["reason"] = "draft_empty"
        return out
    tgt = Path(_expand(target_path)) if target_path else None
    if tgt is not None and not tgt.parent.exists():
        tgt = None
    if tgt is None:
        home = Path(os.environ.get("MIMIR_AETHER_HOME") or (Path.home() / ".mimiraether"))
        tgt = home / "data" / "half_drafts" / f"{_safe_id(task_id)}.md"
        tgt.parent.mkdir(parents=True, exist_ok=True)
    existing = tgt.read_text(encoding="utf-8", errors="replace") if tgt.exists() else ""
    if HALF_MARK in existing and "## 【Mimir · 半段（staging flush）】" in existing:
        out.update(target=str(tgt), reason="already_flushed")
        return out
    block = (
        f"\n\n---\n\n## 【Mimir · 半段（staging flush）】\n"
        f"{HALF_MARK}\n"
        f"<!-- run={_safe_id(task_id)} turn={turn} reason={reason} draft={draft_path} -->\n\n"
        f"{body}\n"
    )
    with tgt.open("a", encoding="utf-8") as fh:
        fh.write(block)
    out.update(flushed=True, target=str(tgt), chars=len(body), reason="flushed")
    return out


class EmptyRunGate:
    """只读预算 + exit 前 staging flush 的运行时状态机（无 IO 依赖，纯在 messages 上演算）。

    接线点（agent_loop）：
      - 每轮 tool 结果 append 后：`tick()` ⇒ 返回硬指令则经 _read_gate_directive 注入；
      - empty_content 出口前 / _finalize_exit：`flush()` ⇒ 带伤交付 + 一次补写机会。
    """

    def __init__(self, task_id: str = "", limit: Optional[int] = None,
                 force_writes: Optional[int] = None) -> None:
        self.task_id = task_id or "run"
        self.limit = int(limit if limit is not None else readonly_turn_limit())
        self.force_remaining = int(force_writes if force_writes is not None else max_force_writes())
        self.streak = 0
        self.directives_sent = 0
        self.flushed_paths: List[str] = []
        self.ignored = 0          # 连续被忽略的指令数（P0-2 升级/硬限判据）

    # --- B 预防 ---
    def tick(self, messages: List[Dict[str, Any]], turn: int = 0) -> Optional[str]:
        """每轮调用：只读预算用尽 ⇒ 返回硬指令（否则 None）。"""
        self.streak = readonly_streak(messages)
        if self.streak < self.limit or deliverable_written(messages):
            self.ignored = 0          # 预算内 / 真交付 ⇒ 复位「被忽略」计数
            return None
        self.directives_sent += 1
        self.ignored += 1
        return build_directive(self.streak, self.limit, staging_writes(messages), turn,
                               ignored=self.ignored)

    def should_block_readonly(self, name: str, raw: str = "") -> bool:
        """硬限判定（纯谓词 · agent_loop 工具派发口调用）：超硬限的只读调用 ⇒ 拒发。

        机制理由（run 337cb513 实证）：指令自 turn 5 起每轮注入、连续 12 轮被忽略
        ⇒ 纯文字提醒在长只读回环里饱和。此处把闸门输出接到**工具面**：超限时只读调用
        由调用方返回 build_blocked_result()，模型拿不到新信息 ⇒ 唯一可推进动作=写。
        """
        hl = readonly_hard_limit()
        if hl <= 0 or self.streak < hl:
            return False
        return classify_tool(name, raw) == "readonly"

    # --- A 止血 ---
    def flush(self, messages: List[Dict[str, Any]], turn: int = 0, reason: str = "") -> List[Dict[str, Any]]:
        if deliverable_written(messages):
            return []
        results = []
        for d in staging_writes(messages):
            r = flush_draft(d, infer_target(messages), self.task_id, turn, reason)
            results.append(r)
            if r.get("flushed"):
                self.flushed_paths.append(str(r.get("target")))
        return results

    def take_force_slot(self) -> bool:
        """exit 时是否还能给模型一次补写机会（有则消耗一格）。"""
        if self.force_remaining <= 0:
            return False
        self.force_remaining -= 1
        return True

    def exit_directive(self, staging: List[str]) -> str:
        where = ("\n草稿已在：" + "、".join(staging)) if staging else ""
        return (
            "【空跑闸门·强制落盘】你正在以**空正文**结束，且本 run 交付物未写——"
            "不许空手退出。现在立即用 write_file/patch 把已读材料落成**半段交付物**"
            "（骨架 + 已确证结论 + 待补清单），然后才允许收尾。"
            f"（禁止再只读）{where}"
        )

    @staticmethod
    def enabled() -> bool:
        return gate_enabled()
