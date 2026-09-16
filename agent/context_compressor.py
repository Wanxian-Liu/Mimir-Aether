"""
MimirAether Context Compressor V2.3

MimirAether native context compressor — standalone, no ABC inheritance.
- V2.2: Initial implementation
- V3.0: Removed ContextEngine ABC; self-designed interface
"""

import re
import time
import logging
import os
import json
import aiohttp
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# RS3（四方裁决 2026-09-13）：夹紧真源在 policy 模块，此处只消费公开名。
from agent.decision_compressor_policy import clamp_compressor_key


def _resolve_api_model_name(model: str) -> str:
    """把 provider 命名空间形式（deepseek/deepseek-flash）归一到官方 API 认的裸名。

    F-A (2026-09-14)：官方 api.deepseek.com **只接受裸模型名**
    （实测 HTTP 400: "The supported API model names are deepseek-flash,
    deepseek-v4-pro, but you passed deepseek/deepseek-flash"）。
    主对话路径在 `agent/callers_mixin.py`（约 L743）已做同样归一；
    本函数复用公共实现 `agent.model_metadata.strip_provider_prefix`
    —— 同一逻辑只应有一份（G11 单一真源）。
    """
    if not model:
        return model
    try:
        from agent.model_metadata import strip_provider_prefix

        stripped = strip_provider_prefix(model)
        if stripped:
            return stripped
    except Exception:
        pass
    # 兜底：与主路径同款行为（provider/model -> model），避免 import 失败时退回未归一
    if "/" in model and not model.startswith("http"):
        return model.split("/")[-1]
    return model

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

SUMMARY_PREFIX = "[CONTEXT COMPACTION — REFERENCE ONLY]"

# ── RS14-C1 (2026-09-14)：确定性实体索引 ──────────────────────────────────
# 问题：_verify_entity_retention 按「整段 pre」收集实体，但中间段在设计上必然被
# 摘要替换 ⇒ 中间实体在 post 缺席 ⇒ 保留率恒 <80% ⇒ 压缩 187/187 全部回滚。
# 修法：摘要（llm 与 template 两条路）追加一段**机器生成**的实体清单，让被压缩掉的
# 中间段实体在 post 里真实存在（修因，而非放宽闸门——闸门强度保持不变）。
ENTITY_PATTERN = (
    r"(discussions/[\w\-\.]+\.md|status:\s*\w+|~/wiki/[\w/\.]+|~/src/MimirAether|commit [0-9a-f]{7})"
)
_ENTITY_INDEX_MAX_ITEMS = 120      # 条数上限（超出则截断并告警）
_ENTITY_INDEX_MAX_CHARS = 6000     # 字符上限（约 1.5K tokens，相对 120K 阈值可忽略）
ENTITY_INDEX_HEADING = "## 实体索引（自动生成，非模型输出）"

# ── RS14-D1 (2026-09-14)：质量记录仪器化 ─────────────────────────────────────
# 为什么（RS14 §0 E5 盘上实测）：历史 275 条记录全 rollback，且
#   ① `missing` 被 `missing[:5]` 截断 ⇒ 明细/分母不可复算（"历史 rate 不可复算"）；
#   ② 无 `entity_count` ⇒ 率无法独立验算；
#   ③ 无 `summary_elapsed_s` / `requested_max_tokens` ⇒ Q3 耗时分布只能拿
#      「30.9s 超时截断值」推断（观测值被截断机制本身决定 = 循环论证）；
#   ④ 无 `gate_version` ⇒ 跨闸门语义的率不可比（RS14 §13.3 约束）。
# 这批字段是 D-3 的 R1/R2/Δ 基线、D-4 的 degraded_streak 与 A5 审计的唯一数据源。
_QUALITY_MISSING_MAX_ITEMS = 200   # missing 明细落盘上限（超出保计数+missing_capped，不丢可复算性）

# 闸门语义版本戳 —— 任何改变「实体收集口径 / 判据阈值 / 硬闸成员」的改动都必须
# 改这个串，否则跨语义分布不可比。当前语义：实体集 = 整段 pre 去重集；判据 R1 >= 0.80。
ENTITY_GATE_VERSION = "rs14.d1.v1.full-pre-set+r1>=0.80"

# ── RS14-C2 (2026-09-14)：摘要输出 token 上限 ─────────────────────────────
# 实测（09-14，真 API，同一 prompt）：请求 max_tokens=1000 → 5.5s OK；
# 3000 → 13.0s OK；8000 → 30.5s **TimeoutError**（硬超时 30s）。
# ⇒ 超时由「请求的输出预算」驱动，与 prompt 体积无关（174K 字符 prompt 在 1000 预算下 5.5s 完成）。
# 原代码 `max_tokens * 2`（budget 上限 8000 ⇒ 请求 16000）必然撞墙。
# 修法：夹到 _SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT，env 可调。
_SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT = 4000
_SUMMARY_MAX_OUTPUT_TOKENS_ENV = "MIMIR_COMPRESS_SUMMARY_MAX_TOKENS"


def _resolve_summary_max_output() -> int:
    """摘要输出 token 上限（env > 默认）。非法值静默降级默认，不抛。"""
    _raw = os.environ.get(_SUMMARY_MAX_OUTPUT_TOKENS_ENV)
    if _raw:
        try:
            _v = int(_raw)
            if _v > 0:
                return _v
        except Exception:
            pass
    return _SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT
# ── T16（2026-09-14）：压缩冷却闸（盘上持久化）────────────────────────────
# 根因（T18 定案）：core_loop.py:907 触发门只有 tokens>=threshold 一句；实体闸门
# 回滚返回原始 messages ⇒ token 不变 ⇒ 下一 turn 必然再触发（确定性热环，非概率）。
# 三处历史冷却全部不可达（死代码 / 零调用者 / 时钟域错 / 只在 LLM 抛异常时武装），
# 且 api_server 每 run 新建 compressor ⇒ 冷却必须落盘才跨 run 存活。
# 见 agent/compress_cooldown.py 与 notes/2026-09-14-T18-压缩热环根因定案.md。
_CC_MODULE = None


def _compress_cooldown():
    """惰性导入冷却模块（导入失败 ⇒ None，调用方一律 fail-open）。"""
    global _CC_MODULE
    if _CC_MODULE is None:
        try:
            from . import compress_cooldown as _m
        except ImportError:  # pragma: no cover - 独立导入时
            try:
                import compress_cooldown as _m  # type: ignore
            except Exception:
                return None
        _CC_MODULE = _m
    return _CC_MODULE


def _run_tag() -> str:
    """当前 run 的 trace_id（取不到则 '-'）。仅用于日志归属（T21）。"""
    try:
        from .run_context import current_run
        _r = current_run() or {}
        _t = _r.get("trace_id") or _r.get("run_id")
        if _t:
            return str(_t)
    except Exception:
        pass
    return os.environ.get("MIMIR_RUN_ID") or "-"


# ── T21（2026-09-14）：[COMPRESS] 行补 pid= / run= ──────────────────────
# 病：1,631 条 [COMPRESS] 行**无任何归属字段** ⇒ 多进程/多 run 交错时无法定位。
# 修法：用 logging.Filter 一处接线，覆盖本模块**全部现有与未来**的 [COMPRESS] 行。
class _CompressAttributionFilter(logging.Filter):
    """给 [COMPRESS] 行**追加** pid=/run=（已带则不重复注入）。

    两条硬契约（D1/D2 修复，2026-09-14 实测后改写）：
    · **前缀契约不可动**：`[COMPRESS] trigger|skip|result|abort` 是既有消费者解析的
      锚点（scripts/b9_weekly_metrics.py · tests/agent/test_compress_unified_caliber.py
      · tests/agent/test_compress_threshold_source.py · tests/scripts/test_b9_weekly_metrics.py）
      ⇒ 注入必须**追加到行尾**，不能插在 `[COMPRESS] ` 之后。
    · **不得用 record.getMessage() 回填 record.msg**：getMessage() 已代入实参，把它拼回
      **原始 args** 会让格式符数 != 实参数（实测
      `TypeError: not all arguments converted during string formatting`），
      logging 走 handleError ⇒ **整行丢弃**。想修可观测性，结果把可观测性抹掉。
    · args 三形态都要能追加；未知形态**不注入**（fail-open，绝不改 args 类型）。
    """

    @staticmethod
    def _inject(base: str, suffix: str) -> str:
        r"""把归属字段插到**锚点行**行尾。

        单行 msg（生产全部现有形态）⇒ 与旧的「拼在整条 msg 末尾」**逐字节等价**。
        跨行 msg（msg 内含 ``\n``）⇒ 插到**第一个 ``\n`` 之前**（批1 护栏 1 实测洞）：
        旧写法把字段拼在整条 msg 末尾 ⇒ 字段落到**第 2 物理行**，而
        ``grep '^\[COMPRESS\]'`` 只拿到第 1 行 ⇒ **归属字段对消费者不可见**
        （实测：含 ``[COMPRESS]`` 的行内 ``pid=`` 命中 0/1）。
        正文一个字节不动（只在**行尾**追加，不插到 ``[COMPRESS] `` 之后）。
        """
        cut = base.find("\n")
        if cut < 0:
            return base + suffix
        return base[:cut] + suffix + base[cut:]

    def filter(self, record):  # noqa: A003 - logging API
        try:
            if not isinstance(record.msg, str) or not record.msg.startswith("[COMPRESS]"):
                return True
            if "pid=" in record.getMessage():       # 已带 ⇒ 不重复注入
                return True
            _pid, _run = os.getpid(), _run_tag()
            _args = record.args
            if _args is None:
                record.msg = self._inject(record.msg, " pid=%d run=%s")
                record.args = (_pid, _run)
            elif isinstance(_args, tuple):
                record.msg = self._inject(record.msg, " pid=%d run=%s")
                record.args = tuple(_args) + (_pid, _run)
            elif isinstance(_args, dict):
                record.msg = self._inject(
                    record.msg, " pid=%(__mimir_pid)d run=%(__mimir_run)s"
                )
                record.args = dict(_args, __mimir_pid=_pid, __mimir_run=_run)
        except Exception:
            return True  # 日志永不因归属注入失败而丢
        return True


