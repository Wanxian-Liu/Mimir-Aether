# [DORMANT] leworldmodel-jepa

**沉寂时间**: 2026-11-22T02:34:57.307441+00:00
**原始分类**: skills
**描述**: LeWorldModel (LeWM) 论文技能——杨立昆团队首个端到端稳定训练的JEPA世界模型。SIGReg正则化解决latent坍缩、2个loss项、15M参数单GPU。用于：JEPA/世界模型架构理解、latent collapse问题研究、自监督预测学习参考。
**触发阈值**: 60天未触碰

---

## 技能要点

# LeWorldModel (LeWM) — 稳定端到端JEPA世界模型

> 论文：LeWorldModel: Stable End-to-End Joint-Embedding Predictive Architecture from Pixels
> arXiv: 2603.19312 | 作者：Lucas Maes, Quentin Le Lidec, Damien Scieur, **Yann LeCun**, Randall Balestriero（Mila/纽约大学/Samsung SAIL/Brown）
> 发表：2026-03-13

## 核心贡献

**LeWM是第一个只用2个loss项就能端到端稳定训练的JEPA世界模型**——解决JEPA 5年来的表征坍缩（representation collapse）问题。

| 属性 | 值 |
|:----|:--|
| 参数量 | 15M |
| 训练资源 | 单GPU，几小时 |
| Loss项 | 仅2个（原端到端替代方案6个可调超参→1个）|
| 规划速度 | 比foundation-model-based世界模型快 **48倍** |
| 代码 | lucas-maes/le-wm（4,100★, MIT）|
| 验证环境 | PushT / Cube / TwoRoom / Reacher |

## 背景问题：JEPA的坍缩困境

JEPA（Joint Embedding Predictive Architecture）在紧凑潜在空间学习世界模型，但现有方法脆弱：
- 依赖复杂多term loss / 指数移动平均（EMA）/ 预训练编码器 / 辅助监督
- 都为了**避免表征坍缩**——编码器把所有输入映射到同一个latent vector（平凡解）

## 解决方案：SIGReg

**SIGReg = 各向同性高斯正则化（Isotropic Gaussian Regularization）**

```
编码器 → z_t ──SIGReg──→ z_t+1 ──SIGReg──→ ...
```

- 强制整个embedding分布匹配**各向同性高斯分布**
- 防止编码器坍缩到单一向量
- **关键**：把"防坍缩"从复杂的多loss架构问题，简化为一个正则项

## 架构

- **2个loss**：
  1. next-embedding预测loss（预测下一个潜在表示）
  2. SIGReg正则（高斯分布约束）
- 端到端从原始像素训练（无需预训练编码器）
- 潜在空间**自然编码物理结构**（position、velocity等），无需监督

## 意义

1. **稳定性**：JEPA从"需要精细调参的脆弱方法"变成"2个loss就能稳定训练"
2. **效率**：15M参数单GPU几小时 vs 大规模模型
3. **速度**：规划比foundation-model世界模型快48倍
4. **通往AGI的一步**：这是LeCun"自主机器智能"愿景的核心组件——世界模型让AI理解物理世界如何运转

## 关联

- **V-JEPA 2.1**（2603.14482）：视频自监督密集特征，4组件（dense predictive loss/deep self-supervision/multi-modal tokenizers/scaling）
- **Hierarchical Planning**（2604.03208）：多层时间尺度世界模型分层规划，零样本机器人成功率70%
- 三部曲关系：LeWM=基座（如何稳定训练）→ V-JEPA=视觉特征 → Hierarchical Planning=规划

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("leworldmodel-jepa")` 即可自动唤醒。
