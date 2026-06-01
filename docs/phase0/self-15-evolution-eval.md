# SELF-15: Evolution Eval

> Generated: 2026-06-01T08:51Z

---

## 指标

| 指标 | 值 | 来源 |
|------|----|------|
| evolution ok% (7d) | **0.0%** (0/11) | iq-p3-baseline.json |
| 有效 session (7d) | 10 | 同上 |
| evolution_log 条目 | 4 SELF entries (exit=0) | evolution_log.md |
| `MIMIR_AUTO_EVOLVE` | `1` (显式配置) | `~/.mimiraether/.env` |

## 分析

Evolution 流水线可跑（`ok=1` 本飞书会话中已触发 2 次），但生产 session 的 `ok=0` 率为 100%。根因与 EVO-12 一致：需要真实带 errors 的 close 才有进化样本进入流水线。

## 下一步

- SELF-17 的 closeout 文档将基于本数据
- 长期需增加有效进化样本（更多错误场景、更频繁的 post-close analysis 触发）