# ── 覆盖面声明（D10 · 批1护栏4 · 2026-09-15 实测 · **2026-09-16 B5 扩面**）──
# 机制（Python logging 官方语义，**未变**）：logger 的 ``filters`` 只作用于
# **直接在该 logger 上发起的记录**；子孙/兄弟记录 propagate 到祖先时只经过祖先的
# **handlers**，不经过祖先 logger 的 **filters**。
# ⇒ 恒成立的结论：**logger 级 filter 的覆盖面 = 被显式挂过的 logger 集合**，
#   它**永远不会自动覆盖别人**。
# ⇒ 于是「覆盖几个」是个**选择**，不是个发现：批1 当时只挂了 1 个 ——
#   ``agent.context_compressor``。故 ``[COMPRESS]`` 归属字段在两类行上缺失：
#     · **兄弟 logger**：``agent.compress_cooldown``（armed / cleared 各 1 条）
#     · **异树 logger**：``gateway.router.agent_route_mixin``（``layer=gateway`` 8 条）
# ⇒ D10 的正解（B5 采纳）：**按名字把 filter 显式挂到这三处 logger**。
#   理由：集合可枚举、可单测、**不动进程级 logging 拓扑**（最小可验证改动）。
#   备选 ``install_attribution_on_ancestor_handler()``（挂祖先 handler ⇒ 自动覆盖
#   全部子孙）**仍保持 opt-in 未接线**：它改的是进程级拓扑（还会让 root 的
#   lastResort 对该子树失效），属**全局面**改动，须四方裁定后再由接线方显式调用。
# ⚠️ 覆盖口径只能写「**本表所列 logger**」，**禁写「全覆盖」** ——
#   将来新增的任何 logger 都不在表内（这是本表存在的意义，不是遗漏）。
ATTRIBUTION_COVERED_LOGGERS = (
    "agent.context_compressor",              # 本模块（批1 唯一）
    "agent.compress_cooldown",               # 兄弟 logger（B5 补 · D10 漏网 A）
    "gateway.router.agent_route_mixin",      # 异树 logger · layer=gateway（B5 补 · 漏网 B）
)


def install_compress_attribution_on(logger_name: str) -> bool:
    """把归属 filter 挂到**指定 logger** 上（幂等）。返回「本次是否新挂」。

    为什么需要它：见上方覆盖面声明 —— logger 级 filter **只覆盖直发该 logger 的记录**，
    故每一个漏网 logger 都必须**显式挂**，不能指望 propagate 帮忙。

    **不抛异常**：归属是观测性设施，绝不允许因它阻断 import 或请求链路。
    """
    try:
        _lg = logging.getLogger(logger_name)
        if any(isinstance(f, _CompressAttributionFilter) for f in _lg.filters):
            return False
        _lg.addFilter(_CompressAttributionFilter())
        return True
    except Exception:
        return False


def _install_compress_attribution() -> None:
    """把 filter 挂到 ATTRIBUTION_COVERED_LOGGERS 列出的**每一个** logger。

    注意：这里**不 import** 那两个模块，只按**名字**取 logger 对象。
    理由：① `logging.getLogger(name)` 是全局单例，先取后建拿到的是同一个对象；
         ② 对 `agent.compress_cooldown` 而言，模块级 import 会与 `_compress_cooldown()`
            的惰性导入形成环。按名字取 = 零耦合，且**不依赖导入顺序**。
    """
    for _name in ATTRIBUTION_COVERED_LOGGERS:
        install_compress_attribution_on(_name)


class _AttributionCarrierHandler(logging.Handler):
    """**只当 filter 载体**的 handler：不输出任何日志，只让 filter 对经它传播的记录生效。

    为什么需要它：见上方覆盖面声明——祖先 logger 的 filters 看不到子孙记录，
    只有**祖先的 handler** 能看到。挂一个 emit 为空的 handler，即把 filter
    的作用面从「1 个 logger」扩到「该祖先的全部子孙 logger」。
    """

    def emit(self, record):  # noqa: A003 - logging API
        return None


def install_attribution_on_ancestor_handler(logger_name: str = "agent") -> logging.Handler:
    """D10 正解（**opt-in，默认不调用**）：把 filter 挂到祖先 handler ⇒ 覆盖全部子孙。

    · 幂等：该 logger 上已有载体 handler ⇒ 直接返回它，不重复挂。
    · 不进生产接线：它改变进程级 logging 拓扑（还会让 root 的 lastResort 对该子树失效），
      属「全局面」改动，须四方裁定后由接线方显式调用。
    · 已验证（受控差分）：挂上后 ``agent.compress_cooldown`` 与
      ``agent.context_compressor`` 两条记录**都**被注入，且不重复注入。
    """
    lg = logging.getLogger(logger_name)
    for h in list(lg.handlers):
        if isinstance(h, _AttributionCarrierHandler):
            return h
    h = _AttributionCarrierHandler(level=logging.NOTSET)
    h.addFilter(_CompressAttributionFilter())
    lg.addHandler(h)
    return h


try:
    _install_compress_attribution()
except Exception:  # pragma: no cover
    pass


LEGACY_PREFIX = "[CONTEXT SUMMARY]:"

_MIN_SUMMARY_TOKENS = 500
_SUMMARY_RATIO = 0.20
# Minimum context length guard
_MINIMUM_CONTEXT_LENGTH = 2000
_SUMMARY_TOKENS_CEILING = 8000
_CHARS_PER_TOKEN = 4
_SUMMARY_FAILURE_COOLDOWN = 600
_PRUNED_TOOL_PLACEHOLDER = "[Old tool output cleared to save context space]"
_PRUNED_TOOL_MIN_CHARS = 200


# ── 压缩阈值单一真源（2026-09-11 档2-②）─────────────────────────────────────
# 此前阈值解析散落三处、互相架空且无日志说明谁赢：
#   1. core_loop:    MIMIR_COMPRESS_THRESHOLD(percent) > tuned > 默认 0.50
#   2. __init__:     MIMIR_COMPRESS_THRESHOLD_TOKENS(absolute) 直接覆盖 threshold_tokens
#   3. update_model: 用 percent 重算 threshold_tokens → 静默丢弃 absolute 覆盖（clobber）
# 后果：改 tuned 可能完全无效（被 env 架空），不同代码路径还会得到不同阈值
# （drift）。现统一由下面两个函数解析，日志一律带 source= 便于取证。
_COMPRESS_THRESHOLD_PERCENT_ENV = "MIMIR_COMPRESS_THRESHOLD"
# B9（2026-09-13）：阈值按「有效窗口」定——一等公民上限。**仅当** tuned 键
# compressor.effective_window_tokens 显式置位时生效：
#   threshold_tokens = min(configured, cap, floor(0.75 x context_length))
# 键缺失 ⇒ 该上限不生效（严格向后兼容，见 resolve_effective_window_cap）。
_EFFECTIVE_WINDOW_TOKENS_KEY = "compressor.effective_window_tokens"
_WINDOW_RATIO_CEILING = 0.75
_COMPRESS_THRESHOLD_TOKENS_ENV = "MIMIR_COMPRESS_THRESHOLD_TOKENS"
_DEFAULT_THRESHOLD_PERCENT = 0.50


def _strip_inline_comment(raw: str):
    """Return ``(value_without_inline_comment, was_comment_stripped)``.

    Why (2026-09-13 D-plan step 3): systemd's ``EnvironmentFile=`` parser does
    **not** strip a trailing ``# comment`` (python-dotenv does) and writes it into
    the value verbatim, so ``KEY=350000  # was 80000`` reaches the process as
    ``'350000  # was 80000'`` (len=19). A bare ``int(raw)`` then raises
    ``ValueError`` and the threshold **silently falls back to percent** - a
    configuration bug disguised as normal operation (real case: ``.env`` L35).
    Strip defensively.
    """
    if "#" not in raw:
        return raw, False
    return raw.split("#", 1)[0].strip(), True


def resolve_effective_window_cap() -> Optional[int]:
    """B9：有效窗口上限真源——tuned 键 ``compressor.effective_window_tokens``。

    **只有显式置位（tuned overrides 里存在该键）才返回上限**；键缺失 / 非法 /
    不可读 ⇒ 返回 ``None`` ⇒ 上限不生效（严格向后兼容：不改变现有行为）。

    刻意不走 ``get_tuned_int`` 的 registry default：那会让任何 registry 默认值
    把小窗口模型静默夹紧——即「配置没动、阈值却变了」的同一类暗路。
    """
    try:
        from agent.tuned_thresholds import load_overrides

        overrides = load_overrides()
    except Exception:
        return None
    if not isinstance(overrides, dict) or _EFFECTIVE_WINDOW_TOKENS_KEY not in overrides:
        return None
    try:
        cap = int(overrides[_EFFECTIVE_WINDOW_TOKENS_KEY])
    except (TypeError, ValueError):
        return None
    return cap if cap > 0 else None


def apply_effective_window_cap(
    configured: int, source: str, context_length: int
) -> Tuple[int, str]:
    """B9：把阈值按「有效窗口」封顶（只降不升）。

    ``threshold = min(configured, cap, floor(0.75 x context_length))``

    * ``cap`` = tuned 键 :data:`_EFFECTIVE_WINDOW_TOKENS_KEY`；**键缺失 ⇒ 原样返回**
      （见 :func:`resolve_effective_window_cap`）。
    * ``source`` **只追加不重写**（既有断言匹配前缀 ``env:MIMIR_...`` 仍成立）：
      取胜项以 ``+cap:effective_window_tokens`` / ``+cap:window_ratio`` 追加。
    * 上限**生效时**打 INFO ``[COMPRESS-CAP]``，含 context_length / configured /
      cap / window_ratio / 最终值 / 取胜原因 —— 「哪一项取胜」可取证。
    """
    ctx = int(context_length or 0)
    base = int(configured)
    if ctx <= 0:
        return base, source
    cap = resolve_effective_window_cap()
    if cap is None:
        return base, source  # 键缺失：零行为变化
    window_ratio = int(_WINDOW_RATIO_CEILING * ctx)
    # 元组顺序即优先级：configured > cap > window_ratio（并列时前者胜）。
    candidates = (
        (base, None),
        (cap, "+cap:effective_window_tokens"),
        (window_ratio, "+cap:window_ratio"),
    )
    winner_value, winner_suffix = min(candidates, key=lambda item: item[0])
    if winner_suffix is None or winner_value >= base:
        return base, source  # configured 本就更小 → 上限未生效，source 不动
    logger.info(
        "[COMPRESS-CAP] context_length=%s configured=%s cap=%s window_ratio=%s "
        "final=%s winner=%s reason=%s",
        ctx, base, cap, window_ratio, winner_value, winner_suffix,
        f"{winner_value} < configured({base})",
    )
    return winner_value, f"{source} {winner_suffix}"


def resolve_threshold_percent(env=None) -> Tuple[float, str]:
    """阈值百分比真源：env MIMIR_COMPRESS_THRESHOLD > tuned > 默认 0.50。

    Returns ``(percent, source)``；source 形如 ``env:MIMIR_COMPRESS_THRESHOLD`` /
    ``tuned:compressor.threshold_percent`` / ``default:0.50``。
    """
    _env = os.environ if env is None else env
    percent, source = _DEFAULT_THRESHOLD_PERCENT, "default:0.50"
    try:
        from agent.tuned_thresholds import get_tuned_float

        percent = float(get_tuned_float("compressor.threshold_percent"))
        source = "tuned:compressor.threshold_percent"
    except Exception:
        pass
    raw = (_env.get(_COMPRESS_THRESHOLD_PERCENT_ENV) or "").strip()
    if raw:
        raw, _stripped = _strip_inline_comment(raw)
        if _stripped:
            logger.warning(
                "%s carried an inline comment - stripped to %r (systemd "
                "EnvironmentFile does not strip it; python-dotenv does)",
                _COMPRESS_THRESHOLD_PERCENT_ENV, raw,
            )
        try:
            percent = float(raw)
            source = f"env:{_COMPRESS_THRESHOLD_PERCENT_ENV}"
        except (TypeError, ValueError):
            logger.warning(
                "Invalid %s=%r — keeping %s (%s)",
                _COMPRESS_THRESHOLD_PERCENT_ENV, raw, percent, source,
            )
    return percent, source


