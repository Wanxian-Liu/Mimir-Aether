---
name: mimiraether-tool-aci-audit
description: 工具面 ACI（Agent-Computer Interface）自查流程——以本轮真实误用为样本、用受控双探针验工具自身认知、按 P0-P3 分级出提案。触发词：ACI/工具自查/工具面审计/Building Effective Agents/B1/工具体验/报错信息/参数设计。
auto_load: false
---

# 工具面 ACI 自查（Anthropic Appendix 2 落地版）

## 何时用

- 收到"对照某方法论自查工具面"类指派（如 B1《Building Effective Agents》）
- 连续两次以上被同一个工具/闸门拦下或误导出错判
- 要动工具 schema / 报错信息 / 安全闸之前（先有证据面再改）

**判据来自官方 Appendix 2（"Prompt engineering your tools"）**：① 站在模型的鞋里 ② 错误要**可操作**（agent 能读着修）③ 参数名/描述对 LLM 直觉友好 ④ **在工作台实测模型怎么误用** ⑤ **poka-yoke：改参数让犯错更难**。

## 核心纪律（三条，缺一条审计就退化成"我感觉")

1. **样本必须来自本轮真实误用**，不是设想"可能会错"。写法：现象（原样报文）/ 证据（file:line 或实测返回）/ 根因 / 建议 / P 级。
2. **"工具自身认知"要受控双探针**：正样本（存在的对象 + 不可能存在的锚点）vs 负对照（不存在的对象）。两者报错**可区分**才算工具健康；可分不清就是真缺口。参考 `mimiraether-probe-attestation`。
3. **改工具前先分清"文档纪律"与"机械护栏"**：只写在 AGENTS.md/SKILL.md 里的规则 = 靠意志；能在**参数/工具层**拦下的才是 poka-yoke。凡有历史事故（≥2 次）的纪律，都该升级成护栏。

## 流程

1. **取样本**：回看本轮会话里每一次工具报错/静默空结果/需要绕行的动作（terminal 拦、白名单拦、0 命中、脱敏 `***`、工具间认知冲突）。
2. **取证到 file:line**：报错字符串往往硬编码（`search_files` → `"Blocked by command guard"` / whitelist → `agent/exec_mixin.py`），grep 到源头才算定位。
3. **分类**：文档缺口（描述缺 example/edge case）/ 错误不可操作（没说怎么办）/ 命名空间错（报错指错子系统）/ 粒度错（整串判定 vs token 判定）/ 护栏缺位（该机械化却在文档里）/ 输出歧义（脱敏、截断、口径混用）/ 工具间不一致（同一对象两个写路径、方向相反）。
4. **分级**（对齐我方惯例）：
   - **P0**：会导致**错误结论**或事故复发（如脱敏致"有/无"不可分、共享文件可整卡覆盖）
   - **P1**：会**阻塞调查动作**或训练 agent 绕行（如只读 grep 被安全闸整批拦、白名单与身份边界反向）
   - **P2**：可恢复但靠先验知识（报错不含允许值/逃生口、0 结果无提示）
   - **P3**：体验优化（schema 缺 example）
5. **改与不改分开写**：能当场做且**不触发重启**的（技能/文档订正）就地做完 + grep 验证；涉及工具代码（需重启 gateway / 影响他方行为面）**只出提案 + 证据 + 逃生参数**，进待裁。
6. **留正面样板**：不只报坏消息——找出"官方推荐形状"的既有实现（如空 pattern 硬闸 + Example hint；大文件 handle + `Use offset=N to continue`），建议其余分支照此对齐。

## 已知坑（都踩过）

- **长报告分块写**：`write_file`/`patch` 载荷过大或超过 ~2KB 易 "Invalid JSON: Unterminated string" → 用末尾句作锚点分块 patch 追加。
- **`skill_manage` 写 repo 侧**（`~/src/MimirAether/skills/...`），home 侧 `~/.mimiraether/skills/...` 需另行同步；**同步前先 `grep -c 关键串` 判侧**，盲 cp 会抹掉自己的改动；改完双侧各 grep 一次（md5 相等只证明"两侧一样"）。
- **`terminal` 里有整串安全扫描**：命令参数中**出现被禁字面量**（如 `python3 -c`、`eval(`）即整条命令被拒，且报错前缀误写成 "Blocked by path whitelist"。⇒ 审计这类闸时**不要在命令里复述被禁字面量**，用 `search_files`/`read_file` 取证。
- **execute_code 沙箱 `~` = `$MIMIR_AETHER_HOME`**（与 terminal 不同）→ 一概用绝对路径。
- **不要写时间戳**：报告用 git/mtime 记录真实时间。

## 交付形状

- 全文落 `~/.mimiraether/notes/<date>-<主题>-ACI 自查.md`（含 file:line 证据 + 可复跑探针段）
- 讨论卡追加**摘要 + 待裁**（patch 追加，禁整卡覆盖），全文用路径指过去
- 给上游/伙伴的建议写成"候选增量 + 理由"，不替对方改他的 skill
