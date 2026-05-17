# MimirAether 执行待办

> 规则：按顺序做下一条未勾选项；做完勾上 `[x]`，简短回报 + tier0/CI。
> 卡住时在 `MIMIR_ISSUES.md` 记一条，停手等确认。

## Backlog

1. [x] memory 工具冒烟 — 验证单例懒加载实例化后可正常读写
   done: 2026-05-17, 仅文档/验证 — 写入→读回→删除全链路正常
2. [x] 追 persistent.json 截断根因 — 谁在 end_session 时覆盖全文件
   done: 2026-05-17, Session 73 已定位+修复: skill_curator.py _load_persistent() JSON异常→{}→覆写。3层防护已加。
3. [ ] 存量胶囊迁移（120 .md → .html） — mimicore/public/ 旧格式 → memory/capsules/

## 已完成

1. [x] 修 list_capsules 路径 — 验证结论：无须修；代码路径正确，`memory/capsules/` HTML契约目录与 `mimicore/public/` 旧格式分离是设计意图。存量 .md 需迁移。
