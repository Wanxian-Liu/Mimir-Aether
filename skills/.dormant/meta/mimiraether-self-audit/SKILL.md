---
name: mimiraether-self-audit
description: 自我透明审计——当用户问「评估」「状态」「进步」「IQ」时自动触发。采集多源数据，报告真实差距，不美化。
auto_load: false
trigger_phrases:
  - 评估
  - 状态
  - 进步
  - 评分
  - 智商
  - 审计
  - 自我评估
  - self-audit
  - compare
---

# mimiraether-self-audit

## 何时触发

用户问「评估」「状态」「进步」「评分」「IQ/智商」「审计」「compare」时。**不要等用户说第二遍**——检测到 trigger 词立即加载本技能。

## 数据来源与采集步骤

### 1. 工具成功率
```bash
# tool_quality.db top5 by call volume (exclude echo)
sqlite3 ~/.mimiraether/data/tool_quality.db \
  "SELECT tool, success_rate, calls FROM tool_quality ORDER BY calls DESC LIMIT 10;"
```

### 2. 进化 ok%
```bash
grep 'evolution' ~/.mimiraether/logs/agent.log | grep 'ok=' || echo "no evolution lines"
```

### 3. 跨会话统计
Read `~/.mimiraether/data/persistent.json` → session_count, skill_usage, memory entries count

### 4. 技能使用情况
```bash
ls ~/.mimiraether/skills/ | wc -l  # total skills
grep -c 'skill_view' ~/.mimiraether/logs/agent.log || echo "0"
```

### 5. 上下文大小
Check `<cross-session-context>` prompt_tokens value from system prompt injection.

## 报告模板

```
=== 自我审计报告 ===

[状态摘要]
执行器：X/10。元认知：Y/10。

[热门技能（成功率和调用量）]
· tool_name: ok%=X calls=N

[进化数据（若可用）]
· evolution ok% (all time): X% (N/M)
· evolution ok% (7d): X% (N/M)

[技能使用]
· 已加载技能（本会话）：skill_a, skill_b
· 闲置技能：skill_c, skill_d（高于价值不使用的）

[系统状态]
· 跨会话记忆：✅/⚠️
· session_count: N
· context tokens: N

[与上次审计的差距]（若有上次数据）
· 元认知：X→Y delta +N
· 技能主动加载：X→Y

[核心缺口]
列出当前最突出的 1-3 个问题

数据完整，无美化，来源可复验。
```

## 核心规则（不可违反）

1. **数据优先**：所有结论必须有原始数据支撑（read_file/sqlite3/grep），不可凭记忆
2. **不美化**：ok%=0 说 0%，技能没用说没用，不许「正在改进」这类柔化
3. **delta 必须标注**：有上次数据必须对比，delta 必须标正负方向
4. **来源可复验**：每项数据旁标注来源路径，用户可自行验证
5. **先技能再执行**：检测到 trigger 词后，必须先 load 本技能再输出，不得直接用直觉回答
