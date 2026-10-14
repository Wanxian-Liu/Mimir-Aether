"""回归：wiki 质量门禁『④ 叠置 frontmatter』检测（2026-10-14 新增 · 两向）。

背景：`FM_BLOCK_RE` 非贪婪 ⇒ 只吃第一块；叠置 fm（空壳块 + 真块）文件的
第二块（含 relations）对 ①死链 / ①b 裸路径 两条判据**全盲** ⇒ 真缺陷静默通过。
实证：`entities/Agent-架构三篇论文.md`、`entities/Agentic-Design-Patterns.md`。
"""
import contextlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import wiki_quality_report as wqr  # noqa: E402

POS = """---
type: entity
title: 正控-叠置
status: pending
---
---
title: 正控-真块
type: entity
relations:
  - type: x
    target: entities/不存在的页
---
"""

NEG = """---
title: 负控-单块
type: entity
status: pending
---

正文里的水平线（不是 frontmatter 分隔符）：

---

结束。
"""


def _run(tmp_path, name, body):
    d = tmp_path / name / "entities"
    d.mkdir(parents=True)
    (d / "页.md").write_text(body, encoding="utf-8")
    out = tmp_path / f"{name}.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = wqr.main(["--wiki", str(tmp_path / name), "--paths", "entities",
                       "--strict", "--json", str(out)])
    return rc, buf.getvalue(), json.loads(out.read_text(encoding="utf-8"))


def test_pos_stacked_frontmatter_fires(tmp_path):
    """正控：连续两行 `---` ⇒ 必须报 + strict rc=1。"""
    rc, text, payload = _run(tmp_path, "pos", POS)
    assert "④ 叠置 frontmatter" in text, text
    assert rc == 1
    assert payload["stacked_frontmatter_count"] == 1


def test_neg_body_hr_not_flagged(tmp_path):
    """负控：正文里的水平线 `---` 不得误报。"""
    rc, text, payload = _run(tmp_path, "neg", NEG)
    assert "④ 叠置 frontmatter" not in text, text
    assert rc == 0
    assert payload["stacked_frontmatter_count"] == 0


def test_second_block_invisible_to_broken_targets(tmp_path):
    """盲区文档化：第二块里的失效 target **不会**被 ①b 捕到 —— 这正是 ④ 存在的原因。

    （若他日修好 `FM_BLOCK_RE` 使全部块可解析，本用例会失败 ⇒ 那是提示：
    可以撤掉 ④ 或改写为等价判据。）
    """
    rc, text, payload = _run(tmp_path, "blind", POS)
    assert payload["broken_targets_count"] == 0
    assert "①b 裸路径引用失效" not in text
