# IQ-34: P1 handoff 汇总 tier0

## 做了什么

汇总三个 handoff（IQ-31、IQ-32、IQ-33）的实现指引，Cursor 在同一 PR 中：

1. **IQ-31** — WM B4 预测器接 agent_loop（~+20 行）
2. **IQ-32** — intent fallback 置信度 < 0.5 弱提示（~+5 行 + ~10 行测试）
3. **IQ-33** — preemptive/recall 不重复契约测（~+40 行测试）

## 为何

三粒都是 P1 级、无相互阻塞、代码改动小且不重叠，适合 Cursor 一次合入。tier0 验证一次到位。

## 风险

🟡 中 — 三个改动并行合入，若某个失败需回溯。解决方案是 IQ-31/32/33 各有一个独立的 VERIFY.md，可单独回滚。

## 建议 commit message

```
feat: IQ-31/32/33 P1 汇总 — WM 预测器接线 + intent fallback + 契约测
```
