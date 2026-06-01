# IQ-32: D intent fallback（置信度 < 0.5 弱提示）

## 做了什么

设计稿。**Cursor 实现** — 当 `intent_predictor.predict()` 返回 `confidence < 0.5` 时，`build_intent_context_block` 输出**精简版 intent-context**，避免弱判断误导 agent。

## 为何

当前 `build_intent_context_block` 无论置信度高低，都注入完整提示（含 "Grounded task: use tools" / "Prefer session_search" 等强指导）。当置信度低（如 `general` 类 0.4、空消息 0.3）时，这些强指导可能导致 agent 做不恰当的工具调用。

刘哥拍板 D=**增强 MVP**，不是重写，不是上 LLM 分类器。

## 风险

🟢 低 — 仅在 `confidence < 0.5` 时弱化提示，不改变预测逻辑、不引入新依赖。回滚：改阈值或改一行代码。

## 建议 commit message

```
feat: IQ-32 intent fallback — confidence < 0.5 输出精简提示
```
