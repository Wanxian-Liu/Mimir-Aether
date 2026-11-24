# [DORMANT] powerpoint

**沉寂时间**: 2026-11-22T02:34:58.693972+00:00
**原始分类**: productivity
**描述**: Create, read, edit .pptx decks with python-pptx.
**触发阈值**: 60天未触碰

---

## 技能要点

# Powerpoint Skill

Create, inspect, and edit PowerPoint (.pptx) presentations using the
python-pptx library. Five helper scripts cover deck creation from a JSON
spec, structured read-back, in-place edits, template-driven brand decks,
and slide rendering — all offline, no PowerPoint installation required.

## When to Use

- The user asks to build a slide deck, report presentation, or pitch deck.
- You need to extract text, notes, tables, chart data, or images from a
  .pptx someone shared.
- You need to update an existing deck: replace text, refresh or patch
  chart data, swap a logo, duplicate/remove/reorder slides, set
  backgrounds, footers, hyperlinks, or speaker notes.
- You must produce an on-brand deck from a company .pptx template.
- Do NOT use this for .ppt (legacy binary) files — convert them first with
  `soffice --convert-to pptx old.ppt` if LibreOffice is available.

## Prerequisites

- Python 3.10+ with `python-pptx` installed
  (`pip install python-pptx`).
- Optional: LibreOffice (`soffice`) plus poppler (`pdftoppm` or
  `pdftocairo`) for rendering slides to PNGs and for PDF export.
  `pptx_render.py` detects both with `shutil.which` and degrades
  gracefully (reports `{"rendered": false, "missing": [...]}`, exit 0)
  when absent — all create/read/edit operations work without them.
- Check availability via `terminal`:
  `python -c "import pptx; print(pptx.__version__)"` and `which soffice pdftoppm`.

## How to Run

All scripts live in `scripts/`, take `--help`, print JSON to stdout, and
exit non-zero on failure. Run them with `terminal`:

```bash
python scripts/pptx_create.py deck.json out.pptx
python scripts/pptx_read.py deck.pptx --outline      # full JSON outline
python scripts/pptx_read.py deck.pptx --notes        # speaker notes
python scripts/pptx_read.py deck.pptx --images ./img # export pictures
python scripts/pptx_edit.py deck.pptx --replace-text "Old Corp" "New Corp"
python scripts/pptx_edit.py deck.pptx --chart-data update.json
python scrip

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("powerpoint")` 即可自动唤醒。
