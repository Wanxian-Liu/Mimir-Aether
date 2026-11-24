# [DORMANT] competitor-news-monitor

**沉寂时间**: 2026-11-22T02:34:59.551331+00:00
**原始分类**: research
**描述**: Watch named companies for material news; cited digests.
**触发阈值**: 60天未触碰

---

## 技能要点

# Competitor News Monitor

Track a declared company set and report only material, new developments with primary-source evidence. This is not a generic page-diff watcher: it applies company-news categories, source hierarchy, event deduplication, and business significance. Setup runs once in the foreground; the recurring check runs as a `cronjob` tick (the `competitor-watch` automation blueprint scaffolds this).

## When to Use

- "Monitor these competitors weekly."
- "Tell me when Company X changes pricing or launches a product."
- "Create a competitor intelligence digest."
- "Track funding, partnerships, executive moves, and incidents."
- A cron tick fires for an existing competitor watch (steps 3-6).

Don't use for: one-off company research (use `web_search`/`web_extract` directly) or plain feed reading (`blogwatcher`).

## Procedure — Setup (foreground, once)

### 1. Freeze the watchlist

Record canonical company names, domains, products, aliases, geography/language, event categories, cadence, audience, and materiality threshold. Done when a candidate article can be accepted or rejected consistently.

### 2. Build source coverage, then schedule

For each company include, where available:

1. official newsroom/blog and changelog
2. pricing/product pages
3. regulatory filings and investor relations
4. status/security pages
5. reputable trade and financial press
6. job postings as weak supporting evidence

Use `rss-feeds` (optional) or `blogwatcher` (optional, stateful) for feeds, `reddit-reading` for community discussion, and `web_search`/`web_extract` for pages. Write the watch contract (watchlist, categories, materiality threshold, last cutoff) to a state file under `~/.hermes/competitor-watches/<watch-slug>.json`, then create the job:

```
cronjob(action="create",
        schedule="every monday 9am",
        prompt="Load the competitor-news-monitor skill and run the tick for the watch contract at ~/.hermes/competitor-watches/<watch-slug>.json.",
        deliver=<

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("competitor-news-monitor")` 即可自动唤醒。
