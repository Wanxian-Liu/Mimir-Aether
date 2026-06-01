# IQ-33: D 与 preemptive 契约测

## 做了什么

设计稿。**Cursor 实现** — 写契约测试验证：当 `search_first_guard` / `preemptive session_search` 已满足时，`intent_predictor` 和 `world_model_spike` 不重复注入相同上下文。

## 为何

IQ-31（WM B4 接线）+ IQ-32（intent fallback 增强）上线后，agent 可能同时收到来自 **preemptive search**、**intent_predictor**、**world_model_spike** 三方的类似建议（如 "search first before answering"）。这会导致上下文膨胀和 nudge 疲劳。

契约测确保这三者**不会叠加**产生重复指导。

## 风险

🟢 低 — 纯测试添加，不改生产代码。

## 建议 commit message

```
test: IQ-33 preemptive+recall 不重复注入测试
```
