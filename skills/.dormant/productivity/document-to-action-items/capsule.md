# [DORMANT] document-to-action-items

**沉寂时间**: 2026-11-22T02:34:59.038496+00:00
**原始分类**: productivity
**描述**: Extract cited obligations, deadlines, tasks from documents.
**触发阈值**: 60天未触碰

---

## 技能要点

# Document to Action Items

Turn documents into cited facts and proposed actions. Extraction is not legal advice, and low-confidence OCR or ambiguous language must remain visible. The `pdf` / `pdf` / `docx` skills own extraction mechanics; this skill owns what happens to the extracted content.

## When to Use

- "Extract deadlines and obligations from this contract."
- "Turn this report into tasks."
- "Read these scanned forms and structure the data."
- "Find risks, owners, and follow-ups in these attachments."

Don't use for: plain text extraction with no downstream structuring (load `pdf` directly).

## Procedure

### 1. Inventory the document set

Use `read_file` for local files and `web_extract` for URLs to identify files, versions, dates, page counts, language, scan quality, and the requested output schema. Detect duplicate/revised copies before analysis. Done when the authoritative or latest version is known or ambiguity is stated.

### 2. Extract with provenance

Load `pdf`, `pdf`, or `docx`. Extract text/tables while retaining file and page/section coordinates. For scans, record OCR confidence or visible quality issues. Done when every extracted field can cite its source location.

### 3. Classify evidence

Separate:

- parties/entities and identifiers
- dates and deadlines
- money/quantities
- obligations and prohibitions
- approvals and signatures
- risks/exceptions
- factual background
- ambiguous or unreadable clauses

Do not collapse "may," "should," and "must." Done when modality and uncertainty are preserved.

### 4. Validate internally

Cross-check dates, totals, repeated names, table sums, defined terms, and references to appendices. Surface contradictions rather than choosing silently. Done when key facts have consistency checks or explicit exceptions.

### 5. Convert to proposed actions

For each actionable obligation create outcome, owner if explicit, due date if explicit, dependency, acceptance condition, risk, and citation. Unknown owners/dates

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("document-to-action-items")` 即可自动唤醒。
