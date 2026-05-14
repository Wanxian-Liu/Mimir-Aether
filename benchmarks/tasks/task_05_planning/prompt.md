# Task 5: 规划深度 (Planning Depth)

> 权重: 15% | 满分: 20

## 任务描述

在 `/tmp/benchmark-sandbox/planning/` 下，有一个多阶段文档迁移任务。

### 背景

`docs/` 目录下有 3 篇 markdown 文章，需要迁移到 Hugo 博客系统。

### 阶段说明

**阶段 1: 内容审计**  
- 列出 `docs/` 下所有 `.md` 文件
- 统计总字数
- 把统计结果写入 `audit.json`

**阶段 2: Frontmatter 转换**  
- Hugo 需要 TOML frontmatter (`+++`)，当前是 YAML (`---`)
- 把所有文章的 frontmatter 从 YAML 转为 TOML
- 添加 `date` 字段（当前日期）
- 输出文件放到 `output/` 目录

**阶段 3: 交叉引用更新**  
- 文章中有对 `docs/xxx.md` 的内部链接
- 转换为 Hugo 格式：`docs/foo.md` → `{{< ref "foo" >}}`
- 更新所有文件

**阶段 4: 验证**  
- 检查所有 `output/` 文件 frontmatter 是 TOML 格式
- 确认无残留 `---` frontmatter
- 确认至少有一个 `ref` 短代码链接

## 评分标准

| # | 检查点 | 分值 |
|---|--------|------|
| 1 | 阶段1: `audit.json` 存在且有文件数+字数统计 | 5 |
| 2 | 阶段2: `output/` 下文件存在且 frontmatter 为 TOML | 5 |
| 3 | 阶段3: 旧链接 `docs/xxx.md` 已转为 `ref` | 5 |
| 4 | 阶段4: 验证通过——无残留 YAML frontmatter | 5 |

**最高: 20 分**
