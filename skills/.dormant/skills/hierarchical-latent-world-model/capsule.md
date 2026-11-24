# [DORMANT] hierarchical-latent-world-model

**沉寂时间**: 2026-11-22T02:34:57.240123+00:00
**原始分类**: skills
**描述**: Hierarchical Planning with Latent World Models 论文技能（杨立昆团队）——多层时间尺度世界模型分层规划。零样本真实机器人pick-and-place 70%成功率（单层0%）、推理计算减3-4倍。用于：世界模型规划、机器人控制、分层决策架构理解。
**触发阈值**: 60天未触碰

---

## 技能要点

# Hierarchical Planning with Latent World Models

> 论文：Hierarchical Planning with Latent World Models
> arXiv: 2604.03208 | 作者：Wancong Zhang, Basile Terver, Artem Zholus, Soham Chitnis, Harsh Sutaria, Mido Assran, Randall Balestriero, Amir Bar, Adrien Bardes, **Yann LeCun**, Nicolas Ballas（NYU + Meta）
> 发表：2026-04-03 | 代码：github.com/kevinghst/HWM_PLDM

## 核心贡献

**在多个时间尺度学习潜在世界模型，并进行跨尺度分层规划**——智能体可以在长时域粗略规划，同时保持细粒度精确控制。

## 关键成果

| 指标 | 分层世界模型 | 单层世界模型 |
|------|:---:|:---:|
| 零样本真实机器人 pick-and-place | **70%** 成功率 | **0%** |
| 模拟环境（推操作/迷宫导航）| 更高成功率 | 较低 |
| 推理计算 | **减少最多3-4倍** | — |

**关键**：真实机器人pick-and-place只需**最终目标规格**（final goal specification），无需中间引导——零样本部署。

## 方法

- 多时间尺度潜在世界模型（multiple temporal scales）
- 分层规划：跨尺度推理——长期粗略规划 + 短期精确执行
- 训练：无标签、任务无关的离线轨迹（offline trajectories）
- **即插即用规划抽象**（plug-in planning abstraction）——适用于多种潜在世界模型架构和领域

## 与经典分层RL的关系

借鉴Sutton等（1999）options、Bacon等（2017）options-critic、Hafner等world models——但用**潜在世界模型**做分层，而非显式策略层次。

## 意义

1. **零样本泛化**：只用目标规格就在真实世界控制机器人——世界模型的泛化能力
2. **计算效率**：分层规划减3-4倍推理计算——长时域推理可行
3. **即插即用**：不绑定特定世界模型架构

## 关联（杨立昆三部曲）

- **LeWorldModel**（2603.19312）：世界模型基座——稳定训练JEPA
- **V-JEPA 2.1**（2603.14482）：视觉特征——视频密集表征
- **Hierarchical Planning**（本篇）：规划——多层时间尺度，让世界模型"会做事"

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("hierarchical-latent-world-model")` 即可自动唤醒。
