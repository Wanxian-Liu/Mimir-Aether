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

## 已完成

1. [x] 修 list_capsules 路径 — 验证结论：无须修；代码路径正确，`memory/capsules/` HTML契约目录与 `mimicore/public/` 旧格式分离是设计意图。存量 .md 需迁移。