def resolve_threshold_tokens(
    context_length: int,
    threshold_percent: Optional[float] = None,
    env=None,
) -> Tuple[int, str]:
    """绝对阈值真源：env MIMIR_COMPRESS_THRESHOLD_TOKENS > percent x context_length。

    绝对 token 数优先（运维一键钉死），否则按百分比解析——百分比本身也走
    :func:`resolve_threshold_percent`，全链路单一实现。非法 env 值降级不抛。

    B9（2026-09-13）：解析出 ``configured`` 之后再过一层**有效窗口上限**
    （:func:`apply_effective_window_cap`）——``min(configured, cap, 0.75 x ctx)``；
    tuned 键 compressor.effective_window_tokens 缺失时该层完全不生效。

    Returns ``(threshold_tokens, source)``；上限取胜时 source 以
    ``+cap:effective_window_tokens`` / ``+cap:window_ratio`` **追加**（不改前缀）。
    """
    _env = os.environ if env is None else env
    ctx = int(context_length or 0)
    raw = (_env.get(_COMPRESS_THRESHOLD_TOKENS_ENV) or "").strip()
    if raw:
        raw, _stripped = _strip_inline_comment(raw)
        if _stripped:
            logger.warning(
                "%s carried an inline comment - stripped to %r (systemd "
                "EnvironmentFile does not strip it; python-dotenv does)",
                _COMPRESS_THRESHOLD_TOKENS_ENV, raw,
            )
        try:
            absolute = int(raw)
            if absolute > 0:
                # B9：env 绝对覆盖只是「configured」，仍须过有效窗口上限。
                return apply_effective_window_cap(
                    absolute, f"env:{_COMPRESS_THRESHOLD_TOKENS_ENV}", ctx
                )
            logger.warning(
                "Invalid %s=%r (must be >0) — falling back to percent",
                _COMPRESS_THRESHOLD_TOKENS_ENV, raw,
            )
        except (TypeError, ValueError):
            logger.warning(
                "Invalid %s=%r (not an int) — falling back to percent",
                _COMPRESS_THRESHOLD_TOKENS_ENV, raw,
            )
    if threshold_percent is None:
        percent, source = resolve_threshold_percent(env=_env)
    else:
        percent, source = float(threshold_percent), "explicit"
    return apply_effective_window_cap(int(ctx * percent), f"{source} x {ctx}", ctx)


@dataclass
class CompressionResult:
    original_count: int = 0
    compressed_count: int = 0
    original_tokens: int = 0
    compressed_tokens: int = 0
    summary: str = ""
    pruned_tool_count: int = 0
    compression_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    summary_mode: str = "none"


