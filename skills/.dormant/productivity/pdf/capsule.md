# [DORMANT] pdf

**沉寂时间**: 2026-11-22T02:34:59.084743+00:00
**原始分类**: productivity
**描述**: PDF files: create, read, merge, fill, OCR, edit text.
**触发阈值**: 60天未触碰

---

## 技能要点

# PDF Skill

Create PDFs from structured specs, build and fill AcroForm forms (with layout linting and visual overlays), extract text/tables/metadata, merge/split/rotate/watermark/stamp pages, export page images, manage metadata and attachments, and encrypt/decrypt — using pypdf, reportlab, and pdfplumber. Two absorbed capabilities live in references/ (read the matching file before those tasks):

- **Scanned/image-only PDFs and OCR** (pymupdf fast path, marker-pdf quality path, scripts/extract_pymupdf.py + scripts/extract_marker.py): `references/ocr-extraction.md`
- **Editing text inside an existing PDF via natural-language prompts** (nano-pdf CLI): `references/nano-pdf-editing.md`

## When to Use

- Generate a report, invoice, or multi-page document as PDF.
- Build a fillable AcroForm (text/checkbox/radio/dropdown) from a JSON spec, linting the layout first.
- Pull text, tables (JSON/CSV), metadata, or form-field values out of a PDF.
- Merge, split, rotate, extract page subsets, watermark, stamp text/images at coordinates, bookmark, or compress PDFs.
- Export pages as PNGs for visual review or for OCR hand-off; set/clear document metadata; add/extract file attachments.
- Fill or flatten AcroForm forms; encrypt or decrypt with passwords.
- NOT for scanned/image-only PDFs (use `references/ocr-extraction.md`) and NOT for pixel-perfect HTML-to-PDF rendering (use a headless browser).

## Prerequisites

- Python 3.10+ with `pypdf`, `reportlab`, `pdfplumber`:
  `python -m pip install pypdf reportlab pdfplumber`
- Optional, for page rasterization (`pdf_page_image.py`, overlay rendering): `python -m pip install pypdfium2`, or poppler's `pdftoppm` on PATH. Scripts fall back pypdfium2 → pdftoppm and report `{"rendered": false, "missing": [...]}` (exit 0) when neither exists.
- Each helper script checks imports lazily and prints an install hint if a dependency is missing.

## How to Run

All helpers live in `scripts/` and are argparse CLIs — run them with the `terminal` tool; 

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("pdf")` 即可自动唤醒。
