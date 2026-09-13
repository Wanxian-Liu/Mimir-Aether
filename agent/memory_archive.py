"""记忆归档层 L3 读入口（B8）。

路径真源（F1 终审 质询 1 · 2026-09-13）
-------------------------------------
* **L3 归档路径 = `memories/archive/MEMORY.archive-l3.md`**（`ARCHIVE_REL`，唯一真源）。
  历史批次原始归档 `memories/ARCHIVE-2026-09-13.md` 已于 F1 终审期间**逐条原文迁入**
  本约定路径（确定性锚点 `uuid5`，原文备份 `backups/<ts>-f1-archive-migration/`），
  源文件仅留指针 stub —— 旧「双位置」不再存在。
* **home 解析必须与写入侧同源**：用 `mimiraether_constants.get_mimiraether_home()`
  （顶层 `mimir_constants.get_mimir_home()`：`MIMIR_AETHER_HOME` → `MIMIRAETHER_HOME`
  → `HERMES_HOME` → `~/.mimiraether`）。**禁止**改用 `agent.mimir_constants.get_mimir_home()`
  —— 那个只认 `MIMIR_HOME`／`~/.mimir`，与 `tools/memory_tool.get_memory_dir()` **不同源**，
  会让读入口指向不存在的目录（2026-09-13 F1 实测：`archive_exists=false`、`blocks=0`）。

背景：`memories/MEMORY.md` 是注入层（MemoryStore 的 55,000 字符上限），
超限时把**最旧、已被取代**的条目折叠进 `memories/archive/MEMORY.archive-l3.md`
（逐字原文 + 锚点注释），锚点→内容映射写在 `memories/memory_anchors.json`。

本模块是该层的**唯一读入口**（CR7 Dependency Direction）：任何调用方都不应
直接 `read_file("memories/archive/MEMORY.archive-l3.md")` —— 那样会把
「注释头 + 逐字条目」的存储格式假设泄漏到调用方；将来换成 sqlite / 向量库
也不应影响调用方。

约定
----
* 折叠**不改条目文本**（只换承载文件）——故 `read_memory_archive(anchor=...)`
  返回的字符串与折叠前 `MEMORY.md` 里那条逐字相同。
* 锚点不写回注入层（每字节都计入 55,000 上限），只存在于归档层注释与 manifest。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ARCHIVE_REL = "archive/MEMORY.archive-l3.md"
MANIFEST_REL = "memory_anchors.json"
ANCHOR_TOKEN = "<!-- anchor: "


def _memories_dir() -> Path:
    """记忆目录（与 tools/memory_tool.get_memory_dir 同源）。"""
    try:
        # 与写入侧（tools/memory_tool.get_memory_dir）同源：顶层 mimiraether_constants
        # → mimir_constants.get_mimir_home（MIMIR_AETHER_HOME > MIMIRAETHER_HOME > HERMES_HOME）。
        # 不得用 agent.mimir_constants.get_mimir_home（只认 MIMIR_HOME／~/.mimir）。
        from mimiraether_constants import get_mimiraether_home  # type: ignore

        return Path(get_mimiraether_home()) / "memories"
    except Exception:
        home = os.environ.get("MIMIR_AETHER_HOME") or (Path.home() / ".mimiraether")
        return Path(home) / "memories"


def archive_path() -> Path:
    return _memories_dir() / ARCHIVE_REL


def manifest_path() -> Path:
    return _memories_dir() / MANIFEST_REL


def load_anchor_index() -> Dict[str, Dict]:
    """锚点索引（读不到时返回空 dict，不抛）。"""
    path = manifest_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    anchors = data.get("anchors") if isinstance(data, dict) else None
    return anchors if isinstance(anchors, dict) else {}


def _strip_leading_comments(text: str) -> str:
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("<!--")):
        i += 1
    return "\n".join(lines[i:]).strip()


def parse_archive_blocks(path: Optional[Path] = None) -> List[Tuple[str, str]]:
    """解析归档层为 [(anchor, 逐字条目)]；坏块跳过，不抛。"""
    target = path or archive_path()
    if not target.is_file():
        return []
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError:
        return []
    out: List[Tuple[str, str]] = []
    for chunk in raw.split(ANCHOR_TOKEN)[1:]:
        if "-->" not in chunk:
            continue
        anchor, rest = chunk.split("-->", 1)
        payload = _strip_leading_comments(rest)
        if payload:
            out.append((anchor.strip(), payload))
    return out



def read_memory_archive(
    section_id: Optional[str] = None,
    anchor: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
) -> Optional[str]:
    """读归档层。三选一（anchor > section_id > query），命中多条时用分隔符拼接。

    * ``anchor``：精确取一条（折叠时生成的 uuid，见 ``list_anchors()``）。
    * ``section_id``：按条目标题的**前缀/包含**匹配（等价于折叠前的 `## 标题`）。
    * ``query``：任意子串匹配（用于「这条事实被折到哪去了」的查证）。

    无命中返回 ``None``（区别于返回空串——调用方可区分「没这把钥匙」与「该条为空」）。
    """
    blocks = parse_archive_blocks()
    if not blocks:
        return None
    hits: List[str] = []
    if anchor:
        for a, payload in blocks:
            if a == anchor:
                return payload
        return None
    needle = (section_id or query or "").strip()
    if not needle:
        return None
    for _, payload in blocks:
        first_line = payload.lstrip("# ").split("\n")[0]
        if section_id and needle in first_line:
            hits.append(payload)
        elif query and needle in payload:
            hits.append(payload)
        if len(hits) >= max(1, int(limit)):
            break
    return "\n\n---\n\n".join(hits) if hits else None


def list_anchors() -> List[Dict]:
    """锚点清单（供体检/审计：每条折叠了什么、为什么、被谁取代）。"""
    idx = load_anchor_index()
    return [dict(meta, anchor=a) for a, meta in idx.items()]


def archive_stats() -> Dict[str, object]:
    """归档层体检数字（blocks / chars / manifest 锚点数 / 一致性）。"""
    blocks = parse_archive_blocks()
    idx = load_anchor_index()
    path = archive_path()
    return {
        "archive_path": str(path),
        "archive_exists": path.is_file(),
        "archive_bytes": path.stat().st_size if path.is_file() else 0,
        "blocks": len(blocks),
        "manifest_anchors": len(idx),
        "blocks_without_manifest": [a for a, _ in blocks if a not in idx],
        "manifest_anchors_without_block": [a for a in idx if a not in {b for b, _ in blocks}],
    }
