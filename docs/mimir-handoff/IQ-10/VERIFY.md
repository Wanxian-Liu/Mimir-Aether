# IQ-10 验证

## tier0

```text
677 passed, 4 failed (pre-existing cross_session_retrieval L2/L3)
```

与基线一致，无新失败。

## 规则注入验证

```bash
rg '必须先 session_search' agent/prompt_builder.py
```

输出：
```
226:    "历史/确认/检查/还记得/上次/之前：回答正文前必须先 session_search（已有程序化 prefetch 时仍须尊重检索结果，不得凭记忆瞎编）。"
```
