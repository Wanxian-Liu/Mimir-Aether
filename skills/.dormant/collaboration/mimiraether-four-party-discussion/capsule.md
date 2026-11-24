# [DORMANT] mimiraether-four-party-discussion

**沉寂时间**: 2026-11-22T02:34:57.765661+00:00
**原始分类**: collaboration
**描述**: 四方讨论卡应答流程——读卡、领角色、调研、patch追加本段、验证落盘。用于 ~/wiki/discussions/ 下的四方讨论任务（Hermes/刘哥在飞书发任务消息时）。
**触发阈值**: 60天未触碰

---

## 技能要点

# 四方讨论卡应答

## 触发条件
- 飞书收到四方讨论任务消息（含"新任务/读X并输出到Y/落盘/写你的段"）
- 消息指向 `~/wiki/discussions/*.md` 讨论卡

## 流程（5步）

1. **读卡**：`read_file` 讨论卡全文。注意 `frontmatter`（议题/轮次/角色）与 `### 名字` 段落结构。
2. **领角色**：读 `~/wiki/entities/Agency-Agent角色索引.md`，从316库选贴题临时角色（避免与已认领角色重复），格式 `### Mimir（泉·我）——[本任务角色: X + Y（临时套用）]`。基座：🧐 Reality Checker + 📒 Bookkeeper。
3. **调研**：web_search 找 2-3 个带 URL 来源（GitHub topics / arXiv / 行业博客），提炼对本地场景的映射。
4. **落盘**：**用 `patch` 追加**（old_string=自己段落锚点/文件末尾行，new_string=锚点+本段），**严禁 write_file 整卡覆盖**——讨论卡被四方并发编辑，整卡覆盖会抹掉他人刚写的段。
5. **验证**：`read_file` 或 grep 确认本段落盘 + `file_size` 增长；回执含路径+调研来源。

## 五段式模板（任务消息强制）
【角色】【任务】【上下文】【边界】【验证】——验证段必须带 grep/stat 证据。

## 坑（实测）
- **并发写卡**：patch 时若提示"file modified since last read"，说明其他 agent 刚写了段——不要重写整卡，只追加自己的段。
- **写盘自评要带证据**：引用具体文件 L 行号 / 字节数 / mtime，不能只写"✅稳定"。
- **任务词优先**：消息含"写入/落盘/输出到"即任务消息，必须落盘；仅含"立场/同意/回执"才是纯讨论。

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-four-party-discussion")` 即可自动唤醒。
