# TaskLoop 架构设计

> BACKLOG #4 | 基于 Karpathy autoresearch 架构提取的通用任务自循环执行器

---

## 一、架构全貌

```
                    ┌──────────────────────────────┐
                    │      人类 (循环前只介入一次)     │
                    │  任务描述 + 评测命令 + 预算      │
                    └──────────┬───────────────────┘
                               │ 启动参数
                               ▼
┌─────────────────────────────────────────────────────────┐
│                   TaskLoop 引擎 (纯代码)                   │
│                                                         │
│  while not stop_condition:                               │
│    ┌──────────────────────────────────────────────┐      │
│    │ ① LLM: 读 state → 策略 → 执行                 │      │
│    │    加载: plan-mode + recovery + guard         │      │
│    │    产出: 本轮修改 + 假设描述                   │      │
│    └───────────┬──────────────────────────────────┘      │
│                ▼                                          │
│    ┌──────────────────────────────────────────────┐      │
│    │ ② Shell: 运行评测命令 (纯确定性计算)           │      │
│    │    timeout 5min → 超时=FAIL                   │      │
│    └───────────┬──────────────────────────────────┘      │
│                ▼                                          │
│    ┌──────────────────────────────────────────────┐      │
│    │ ③ Gate: 数值比较 + Git 操作                   │      │
│    │    score↑ → commit, score↓ → reset            │      │
│    │    追加 results.tsv                           │      │
│    └───────────┬──────────────────────────────────┘      │
│                ▼                                          │
│    ┌──────────────────────────────────────────────┐      │
│    │ ④ Stop Check: 5条停止条件                      │      │
│    │    达标/预算耗尽/退化/死胡同 → break           │      │
│    └──────────────────────────────────────────────┘      │
│                                                         │
│  → 汇总报告                                              │
└─────────────────────────────────────────────────────────┘
```

---

## 二、核心数据结构

### 2.1 任务配置 (启动时传入)

```python
@dataclass
class TaskLoopConfig:
    task: str              # "优化 capsule 生成质量，目标 GDI≥70"
    eval_cmd: str          # "python3 -c 'from test import score; print(score())'"
    target_score: float    # 0.95
    max_rounds: int        # 20
    max_time: int          # 600 (秒)
    no_go: list[str]       # ["不要改 data/", "不要调 API key"]
    workdir: str           # "./"  工作目录
```

### 2.2 轮次状态

```python
@dataclass
class RoundState:
    round: int
    hypothesis: str        # "试试把 chunk_size 从 512 改到 1024"
    score: float
    delta: float           # 相比上一轮的提升
    passed: bool
    duration_s: float
    commit_hash: str | None
    error: str | None
```

### 2.3 停止条件 (枚举)

```python
class StopReason(Enum):
    TARGET_REACHED = "目标达成"
    ROUNDS_EXHAUSTED = "轮次耗尽"
    TIME_EXHAUSTED = "时间耗尽"
    DEGENERATION = "连续退化"
    DEAD_END = "死胡同"
    SAFETY = "安全风险"
```

---

## 三、引擎核心：task_loop.py

### 3.1 主循环

```python
def run(config: TaskLoopConfig) -> TaskLoopResult:
    state = init_state(config)
    rounds: list[RoundState] = []
    
    while not should_stop(rounds, config):
        # ① LLM 策略+执行
        llm_result = call_llm_strategy(state, rounds, config)
        apply_changes(llm_result)
        
        # ② 评测
        score, ok, duration = run_eval(config.eval_cmd, timeout=300)
        
        # ③ 门控
        if ok and is_better(score, state.best_score):
            commit(f"round_{len(rounds)}: {llm_result.hypothesis}")
        else:
            rollback()
        
        # ④ 记录
        rounds.append(RoundState(
            round=len(rounds)+1,
            hypothesis=llm_result.hypothesis,
            score=score if ok else -1,
            delta=score - state.best_score if ok else 0,
            passed=ok,
            duration_s=duration,
            ...
        ))
        
    return summarize(rounds, stop_reason)
```

### 3.2 LLM 调用：单次、精炼

