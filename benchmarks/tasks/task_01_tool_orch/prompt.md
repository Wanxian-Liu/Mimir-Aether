# Task 1: 工具编排 (Tool Orchestration)

> 权重: 25% | 满分: 25

## 任务描述

在 `/tmp/benchmark-sandbox` 下完成以下操作：

1. 创建目录 `project-orch`
2. 写入文件 `README.md`，内容必须包含标题 `# Benchmark Project` 和描述段落 `This is an automated benchmark test.`
3. 在 `project-orch` 下执行 `git init`
4. 创建 `.gitignore`，内容包含 `*.log` 和 `__pycache__/`
5. 做初始 commit，message 包含 `"initial commit"`
6. 搜索 `README.md` 中是否有 `TODO` 字样（应该没有）
7. 创建一个文件 `config.json`，内容为 `{"version": "1.0", "debug": false}`

## 评分标准

| # | 检查点 | 分值 |
|---|--------|------|
| 1 | 目录 `project-orch` 存在 | 4 |
| 2 | `README.md` 内容正确 | 4 |
| 3 | `git init` 完成 | 3 |
| 4 | `.gitignore` 内容正确 | 3 |
| 5 | git commit 成功且 message 正确 | 4 |
| 6 | 搜索 TODO 已执行 | 3 |
| 7 | `config.json` 存在且 JSON 有效 | 4 |

**最高: 25 分**
