# [DORMANT] xlsx

**沉寂时间**: 2026-11-22T02:34:58.844328+00:00
**原始分类**: productivity
**描述**: Create, read, edit Excel .xlsx workbooks and CSVs.
**触发阈值**: 60天未触碰

---

## 技能要点

# Xlsx Skill

Work with Excel .xlsx workbooks using Python and openpyxl: build styled
multi-sheet workbooks with formulas and charts, inspect or dump existing
files, edit cells and structure, and convert to/from CSV. All helper
scripts are argparse CLIs that print JSON and use explicit UTF-8 I/O.

## When to Use

- Creating .xlsx reports: multiple sheets, number formats, styling,
  merged cells, freeze panes, autofilter, conditional formatting,
  charts, data-validation dropdowns, native Excel tables, defined
  names, hyperlinks, cell notes, sheet protection.
- Reading a workbook: sheet inventory, dumping data as JSON or CSV,
  listing formulas vs cached values, notes, defined names, tables.
- Editing existing files: set cells, append rows, insert/delete
  rows/columns (reference-aware via `xlsx_restructure.py`),
  copy/rename sheets, tables, names, notes, protection.
- Recalculating formulas headlessly via LibreOffice
  (`xlsx_recalc.py`).
- CSV interop with type inference and non-UTF-8 encodings.
- Not for the legacy .xls binary format (use LibreOffice to convert
  first: `soffice --headless --convert-to xlsx old.xls`).

## Prerequisites

- Python 3.10+ with `openpyxl` (`pip install openpyxl`). No other
  third-party packages are needed; everything else is stdlib.
- Optional: LibreOffice (`soffice`) for headless recalculation or
  format conversion.

## How to Run

Run the helper scripts with the `terminal` tool from this skill's
`scripts/` directory (every script supports `--help`):

```bash
python scripts/xlsx_create.py spec.json report.xlsx   # build from JSON spec
python scripts/xlsx_read.py report.xlsx --sheets      # inventory
python scripts/xlsx_read.py report.xlsx --json --sheet Data
python scripts/xlsx_read.py report.xlsx --formulas
python scripts/xlsx_edit.py report.xlsx --sheet Data --set B2=42 --recalc
python scripts/xlsx_restructure.py report.xlsx --sheet Data --insert-rows 3:2
python scripts/xlsx_recalc.py report.xlsx
python scripts/csv_to_xlsx.py da

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("xlsx")` 即可自动唤醒。
