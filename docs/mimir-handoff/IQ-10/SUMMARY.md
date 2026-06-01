# IQ-10: A prompt 硬规则

## 做了什么

在 `agent/prompt_builder.py` 的 `IQ_EVOLUTION_DIRECTION_GUIDANCE` 追加一条硬规则：

```
历史/确认/检查/还记得/上次/之前：回答正文前必须先 session_search
（已有程序化 prefetch 时仍须尊重检索结果，不得凭记忆瞎编）。
```

## 为何

刘哥拍板 A=开。已有 `SESSION_SEARCH_GUIDANCE`（line 112-124）但偏软性指导。
本条注入 IQ 方向段，与 4.9→5.2 提升目标对齐，强调禁止凭记忆瞎编。

## 风险

🟢 低 — 纯 prompt 追加，不影响现有逻辑；可逆（删一行即可）。

## 建议 commit message

```
feat: IQ-10 A prompt 先搜再答硬规则
```
