# Hermes vs MimirAether — Ecosystem（生态/集成）架构对比

> 第8小节 · 2025-07-17

---

## 1. 概览

| 维度 | Hermes | MimirAether |
|------|--------|-------------|
| 核心目录 | `environments/` (~2500行核心) | 无顶层 `environments/` 目录 |
| 终端后端 | 6种 (local/docker/modal/daytona/ssh/singularity) | tools/environments/ 已复制（对齐） |
| RL训练框架 | Atropos深度集成 | rl/ 骨架级实现 |
| 具体训练环境 | 4个 (SWE/OPD/Web/TerminalTest) | 0个 |
| 基准评测 | 3个 (TB2/tblite/yc_bench) | 1个（仅内存性能benchmark） |
| 工具调用解析 | 11个模型家族解析器 | 无 |
| 双阶段操作 | Phase 1 (eval) + Phase 2 (RL) | 无 |
| Wandb集成 | 完整rollout可视化 | 无 |
| ToolContext模式 | 奖励函数全工具访问 | 无 |

---

## 2. Hermes environments/ 架构详解

### 2.1 分层架构

```
Atropos Framework (外部依赖)
  └── BaseEnv (服务器管理/Worker调度/Wandb/CLI)
        └── HermesAgentBaseEnv (终端后端/工具解析/Agent Loop/ToolContext)
              ├── TerminalTestEnv (栈验证)
              ├── HermesSweEnv (SWE-bench训练)
              ├── AgenticOPDEnv (On-Policy Distillation)
              └── WebResearchEnv (多步网页研究)
```

### 2.2 核心组件

| 组件 | 文件 | 行数 | 功能 |
|------|------|------|------|
| HermesAgentBaseEnv | `hermes_base_env.py` | ~500 | 抽象基类，Atropos集成管道 |
| HermesAgentLoop | `agent_loop.py` | ~400 | 可复用多轮Agent引擎 |
| ToolContext | `tool_context.py` | ~300 | 奖励函数的全工具访问句柄 |
| HermesAgentEnvConfig | (同上) | ~200 | Pydantic配置（工具集/后端/预算） |
| patches | `patches.py` | ~30 | 异步安全补丁（已退化为no-op） |

### 2.3 工具调用解析器（tool_call_parsers/）

11个独立解析器，用于Phase 2（VLLM ManagedServer客户端解析）：

- `hermes`, `mistral`, `llama`, `qwen`, `qwen3_coder`
- `deepseek_v3`, `deepseek_v3_1`, `kimi_k2`, `longcat`
- `glm45`, `glm47`

设计模式：ABC基类 + `@register_parser` 装饰器注册。

### 2.4 具体训练环境

| 环境 | 行数 | 用途 | 数据集 |
|------|------|------|--------|
| TerminalTestEnv | 292 | 栈端到端验证 | 内置 |
| HermesSweEnv | 229 | SWE-bench风格编码 | HF bigcode/humanevalpack |
| AgenticOPDEnv | 1214 | On-Policy教师-学生蒸馏 | 编码任务 |
| WebResearchEnv | 719 | 多步网页研究 | FRAMES benchmark |

### 2.5 基准评测环境（benchmarks/）

| 基准 | 任务数 | 特点 |
|------|--------|------|
| TerminalBench 2 | 89 | Docker Hub预构建镜像 |
| tblite | 100 | 快速TB2代理（校准） |
| yc_bench | - | 长时域策略任务 |

### 2.6 关键集成能力

1. **双阶段操作**：
   - Phase 1: OpenAI Server → 原生tool_calls，适合eval/SFT
   - Phase 2: VLLM ManagedServer → 精确token/logprobs，适合RL训练

2. **ToolContext模式**：奖励函数获得rollout沙箱的全工具访问（终端/文件/网页/浏览器/上传下载），无需硬编码

3. **工具结果预算管理**：per-tool阈值 + per-turn聚合预算 + 大结果磁盘持久化

4. **线程池异步安全**：128 worker ThreadPoolExecutor，避免Modal/Docker的asyncio.run()死锁

5. **Wandb rollout可视化**：格式化trajectory展示（工具调用/推理/错误），工具错误统计

6. **OpenRouter路由**：extra_body支持provider偏好/过滤/transforms

---

## 3. MimirAether 生态现状

### 3.1 已有能力

| 能力 | 位置 | 状态 |
|------|------|------|
| 终端后端 | `tools/environments/` | ✅ 对齐（从Hermes复制） |
| 工具集 | `tools/` | ✅ 对齐（从Hermes复制） |
| RL骨架 | `rl/` | ⚠️ 5文件骨架（collector/reward/optimizer/trainer） |
| 自进化 | `mimicore/evolve/` | ✅ MimirAether独有（三环架构） |
| 性能benchmark | `mimicore/benchmark.py` | ⚠️ 仅内存系统性能测试 |

### 3.2 完全缺失

