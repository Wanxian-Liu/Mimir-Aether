"""persistent.json 写盘前的字段规范化（RS20 治本 · 2026-09-26）。

为什么需要这个模块
--------------------------------------------------------------------------------
2026-09-26 定位到一个**自我回滚**：对 ``data/persistent.json`` 的瘦身改动会在
约 7 分钟内被系统自己撤销，且无人察觉。

根因不是某个机制坏了，而是**写入侧没有消除复兴源**：
``CrossSessionMemory.save()`` 在 run 收尾时用**进程内快照**整文件重写
（``merge_disk_into_memory`` 内 ``out[key] = {**disk_seg, **mem_seg}`` —— 内存胜出），
而该实例的加载时刻**早于**瘦身时刻 ⇒ 一份旧内存副本把废弃字段全部复活。

旧解药（``scripts/mem_l2_slim.py``）是**事后重放**：没有调度器、依赖人记得跑。
实测在回滚后 4 分钟内无人发现，是本轮审计才抓到的 —— 属「坏消息长得像好消息」族。

本模块把废弃字段的消除放到**写盘前的唯一咽喉**
（``agent/persistent_store._save_unlocked``），使**任何**写入者
（``save`` / ``save_merged`` / ``read_modify_write``）都无法复活它们。
事后重放脚本因此降级为兜底，并在治本落地后成为死代码。

设计约束（改这个模块前先读这条）
--------------------------------------------------------------------------------
1. **单一真源**：废弃字段只在 :data:`DEPRECATED_FIELDS` 声明一次。
2. **幂等**：``normalize()`` 跑第二次必须与第一次结果相同。
3. **非静默**：真的删/改了东西就 INFO 记账（字段名 + 省下的字节）；干净时零日志。
   这是「坏消息长得像好消息」族的**结构性**修复 —— 瘦身不再是隐形动作。
4. **只动已实证「只写不读」的字段**：每条 ``DeprecatedField.evidence`` 必须写清读侧
   取证。**禁止**在这里加「看起来没用」的字段 —— 本文件的前身
   （``cross_session_memory.py`` L347-363 的 fallthrough）正是为了一次白名单式吞字段
   事故（``milestone_relations`` 104→1247 边数字不一致）才加的，代价是每轮 21 KB 死重。
   ⇒ 加字段 = 必须给读侧取证，否则不加。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

#: ``dormant_skills[*].summary`` 保留上限（字符）。与 F1「长条目保尾收缩」同族策略：
#: 头 2/3 + 尾 1/3，避免「纯头部截断」丢失条目的结论（旧 ``max_entry_chars=300``
#: 纯头部截断是 45 处不可恢复丢失的根因）。
MAX_DORMANT_SUMMARY_CHARS = 120

#: ``dormant_skills[*].dormant_at`` 保留长度（ISO 8601 的 ``YYYY-MM-DD``）。
DORMANT_AT_DATE_CHARS = 10

_DROP: Literal["drop"] = "drop"
_TRUNCATE: Literal["truncate"] = "truncate"


@dataclass(frozen=True)
class DeprecatedField:
    """一条废弃字段声明（单一真源的元素）。"""

    key: str
    """点路径。支持 ``a.b``（顶层段）与 ``a.*.b``（段的每个 dict 成员）。"""

    action: Literal["drop", "truncate"]
    """``drop`` = 整键删除；``truncate`` = 按 ``limit`` 缩短值。"""

    reason: str
    """为什么可以动它（一句话）。"""

    evidence: str
    """读侧取证：谁读过它 / 为什么可以安全丢弃。**必填**。"""

    archived: str = ""
    """原值归档落点（可回读）。删除类字段必填。"""

    limit: int = 0
    """``truncate`` 的保留上限（字符）。"""


DEPRECATED_FIELDS: tuple[DeprecatedField, ...] = (
    DeprecatedField(
        key="progress.milestone_relations",
        action=_DROP,
        reason="只写不读的里程碑关系图（84 节点，回滚态 21,160 B ≈ 每轮 5,290 tokens）",
        evidence=(
            "repo 侧唯一引用是注释 cross_session_memory.py:354；"
            "home 侧仅死一次性脚本 scripts/p1/p1_add_related.py（写）+ p1_verify.py（读），"
            "但 cron 引用 0 / logs 运行留痕 0 / home 仓跟踪 0 ⇒ 无生产消费者"
        ),
        archived=(
            "~/.mimiraether/notes/2026-09-26-记忆整理执行记录.md"
            "（含归档 JSON：milestone_relations 84/84 键逐值完整）"
        ),
    ),
    DeprecatedField(
        key="dormant_skills.*.capsule_path",
        action=_DROP,
        reason="可推导死重（79 条，回滚态 4,795 B）",
        evidence=(
            "唯一写点 skill_curator.py:566/577；唤醒走 _find_dormant_skill()"
            "（:438-455）扫描文件系统 .dormant/<category>/<name>，不读该字段"
        ),
        archived="~/.mimiraether/notes/2026-09-26-记忆整理执行记录.md（79/79 条）",
    ),
    DeprecatedField(
        key="dormant_skills.*.dormant_at",
        action=_TRUNCATE,
        reason="只写不读的时间戳（79 条，回滚态 3,792 B）压成日期",
        evidence="唯一写点 skill_curator.py:568；全仓零读点（grep 已证）",
        limit=DORMANT_AT_DATE_CHARS,
    ),
    DeprecatedField(
        key="dormant_skills.*.summary",
        action=_TRUNCATE,
        reason="沉寂技能摘要超长（37 条 >120 字，回滚态约 9,183 字符被截）",
        evidence=(
            "唯一读点 _get_dormant_registry() 的消费方只用 original_category"
            "（capsulize_and_dormant:520-521 判定分类 / revive_skill:602-603 还原目录）；"
            "summary 不在任何读路径（原值已归档，可回读）"
        ),
        archived="~/.mimiraether/notes/2026-09-26-记忆整理执行记录.md（9,183 字符原值）",
        limit=MAX_DORMANT_SUMMARY_CHARS,
    ),
)


@dataclass
class NormalizeReport:
    """一次规范化的结果（供日志与测试断言）。"""

    removed: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    bytes_saved: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.removed or self.truncated)

    def as_dict(self) -> dict:
        return {
            "removed": len(self.removed),
            "truncated": len(self.truncated),
            "bytes_saved": self.bytes_saved,
        }


def _truncate_keep_tail(value: object, limit: int) -> object:
    """头 2/3 + 尾 1/3 收缩。**结果不变短就原样返回**。

    最后那句不是防御性代码：初版重放脚本在 ``len(s) == limit + 1`` 时产出的
    结果与输入等长（``s[:limit] + "…"`` 恰等值），却把 ``changed`` 置真 ——
    「无操作」被报成「改过了」。该 bug 由负控当场抓到，此处以「不变短即不改」
    作为结构性守卫，不依赖调用方记得检查。
    """
    if not isinstance(value, str) or limit <= 0 or len(value) <= limit:
        return value
    head = int(limit * 2 / 3)
    tail = limit - head - 1
    candidate = value[:head] + "\u2026" + (value[-tail:] if tail > 0 else "")
    return candidate if len(candidate) < len(value) else value


def _truncate_date(value: object, limit: int) -> object:
    """ISO 时间戳压成日期部分（``2026-07-12T04:37:29+00:00`` → ``2026-07-12``）。"""
    if not isinstance(value, str) or len(value) <= limit:
        return value
    candidate = value[:limit]
    # 只接受形如 YYYY-MM-DD 的前缀，避免把非时间戳字符串切坏
    if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
        return candidate
    return value


_TRUNCATORS = {"truncate": _truncate_keep_tail, "truncate_date": _truncate_date}


def _apply_top_level(data: dict, spec: DeprecatedField, report: NormalizeReport) -> None:
    parent, _, leaf = spec.key.partition(".")
    seg = data.get(parent)
    if not isinstance(seg, dict) or leaf not in seg:
        return
    if spec.action == _DROP:
        del seg[leaf]
        report.removed.append(spec.key)
        return
    fn = _TRUNCATORS.get("truncate_date" if spec.key.endswith("dormant_at") else "truncate")
    new = fn(seg[leaf], spec.limit)
    if new != seg[leaf]:
        seg[leaf] = new
        report.truncated.append(spec.key)


def _apply_nested(data: dict, spec: DeprecatedField, report: NormalizeReport) -> None:
    root, _, rest = spec.key.partition(".*.")
    leaf = rest
    container = data.get(root)
    if not isinstance(container, dict):
        return
    fn = _TRUNCATORS.get("truncate_date" if leaf.endswith("dormant_at") else "truncate")
    for name, entry in container.items():
        if not isinstance(entry, dict) or leaf not in entry:
            continue
        if spec.action == _DROP:
            del entry[leaf]
            report.removed.append(f"{spec.key}#{name}")
            continue
        new = fn(entry[leaf], spec.limit)
        if new != entry[leaf]:
            entry[leaf] = new
            report.truncated.append(f"{spec.key}#{name}")


def _measure(data: dict) -> int:
    return len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def normalize(data: dict) -> NormalizeReport:
    """就地消除废弃字段。幂等；返回报告（``changed`` 为假 = 本次什么都没做）。"""
    report = NormalizeReport()
    if not isinstance(data, dict):
        return report
    before = _measure(data)
    for spec in DEPRECATED_FIELDS:
        if ".*." in spec.key:
            _apply_nested(data, spec, report)
        else:
            _apply_top_level(data, spec, report)
    if report.changed:
        report.bytes_saved = max(0, before - _measure(data))
    return report


def normalize_and_log(data: dict, *, source: str = "") -> NormalizeReport:
    """``normalize`` + 非静默记账（真的动了才写日志）。"""
    report = normalize(data)
    if report.changed:
        logger.info(
            "[PERSISTENT-NORMALIZE] 写盘前消除废弃字段 (%s): removed=%d truncated=%d 省 %d 字节",
            source or "save",
            len(report.removed),
            len(report.truncated),
            report.bytes_saved,
        )
    return report