```
输入（压缩后）:
  - 任务描述
  - 当前轮次 + 最佳分数
  - 最近 3 轮的结果（含假设+分数+delta）
  - 禁区列表

输出:
  - hypothesis: "把 chunk_size 从 512 改到 1024"
  - changes: [ { file: "config.py", patch: "..." } ]

规则:
  - 一次只改一个变量
  - 不改禁区 (no_go)
  - 不改评测命令 eval_cmd — 这是"一个文件"原则：评测框架神圣不可触碰
  - 改动越少越好：删代码优于加代码
```

### 3.3 时间预算

```python
def run_eval(cmd, timeout=300):
    """超时自动 kill，标记 FAIL"""
    proc = subprocess.Popen(cmd, shell=True)
    try:
        stdout, _ = proc.communicate(timeout=timeout)
        score = float(stdout.strip())
        return score, True, proc.elapsed
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, False, timeout
    except ValueError:
        return -1, False, proc.elapsed
```

---

## 四、与现有模块的集成

| 现有模块 | 在 TaskLoop 中的角色 |
|----------|-------------------|
| `plan-mode` | LLM 每轮调用时加载，拆解本轮假设 |
| `recovery patterns` | ① eval 失败/超时 → 自动重试 → 仍失败 → 本轮 FAIL + 下一轮 |
| `degeneration_guard` | 检测连续退化信号 → 触发 DEGENERATION 停止 |
| `persistent.json` | 循环中断时保存状态，重启后恢复继续 |
| `curator` | 无关。TaskLoop 不依赖 curator |

### 4.1 崩溃分级处理（三梯级，不浪费轮次）

```
梯级 1 — 哑崩溃 (typo/缺import/语法错):
  修 → 重跑 → 正常继续（不占轮次，不计入结果）

梯级 2 — 硬崩溃 (OOM/超时/架构崩):
  git reset --hard → 记录 "crash" → 下轮 → LLM 读到此信息回避

梯级 3 — LLM 自身失败 (API超时/429):
  重试 1 次 → 仍失败 → DEAD_END 停止
```

原则：只有梯级 2/3 消耗轮次预算。哑崩溃修复不算轮次——autoresearch 一晚修几十次 typo 不计数。

### 4.2 简洁判据（保留条件）

不是分数升就保留。额外约束：

```
Δ > 0 且 改动 ≤ 10 行 → keep   (简洁改进)
Δ > 0 且 改动 > 30 行 → 警告，仅当 Δ ≥ 0.005 才 keep
Δ = 0 且 改动 = 删代码  → keep   (简化等效)
Δ < 0 → discard
```

防止 agent 堆 50 行代码换 0.001 提升。

---

## 五、文件结构

```
scripts/
  task_loop.py           # 引擎主程序
  task_loop_config.py    # 数据结构定义

docs/
  TASKLOOP_PROGRAM.md    # 行为规范 (已有)
  TASKLOOP_ARCH.md       # 本文件
  TASKLOOP_INSTANCE_*.md # 具体任务实例

data/
  results.tsv            # 实验记录 (轮次/分数/delta/假设)
```

---

## 六、首个验证目标：capsule 生成质量

### 6.1 任务定义

```
task: "优化 mimicore capsule 生成质量，提升 GDI 评分"
eval_cmd: "python3 -c 'from mimicore.score import gdi_batch; print(gdi_batch(\"data/capsules_test.jsonl\"))'"
target_score: 70.0
max_rounds: 10
max_time: 1800
no_go: ["不要改 mimicore/ 核心评分函数", "不要改 data/capsules_test.jsonl"]
```

### 6.2 为什么选 capsule

- MimirAether 自家模块，零外部依赖
- GDI ≥ 70 是硬数值评测（纯 shell，不需要 LLM 判断）
- 变量明确：prompt/参数/过滤策略，每次只改一维
- 结果可量化对比（GDI 数值直接比较）

---

## 七、与 Karpathy 的对照

| Karpathy | 我们的 TaskLoop |
|----------|----------------|
| program.md (任务方向) | TASKLOOP_PROGRAM.md + 实例配置 |
| train.py (基线) | 目标代码的当前状态 |
| results.tsv (实验记录) | data/results.tsv |
| while True + 时间预算 | scripts/task_loop.py |
| git commit/reset | 同 |
| LLM 调参 | LLM 调代码/配置 |
| val_bpb 评测 | 用户定义的 eval_cmd |

**区别**：autoresearch 专用 ML 训练，TaskLoop 通用——任何有数值评测的任务都能跑。
