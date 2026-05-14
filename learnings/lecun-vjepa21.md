# V-JEPA 2.1 — 精读笔记

> **论文**: V-JEPA 2.1: Unlocking Dense Features in Video Self-Supervised Learning
> **arXiv**: 2603.14482v2 | **日期**: 2026-03-15 | **分类**: cs.CV
> **作者**: Lorenzo Mur-Labadia, Matthew Muckley, Amir Bar, Mido Assran, Koustuv Sinha, Mike Rabbat, Yann LeCun, Nicolas Ballas, Adrien Bardes
> **机构**: FAIR at Meta, Universidad de Zaragoza
> **代码**: https://github.com/facebookresearch/vjepa2

---

## 核心贡献（一句话）

**解锁 JEPA 的密集特征学习**——通过四个关键组件使视频自监督模型同时获得精细空间结构 + 语义一致性 + 时间连贯性，在预测/理解/机器人三大类任务上实现 SOTA。

---

## 1. 问题诊断：V-JEPA 2 的特征缺陷

### 观察

- V-JEPA 2 的 PCA 特征图**噪声大且只有碎片化局部结构**
- 密集任务线性探针性能差：ADE20K 22.2 mIoU, NYUv2 0.682 RMSE

### 根因假设

原始 V-JEPA 2 损失 **仅应用于被遮罩的 token**——上下文 token 无监督信号。
→ 上下文 token 退化为全局聚合器（类似 register tokens），不编码局部信息。

### 验证实验

加入 Context Loss ℒ_ctx——监督上下文 token 的预测——PCA 特征图立刻出现清晰的语义结构。

---

## 2. 四大组件

### 2.1 密集预测损失 (Dense Predictive Loss)

```
ℒ_dense = ℒ_predict + ℒ_ctx
```

**关键创新：all tokens 参与训练信号**

- ℒ_predict：原始 V-JEPA 2 的掩码 token L1 损失
- ℒ_ctx：上下文 token 的加权 L1 损失
  - 权重 λ_i = λ / √(d_min(i, M))，其中 d_min 是上下文 token 到最近掩码 token 的时空距离
  - **距离加权**：靠近掩码区域的上下文 token 权重更高，强制局部连续性
  - λ 从 epoch 50-100 渐进预热

**效果**：
| 指标 | V-JEPA 2 | +ℒ_ctx |
|------|----------|--------|
| ADE20K mIoU | 22.2 | 33.9 |
| NYUv2 RMSE | 0.682 | 0.473 |
| SSv2 (副作用) | 72.8 | 62.5 |

### 2.2 深层自监督 (Deep Self-Supervision)

**关键创新：在编码器多个中间层分层施加自监督目标**

- 从 3 个中间层 + 输出层提取表示，沿通道维拼接
- 轻量 MLP 融合多层级表示 → 喂给 Predictor
- Predictor 输出 4 个层级的预测
- **预测损失和上下文损失在每一层独立应用**

**效果**：
- 恢复了全局理解能力：SSv2 62.5→72.1, IN1K 72.6→80.8
- 进一步提升了密集任务：ADE20K 33.9→38.6
- **使中间层在密集下游任务中不再必需**——最终层已包含精细信息

### 2.3 多模态 Tokenizer

**关键创新：图像和视频使用不同的 patch embedding**

- 视频：3D 卷积 16×16×2
- 图像：2D 卷积 16×16
- 加入可学习的模态 embedding（告诉 encoder/predictor 输入来自图像还是视频路径）
- 图像不再需要时间复制（之前 V-JEPA 2 把图像当作 16 帧静态视频）

**效果**：
- 计算效率提升（图像不再重复 16 次）
- 密集任务改善：ADE20K 40.8→41.4 mIoU

### 2.4 数据与模型缩放

**VisionMix163M 数据集**：
- 用 LVD-142M（142M 精选图像）替换 ImageNet-1K
- 增加动态视频权重：SSv2 0.056→0.170, YT-1B 0.188→0.720
- 图像/视频分开处理（不同 worker），梯度聚合

