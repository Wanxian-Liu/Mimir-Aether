# TaskLoop Program — capsule GDI 元级自改进

## 任务
优化 capsule 生成质量，提升 GDI 评分到 ≥ 0.80。

## 硬约束

### NEVER STOP
一旦循环开始，不停下来问人。读结果→策略→执行→评测→循环。

### 评测神圣不可改
- `gdi_scorer.py` → 绝对不可修改
- `gen_and_score.py` 的 TEST_INPUTS → 不可修改
- 评测命令 → 不可修改

### 可修改区域
- `mimicore/mapping_config.json` → symptom_to_cause / cause_to_solution / cause_chain
- 映射表决定 CapsuleGenerator 的根因推理和方案生成质量

## 1-hop 链路
```
改 mapping_config.json → CapsuleGenerator 读映射表 → 生成内容 → GDI scorer → 分数
```
单一文件，直接响应。

## 评测
```bash
python3 scripts/gen_and_score.py
```
stdout 末行为平均 GDI 浮点数（0-1）。

## 门控规则
- Δ > 0.001: commit（提升）
- Δ ≤ 0.001: reset（不变即浪费）
- Δ < 0: reset（退步）
- 简洁判据: Δ小但加行数多 → 拒绝

## 停止条件
1. GDI ≥ 0.80 → 目标达成
2. 连续3轮无提升 → 退化停止
3. 最大20轮 → 预算耗尽
4. 单步超60秒 → 超时

## 循环后
汇总 best_score, best_round, rounds, 停止原因。