class ContextCompressorV2:
    """
    上下文压缩器 V2.3
    
    Standalone compressor with plugin support via duck-typing
    """
    
    @property
    def name(self) -> str:
        return "compressor"
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        context_length: int = 1048576,  # DeepSeek V4 Pro 1M; overridden at init
        threshold_percent: float = 0.50,  # Tuned for DeepSeek context window
        protect_first_n: int = 3,
        protect_last_n: int = 6,
        tail_token_budget: int = None,
        summary_target_ratio: float = 0.20,
        preflight_relax_ratio: float = 0.80,
        summary_failure_cooldown_s: int = 600,
        summary_model: str = None,
        base_url: str = "https://api.deepseek.com",
        api_key: str = "",
        quiet_mode: bool = False,
    ):
        # Initialize token state
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.threshold_percent = threshold_percent
        self.protect_first_n = protect_first_n
        self.protect_last_n = protect_last_n
        self.summary_target_ratio = summary_target_ratio
        self.preflight_relax_ratio = float(preflight_relax_ratio)
        self.summary_failure_cooldown_s = int(summary_failure_cooldown_s)
        self.summary_model = summary_model or model
        self._last_summary_error = ""
        self.quiet_mode = quiet_mode
        
        self.context_length = context_length
        self.threshold_percent = threshold_percent
        self.threshold_tokens = int(self.context_length * threshold_percent)
        
        # Dynamic tail token budget
        # tail_budget = threshold_tokens * summary_target_ratio
        if tail_token_budget is None:
            self.tail_token_budget = clamp_compressor_key(
                "tail_token_budget", int(self.threshold_tokens * summary_target_ratio)
            )
        else:
            self.tail_token_budget = clamp_compressor_key(
                "tail_token_budget", int(tail_token_budget)
            )
        # 修复（2026-08-05，核心体检-2 OpenClaw发现）：cooldown/anti-thrashing状态
        self._last_compress_time = 0.0        # cooldown：上次压缩时间戳（T16 实测：零调用者）
        # T16（2026-09-14）：盘上冷却闸的"已打印"水位 —— 只在状态变化时打 skip 行
        self._cooldown_logged_until = None
        self._cooldown_attempt_id = None
        # T20（2026-09-14）：摘要调用自身的 token 用量（此前压缩代价无任何 token 埋点）
        self._last_summary_usage = {}
        self._pre_tokens_for_ledger = None
        # T20-b（2026-09-15 · T2 首算发现）：API **实计**口径的 pre token（分列两栏用）
        self._pre_tokens_actual_for_ledger = None
        # ── T20-c（2026-09-16）post 实计口径：「挂账—结算」两段式 ─────────────
        # 病：台账 ``prompt_tokens_after`` = ``result.compressed_tokens``（**内部估算**），
        #     不是实计 ⇒ 净收益只能两端估算相减，**符号可能整错**（T2/T3/T4 因此阻塞）。
        # 修法：applied 时**挂账**（记下 pre 实计 + 摘要自身开销），等**下一次真实调用**
        #     回来，用那条 ``usage.prompt_tokens``（API 实计）**结算**。
        # 为何挂在实例上而不新建模块：applied 与 usage 回灌是**同一条调用链上的同一个
        #     compressor 实例**（callers_mixin._compressor_sync_usage_from_llm 已持有
        #     ``self.compressor``）⇒ 无需跨模块共享，也避开循环导入。
        # 为何「下一次调用」就是 post：压缩发生在调用**之前**，故紧接着那次调用正是
        #     「压缩后载荷」的第一次真实计费 —— 这是定义，不是近似。
        self._pending_post_measure = None
        self._last_savings: list[float] = []   # anti-thrashing：最近压缩节省比例
        self._compress_failures = 0            # 连续失败计数（触发cooldown）
        
        self.max_summary_tokens = min(
            int(self.context_length * 0.05), 
            _SUMMARY_TOKENS_CEILING
        )
        
        # 内部状态
        self._previous_summary: Optional[str] = None
        self._summary_failure_cooldown_until: float = 0.0
        # compression_count tracks cumulative compressions per session
        # P0-2 修复（2026-08-12）：此前 __init__ 缺失该初始化，首次真实压缩到 L641 时
        # `self.compression_count += 1` 抛 AttributeError——被 8/2 coroutine bug 掩盖，
        # await 链修复后暴露（tests/agent/test_context_compressor_await.py 捕获）。
        self.compression_count = 0
        
        if not quiet_mode:
            logger.info(
                f"V2.3 initialized: context_length={self.context_length}, "
                f"threshold={self.threshold_tokens}, "
                f"tail={self.tail_token_budget} (dynamic)"
            )
    
    def ingest_usage(self, usage: Dict[str, Any]) -> None:
        """Ingest token usage from LLM API response."""
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)
        self.last_total_tokens = usage.get("total_tokens", 0)
    
    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
        api_mode: str = "",
    ) -> None:
        """Update model configuration and recalculate thresholds."""
        self.model = model
        self.base_url = base_url or self.base_url
        self.api_key = api_key or self.api_key
        self.provider = provider
        self.api_mode = api_mode
        self.context_length = context_length
        self.threshold_tokens = max(
            int(context_length * self.threshold_percent),
            _MINIMUM_CONTEXT_LENGTH,
        )
        self.max_summary_tokens = min(
            int(context_length * 0.05),
            _SUMMARY_TOKENS_CEILING,
        )
    
    def should_compress(self, prompt_tokens: int = None) -> bool:
        """Check if compression is needed (token-based)."""
        tokens = prompt_tokens if prompt_tokens is not None else 0
        return tokens >= self.threshold_tokens

    def should_compress_info(self, prompt_tokens: Optional[int] = None, now: Optional[float] = None) -> Tuple[bool, str]:
        """修复（2026-08-05，核心体检-2 OpenClaw发现）：返回(bool, reason) tuple——对齐Hermes。

        原should_compress只返回bool，无reason（silent overflow）：
        - "cooldown:<s>"：summary LLM刚失败/刚压缩过，冷却中
        - "ineffective"：anti-thrashing——最近2次压缩节省<10%，跳过
        - "task_state:WRITING"：任务正在写盘，延迟压缩（task_state接入——四方共识）
        - "threshold"：正常触发（tokens超阈值）
        - "ok"：不需要压缩
        """
        now = now or time.monotonic()
        tokens = prompt_tokens if prompt_tokens is not None else 0

        # cooldown：压缩后冷却期（避免连续压缩）
        if self._last_compress_time > 0:
            elapsed = now - self._last_compress_time
            if elapsed < self.summary_failure_cooldown_s:
                return False, f"cooldown:{int(self.summary_failure_cooldown_s - elapsed)}s"
        # 连续失败也冷却
        if self._compress_failures >= 2:
            return False, f"cooldown:failures={self._compress_failures}"

        if tokens < self.threshold_tokens:
            return False, "ok"

        # task_state接入（四方共识，2026-08-05）：任务正在写盘时延迟压缩（防摘要丢写盘变量）
        if getattr(self, '_task_state', None) == "writing":
            return False, "task_state:WRITING"

        # anti-thrashing：最近2次压缩节省<10% → 无效压缩，跳过
        if len(self._last_savings) >= 2 and all(s < 0.10 for s in self._last_savings[-2:]):
            return False, "ineffective"

        return True, "threshold"

    def has_content_to_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """Quick check: is there anything in messages that can be compacted?

        Returns False when messages are entirely within the protected zone
        (head + tail), so callers can skip the LLM compression call entirely.
        Preflight guard — returns False if messages are within protected zone.
        """
        if not messages:
            return False
        protected = self.protect_first_n + self.protect_last_n
        return len(messages) > protected

    def should_compress_preflight(self, messages: List[Dict[str, Any]]) -> bool:
        """API调用前的快速预检（廉价估算，无真实token计数）。

        先检查是否有内容可压缩（has_content_to_compress），
        再估算 token 数是否可能接近阈值。
        """
        if not self.has_content_to_compress(messages):
            return False
        estimated = self._estimate_tokens(messages)
        return estimated >= self.threshold_tokens * self.preflight_relax_ratio
    
    def needs_compression(self, messages: List[Dict] = None) -> bool:
        """Check if compression is needed (uses last_prompt_tokens).

        T16（2026-09-14）：加**盘上持久化**冷却闸（agent/compress_cooldown.py）。
        原因：实体闸门回滚返回原始 messages ⇒ token 不变 ⇒ 下一 turn 必然再触发；
        且每 run 新建 compressor ⇒ 实例内冷却跨 run 失效。实测最长两串 ≈84 次真
        LLM 摘要、1209s **全部丢弃**。冷却窗口内直接返回 False，**不发起**摘要调用。
        env 回滚：MIMIR_COMPRESS_COOLDOWN=0。
        """
        tokens = getattr(self, 'last_prompt_tokens', 0) or 0
        if tokens < self.threshold_tokens:
            return False
        _cc = _compress_cooldown()
        if _cc is not None:
            try:
                _cooling, _st = _cc.is_cooling()
            except Exception as _e:  # 冷却判定失败绝不阻断主流程
                _cooling, _st = False, {}
                logger.warning("[COMPRESS] cooldown check failed (%s) — fail-open", _e)
            if _cooling:
                _until = _st.get("cooldown_until_epoch")
                if getattr(self, "_cooldown_logged_until", None) != _until:
                    self._cooldown_logged_until = _until
                    logger.warning(
                        "[COMPRESS] skip reason=cooldown tokens=%s threshold=%s "
                        "failures=%s remaining_s=%s (热环已被挡住)",
                        tokens, self.threshold_tokens,
                        _st.get("consecutive_failures"), _st.get("remaining_s"),
                    )
                return False
        return True
    
    def _estimate_tokens(self, messages: List[Dict]) -> int:
        total = 0
        for msg in messages:
            # P0-4: 跳过 C1 注入的消息（避免压缩机误判上下文膨胀）
            if msg.get("_c1_injected"):
                continue
            content = msg.get("content", "") or ""
            total += len(content) // _CHARS_PER_TOKEN + 20
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    args = tc.get("function", {}).get("arguments", "") or ""
                    total += len(args) // _CHARS_PER_TOKEN
        return total
    
    def _prune_old_tool_results(
        self, 
        messages: List[Dict], 
        protect_tail_count: int = 10,
        protect_tail_tokens: int = None
    ) -> Tuple[List[Dict], int]:
        if not messages:
            return messages, 0
        
        result = [m.copy() for m in messages]
        pruned = 0
        
        if protect_tail_tokens and protect_tail_tokens > 0:
            accumulated = 0
            boundary = len(result)
            min_protect = min(protect_tail_count, len(result) - 1)
            
            for i in range(len(result) - 1, -1, -1):
                msg = result[i]
                content = msg.get("content") or ""
                msg_tokens = len(content) // _CHARS_PER_TOKEN + 10
                
                for tc in msg.get("tool_calls") or []:
                    args = tc.get("function", {}).get("arguments", "") or ""
                    msg_tokens += len(args) // _CHARS_PER_TOKEN
                
                if accumulated + msg_tokens > protect_tail_tokens and (len(result) - i) >= min_protect:
                    boundary = i
                    break
                accumulated += msg_tokens
                boundary = i
            
            prune_boundary = max(boundary, len(result) - min_protect)
        else:
            prune_boundary = len(result) - protect_tail_count
        
        for i in range(prune_boundary):
            msg = result[i]
            if msg.get("role") != "tool":
                continue
            content = msg.get("content") or ""
            if content and content != _PRUNED_TOOL_PLACEHOLDER and len(content) > _PRUNED_TOOL_MIN_CHARS:
                result[i] = {**msg, "content": _PRUNED_TOOL_PLACEHOLDER}
                pruned += 1
        
        return result, pruned
    
    def _compute_summary_budget(self, turns: List[Dict]) -> int:
        content_tokens = self._estimate_tokens(turns)
        budget = int(content_tokens * _SUMMARY_RATIO)
        return max(_MIN_SUMMARY_TOKENS, min(budget, self.max_summary_tokens))
    
    def _serialize_for_summary(self, turns: List[Dict]) -> str:
        parts = []
        _CONTENT_MAX = 6000
        _CONTENT_HEAD = 4000
        _CONTENT_TAIL = 1500
        
        for msg in turns:
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            
            if role == "tool":
                tool_id = msg.get("tool_call_id", "")
                if len(content) > _CONTENT_MAX:
                    content = content[:_CONTENT_HEAD] + "\n...[truncated]...\n" + content[-_CONTENT_TAIL:]
                parts.append(f"[TOOL RESULT {tool_id}]: {content}")
                continue
            
            if role == "assistant":
                if len(content) > _CONTENT_MAX:
                    content = content[:_CONTENT_HEAD] + "\n...[truncated]...\n" + content[-_CONTENT_TAIL:]
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    tc_parts = []
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        name = fn.get("name", "?")
                        args = fn.get("arguments", "") or ""
                        if len(args) > 1500:
                            args = args[:1200] + "..."
                        tc_parts.append(f"  {name}({args})")
                    content += "\n[Tool calls:\n" + "\n".join(tc_parts) + "\n]"
                parts.append(f"[ASSISTANT]: {content}")
                continue
            
            if len(content) > _CONTENT_MAX:
                content = content[:_CONTENT_HEAD] + "\n...[truncated]...\n" + content[-_CONTENT_TAIL:]
            parts.append(f"[{role.upper()}]: {content}")
        
        return "\n\n".join(parts)
    
    def _generate_template_summary(self, turns: List[Dict], previous: str = None) -> str:
        user_count = sum(1 for m in turns if m.get("role") == "user")
        assistant_count = sum(1 for m in turns if m.get("role") == "assistant")
        tool_count = sum(1 for m in turns if m.get("role") == "tool")
        
        topics = []
        tools = []
        for msg in turns:
            if msg.get("role") == "tool":
                content = msg.get("content", "")[:100]
                tools.append(content)
            elif msg.get("role") == "user":
                content = msg.get("content", "")
                if len(content) > 50:
                    topics.append(content[:80])
        
        lines = [
            f"## 对话摘要",
            f"共{len(turns)}条消息（用户:{user_count} 助手:{assistant_count} 工具:{tool_count}）",
            "",
            f"## 涉及内容",
        ]
        
        if topics:
            lines.append(f"- 首条用户请求: {topics[0]}...")
        if tools:
            lines.append(f"- 工具输出: {tools[0]}...")
        
        if previous:
            lines.insert(2, f"\n## 前序摘要\n{previous}\n")
        
        return "\n".join(lines)
    
    def _collect_entities(self, messages) -> List[str]:
        """RS14-C1：按 ENTITY_PATTERN 提取关键实体（去重排序，不截断——闸门按全量判定）。"""
        text = (
            json.dumps(messages, ensure_ascii=False)
            if isinstance(messages, list) else str(messages)
        )
        return sorted({m.group(1) for m in re.finditer(ENTITY_PATTERN, text)})

    def _entity_index_block(self, messages) -> str:
        """RS14-C1：生成确定性实体索引块（无实体→空串；超上限→截断并告警）。

        为什么机器生成而不依赖模型：模型摘要是有损的，`## Relevant Files` 之类
        章节是否列出文件名不可保证（实测 LLM 摘要保留率 0.21 < 模板 0.53）。
        索引块让「被压缩掉的中间段实体」在 post 里确定性地存在。
        """
        entities = self._collect_entities(messages)
        # RS14-D1：索引统计初值（entity_total = 分母口径可见化）
        self._last_index_stats = {
            "index_items": 0, "index_chars": 0,
            "index_capped": False, "entity_total": len(entities),
        }
        if not entities:
            return ""
        kept, used = [], 0
        for _e in entities:
            if len(kept) >= _ENTITY_INDEX_MAX_ITEMS:
                break
            if used + len(_e) + 3 > _ENTITY_INDEX_MAX_CHARS:
                break
            kept.append(_e)
            used += len(_e) + 3
        self._last_index_stats = {
            "index_items": len(kept), "index_chars": used,
            "index_capped": len(kept) < len(entities), "entity_total": len(entities),
        }
        if len(kept) < len(entities):
            logger.warning(
                "[COMPRESS] entity index truncated: carried=%d total=%d "
                "(caps items=%d chars=%d) — retention gate may fail",
                len(kept), len(entities), _ENTITY_INDEX_MAX_ITEMS, _ENTITY_INDEX_MAX_CHARS,
            )
        return "\n\n" + ENTITY_INDEX_HEADING + "\n" + "\n".join(f"- {e}" for e in kept) + "\n"

    async def _generate_summary(self, turns_to_summarize: List[Dict]) -> Tuple[Optional[str], str]:
        now = time.monotonic()
        # RS14-D1：本次尝试的仪器化初值（必须放在 cooldown 早退之前，否则早退时
        # 记录会带上上一轮的残留耗时 —— 又一处"读数不可信"）
        self._last_summary_attempts = 0
        self._last_summary_elapsed_s = None
        self._last_summary_requested_max_tokens = None
        self._last_summary_budget_raw = None
        if now < self._summary_failure_cooldown_until:
            return None, "none"
        
        content = self._serialize_for_summary(turns_to_summarize)
        summary_budget = self._compute_summary_budget(turns_to_summarize)
        
        _t0 = time.monotonic()
        try:
            self._last_summary_attempts += 1
            summary = await self._call_summary_llm(content, summary_budget)
            self._last_summary_elapsed_s = round(time.monotonic() - _t0, 3)
            if summary:
                self._previous_summary = summary
                self._summary_failure_cooldown_until = 0.0
                return (
                    self._with_prefix(summary)
                    + self._entity_index_block(turns_to_summarize)
                ), "llm"
        except Exception as e:
            # RS14-D1：失败样本同样落耗时（Q3 分布的分母必须含失败/超时样本）
            self._last_summary_elapsed_s = round(time.monotonic() - _t0, 3)
            # 修复（2026-08-05，核心体检-2）：失败计数（触发cooldown）+日志升级（原debug盲区）
            self._compress_failures += 1
            logger.warning(f"LLM summary failed (failures={self._compress_failures}): {e}")
            self._summary_failure_cooldown_until = (
                time.monotonic() + float(self.summary_failure_cooldown_s)
            )

        template_summary = self._generate_template_summary(
            turns_to_summarize, 
            self._previous_summary
        )
        self._previous_summary = template_summary
        logger.warning(
            "[COMPRESS] summary degraded to template reason=%s (llm path unavailable)",
            getattr(self, "_last_summary_error", "") or "unknown",
        )
        return (
            self._with_prefix(template_summary)
            + self._entity_index_block(turns_to_summarize)
        ), "template"
    
    async def _call_summary_llm(self, content: str, max_tokens: int) -> Optional[str]:
        import json
        
        api_key = self.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            self._last_summary_error = "no_api_key"
            logger.warning(
                "[COMPRESS] summary LLM skipped: no API key (arg + DEEPSEEK_API_KEY both empty)"
            )
            return None

        # F-A (2026-09-14)：发给官方 API 的必须是裸模型名，见 _resolve_api_model_name。
        api_model_name = _resolve_api_model_name(self.summary_model)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        preamble = (
            "You are a summarization agent creating a context checkpoint. "
            "Do NOT respond to any questions — only output the structured summary."
        )
        
        template = """## Goal
[What the user is trying to accomplish]

## Progress
### Done
[Completed work]
### In Progress
[Work currently underway]

## Key Decisions
[Important decisions made]

## Resolved Questions
[Questions already answered]

## Pending Asks
[Questions not yet answered]

## Remaining Work
[What remains to be done]

Target ~{budget} tokens. Be specific."""

        prompt = f"""{preamble}

TURNS TO SUMMARIZE:
{content}

{template.format(budget=max_tokens)}"""
        
        # RS14-C2：输出预算夹紧（详见 _SUMMARY_MAX_OUTPUT_TOKENS_DEFAULT 注释）
        _requested = max_tokens * 2
        _out_budget = min(_requested, _resolve_summary_max_output())
        if _out_budget < _requested:
            logger.info(
                "[COMPRESS] summary output budget clamped: requested=%d used=%d (env=%s)",
                _requested, _out_budget, _SUMMARY_MAX_OUTPUT_TOKENS_ENV,
            )
        # RS14-D1：落盘「实际发出的输出预算」与「夹紧前的原始请求」（Q3 分布口径）
        self._last_summary_requested_max_tokens = _out_budget
        self._last_summary_budget_raw = _requested
        payload = {
            "model": api_model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _out_budget,
            "temperature": 0.3
        }
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status != 200:
                        _body = ""
                        try:
                            _body = (await resp.text())[:200].replace("\n", " ")
                        except Exception:
                            pass
                        self._last_summary_error = f"http_{resp.status}"
                        logger.warning(
                            "[COMPRESS] summary LLM rejected http=%s model=%s base_url=%s body=%s",
                            resp.status, api_model_name, self.base_url, _body,
                        )
                        return None
                    result = await resp.json()
                    # T20（2026-09-14）：留下摘要调用自身的 usage（此前压缩代价无 token 埋点）
                    try:
                        _u = result.get("usage") or {}
                        self._last_summary_usage = {
                            "prompt_tokens": int(_u.get("prompt_tokens") or 0),
                            "completion_tokens": int(_u.get("completion_tokens") or 0),
                            "total_tokens": int(_u.get("total_tokens") or 0),
                        }
                    except Exception:
                        self._last_summary_usage = {}
                    return result["choices"][0]["message"]["content"]
        except Exception as e:
            self._last_summary_error = f"exc_{type(e).__name__}"
            logger.warning(
                "[COMPRESS] summary LLM call failed (%s): %s", type(e).__name__, e
            )
            return None
    
    def _with_prefix(self, summary: str) -> str:
        text = (summary or "").strip()
        for prefix in (LEGACY_PREFIX, SUMMARY_PREFIX):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break
        return f"{SUMMARY_PREFIX}\n{text}" if text else SUMMARY_PREFIX
    
    def _sanitize_tool_pairs(self, messages: List[Dict]) -> List[Dict]:
        surviving_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    cid = tc.get("id") or ""
                    if cid:
                        surviving_ids.add(cid)
        
        result_ids = set()
        for msg in messages:
            if msg.get("role") == "tool":
                cid = msg.get("tool_call_id")
                if cid:
                    result_ids.add(cid)
        
        orphaned = result_ids - surviving_ids
        if orphaned:
            messages = [m for m in messages if not (m.get("role") == "tool" and m.get("tool_call_id") in orphaned)]
            if not self.quiet_mode:
                logger.info(f"Removed {len(orphaned)} orphaned tool results")
        
        missing = surviving_ids - result_ids
        if missing:
            patched = []
            for msg in messages:
                patched.append(msg)
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls") or []:
                        cid = tc.get("id") or ""
                        if cid in missing:
                            patched.append({
                                "role": "tool",
                                "content": "[Result from earlier conversation]",
                                "tool_call_id": cid,
                            })
            messages = patched
        
        # 改动2（2026-08-25 修复卡·读闸400根因修复）：合成 user 消息插在
        # assistant(tool_calls) 与其 tool 结果之间会破坏 API 消息序列
        # （"assistant message with 'tool_calls' must be followed by tool messages" 400）。
        # 规则：扫描序列，若存在 role=user 的消息位于 assistant(tool_calls) 与对应
        # tool 结果之间 → 移到序列尾部（保证修复后序列合法；语义保留——模型仍可见该指令）。
        _pending_tool_ids = set()
        _moved_users = []
        _clean = []
        for _msg in messages:
            _role = _msg.get("role")
            if _role == "assistant":
                for _tc in _msg.get("tool_calls") or []:
                    _cid = _tc.get("id") or ""
                    if _cid:
                        _pending_tool_ids.add(_cid)
                _clean.append(_msg)
            elif _role == "tool":
                _cid = _msg.get("tool_call_id")
                if _cid in _pending_tool_ids:
                    _pending_tool_ids.discard(_cid)
                _clean.append(_msg)
            elif _role == "user" and _pending_tool_ids:
                # 此 user 消息插在 assistant(tool_calls) 与 tool 结果之间 → 移到尾部
                _moved_users.append(_msg)
            else:
                _clean.append(_msg)
        if _moved_users:
            _clean.extend(_moved_users)
            messages = _clean
            if not self.quiet_mode:
                logger.info(f"Moved {len(_moved_users)} user message(s) inserted between assistant(tool_calls) and tool results to sequence tail (read-gate fix)")
        
        return messages
    
    def _find_tail_cut_by_tokens(self, messages: List[Dict], head_end: int) -> int:
        n = len(messages)
        min_tail = min(3, n - head_end - 1) if n - head_end > 1 else 0
        soft_ceiling = int(self.tail_token_budget * 1.5)
        accumulated = 0
        cut_idx = n
        
        for i in range(n - 1, head_end - 1, -1):
            msg = messages[i]
            content = msg.get("content") or ""
            msg_tokens = len(content) // _CHARS_PER_TOKEN + 10
            
            for tc in msg.get("tool_calls") or []:
                args = tc.get("function", {}).get("arguments", "") or ""
                msg_tokens += len(args) // _CHARS_PER_TOKEN
            
            if accumulated + msg_tokens > soft_ceiling and (n - i) >= min_tail:
                break
            accumulated += msg_tokens
            cut_idx = i
        
        fallback_cut = n - min_tail
        if cut_idx > fallback_cut:
            cut_idx = fallback_cut
        if cut_idx <= head_end:
            cut_idx = max(fallback_cut, head_end + 1)
        
        return max(cut_idx, head_end + 1)
    
    def _align_boundary_forward(self, messages: List[Dict], idx: int) -> int:
        while idx < len(messages) and messages[idx].get("role") == "tool":
            idx += 1
        return idx
    
    def _align_boundary_backward(self, messages: List[Dict], idx: int) -> int:
        """Align backward to non-tool message boundary."""
        while idx > 0 and messages[idx - 1].get("role") == "tool":
            idx -= 1
        return max(idx, 0)
    
    @staticmethod
    def _get_tool_call_id(msg: Dict) -> Optional[str]:
        """Extract tool call ID from a message dict."""
        if msg.get("role") != "tool":
            return None
        # 优先从tool_call_id获取
        tc_id = msg.get("tool_call_id")
        if tc_id:
            return tc_id
        # 兼容其他格式
        tool_calls = msg.get("tool_calls", [])
        if tool_calls and isinstance(tool_calls[0], dict):
            return tool_calls[0].get("id")
        return None
    
    async def compress(
        self, 
        messages: List[Dict], 
        current_tokens: int = None,
        focus_topic: str = None
    ) -> Tuple[List[Dict], CompressionResult]:
        n_messages = len(messages)
        _min_for_compress = self.protect_first_n + 3 + 1
        
        display_tokens = current_tokens or self._estimate_tokens(messages)
        
        # 统一判断：token超过阈值 且 消息数足够
        if display_tokens < self.threshold_tokens or n_messages <= _min_for_compress:
            return messages, CompressionResult(
                original_count=n_messages,
                compressed_count=n_messages,
                original_tokens=display_tokens,
                compressed_tokens=display_tokens,
            )
        
        # Phase 1: 修剪
        messages, pruned_count = self._prune_old_tool_results(
            messages, 
            protect_tail_count=self.protect_first_n,
            protect_tail_tokens=self.tail_token_budget
        )
        
        # Phase 2: 边界
        compress_start = self._align_boundary_forward(messages, self.protect_first_n)
        compress_end = self._find_tail_cut_by_tokens(messages, compress_start)
        
        if compress_start >= compress_end:
            return messages, CompressionResult(
                original_count=n_messages,
                compressed_count=n_messages,
                original_tokens=display_tokens,
                compressed_tokens=display_tokens,
            )
        
        turns_to_summarize = messages[compress_start:compress_end]
        
        # Phase 3: 摘要
        summary, summary_mode = await self._generate_summary(turns_to_summarize)
        
        # Phase 4: 组装
        compressed = []
        
        for i in range(compress_start):
            msg = messages[i].copy()
            if i == 0 and msg.get("role") == "system" and self.compression_count == 0:
                note = "\n\n[Note: Some earlier turns have been compacted.]"
                msg["content"] = (msg.get("content") or "") + note
            compressed.append(msg)
        
        if summary:
            last_head_role = messages[compress_start - 1].get("role") if compress_start > 0 else "user"
            first_tail_role = messages[compress_end].get("role") if compress_end < n_messages else "user"
            
            if last_head_role in ("assistant", "tool"):
                summary_role = "user"
            else:
                summary_role = "assistant"
            
            if summary_role == first_tail_role:
                summary_role = "assistant" if summary_role == "user" else "user"
            
            compressed.append({"role": summary_role, "content": summary})
        else:
            compressed.append({
                "role": "user",
                "content": f"{SUMMARY_PREFIX}\n{compress_end - compress_start} turns removed.\nContinue."
            })
        
        for i in range(compress_end, n_messages):
            compressed.append(messages[i].copy())
        
        self.compression_count += 1
        compressed = self._sanitize_tool_pairs(compressed)
        
        compressed_tokens = self._estimate_tokens(compressed)
        # 修复（2026-08-05，核心体检-2 OpenClaw发现）：记录压缩效果（anti-thrashing状态）
        self._last_compress_time = time.monotonic()
        savings_ratio = (display_tokens - compressed_tokens) / max(display_tokens, 1)
        self._last_savings.append(savings_ratio)
        self._last_savings = self._last_savings[-3:]  # 只保留最近3次
        self._compress_failures = 0  # 成功压缩清零失败计数
        
        result = CompressionResult(
            original_count=n_messages,
            compressed_count=len(compressed),
            original_tokens=display_tokens,
            compressed_tokens=compressed_tokens,
            summary=summary or "",
            pruned_tool_count=pruned_count,
            compression_count=self.compression_count,
            summary_mode=summary_mode
        )
        
        if not self.quiet_mode:
            logger.info(
                f"Compression #{self.compression_count}: "
                f"{n_messages}->{len(compressed)}, "
                f"{display_tokens}->{compressed_tokens} tokens, "
                f"mode={summary_mode}"
            )
        
        return compressed, result
    
    def reset(self):
        self._previous_summary = None
        self.compression_count = 0
        self._summary_failure_cooldown_until = 0.0

    def reset_history(self) -> None:
        """Alias for ``MimirAetherAgent.reset`` / gateway compatibility."""
        self.reset_step()

    def reset_step(self) -> None:
        """Reset per-step state (turn-level, not session-level)."""
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0
        self.reset()


