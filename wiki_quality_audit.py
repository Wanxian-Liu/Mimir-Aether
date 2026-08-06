#!/usr/bin/env python3
"""Wiki Quality Audit — 10 parallel subagents, each checking one dimension across 12 cards.

Usage: python ~/src/MimirAether/wiki_quality_audit.py
Output: ~/wiki/reports/quality-audit-20260730.md
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subagent_bridge import spawn_multi

WIKI = os.path.expanduser("~/wiki/concepts")
REPORT = os.path.expanduser("~/wiki/reports/quality-audit-20260730.md")

# ── Gather all cards ──
cards = sorted([f for f in os.listdir(WIKI) if f.endswith(".md")])
total_cards = len(cards)
cards_per_agent = (total_cards + 9) // 10  # 12 each for ~120 cards

print(f"Total cards: {total_cards} | Cards/agent: {cards_per_agent} | Agents: 10")

# ── 10 dimensions × 10 subagent groups ──
dimensions = [
    # 1. File size — check for stubs/empty cards
    ("file_size", f"Run stat --format='%s %n' on each of these 12 wiki files (one per line). Report any file under 500 bytes with its size. Respond with JSON: {{'dimension':'file_size','total':12,'issues':[{{'file':'...','bytes':N,'severity':'stub'}}],'stubs_under_500':0,'stubs_under_200':0,'largest_bytes':0,'avg_bytes':0,'note':'...'}}"),

    # 2. Frontmatter — check for metadata headers
    ("frontmatter", f"Run head -10 on each of these 12 wiki files. Check if each has proper YAML frontmatter (--- at line 1, closing ---, with date/tags/title). Report any without frontmatter. Respond with JSON: {{'dimension':'frontmatter','total':12,'issues':[{{'file':'...','problem':'...'}}],'has_frontmatter':0,'no_frontmatter':0,'has_tags':0,'note':'...'}}"),

    # 3. Headings — check valid markdown structure
    ("headings", f"Run grep -c '^##' on each of these 12 wiki files. Report any file with 0 headings or malformed structure. Respond with JSON: {{'dimension':'headings','total':12,'issues':[{{'file':'...','heading_count':N,'problem':'no headings'}}],'no_headings':0,'single_heading_only':0,'avg_headings':0,'note':'...'}}"),

    # 4. Word count — content depth
    ("word_count", f"Run wc -w on each of these 12 wiki files. Report any under 50 words or over 2000 words. Respond with JSON: {{'dimension':'word_count','total':12,'issues':[{{'file':'...','words':N,'severity':'too_short'}}],'under_50':0,'over_2000':0,'avg_words':0,'min_words':0,'max_words':0,'note':'...'}}"),

    # 5. Links — check internal wiki links ([[...]] or relative paths)
    ("links", f"Run grep -c '\\[\\[' on each of these 12 wiki files for wikilinks, and grep -c '(\\\\.\\./' for relative links. Report files with 0 internal links. Respond with JSON: {{'dimension':'links','total':12,'issues':[{{'file':'...','wikilinks':0}}],'no_links':0,'has_wikilinks':0,'avg_wikilinks':0,'note':'...'}}"),

    # 6. References — check for citations/URLs/arXiv refs
    ("references", f"Run grep -cP 'https?://|arxiv|doi:|\\\\[\\\\d+\\\\]' on each of these 12 wiki files. Report files with 0 external references. Respond with JSON: {{'dimension':'references','total':12,'issues':[{{'file':'...','refs':0}}],'no_refs':0,'has_refs':0,'avg_refs':0,'note':'...'}}"),

    # 7. Duplicates — find cards with similar names or redirect markers
    ("duplicates", f"For these 12 wiki files, check their basenames for near-duplicates (e.g., 'foo-bar.md' vs 'foo_bar.md' vs 'foo%20bar.md'). Use ls and diff. Report any suspected duplicates with actual file names and sizes. Respond with JSON: {{'dimension':'duplicates','total':12,'issues':[{{'file1':'...','file2':'...','reason':'near-identical name'}}],'suspected_dupes':0,'note':'...'}}"),

    # 8. Freshness — last modified date
    ("freshness", f"Run stat --format='%Y %n' on each of these 12 wiki files. Report any file not modified in 90+ days. Respond with JSON: {{'dimension':'freshness','total':12,'issues':[{{'file':'...','last_modified_days_ago':N}}],'stale_90plus':0,'stale_180plus':0,'avg_days_since_mod':0,'newest_card':'...','oldest_card':'...','note':'...'}}"),

    # 9. Structure — proper sections (at least intro + body)
    ("structure", f"For each of these 12 wiki files, check: does it have 2+ sections? Does it have a proper intro paragraph (not just a heading)? Count blank lines as structure markers. Respond with JSON: {{'dimension':'structure','total':12,'issues':[{{'file':'...','sections':1,'problem':'single-section'}}],'single_section':0,'multi_section':0,'has_intro':0,'no_intro':0,'note':'...'}}"),

    # 10. Tags — check for tag presence and format
    ("tags", f"Run grep -i 'tags:' on each of these 12 wiki files. Report files without tags or with malformed tag format. Respond with JSON: {{'dimension':'tags','total':12,'issues':[{{'file':'...','problem':'no tags found'}}],'no_tags':0,'has_tags':0,'malformed_tags':0,'note':'...'}}"),
]

# ── Build task prompts — each agent gets 12 cards ──
tasks = []
for i, (dim_name, dim_template) in enumerate(dimensions):
    start = i * cards_per_agent
    end = min(start + cards_per_agent, total_cards)
    agent_cards = cards[start:end]
    if not agent_cards:
        break
    
    card_lines = "\n".join(f"  {WIKI}/{c}" for c in agent_cards)
    prompt = dim_template.replace("these 12 wiki files (one per line)", f"the following files:\n{card_lines}")
    # Also replace "these 12" occurrences
    prompt = prompt.replace("these 12 wiki files", f"the following {len(agent_cards)} files")
    
    tasks.append({
        "type": "Explore",
        "prompt": prompt,
        "model": "deepseek/deepseek-v4-flash",
        "tools_list": ["bash", "read", "grep", "find", "ls"],
    })

print(f"\nSpawning {len(tasks)} parallel subagents...")
start_time = time.time()

# ── Run ──
results = spawn_multi(tasks, parallel=True)

elapsed = time.time() - start_time
print(f"All {len(results)} agents completed in {elapsed:.1f}s (parallel)")

# ── Aggregate & write report ──
os.makedirs(os.path.dirname(REPORT), exist_ok=True)

lines = [
    "# Wiki Quality Audit — 2026-07-30",
    f"",
    f"**Total cards:** {total_cards}",
    f"**Subagents:** {len(results)} (parallel via `spawn_multi()`)",
    f"**Dimensions:** file_size, frontmatter, headings, word_count, links, references, duplicates, freshness, structure, tags",
    f"**Elapsed:** {elapsed:.1f}s",
    f"**Model:** deepseek/deepseek-v4-flash (Explore)",
    f"**Bridge:** `subagent_bridge.py` → `spawn_multi()` → `asyncio.gather(*N_tasks)`",
    f"",
    f"## Per-Dimension Results",
    f"",
]

total_issues = 0
dimension_summaries = []

for i, (dim_name, _) in enumerate(dimensions[:len(results)]):
    result = results[i]
    lines.append(f"### {i+1}. {dim_name}")
    lines.append(f"")
    lines.append(f"- **Status:** {'✅ success' if result.success else '❌ FAILED'}")
    lines.append(f"- **Exit code:** {result.exit_code}")
    
    if result.success and result.stdout:
        # Try to parse JSON from stdout
        try:
            # Find JSON in output (pi may add conversational text)
            stdout = result.stdout
            json_start = stdout.find('{')
            json_end = stdout.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(stdout[json_start:json_end])
                dim_summary = {
                    "dimension": data.get("dimension", dim_name),
                    "total": data.get("total", 0),
                    "issues_count": len(data.get("issues", [])),
                    "note": data.get("note", ""),
                }
                dimension_summaries.append(dim_summary)
                lines.append(f"- **Cards checked:** {dim_summary['total']}")
                lines.append(f"- **Issues found:** {dim_summary['issues_count']}")
                if dim_summary['note']:
                    lines.append(f"- **Note:** {dim_summary['note']}")
                total_issues += dim_summary['issues_count']
                
                # Top issues
                issues = data.get("issues", [])
                for issue in issues[:5]:
                    file = issue.get("file", "?")
                    problem = issue.get("problem") or str({k:v for k,v in issue.items() if k != "file"})
                    lines.append(f"  - `{file}`: {problem}")
                if len(issues) > 5:
                    lines.append(f"  - ... and {len(issues)-5} more")
            else:
                lines.append(f"- **Raw output:** (no JSON found in response)")
                # Show first 300 chars
                lines.append(f"```\n{stdout[:300]}\n```")
        except json.JSONDecodeError:
            lines.append(f"- **Parse error:** could not decode JSON")
            lines.append(f"```\n{result.stdout[:200]}\n```")
    else:
        lines.append(f"- **Stderr:** {result.stderr[:200] if result.stderr else 'none'}")
        if result.error:
            lines.append(f"- **Error:** {result.error}")
    
    lines.append(f"")

# ── Summary table ──
lines.append(f"## Summary")
lines.append(f"")
lines.append(f"| # | Dimension | Cards | Issues | Status |")
lines.append(f"|:-:|:----------|:-----:|:------:|:------:|")
for ds in dimension_summaries:
    status_icon = "✅" if ds["issues_count"] == 0 else "⚠️" if ds["issues_count"] <= 3 else "🔴"
    lines.append(f"| {dimension_summaries.index(ds)+1} | {ds['dimension']} | {ds['total']} | {ds['issues_count']} | {status_icon} |")
lines.append(f"")
lines.append(f"**Total issues across all dimensions:** {total_issues}")
lines.append(f"")
lines.append(f"## Meta")
lines.append(f"")
lines.append(f"- **Bridge version:** `spawn_multi()` via `asyncio.gather()` — true N-way parallel")
lines.append(f"- **AGENTS.md §2:** N subagents, no 2-agent limit")
lines.append(f"- **Generated:** 2026-07-30T{time.strftime('%H:%M:%S')} UTC+8")

content = "\n".join(lines)
with open(REPORT, "w") as f:
    f.write(content)

print(f"\nReport written to {REPORT} ({len(content)} bytes)")
print(f"Total issues: {total_issues}")
