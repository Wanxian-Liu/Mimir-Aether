# [DORMANT] math-ml-foundations

**沉寂时间**: 2026-11-22T02:34:58.315848+00:00
**原始分类**: skills
**描述**: 《Mathematics for Machine Learning》核心知识技能 —— 线性代数、解析几何、矩阵分解、向量微积分、概率分布、连续优化、回归、降维、密度估计、分类。用于：AI 数学基础自学、模型调试时回溯数学原理、推导公式时查核心定义。
**触发阈值**: 60天未触碰

---

## 技能要点

# Mathematics for Machine Learning — 核心数学框架技能

> **定位**：把 ML 数学基础（Part I：6 章）+ 核心 ML 问题（Part II：4 章）提炼成可按需加载的知识技能。不写书评，只提取可复用的框架、定义、推导路径、反模式。

## 使用方式

| 场景 | 怎么用 |
|------|--------|
| 自学某章 | `skill_view(name='math-ml-foundations', file_path='chapters/ch02-linear-algebra.md')` |
| 查核心定义/公式 | 读 `glossary.md` + 对应章节 |
| 遇到反模式/坑 | 读 `patterns.md` |
| 快速回顾 | 读 `cheatsheet.md` |

## 核心心智模型（全书一张图）

```
Part I: 数学基础（按依赖顺序）
  Ch2  线性代数        → 向量/矩阵/基/线性映射/特征值
  Ch3  解析几何        → 内积/范数/距离/角度/正交投影
  Ch4  矩阵分解        → SVD/特征分解/QR/Cholesky → 降维/求解核心
  Ch5  向量微积分      → 梯度/雅可比/链式法则/自动求导基础
  Ch6  概率与分布      → 随机变量/贝叶斯/指数族/高斯/共轭先验
  Ch7  连续优化        → 凸性/梯度下降/牛顿/约束优化/KKT

Part II: 四大支柱（松耦合，可任意序）
  Ch8  模型/数据/学习数学化 → 实验设计/泛化/正则化
  Ch9  线性回归         → MLE/MAP/贝叶斯线性回归
  Ch10 降维(PCA)        → SVD/特征值/主成分/重构误差
  Ch11 密度估计(GMM)    → EM/混合模型/变分推断入门
  Ch12 分类(SVM)        → 间隔/核技巧/对偶/铰链损失
```

**依赖链**：2→3→4→5→7 是硬依赖；6 独立但被 9/11 用；8 承接 1-7；9-12 各自只依赖 1-7 子集。

## 章节速查

| 章 | 标题 | 核心产出 | 依赖 |
|---|------|----------|------|
| 1 | Introduction & Motivation | 三要素（数据/模型/学习）、两种读法、四支柱图 | — |
| 2 | **Linear Algebra** | 向量空间、基、线性映射、特征值分解、SVD 预览 | — |
| 3 | **Analytic Geometry** | 内积、范数、距离、角度、正交投影、Gram-Schmidt | 2 |
| 4 | **Matrix Decompositions** | 特征分解、SVD、QR、Cholesky、低秩近似 | 2, 3 |
| 5 | **Vector Calculus** | 梯度、雅可比、海森、链式法则、自动微分原理 | 2 |
| 6 | **Probability and Distributions** | 随机变量、期望/方差、贝叶斯、高斯、指数族、共轭先验 | — |
| 7 | **Continuous Optimization** | 凸集/凸函数、梯度下降、牛顿、Lagrange/KKT、约束优化 | 2, 5 |
| 8 | **When Models Meet Data** | 三要素数学化、训练/测试分离、交叉验证、正则化、模型选择 | 1-7 |
| 9 | **Linear Regression** | MLE/MAP、贝叶斯线性回归、预测分布、模型证据 | 2, 3, 5, 6, 7 |
| 10 | **Dimensionality Reduction (PCA)** | 最大方差/最小重构误差、SVD 计算、主成分选择 | 2, 3, 4 |
| 11 | **Density Estimation (GMM)** | 混合高斯、EM 算法、模型选择 (BIC/AIC)、变分推断概念 | 2, 3, 6 |
| 12 | **Classification (SVM)** | 硬/软间隔、核技巧、对偶、SMO 概念、铰链损失 | 2, 3, 5, 7 |

## 关键反模式

| 反模式 | 正确认知 | 出处 |
|--------|----------|------|
| "先学完所有数学再做 ML" | 模块化读法：按需回溯（Top-down）或底层构建 | Ch1.2 |
| 把向量当纯数组 | 三视角：数组/几

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("math-ml-foundations")` 即可自动唤醒。