# ============================================================================
# Standalone helper functions
# ============================================================================

def _with_summary_prefix(summary: str) -> str:
    """
    将摘要文本标准化为当前compaction handoff格式（Hermès兼容）

    移除旧前缀（LEGACY_PREFIX或SUMMARY_PREFIX），
    然后添加当前SUMMARY_PREFIX。
    """
    text = (summary or "").strip()
    for prefix in (LEGACY_PREFIX, SUMMARY_PREFIX):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
            break
    return f"{SUMMARY_PREFIX}\n{text}" if text else SUMMARY_PREFIX


# 向后兼容导出（core_loop.py使用ContextCompressor）
ContextCompressor = ContextCompressorV2


def compress_conversation(messages: List[Dict], **kwargs) -> Tuple[List[Dict], CompressionResult]:
    # 分离ContextCompressorV2的__init__参数和其他参数
    init_keys = {'model', 'threshold_percent', 'protect_first_n', 'protect_last_n', 
                 'tail_token_budget', 'summary_target_ratio', 'summary_model', 
                 'base_url', 'api_key', 'credential_pool', 'model_context_length'}
    init_kwargs = {k: v for k, v in kwargs.items() if k in init_keys}
    
    compressor = ContextCompressorV2(**init_kwargs)
    tokens = compressor._estimate_tokens(messages)
    if not compressor.should_compress(prompt_tokens=tokens):
        return messages, CompressionResult(
            original_count=len(messages),
            compressed_count=len(messages),
            original_tokens=tokens,
            compressed_tokens=tokens,
        )
    return compressor.compress(messages)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("=" * 60)
    print("ContextCompressor V2.2 测试")
    print("=" * 60)
    
    # 测试1: 基本压缩
    print("\n[测试1] 基本压缩测试")
    test_messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a Python function to sort a list"},
        {"role": "assistant", "content": "Here is a quick sort implementation..."},
        {"role": "tool", "tool_call_id": "tc1", "content": "User wants to sort [3,1,4,1,5]"},
        {"role": "user", "content": "Can you make it more efficient?"},
        {"role": "assistant", "content": "Sure! Using merge sort with O(n log n)..."},
    ] * 15
    
    compressor = ContextCompressorV2(quiet_mode=False)
    tokens = compressor._estimate_tokens(test_messages)
    print(f"输入: {len(test_messages)} 条消息, ~{tokens} tokens")
    print(f"应压缩: {compressor.should_compress(test_messages, tokens)}")
    
    compressed, result = compressor.compress(test_messages)
    
    print(f"\n结果:")
    print(f"  压缩后: {result.compressed_count} 条消息")
    print(f"  Token节省: {result.original_tokens - result.compressed_tokens}")
    print(f"  摘要模式: {result.summary_mode}")
    print(f"  摘要长度: {len(result.summary)} 字符")
    
    # 测试2: 短对话不压缩
    print("\n[测试2] 短对话不压缩")
    short_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]
    tokens2 = compressor._estimate_tokens(short_messages)
    compressed2, result2 = compressor.compress(short_messages)
    print(f"  输入: {len(short_messages)} msg, ~{tokens2} tokens")
    print(f"  应压缩: {compressor.should_compress(short_messages, tokens2)}")
    print(f"  输出: {len(compressed2)} msg")
    
    # 测试3: 迭代压缩
    print("\n[测试3] 迭代压缩")
    compressor.reset()
    comp1, res1 = compressor.compress(test_messages)
    tokens_c1 = compressor._estimate_tokens(comp1)
    print(f"  第1次: {res1.compressed_count} msg, ~{tokens_c1} tokens, 应压缩={compressor.should_compress(comp1, tokens_c1)}")
    
    comp2, res2 = compressor.compress(comp1)
    tokens_c2 = compressor._estimate_tokens(comp2)
    print(f"  第2次: {res2.compressed_count} msg, ~{tokens_c2} tokens, 应压缩={compressor.should_compress(comp2, tokens_c2)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

# ============================================================================
# Full-Featured Compressor with Probing Support
# ============================================================================

class MimirContextCompressor(ContextCompressorV2):
    """
    Full-featured context compressor with probing support.
    
    Compression strategy:
    1. 工具结果修剪（无LLM调用）
    2. 保护头部消息（system + first exchange）
    3. 保护尾部消息（按token预算）
    4. LLM摘要中间消息
    5. 迭代摘要更新
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # calls ContextCompressorV2.__init__
        # Extra configuration
        self._iterative_summary = True  # 迭代摘要
        self._tool_pruning_enabled = True
        self._context_probed = False
        # E1 (2026-08-19 block4): compaction summary writeback callback (optional)
        self._writeback_callback = None
        # RS14-D1 (2026-09-14)：质量记录仪器化状态（每次 compress() 开头重置）
        self._last_entity_stats = {"entity_count": 0, "missing_count": 0}
        self._last_index_stats = {
            "index_items": 0, "index_chars": 0,
            "index_capped": False, "entity_total": 0,
        }
        self._last_summary_attempts = 0
        self._last_summary_elapsed_s = None
        self._last_summary_requested_max_tokens = None
        self._last_summary_budget_raw = None
        # P2-1 (2026-08-19 执行卡) → 2026-09-11 档2-② 收编：绝对 token 阈值 env
        # 覆盖（MIMIR_COMPRESS_THRESHOLD_TOKENS）。解析逻辑移入模块级
        # resolve_threshold_tokens()，与 core_loop 的 percent 链共用同一真源，
        # 消除"env 架空 tuned / update_model 架空 env"两条暗路。
        _resolved_tokens, _resolved_source = resolve_threshold_tokens(
            int(self.context_length or 0), self.threshold_percent
        )
        self.threshold_source = _resolved_source
        # B9：env 绝对覆盖 **或** 有效窗口上限生效（source 含 "+cap:"）时同步
        # threshold_tokens。上限只把阈值往下夹，故与原 env 分支同构、无副作用。
        if (
            _resolved_source.startswith("env:") or "+cap:" in _resolved_source
        ) and _resolved_tokens != self.threshold_tokens:
            self.threshold_tokens = _resolved_tokens
            self.tail_token_budget = clamp_compressor_key(
                "tail_token_budget", int(self.threshold_tokens * self.summary_target_ratio)
            )
        logger.info(
            "[COMPRESS-INIT] threshold_tokens=%s source=%s context_length=%s percent=%s tail=%s",
            self.threshold_tokens, self.threshold_source,
            self.context_length, self.threshold_percent, self.tail_token_budget,
        )

    def update_model(self, *args, **kwargs) -> None:
        """档2-②：update_model 不再静默丢弃 env 绝对阈值覆盖（修 clobber）。

        基类实现用 ``context_length x threshold_percent`` 重算 threshold_tokens，
        会静默抹掉环境变量给的绝对覆盖——即"配置改了不生效"的同一类病。此处
        重算后按同一真源再解析一次。
        """
        super().update_model(*args, **kwargs)
        _resolved_tokens, _resolved_source = resolve_threshold_tokens(
            int(self.context_length or 0), self.threshold_percent
        )
        self.threshold_source = _resolved_source
        # B9：env 绝对覆盖 **或** 有效窗口上限生效（source 含 "+cap:"）时同步
        # threshold_tokens。上限只把阈值往下夹，故与原 env 分支同构、无副作用。
        if (
            _resolved_source.startswith("env:") or "+cap:" in _resolved_source
        ) and _resolved_tokens != self.threshold_tokens:
            self.threshold_tokens = _resolved_tokens
            self.tail_token_budget = clamp_compressor_key(
                "tail_token_budget", int(self.threshold_tokens * self.summary_target_ratio)
            )
            logger.info(
                "[COMPRESS-UPDATE] threshold_tokens=%s source=%s (env/cap override re-applied "
                "after update_model)",
                self.threshold_tokens, self.threshold_source,
            )

    def reset_step(self) -> None:
        """Reset per-step state."""
        super().reset_step()
        self._context_probed = False
        self._previous_summary = None

    # ── E1 (2026-08-19 block4): writeback callback injection ─────────────────
    def set_writeback_callback(self, callback) -> None:
        """E1: inject compaction summary writeback callback (optional).

        callback(event_data: dict) — event_data contains summary/pruned_count/ts.
        compressor stays store-agnostic (callback injection — 四方卡 L748);
        session_id is captured by the core_loop closure (compress has no
        session_id param — Mimir audit L1141 gap, filled on core_loop side).
        """
        self._writeback_callback = callback

    # ── P2-1/P5-2 (2026-08-19 执行卡): 压缩验证钩子 ──────────────────────────
    async def compress(self, messages, current_tokens=None, focus_topic=None):
        """覆写基类 compress——压缩后验证关键实体保留率 ≥80%，<80% 告警+回滚。"""
        pre = messages
        # ── 档2-① 三行日志：trigger / result / abort ──────────────────────
        _pre_n = len(messages)
        _pre_t0 = time.monotonic()
        # T16：本次尝试唯一 id —— 同一次 compress() 内多条失败上报只计 1 次退避
        #（否则"摘要降级 + 闸门回滚"会双计，退避跳级）
        self._cooldown_attempt_id = "%d-%d" % (os.getpid(), int(_pre_t0 * 1000) % 10**9)
        # T20：本次尝试的摘要用量从空开始（防上一轮残留）
        self._last_summary_usage = {}
        # RS14-D1：本轮仪器化状态重置（防上一轮残留值污染记录）
        self._last_entity_stats = {"entity_count": 0, "missing_count": 0}
        self._last_index_stats = {
            "index_items": 0, "index_chars": 0,
            "index_capped": False, "entity_total": 0,
        }
        self._last_summary_attempts = 0
        self._last_summary_elapsed_s = None
        self._last_summary_requested_max_tokens = None
        self._last_summary_budget_raw = None
        try:
            _pre_tokens = self._estimate_tokens(messages)
        except Exception:
            _pre_tokens = 0
        self._pre_tokens_for_ledger = _pre_tokens
        # ── T20-b（2026-09-15 · T2 首算发现的「口径混用」）────────────────────
        # 病：``_estimate_tokens`` = ``len(content)//4 + 20``（``_CHARS_PER_TOKEN=4``），
        # 对 CJK/代码是**低估**（实测同行 ratio = summary_prompt_tokens / pre_estimate
        # 达 1.63 > 1 —— 摘要 prompt 是**中段子集**却比整段 pre 还大，物理上不可能
        # ⇒ 反证 pre 被低估，而非序列化膨胀：``_serialize_for_summary`` 只**截断**
        # 长内容，合成对照 ratio(ser/est) = 0.97）。
        # 而调用方（``core_loop.py:916`` / ``agent_loop.py:654``）**已把 API 实计值
        # 传进来**（``current_tokens=compressor.last_prompt_tokens``）却被丢掉
        # ⇒ 台账里「成本=API 实计、收益=粗估」两种口径混在一行，**投产比不可算**
        #（T3/T4 因此阻塞）。此处把实计值留下，不改变任何判定行为。
        self._pre_tokens_actual_for_ledger = (
            int(current_tokens)
            if isinstance(current_tokens, (int, float)) and current_tokens > 0
            else None
        )
        _thr = getattr(self, "threshold_tokens", 0) or 0
        _thr_src = getattr(self, "threshold_source", "unknown")
        logger.info(
            "[COMPRESS] %s layer=agent tokens=%s threshold=%s msgs=%s source=%s current_tokens=%s",
            "trigger" if _pre_tokens >= _thr else "skip",
            _pre_tokens, _thr, _pre_n, _thr_src, current_tokens,
        )
        try:
            post, result = await super().compress(messages, current_tokens, focus_topic)
        except Exception as _e:
            # T16 顺带修：原代码此处**同一行日志重复打两遍**（已删一条）
            logger.warning("[P2-1] compress failed: %s — keep original messages", _e)
            _cc_x = _compress_cooldown()
            if _cc_x is not None:
                try:
                    _cc_x.record_failure(
                        "compress_exception:%s" % type(_e).__name__,
                        attempt_id=self._cooldown_attempt_id,
                    )
                except Exception:
                    pass
            logger.warning(
                "[COMPRESS] abort layer=agent reason=exception msgs=%s tokens=%s "
                "threshold=%s source=%s err=%s",
                _pre_n, _pre_tokens, _thr, _thr_src, _e,
            )
            return messages, CompressionResult(
                original_count=len(messages), compressed_count=len(messages),
            )
        # ── 档2-① result / abort(noop) ────────────────────────────────────
        _elapsed = time.monotonic() - _pre_t0
        _res_n = len(post)
        _pruned = getattr(result, "pruned_tool_count", 0) or 0
        if _res_n >= _pre_n and _pruned == 0:
            logger.warning(
                "[COMPRESS] abort layer=agent reason=noop msgs=%s->%s pruned=%s "
                "tokens=%s threshold=%s source=%s elapsed=%.2fs (nothing compressed)",
                _pre_n, _res_n, _pruned, _pre_tokens, _thr, _thr_src, _elapsed,
            )
        else:
            logger.info(
                "[COMPRESS] result layer=agent msgs=%s->%s pruned=%s mode=%s "
                "tokens=%s->%s threshold=%s source=%s elapsed=%.2fs",
                _pre_n, _res_n, _pruned, getattr(result, "summary_mode", "none"),
                _pre_tokens, getattr(result, "compressed_tokens", 0) or 0,
                _thr, _thr_src, _elapsed,
            )
        # 实体保留率验证（env MIMIR_COMPRESS_VERIFY=0 关闭）
        _verify = os.environ.get("MIMIR_COMPRESS_VERIFY", "1").strip().lower()
        if _verify not in ("0", "false", "no", "off"):
            try:
                rate, missing = self._verify_entity_retention(pre, post)
                if rate < 0.80:
                    # RS14-D1：日志带全仪器化字段（可直接 grep 出分布，不必读 jsonl）
                    logger.warning(
                        "[P2-1] 实体保留率 %.0f%% < 80%% —— 回滚压缩 "
                        "(entity_count=%s missing_count=%s head3=%s idx_items=%s "
                        "idx_chars=%s idx_capped=%s summary_elapsed=%ss "
                        "requested_max_tokens=%s gate=%s)",
                        rate * 100,
                        self._last_entity_stats.get("entity_count"),
                        self._last_entity_stats.get("missing_count"),
                        missing[:3],
                        self._last_index_stats.get("index_items"),
                        self._last_index_stats.get("index_chars"),
                        self._last_index_stats.get("index_capped"),
                        self._last_summary_elapsed_s,
                        self._last_summary_requested_max_tokens,
                        ENTITY_GATE_VERSION,
                    )
                    # E1/E5 (2026-08-20): 质量告警落盘 + 回滚分支不写回（防记录未生效压缩）
                    logger.warning(
                        "[COMPRESS] abort layer=agent reason=entity_retention_low "
                        "rate=%.0f%% msgs=%s->%s (rolled back to original)",
                        rate * 100, _pre_n, len(post),
                    )
                    self._record_quality_alert(rate, missing, result, outcome="rollback")
                    # ── T16 核心修复 ──────────────────────────────────────
                    # 回滚 = 压缩未应用 = token 不变 ⇒ 不禁的话下一 turn 必然重来。
                    # 这是三处历史冷却都没覆盖的唯一路径。
                    _cc_r = _compress_cooldown()
                    if _cc_r is not None:
                        try:
                            _cc_r.record_failure(
                                "entity_retention_low(rate=%.2f)" % rate,
                                attempt_id=self._cooldown_attempt_id,
                            )
                        except Exception as _ce:
                            logger.warning("[COMPRESS] cooldown record failed: %s", _ce)
                    return messages, result  # 回滚：返回压缩前（保状态不丢）
                logger.info(
                    "[P2-1] 实体保留率 %.0f%% OK (entity_count=%s missing=%d "
                    "summary_elapsed=%ss requested_max_tokens=%s gate=%s)",
                    rate * 100, self._last_entity_stats.get("entity_count"), len(missing),
                    self._last_summary_elapsed_s, self._last_summary_requested_max_tokens,
                    ENTITY_GATE_VERSION,
                )
                # RS14-D1：**成功应用也落盘**。历史只有回滚落盘 ⇒ C1 生效后回滚率→0，
                # 新数据将无处产生：Q3 分布 / D-3 的 R1·R2·Δ 基线 / D-4 的
                # degraded_streak 全部无源。故 applied 与 rollback 两条路都记。
                self._record_quality_alert(rate, missing, result, outcome="applied")
                # T16：压缩真正应用 ⇒ 热环结束，冷却清零（下一次失败从 600s 重新起算）
                _cc_a = _compress_cooldown()
                if _cc_a is not None:
                    try:
                        _cc_a.record_success(attempt_id=self._cooldown_attempt_id)
                    except Exception as _ce:
                        logger.warning("[COMPRESS] cooldown clear failed: %s", _ce)
            except Exception as _ve:
                logger.warning("[P2-1] verify hook failed (degrade: keep compressed): %s", _ve)
        # E1 (2026-08-20): 压缩成功且验证通过 → 摘要写回（callback 可空；异常降级不阻断压缩）
        self._emit_writeback(result)
        return post, result

    # ── E1/E5 (2026-08-20): 写回与质量落盘 ───────────────────────────────────
    def _emit_writeback(self, result: CompressionResult) -> None:
        """E1: 通过注入回调写回压缩摘要事件（失败降级 warning，不阻断压缩）。

        event_data = {summary, pruned_count, ts}——compressor 保持 store-agnostic，
        session_id 由 core_loop 闭包捕获（见 set_writeback_callback docstring）。
        """
        cb = self._writeback_callback
        if cb is None:
            return
        try:
            cb({
                "summary": result.summary or "",
                "pruned_count": result.pruned_tool_count,
                "ts": result.timestamp,
            })
            logger.info("[E1] compaction writeback emitted (pruned=%d)", result.pruned_tool_count)
        except Exception as _e:
            logger.warning("[E1] writeback callback failed (non-blocking): %s", _e)

    def _record_quality_alert(self, rate, missing, result: CompressionResult, outcome: str) -> None:
        """E5 → RS14-D1: 质量记录落盘 ~/.mimiraether/data/compression_quality.jsonl（不阻断）。

        outcome: ``"applied"``（压缩已应用）｜``"rollback"``（实体闸门回滚）。
        RS14-D1 变更（2026-09-14 · 四方终审 §13.2 P0）：
          · 新增 ``entity_count`` / ``missing_count`` ⇒ 率**可独立复算**（历史只有被截断的 missing）；
          · ``missing`` 由 ``[:5]`` 改为全量（上限 ``_QUALITY_MISSING_MAX_ITEMS`` + ``missing_capped``）；
          · 新增 ``index_items`` / ``index_chars`` / ``index_capped`` ⇒ 索引上限是否绑定可见；
          · 新增 ``summary_elapsed_s`` / ``requested_max_tokens`` / ``summary_budget_raw``
            / ``summary_attempts`` ⇒ Q3 耗时分布不再拿超时截断值反推；
          · 新增 ``gate_version`` ⇒ 跨闸门语义分布不可比性显式化（RS14 §13.3）；
          · 成功路径也落盘（``outcome="applied"``）⇒ C1 生效后仍有数据（历史 275/275 全 rollback）。
        """
        try:
            from mimir_constants import get_mimir_home
            _q_path = get_mimir_home() / "data" / "compression_quality.jsonl"
            _q_path.parent.mkdir(parents=True, exist_ok=True)
            _missing_full = list(missing or [])
            _st = getattr(self, "_last_entity_stats", None) or {}
            _idx = getattr(self, "_last_index_stats", None) or {}
            # 兜底（验证钩子被替换 / 抛异常时）：由明细返推计数，绝不让 entity_count=0
            # 与 missing 非空同时出现（那会让率无法复算 = 本卡要修的原始病）
            _miss_n = max(int(_st.get("missing_count", 0) or 0), len(_missing_full))
            _ent_n = max(int(_st.get("entity_count", 0) or 0), _miss_n)
            # ── T20（2026-09-14）：压缩代价埋点（派生量）────────────────
            # 背景：T2「压缩到底烧多少 token」此前**算不出** —— 台账 18 字段里
            # 没有任何 token 字段。注意口径：摘要走独立 aiohttp 通路
            # （_call_summary_llm），**不写 [S2-cache]**，与主循环是两个总体
            # （T1 已因分母混用自我更正过一次，此处务必分开记）。
            _usage = dict(getattr(self, "_last_summary_usage", None) or {})
            _before_tokens = getattr(self, "_pre_tokens_for_ledger", None)
            _before_actual = getattr(self, "_pre_tokens_actual_for_ledger", None)
            _pre_caliber = "api" if _before_actual else "estimate_only"
            _after_tokens = (
                _before_tokens if outcome == "rollback"
                else (int(getattr(result, "compressed_tokens", 0) or 0) or _before_tokens)
            )
            _ccm = _compress_cooldown()
            try:
                _cooling_n = (int(_ccm.state().get("consecutive_failures") or 0)
                              if _ccm else None)
            except Exception:
                _cooling_n = None
            _line = {
                "ts": datetime.now().isoformat(),
                "gate_version": ENTITY_GATE_VERSION,
                "entity_retention_rate": round(float(rate), 4),
                "entity_count": _ent_n,
                "missing_count": _miss_n,
                "missing": _missing_full[:_QUALITY_MISSING_MAX_ITEMS],
                "missing_capped": len(_missing_full) > _QUALITY_MISSING_MAX_ITEMS,
                "index_items": int(_idx.get("index_items", 0) or 0),
                "index_chars": int(_idx.get("index_chars", 0) or 0),
                "index_capped": bool(_idx.get("index_capped", False)),
                "summary_elapsed_s": getattr(self, "_last_summary_elapsed_s", None),
                "requested_max_tokens": getattr(self, "_last_summary_requested_max_tokens", None),
                "summary_budget_raw": getattr(self, "_last_summary_budget_raw", None),
                "summary_attempts": int(getattr(self, "_last_summary_attempts", 0) or 0),
                # ── T20 新增：token 代价 ─────────────────────────────────
                "prompt_tokens_before": _before_tokens,
                "prompt_tokens_before_actual": _before_actual,
                "pre_tokens_caliber": _pre_caliber,
                "prompt_tokens_after": _after_tokens,
                "candidate_tokens": int(getattr(result, "compressed_tokens", 0) or 0),
                "summary_prompt_tokens": _usage.get("prompt_tokens"),
                "summary_completion_tokens": _usage.get("completion_tokens"),
                "summary_total_tokens": _usage.get("total_tokens"),
                "summary_usage_present": bool(_usage),
                "cooldown_consecutive_failures": _cooling_n,
                "pid": os.getpid(),
                "trace_id": _run_tag(),
                "outcome": outcome,
                "original_count": result.original_count,
                "compressed_count": result.compressed_count,
                "summary_mode": result.summary_mode,
            }
            with open(_q_path, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_line, ensure_ascii=False) + "\n")
            # ── T20-c：applied ⇒ 挂账，等下一次真实调用结算（纯埋点，不改判定）──
            if outcome == "applied":
                try:
                    self._pending_post_measure = {
                        "of_ts": _line["ts"],
                        "pre_actual": _before_actual,
                        "pre_estimate": _before_tokens,
                        "estimate_after": int(getattr(result, "compressed_tokens", 0) or 0),
                        "summary_total_tokens": _usage.get("total_tokens"),
                        "summary_prompt_tokens": _usage.get("prompt_tokens"),
                        "summary_mode": result.summary_mode,
                        "gate_version": ENTITY_GATE_VERSION,
                        "armed_at": time.time(),
                        "compressed_count": result.compressed_count,
                        "original_count": result.original_count,
                    }
                except Exception as _pe:
                    self._pending_post_measure = None
                    logger.debug("[COMPRESS] post-measure arm skipped: %s", _pe)
            if outcome == "applied":
                logger.info("[E1/E5] compression quality record appended (applied): %s", _q_path)
            else:
                logger.warning("[E1/E5] compression quality alert appended: %s", _q_path)
        except Exception as _e:
            logger.warning("[E1/E5] quality alert write failed (non-blocking): %s", _e)

    # ── T20-c（2026-09-16）：「挂账—结算」的**结算端** ─────────────────────
    def settle_post_measure(self, actual_prompt_tokens, message_count=None,
                            is_actual: bool = True) -> None:
        """用**下一次真实调用**的 ``prompt_tokens`` 结算上一次 applied 的压缩收益。

        纯埋点：只**追加** ``kind="post_measure"`` 行到 compression_quality.jsonl，
        不改任何已有字段、不改任何判定、**不抛异常**（异常一律吞掉 —— 埋点绝不阻断主循环）。

        三障（防「结算错对象」；这正是本项目反复吃过的病）：
          1. **无账不结**：``_pending_post_measure`` 为空 ⇒ 立即返回（绝大多数调用属此，
             开销 = 一次属性判空）
          2. **过期不结**：挂账超 TTL（默认 1800s，env ``MIMIR_POST_MEASURE_TTL_S``）
             ⇒ 记 ``settle_reason="expired"`` 并丢弃，**宁可漏、不可跨时段错配**
          3. **非实计不结**：``is_actual=False``（pt 来自粗估兜底）⇒ 记 ``"unmeasured"``

        口径（写进行的自解释字段）：
          · ``pre_actual``  = applied 那次的 API 实计 prompt（T20-b 引入）
          · ``post_actual`` = 紧接着那次调用的 API 实计 prompt  ← **本卡要的真值**
          · ``actual_delta``= pre_actual - post_actual（正=省了）
          · ``net_tokens``  = actual_delta - 摘要自身 total_tokens（净收益；正=赚）
          · ``estimate_error`` = post_actual - estimate_after（估算偏离实计多少）

        ⚠️ **已知局限（自报，不掩盖）**：``post_actual`` 里可能还含**非压缩因素**
        （上一轮工具输出增长等）⇒ ``net_tokens``是**乐观上界**，不是纯压缩效应。
        故凡下结论必须同时看 ``post_message_count`` 与 ``compressed_count`` 是否守恒。
        """
        try:
            pend = getattr(self, "_pending_post_measure", None)
            if not pend:
                return
            self._pending_post_measure = None       # 单飞：一账最多结一次
            try:
                _ttl = float(os.environ.get("MIMIR_POST_MEASURE_TTL_S") or 1800)
            except Exception:
                _ttl = 1800.0
            _age = None
            try:
                _age = max(0.0, time.time() - float(pend.get("armed_at") or 0))
            except Exception:
                pass
            if _age is not None and _age > _ttl:
                _reason = "expired"
            elif not is_actual:
                _reason = "unmeasured"
            else:
                _reason = "settled"
            _pre_a = pend.get("pre_actual")
            _post = int(actual_prompt_tokens or 0) if _reason == "settled" else None
            _sum_tot = pend.get("summary_total_tokens")
            _est_after = pend.get("estimate_after")
            _delta = (_pre_a - _post) if (_pre_a is not None and _post is not None) else None
            _net = None
            if _delta is not None:
                _net = _delta - int(_sum_tot or 0)
            _sign = ("unmeasured" if _net is None
                     else ("positive" if _net > 0 else ("negative" if _net < 0 else "zero")))
            _err = (None if (_post is None or not _est_after)
                    else (_post - int(_est_after)))
            line = {
                "kind": "post_measure",              # ← 判别键：老消费者只看有/无此键
                "ts": datetime.now().isoformat(),
                "of_ts": pend.get("of_ts"),
                "settle_reason": _reason,
                "pending_age_s": (round(_age, 2) if _age is not None else None),
                "pre_actual_prompt_tokens": _pre_a,
                "pre_estimate_tokens": pend.get("pre_estimate"),
                "post_actual_prompt_tokens": _post,
                "estimate_after_tokens": _est_after,
                "estimate_error_tokens": _err,
                "actual_delta_tokens": _delta,
                "summary_total_tokens": _sum_tot,
                "summary_prompt_tokens": pend.get("summary_prompt_tokens"),
                "net_tokens": _net,
                "net_sign": _sign,
                "post_message_count": message_count,
                "compressed_count": pend.get("compressed_count"),
                "original_count": pend.get("original_count"),
                "summary_mode": pend.get("summary_mode"),
                "gate_version": pend.get("gate_version"),
                "pid": os.getpid(),
                "trace_id": _run_tag(),
            }
            from mimir_constants import get_mimir_home
            _q = get_mimir_home() / "data" / "compression_quality.jsonl"
            _q.parent.mkdir(parents=True, exist_ok=True)
            with open(_q, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(line, ensure_ascii=False) + "\n")
            logger.info(
                "[COMPRESS] post-measure %s net=%s sign=%s age=%ss of_ts=%s",
                _reason, _net, _sign, (round(_age, 1) if _age is not None else "?"),
                pend.get("of_ts"),
            )
        except Exception as _e:
            logger.debug("[COMPRESS] post-measure settle skipped: %s", _e)

    def _verify_entity_retention(self, pre, post):
        """关键实体保留率：讨论卡路径 / status 字段 / 任务路径 / commit 哈希。"""
        post_text = json.dumps(post, ensure_ascii=False) if isinstance(post, list) else str(post)
        entities = self._collect_entities(pre)
        if not entities:
            self._last_entity_stats = {"entity_count": 0, "missing_count": 0}
            return 1.0, []
        missing = [e for e in entities if e not in post_text]
        # RS14-D1：实体计数落盘（历史只有被截断的 missing ⇒ 率不可独立验算）。
        # 口径（D-2 文档已同步）：entity_count = **整段 pre 的去重实体集**，
        # 不是 HEAD 子集 —— 按 HEAD 收集会让闸门恒真（实测 HEAD 实体 = 0）。
        self._last_entity_stats = {"entity_count": len(entities), "missing_count": len(missing)}
        return (len(entities) - len(missing)) / len(entities), missing
    
    def mark_context_probed(self) -> None:
        """标记上下文已探测（从上下文错误恢复后）"""
        self._context_probed = True
    
    def is_context_probed(self) -> bool:
        """检查是否已探测上下文"""
        return self._context_probed
    
    def prune_tool_results_aggressive(
        self, 
        messages: List[Dict],
        keep_last: int = 5
    ) -> List[Dict]:
        """
        激进工具结果修剪
        
        : 清除旧工具输出以节省上下文空间
        """
        if not messages:
            return messages
        
        result = []
        tool_count = 0
        
        for msg in messages:
            msg_copy = msg.copy()
            content = msg.get("content", "")
            
            # 检测工具消息
            if msg.get("role") == "tool" or "tool_call" in str(msg):
                tool_count += 1
                # 保留最近N个工具结果
                if tool_count > keep_last:
                    msg_copy["content"] = _PRUNED_TOOL_PLACEHOLDER
            
            result.append(msg_copy)
        
        return result
    
    def protect_tail_by_tokens(
        self,
        messages: List[Dict],
        token_budget: int
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        按token预算保护尾部消息
        
        : 使用token预算而不是固定消息数
        """
        if not messages or token_budget <= 0:
            return [], messages
        
        protected = []
        current_tokens = 0
        
        # 从后向前保护
        for msg in reversed(messages):
            content = msg.get("content", "") or ""
            msg_tokens = len(content) // _CHARS_PER_TOKEN + 50  # 估算开销
            
            if current_tokens + msg_tokens <= token_budget:
                protected.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # 分割点
                break
        
        # 未保护的部分
        unprotected = messages[:-len(protected)] if protected else messages
        
        return unprotected, protected
    
    def get_compression_ratio(self) -> float:
        """获取压缩比率"""
        if self.original_tokens == 0:
            return 0.0
        return 1.0 - (self.compressed_tokens / self.original_tokens)
    
    def should_trigger_compression(
        self,
        prompt_tokens: int,
        completion_tokens: int = 0,
        include_reserve: bool = True
    ) -> Tuple[bool, str]:
        """
        判断是否应触发压缩
        
        Returns:
            (should_compress, reason)
        """
        total_tokens = prompt_tokens + completion_tokens
        
        # 检查阈值
        if total_tokens >= self.threshold_tokens:
            reserve = 2000 if include_reserve else 0
            if total_tokens >= self.threshold_tokens + reserve:
                return True, f"Exceeded threshold: {total_tokens} >= {self.threshold_tokens + reserve}"
        
        # 检查冷却
        if time.time() < self._summary_failure_cooldown_until:
            return False, "In cooldown period"
        
        # 检查是否已探测
        if self._context_probed:
            # 已经压缩过，警告但允许
            return True, "Context already probed, re-compression allowed"
        
        return False, "Within safe bounds"


# Backward compatibility alias
HermesStyleCompressor = MimirContextCompressor
