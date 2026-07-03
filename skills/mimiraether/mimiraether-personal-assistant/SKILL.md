# Mimir 个人助理 — 自动收口工作流

## 工作方式
用户告诉我任何事（计划、结果、想法、联系人、交易等），不需要用户指定分类，我自动判断该存到哪里。

## 三份数据文件（~/.mimiraether/data/）

| 文件 | 用途 | 触发关键词 |
|:----|:-----|:----------|
| `reminders.json` | 时间敏感的待办任务 | 时间/日期/明天/后天/几点/提醒我 |
| `stock_portfolio.json` | 股票持仓、买卖记录 | 股票/买入/卖出/持仓/行情/代码 |
| `personal_journal.json` | 其他一切（人、决策、随笔、偏好） | 上面两类之外的 |

## 自动分类规则（personal_journal.json）

```
提到人名+职务/公司 → category: "person"
提到"我决定/我想/我认为" → category: "decision"  
提到日常记事/观察 → category: "note"
提到未来计划（不带具体时间） → category: "event"
提到"我习惯/我喜欢/我不喜欢" → category: "preference"
技术分析/深度思考 → category: "insight"
```

## 查询方式
用户问任何相关问题时，先读对应文件，再组织回答。
不要问用户"这属于什么分类"——自己判断。

## 文件格式
### personal_journal.json
```json
{
  "version": 1,
  "entries": [
    {
      "timestamp": "ISO-8601",
      "category": "person|decision|note|event|insight|preference|other",
      "content": "内容",
      "related_to": ["相关实体"],
      "context": "会话上下文"
    }
  ]
}
```

## 注意事项
- 不要重复写入相同信息（写入前检查已有关键词匹配）
- 股票价格/数量信息必须精确记录（涉及真金白银）
- 联系人信息要包含全名+职务+公司+来源场景
