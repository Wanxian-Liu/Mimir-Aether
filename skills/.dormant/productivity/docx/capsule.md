# [DORMANT] docx

**沉寂时间**: 2026-11-22T02:34:58.537870+00:00
**原始分类**: productivity
**描述**: Create, read, edit, template, and review Word .docx files.
**触发阈值**: 60天未触碰

---

## 技能要点

# Docx Skill

Create, read, edit, and template Microsoft Word `.docx` files with
python-docx via small CLIs. It handles text, styles, lists, tables,
images, headers/footers, `{{token}}` templating, tracked changes
(list/accept/reject), comments (list/add/delete), TOC and page-number
fields, and package health checks. It does not render documents itself
(PDF needs LibreOffice — see Converting to PDF) or edit legacy `.doc`.

## When to Use

- The user asks to generate a Word document (report, letter, contract).
- You need the text, outline, styles, or embedded images of a `.docx`.
- You must change an existing `.docx`: replace text, edit table cells,
  insert/delete paragraphs, apply styles, merge fragmented runs.
- You have a `.docx` template with `{{placeholders}}` to fill from data.
- The document has tracked changes to review, accept, or reject.
- You need to read reviewers' comments, or add/delete comments.
- A `.docx` won't open or behaves oddly and you need corruption triage.
- The document needs a table of contents or "Page X of Y" footers.
- Not for: `.doc` (legacy), `.odt`, or WYSIWYG layout work.

## Prerequisites

- Python 3.10+ with `python-docx` installed:
  `pip install python-docx` (import name is `docx`; lxml comes with it).
- Comments `add` uses the native API on python-docx >= 1.2 and an XML
  fallback on older versions — both are automatic.
- For image blocks: the image files must exist locally (PNG/JPEG).

## How to Run

All helpers live in `scripts/` next to this file. Run them with the
`terminal` tool; each supports `--help` and prints JSON to stdout.

```bash
python scripts/docx_create.py spec.json out.docx
python scripts/docx_read.py out.docx --text
python scripts/docx_edit.py replace out.docx --find old --replace new
python scripts/docx_template.py tpl.docx values.json filled.docx
python scripts/docx_revisions.py list out.docx
python scripts/docx_comments.py list out.docx
python scripts/docx_validate.py out.docx
```

## Quick Reference

| Tas

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("docx")` 即可自动唤醒。
