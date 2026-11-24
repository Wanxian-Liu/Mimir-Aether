# [DORMANT] product-price-monitor

**沉寂时间**: 2026-11-22T02:34:58.744729+00:00
**原始分类**: productivity
**描述**: Watch product, flight, or listing prices; alert on target.
**触发阈值**: 60天未触碰

---

## 技能要点

# Product Price Monitor

Monitor a concrete purchasable item and alert on a normalized all-in price or availability condition. Handle variants, taxes, fees, currencies, stock, cancellation terms, and duplicate alerts explicitly. Setup runs once in the foreground; the recurring check runs as a `cronjob` tick (the `price-watch` automation blueprint scaffolds this).

## When to Use

- "Alert me when this laptop drops below $1,000."
- "Watch these flights for a fare under $500."
- "Tell me when this hotel has a refundable room."
- "Track ticket/listing availability."
- A cron tick fires for an existing price watch (steps 4-6).

Don't use for: one-off "what does this cost right now" lookups (use `web_search`/`web_extract` directly).

## Procedure — Setup (foreground, once)

### 1. Define the exact item

Record source URL/provider, product/listing ID where available, variant, quantity, location, dates, travelers/guests, membership/login assumptions, condition, seller, and acceptable substitutes. Done when two variants cannot be confused.

### 2. Define the alert condition

Specify currency, all-in vs pre-tax price, maximum price, availability/stock rule, shipping, refundability, cabin/room/ticket class, cooldown, and notification destination. Done when synthetic examples have deterministic alert decisions.

### 3. Establish a live baseline, then schedule

Fetch a bounded live result with `web_extract` or `browser_navigate` and record retrieval time, source price, fees/taxes, availability, and terms. Do not schedule until one foreground fetch works. Write the watch contract (item, condition, baseline observation) to a state file under `~/.hermes/price-watches/<watch-slug>.json`, then create the job:

```
cronjob(action="create",
        schedule="every 6h",
        prompt="Load the product-price-monitor skill and run the tick for the watch contract at ~/.hermes/price-watches/<watch-slug>.json.",
        deliver=<user's destination>)
```

Pick a cadence that respects rate l

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("product-price-monitor")` 即可自动唤醒。
