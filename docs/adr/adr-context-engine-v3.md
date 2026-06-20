# ADR: ContextEngine V3 — Keep Self-Designed Route

**决策 ID:** HC-23
**日期:** 2026-06-04
**状态:** ✅ 已通过
**影响范围:** `agent/context_compressor.py`, 系统提示组装

## 背景

HC-23 要求评估：是否恢复 Hermes 的 ABC（Abstract Base Class）模式的 ContextEngine，或者保持 Mimir V3.0 的 self-designed 路线。

## 对比分析

| 维度 | Hermes ABC | Mimir V3.0（当前） |
|:-----|:-----------|:------------------|
| **文件** | `context_engine.py` (211 行, ABC) + 子类 | `context_compressor.py` (884 行, 自设计) |
| **抽象** | 形式化 ABC（`compress`, `should_compress` 接口） | Duck-typing（`compress()`, `should_compress()` 方法无抽象约束） |
| **策略** | ABC 无默认实现，子类写全 | V2.3 完整实现 + Headroom CacheAligner 移植 |
| **扩展** | +1 压缩器 = +1 子类 | +1 策略 = +1 `else-if` 或注册 |
| **MVP 代价** | 211 + 子类 ~ 500-800 行 | 884 行，开了即用 |

## 真正的缺口（Hermes ABC 帮不了的）

| 缺口 | 现有 | 缺什么 |
|:-----|:-----|:-------|
| **CCR 可逆压缩** | ❌ 摘要不可逆 | LRU cache 本地存原始消息 |
| **多策略注册** | ❌ 单 `compress()` 方法 | 策略选择器（token节省 vs 信息保留 vs 速度） |

这些缺口与 ABC 形式无关——即使有 Hermes ABC 也一样要补。

## 决策

**V3 走自设计路线 ✅**
- 不恢复 Hermes ABC
- 不引入抽象层
- 保持单文件 884 行（策略不足时再拆）

**V4 的可选方向（当前不必）：**
- ▢ 加 CCR（成本低，收益高 — 可优先做）
- ▢ 加策略注册（成本中，等真有多个策略再拆）
- ▢ 恢复 ABC（除非发现明确好处，否则不做）

## 原因

1. V3.0 移除 ABC 是正确的架构决定——ABC 层在当前单策略场景下是噪音
2. 当前压缩行为（滚动窗口 + 尾部保护 + CacheAligner 前缀稳定）覆盖了全部需求
3. 下一个压缩需求（CCR 可逆压缩）不需要 ABC 层支持
4. 引入 ABC 不解决任何现有问题，只增加认知负载

## 影响

- 无迁移成本（当前架构不变）
- 无行为改变（压缩逻辑不变）
- 未来加 CCR 时直接追加到 `context_compressor.py` 即可

## 签署

- **提议:** Mimir (Agent)
- **批准:** Ray (Human)
- **日期:** 2026-06-04
