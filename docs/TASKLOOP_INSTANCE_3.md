# TaskLoop Instance: 胶囊迁移 #3

## 任务参数

task: "将 mimicore/public/ 下 131 枚 .md 胶囊转换为 .html，放入 memory/capsules/"
eval_cmd: "python3 scripts/verify_migration.py"
target_score: 131
max_rounds: 5
max_time: "30m"
no_go: ["不要删除 mimicore/public/*.md 原件", "不要修改 memory/capsules/ 下已有的 179 枚 .html"]

## 评测定义

每轮验证：
1. 新生成的 .html 数量
2. 内容完整性（源 .md 的关键信息在 .html 中保留）
3. 命名一致性（源文件名 → hash前缀命名）

score = 成功迁移的文件数（目标 131）
