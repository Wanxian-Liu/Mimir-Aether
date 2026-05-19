# MimirAether 执行待办

> 规则：按顺序做下一条未勾选项；做完勾上 `[x]`，简短回报 + tier0/CI。
> 卡住时在 `MIMIR_ISSUES.md` 记一条，停手等确认。

## Backlog

1. [x] memory 工具冒烟 — 验证单例懒加载实例化后可正常读写
   done: 2026-05-17, 仅文档/验证 — 写入→读回→删除全链路正常
2. [x] 追 persistent.json 截断根因 — 谁在 end_session 时覆盖全文件
   done: 2026-05-17, Session 73 已定位+修复: skill_curator.py _load_persistent() JSON异常→{}→覆写。3层防护已加。
3. [x] 存量胶囊迁移（120 .md → .html） — mimicore/public/ 旧格式 → memory/capsules/
   done: 2026-05-19, P1-1 审计 131/131 已覆盖、0 缺失；P1-3 抽检 10/10；P1-4 tier0 绿；见 docs/phase1/
4. [x] Context 压缩链 — 删 ContextEngine；MimirContextCompressor + plugins 鸭子类型
   done: 2026-05-19, cd6b71d；tier0 绿；与 d00347d（budget/tool）成对
5. [x] P2-1 飞书收图 — feishu_adapter 下载前 token（ISSUES #1）
   done: 2026-05-19, `_ensure_tenant_token_sync` + `_refresh_token_sync`; `tests/test_feishu_image_token.py`; `docs/phase2/P2-1-feishu-image.md`
6. [x] P2-2 飞书表格空列名 — html_to_feishu_card（ISSUES #2）— 空 `<th>` → `"—"`，避免飞书 `230099`/`200907` 卡片失败回退纯文本
   done: 2026-05-19, `tests/test_html_to_feishu_table.py` + tier0 PASS
7. [ ] P3-0 persistent 单写者 — ADR 仅文档（ISSUES #4）
8. [ ] P4-1 memory/index.html + wiki 路径（ISSUES #3 一部分）

---

## Mimir 可执行（无架构 — 按顺序）

> 计划全文：`docs/plans/2026-05-19_stability_sprint.md`  
> Gateway 十条：`docs/GATEWAY_STABILITY_BACKLOG.md`  
> **禁止**：删光 `role=tool` 消息；勿提交 `data/persistent.json`。

| # | 任务 | 成功标准 |
|---|------|----------|
| M1 | 重启 gateway（`main` 含 `43cbd3a` + `b50c71c`） | `feishu connected`；PID 与 `~/.mimiraether/data/gateway.pid` 一致 |
| M2 | 飞书 mimiraether **发图** | `Image downloaded` + URL 含 `resources/`；vision 无 `image_url` 400；能描述图片 |
| M3 | 飞书 **空表头** HTML 表 | 列名 `—`，非纯文本回退 |
| M4 | 飞书 **触发 tool** 一句 | 无 `tool must be a response` |
| M5 | 确认 vision 回退凭证 | `OPENROUTER_API_KEY` 或 `config.yaml` → `auxiliary.vision.provider` |
| M6 | `ISSUES.md` #1/#2 改 `resolved`（M2/M3 通过后） | 文档 only |
| M7 | Gateway 十条：逐条在 `GATEWAY_STABILITY_BACKLOG.md` 标状态 | 仅复现/配置/记 ISSUES，不改大逻辑 |
| M8 | （可选）`git push origin main` | 刘哥授权后 |

### 回报模板（贴给 Cursor / 刘哥）

```text
Mimir 冒烟回报
- gateway PID / 启动时间:
- M2 发图: 通过/失败 + grep 最后 5 行
- M3 表头: 通过/失败
- M4 tool: 通过/失败
- M5 OPENROUTER: 有/无
- 未完成项:
```

---

## 需工程 / Cursor（勿交给 Mimir 改架构）

| 项 | 说明 |
|----|------|
| WebSocket 推理阻塞心跳 | gstack P0#2 |
| 监控与告警 | gstack P0#3 |
| 自修回滚护栏 | gstack P0#4 |
| P3-0 / P4-1 | ADR + memory 三入口 |
| Gateway #5/#10 等 | 见 GATEWAY_STABILITY_BACKLOG「工程」列 |

## 已完成

1. [x] 修 list_capsules 路径 — 验证结论：无须修；代码路径正确，`memory/capsules/` HTML契约目录与 `mimicore/public/` 旧格式分离是设计意图。存量 .md 需迁移。
