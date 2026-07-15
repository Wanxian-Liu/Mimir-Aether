---
name: "mimiraether-capsule-repair-reasoning"
description: >
  修复胶囊推理引擎 — _generate_repair_capsule 在输入文本信息不足时不再fallback到占位符，而是基于症状关键词反推根因与解决方案。包含症状→根因映射表和方案推理模板。

version: "1.0.0"
category: "mimiraether"
tags:
  - capsule
  - repair
  - reasoning
  - 根因分析
  - 修复推理
---
# 修复胶囊推理引擎

## 问题

`_generate_repair_capsule` 在输入文本信息不足时，fallback 到占位符（"待分析根本原因"/"待制定解决方案"），产生空壳胶囊。

## 核心原则

当输入文本没有明确给出根因或方案时，**不填占位符，而是基于已有的内容反推**。

## 推理规则

### 根因推理（基于问题诊断 + 背景症状）

症状关键词 → 根因映射（双向推理）：

| 症状关键词 | 推断根因 |
|-----------|---------|
| 未启用、未集成、未接入、缺失 | 对应模块未被集成到生命周期 |
| 为空、无数据、空白 | 缺少初始化/写入逻辑 |
| 超时、卡住、无响应 | 缺少超时处理/异步机制 |
| 重复、冗余、多次触发 | 缺少去重/状态检查 |
| 崩溃、异常退出、OOM | 缺少资源限制/错误处理 |
| 不一致、对不上、不同步 | 缺少状态同步机制 |
| 慢、延迟、性能差 | 缺少缓存/批量处理 |
| 权限、拒绝、403/401 | 缺少认证/授权检查 |
| 丢失、消失、找不到 | 缺少持久化/备份机制 |
| 默认值、不对、错误 | 缺少输入验证/默认值策略 |

### 方案推理（基于根因）

| 根因类型 | 推断方案模板 |
|---------|------------|
| 未集成到生命周期 | 在启动/结束点集成对应模块 |
| 缺少初始化逻辑 | 添加初始化步骤，确保启动时加载 |
| 缺少超时处理 | 添加超时配置 + 异步超时保护 |
| 缺少去重 | 添加状态跟踪 + 幂等性检查 |
| 缺少错误处理 | 添加 try/except + 降级策略 |
| 缺少状态同步 | 添加单向/双向同步机制 |
| 缺少缓存 | 添加 LRU 缓存 + 预热策略 |
| 缺少认证 | 添加 token 刷新/权限验证中间件 |
| 缺少持久化 | 添加读写文件/数据库逻辑 |
| 缺少输入验证 | 添加 schema 验证 + 默认值策略 |

### 实施步骤推理

基于方案自动展开为步骤序列：
1. 诊断确认 — 验证问题确实存在
2. 方案设计 — 确定具体实现方式
3. 代码实施 — 修改/添加对应代码
4. 测试验证 — 运行测试确认修复
5. 回归检查 — 确认无副作用

## 实现模式

```python
@staticmethod
def _infer_root_cause(diagnosis: str, symptoms: str) -> str:
    """基于诊断和症状反推根因"""
    # 关键词匹配 → 根因映射
    cause_map = [
        (["未启用", "未集成", "未接入", "缺失"], "相关模块未被集成到系统生命周期"),
        (["为空", "无数据", "空白"], "缺少初始化或写入逻辑，导致数据未被持久化"),
        (["超时", "卡住", "无响应"], "缺少超时处理或异步等待机制"),
        (["重复", "冗余"], "缺少去重或幂等性检查"),
        (["崩溃", "异常退出"], "缺少资源限制或错误恢复机制"),
        (["不一致", "对不上", "不同步"], "缺少状态同步或数据一致性保障"),
        (["慢", "延迟", "性能"], "缺少缓存或批量处理优化"),
        (["丢失", "消失", "找不到"], "缺少持久化或备份恢复机制"),
    ]
    
    combined = diagnosis + " " + symptoms
    matched_causes = []
    for keywords, cause in cause_map:
        if any(k in combined for k in keywords):
            matched_causes.append(cause)
    
    if matched_causes:
        return "根据症状分析，根因如下：\n" + "\n".join(f"- {c}" for c in matched_causes[:3])
    return f"基于症状「{CapsuleGenerator._smart_truncate(symptoms, 100)}」分析，根本原因与{CapsuleGenerator._smart_truncate(diagnosis, 80)}直接相关，需要检查对应模块的实现逻辑。"

@staticmethod
def _infer_solution(diagnosis: str, symptoms: str, root_cause: str) -> str:
    """基于诊断、症状、根因反推解决方案"""
    # 根因关键词 → 方案模板
    solution_map = [
        ("未集成到系统生命周期", "将对应模块集成到系统启动/关闭生命周期中，确保在合适的时机初始化和清理"),
        ("缺少初始化", "添加初始化逻辑，在系统启动时自动加载对应模块"),
        ("缺少写入", "添加数据写入逻辑，确保状态变更时持久化到存储"),
        ("缺少超时处理", "添加超时配置和异步超时保护机制"),
        ("缺少去重", "添加状态跟踪和幂等性检查，防止重复触发"),
        ("缺少错误处理", "添加 try/except 异常捕获和优雅降级策略"),
        ("缺少状态同步", "添加单向或双向状态同步机制，确保数据一致性"),
        ("缺少缓存", "添加 LRU 缓存和预热策略，减少重复计算"),
        ("缺少持久化", "添加文件或数据库读写逻辑，确保数据不丢失"),
        ("缺少备份", "添加自动备份和恢复机制"),
    ]
    
    combined = diagnosis + " " + symptoms + " " + root_cause
    matched_solutions = []
    for keywords, solution in solution_map:
        if any(k in combined for k in [keywords]):
            matched_solutions.append(solution)
    
    if matched_solutions:
        return "根据根因分析，建议方案如下：\n" + "\n".join(f"- {s}" for s in matched_solutions[:3])
    
    return (
        f"基于问题「{CapsuleGenerator._smart_truncate(diagnosis, 60)}」分析，"
        f"建议从以下方向入手：\n"
        f"1. 定位问题发生的模块和触发条件\n"
        f"2. 分析模块间的交互和数据流\n"
        f"3. 设计修复方案并验证"
    )
```

## 验证

用短输入测试，确认输出不再是占位符而是推理后的内容。
