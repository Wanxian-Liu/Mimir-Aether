# [DORMANT] vjepa-21-dense-video

**沉寂时间**: 2026-11-22T02:34:57.572068+00:00
**原始分类**: skills
**描述**: V-JEPA 2.1 论文技能——视频自监督学习密集特征（Meta/LeCun团队）。4个关键组件：Dense Predictive Loss/Deep Self-Supervision/Multi-Modal Tokenizers/Scaling。用于：视频自监督学习、密集视觉特征、世界模型视觉组件理解。
**触发阈值**: 60天未触碰

---

## 技能要点

# V-JEPA 2.1 — 视频自监督学习的密集特征

> 论文：V-JEPA 2.1: Unlocking Dense Features in Video Self-Supervised Learning
> arXiv: 2603.14482 | 作者：Lorenzo Mur-Labadia, Matthew Muckley, Amir Bar, Mido Assran, Koustuv Sinha, Mike Rabbat, **Yann LeCun**, Nicolas Ballas, Adrien Bardes（Meta + 高校）
> 发表：2026-03-15

## 核心贡献

**V-JEPA 2.1是自监督模型家族，学习密集、高质量的时空表征**——所有token（可见上下文+掩码token）都贡献训练loss，实现显式时空接地。

## 4个关键组件

1. **Dense Predictive Loss（密集预测损失）**——所有token参与训练损失，鼓励显式时空接地（spatial and temporal grounding）
2. **Deep Self-Supervision（深度自监督）**——在多个中间编码器层分层应用自监督目标，提升表征质量
3. **Multi-Modal Tokenizers（多模态分词器）**——支持图像和视频统一训练
4. **Effective Scaling（有效缩放）**——模型和数据缩放

## 基准成绩（State-of-the-Art）

| 任务 | 指标 | 成绩 |
|------|------|------|
| Ego4D 短期物体交互预测 | mAP | **7.71** |
| EPIC-KITCHENS 高层动作预测 | Recall@5 | **40.8** |
| 真实机器人抓取 | 成功率 | **+20%** vs V-JEPA-2 AC |
| 机器人导航（Tartan Drive）| ATE | 5.687 |
| 深度估计（NYUv2 linear probe）| RMSE | 0.307 |
| 全局识别（Something-Something-V2）| 准确率 | 77.7% |

## 关键特性

- 产生**空间结构清晰、语义连贯、时间一致**的密集表征
- 相比V-JEPA-2，密集特征质量大幅提升
- 视觉理解与世界建模的双重先进水平

## 意义

- 世界模型的**视觉感知组件**——视频理解需要密集时空特征
- 自监督（无需标注）学习密集表征——扩展LeCun"机器自主智能"愿景
- 机器人操作/导航的实际性能提升（抓取+20%）

## 关联（杨立昆三部曲）

- **LeWorldModel**（2603.19312）：世界模型基座——如何稳定训练JEPA
- **V-JEPA 2.1**（本篇）：视觉特征——视频自监督密集表征
- **Hierarchical Planning**（2604.03208）：规划——多层时间尺度世界模型

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("vjepa-21-dense-video")` 即可自动唤醒。
