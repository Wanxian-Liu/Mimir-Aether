# [DORMANT] airtable

**沉寂时间**: 2026-11-22T02:34:58.429758+00:00
**原始分类**: productivity
**描述**: Airtable REST API via curl. Records CRUD, filters, upserts.
**触发阈值**: 60天未触碰

---

## 技能要点

# Airtable — Bases, Tables & Records

Work with Airtable's REST API directly via `curl` using the `terminal` tool. No MCP server, no OAuth flow, no Python SDK — just `curl` and a personal access token.

## Prerequisites

1. Create a **Personal Access Token (PAT)** at https://airtable.com/create/tokens (tokens start with `pat...`).
2. Grant these scopes (minimum):
   - `data.records:read` — read rows
   - `data.records:write` — create / update / delete rows
   - `schema.bases:read` — list bases and tables
3. **Important:** in the same token UI, add each base you want to access to the token's **Access** list. PATs are scoped per-base — a valid token on the wrong base returns `403`.
4. Store the token in `${HERMES_HOME:-~/.hermes}/.env` (or via `hermes setup`):
   ```
   AIRTABLE_API_KEY=pat_your_token_here
   ```

> Note: legacy `key...` API keys were deprecated Feb 2024. Only PATs and OAuth tokens work now.

## API Basics

- **Endpoint:** `https://api.airtable.com/v0`
- **Auth header:** `Authorization: Bearer $AIRTABLE_API_KEY`
- **All requests** use JSON (`Content-Type: application/json` for any POST/PATCH/PUT body).
- **Object IDs:** bases `app...`, tables `tbl...`, records `rec...`, fields `fld...`. IDs never change; names can. Prefer IDs in automations.
- **Rate limit:** 5 requests/sec/base. `429` → back off. Burst on a single base will be throttled.

Base curl pattern:
```bash
curl -s "https://api.airtable.com/v0/$BASE_ID/$TABLE?maxRecords=5" \
  -H "Authorization: Bearer $AIRTABLE_API_KEY" | python -m json.tool
```

`-s` suppresses curl's progress bar — keep it set for every call so the tool output stays clean for Hermes. Pipe through `python -m json.tool` (always present) or `jq` (if installed) for readable JSON.

## Field Types (request body shapes)

| Field type | Write shape |
|---|---|
| Single line text | `"Name": "hello"` |
| Long text | `"Notes": "multi\nline"` |
| Number | `"Score": 42` |
| Checkbox | `"Done": true` |
| Single select | `"Status": "Todo

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("airtable")` 即可自动唤醒。