**模型缩放**：
- ViT-L (300M) → ViT-G (2B)：全任务持续提升
- Cool-down 阶段：降低学习率 + 提高分辨率
  - 视频：16帧@256² → 64帧@384²
  - 图像：256² → 512²

---

## 3. 完整训练流水线效果累积

| 阶段 | IN1K | SSv2 | NYUv2↓ | ADE20K |
|------|------|------|--------|--------|
| V-JEPA 2 baseline | 82.2 | 72.8 | 0.682 | 22.2 |
| + Context Loss | 72.6 | 62.5 | 0.474 | 33.8 |
| + Multi-level Pred. | 80.8 | 72.1 | 0.463 | 38.6 |
| + Vision Mix | 81.6 | 72.6 | 0.418 | 40.8 |
| + Multi-modal Tok. | 81.6 | 72.6 | 0.415 | 41.4 |
| + Model Scaling | 84.8 | 76.1 | 0.365 | 47.1 |
| + Cool-down | **85.5** | **77.7** | **0.307** | **47.9** |

---

## 4. 下游任务结果

### 预测任务

| 任务 | 指标 | 之前 SOTA | V-JEPA 2.1 |
|------|------|----------|------------|
| Ego4D STA | mAP All | 6.02 (V-JEPA 2) | **7.71** |
| EPIC-KITCHENS 动作预测 | Action Recall@5 | 39.7 (V-JEPA 2) | **40.8** |

### 机器人

| 任务 | V-JEPA 2 | V-JEPA 2.1 | 提升 |
|------|----------|-----------|------|
| Grasp (300 samples, 15 iter) | 60% | **80%** | +20pp |
| Pick-&-Place | 80% | 80% | - |
| 导航 TartanDrive ATE | 5.831 | **5.687** | +10× faster |

### 密集理解

| 任务 | 指标 | V-JEPA 2.1 | 对比 |
|------|------|-----------|------|
| NYUv2 深度估计 | RMSE | **0.307** | 超越 DINOv3 ViT-7B (0.309) |
| KITTI 深度 | RMSE | 2.461 | 同级最佳（<2B参数） |
| VOC12 语义分割 | mIoU | 85.0 | 接近 DINOv3 |
| YouTube-VOS | J&F-Mean | 72.7 | 仅次 DINOv3 |

### 全局理解

| 任务 | V-JEPA 2.1 |
|------|-----------|
| SSv2 动作识别 | **77.7** (新 SOTA) |
| K400 | 87.7 |
| ImageNet | 85.5 |

---

## 5. 蒸馏

ViT-G (2B) → ViT-L (300M) → ViT-B (80M)

- 蒸馏损失同预训练（但仅用教师最后一层，无深层自监督）
- ViT-L 蒸馏后性能接近 ViT-G（SSv2 76.5 vs 77.7, ADE20K 46.7 vs 47.9）

---

## 6. MimirAether 映射

### 关键可迁移概念

1. **密集预测损失 → 三层记忆自检**
   - 不仅是最终输出，中间表示层也要参与质量评估
   - Session 记忆 / Cross-session 记忆 / Wiki——每层独立自检

2. **深层自监督 → 信息流贯通**
   - 类比：最终层的压缩表示不应丢失中间步骤的精细信息
   - 上下文压缩时保留"每个中间步骤的质量分数"

3. **多模态 Tokenizer → 跨模态记忆统一**
   - 飞书消息 / 终端输出 / 文件内容 → 统一 tokenization 策略
   - 模态 embedding 告知处理管线输入类型

4. **距离加权损失 → 关联强度衰减**
   - 靠近关键信息的记忆节点权重更高
   - 远离上下文的无关信息自然衰减

5. **缩放 → 记忆质量随数据增长的监控**
   - 随技能数/会话数增长，表示质量不应退化
   - Cool-down 类比：定期降低"学习率"巩固已有知识