1. ❌ **Atropos集成** — 无BaseEnv继承，无服务器管理/Worker调度
2. ❌ **具体训练环境** — 无SWE-bench/WebResearch/OPD环境
3. ❌ **工具调用解析器** — 无 `tool_call_parsers/` 目录
4. ❌ **双阶段操作** — 无Phase 1/Phase 2概念
5. ❌ **ToolContext模式** — 奖励函数无法访问rollout沙箱
6. ❌ **基准评测环境** — 无TB2/tblite/yc_bench
7. ❌ **Wandb集成** — 无rollout可视化/工具错误统计
8. ❌ **OPD蒸馏** — 无On-Policy Distillation能力
9. ❌ **AgentLoop独立模块** — Agent Loop嵌入在主Agent中，非独立可复用

### 3.3 MimirAether独有优势

1. ✅ **三环自进化架构** (`mimicore/evolve/`) — Hermes无此能力
2. ✅ **记忆殿堂系统** — 持久化知识存储，Hermes无等价物
3. ✅ **胶囊知识工厂** (MimirCore) — 知识萃取/评分/GDI
4. ✅ **调度器** (`scheduler/`) — 定时自学习任务
5. ✅ **技能系统** (`skills/`) — 比Hermes更完整的技能生态

---

## 4. 差距矩阵

### 4.1 生态维度评分

| 维度 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| RL训练框架集成 | 10/10 | 2/10 | ❌ 严重 |
| 训练环境多样性 | 9/10 | 0/10 | ❌ 严重 |
| 基准评测 | 8/10 | 1/10 | ❌ 严重 |
| 多模型工具调用 | 10/10 | 0/10 | ❌ 严重 |
| 终端沙箱后端 | 9/10 | 9/10 | ✅ 对齐 |
| 工具集 | 9/10 | 9/10 | ✅ 对齐 |
| 自进化/自我改进 | 0/10 | 8/10 | ✅ 领先 |
| 知识管理 | 2/10 | 9/10 | ✅ 领先 |

### 4.2 详细差距清单

```
❌ 完全缺失 (8项):
  1. Atropos RL框架集成（BaseEnv继承链）
  2. 具体训练环境（SWE/OPD/Web/TerminalTest）
  3. 工具调用解析器（11个模型家族）
  4. Phase 1/Phase 2 双阶段操作
  5. ToolContext奖励函数模式
  6. 基准评测环境（TB2/tblite/yc_bench）
  7. Wandb rollout可视化
  8. 独立可复用AgentLoop模块

⚠️ 部分实现 (2项):
  1. RL框架（仅骨架，无训练循环/GRPO/PPO实战）
  2. 性能benchmark（仅内存系统，无Agent评测）

✅ 已对齐 (3项):
  1. 终端沙箱后端（完整6种）
  2. 工具集（从Hermes复制）
  3. 工具结果预算管理

✅ MimirAether领先 (3项):
  1. 三环自进化架构
  2. 记忆殿堂/知识管理
  3. 胶囊知识工厂
```

---

## 5. 演进建议

### 5.1 短期（1-2周）

- **提取AgentLoop为独立模块** — 将主Agent中的loop逻辑提取为 `agent/agent_loop.py`
- **搭建RL训练管道** — 从 `rl/` 骨架开始，实现最小可用的GRPO训练循环
- **创建ToolContext** — 参考Hermes的 `tool_context.py`

### 5.2 中期（3-4周）

- **集成Atropos** — 实现 `HermesAgentBaseEnv` 等价基类
- **创建1个训练环境** — 从HermesSweEnv移植或自建
- **实现工具调用解析器** — 至少支持hermes + qwen + deepseek格式

### 5.3 长期（5-8周）

- **基准评测系统** — 接入TerminalBench 2或自建
- **Wandb集成** — rollout可视化 + 工具错误统计
- **OPD蒸馏** — On-Policy Distillation能力

### 5.4 差异化策略

MimirAether不应完全复制Hermes的RL管道，而应发挥自身优势：

- **三环进化 + RL结合** — 用RL训练Agent基础能力，用三环进化做持续自我改进
- **记忆殿堂 + 经验回放** — 用记忆殿堂存储trajectory，替代传统replay buffer
- **胶囊工厂 + 奖励塑形** — 用MimirCore生成的高质量胶囊做奖励信号

---

## 6. 关键代码参考

### Hermes参考文件清单

```
environments/hermes_base_env.py        # 基类 + 配置（~500行）
environments/agent_loop.py             # Agent引擎（~400行）
environments/tool_context.py           # 奖励工具访问（~300行）
environments/tool_call_parsers/        # 11个解析器
environments/hermes_swe_env/           # SWE训练环境
environments/agentic_opd_env.py        # OPD蒸馏（~1200行）
environments/web_research_env.py       # 网页研究（~700行）
environments/benchmarks/               # 3个评测基准
```

### MimirAether对应位置

```
rl/                                    # RL骨架（需扩展）
tools/environments/                    # 终端后端（已对齐）
mimicore/evolve/                       # 自进化（独有优势）
mimicore/benchmark.py                  # 性能测试（需扩展为Agent评测）
agent/                                 # Agent核心（需提取loop）
```

---

_撰写: MimirAether · 第8小节 · Ecosystem架构对比_
