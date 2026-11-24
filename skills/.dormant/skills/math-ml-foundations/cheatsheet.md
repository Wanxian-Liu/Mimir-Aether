# 速查表 —— Mathematics for Machine Learning

## 依赖链（按序学或按需回溯）
```
Ch2 线性代数 → Ch3 解析几何 → Ch4 矩阵分解 → Ch5 向量微积分 → Ch7 优化
                    ↘                              ↗
                      Ch6 概率 ──────────────────┘
                              ↓
                         Ch8 模型/数据/学习数学化
                              ↓
              ┌──────┬──────┴──────┬──────┐
              ↓      ↓             ↓      ↓
            Ch9    Ch10           Ch11   Ch12
           回归    PCA降维         GMM    SVM
```

## 核心公式一页纸

### 线性代数
| 操作 | 公式 |
|------|------|
| 线性映射矩阵 | f(v) = Av，A_j = f(e_j) |
| 换基 | A' = P⁻¹AP |
| 正交投影 | P_U = A(AᵀA)⁻¹Aᵀ |
| SVD 低秩近似 | A_k = Σ_{i=1}^k σ_i u_i v_iᵀ |
| 伪逆 | A⁺ = VΣ⁺Uᵀ |
| 正规方程 | AᵀAx = Aᵀb |

### 解析几何
| 操作 | 公式 |
|------|------|
| 内积 | ⟨x,y⟩ = xᵀAy |
| 范数 | ‖x‖ = √⟨x,x⟩ |
| 距离 | d(x,y) = ‖x-y‖ |
| 角度 | cos θ = ⟨x,y⟩/(‖x‖‖y‖) |
| 投影 | π_U(x) = QQᵀx (Q标准正交) |
| Gram-Schmidt | u_k = v_k - Σ_{j<k} ⟨v_k,u_j⟩u_j/⟨u_j,u_j⟩ |

### 矩阵分解
| 分解 | 形式 | 用途 |
|------|------|------|
| 特征分解 | A = QΛQᵀ (对称) | PCA、谱聚类 |
| SVD | A = UΣVᵀ (任意) | 万能工具 |
| QR | A = QR | 最小二乘稳定解 |
| Cholesky | A = LLᵀ (正定) | 采样、优化 |

### 向量微积分
| 导数 | 公式 |
|------|------|
| 梯度 | ∇(xᵀAx) = (A+Aᵀ)x |
| 矩阵导数 | ∂(aᵀXb)/∂X = abᵀ |
| logdet | ∂log det(X)/∂X = X⁻ᵀ |
| 迹 | ∂tr(AXB)/∂X = AᵀBᵀ |
| 链式法则 | J_{f∘g} = J_f J_g |

### 概率/分布
| 分布 | 共轭先验 |
|------|----------|
| Bernoulli/Binomial | Beta |
| Categorical/Multinomial | Dirichlet |
| Poisson/Exponential | Gamma |
| Gaussian (μ) | Gaussian |
| Gaussian (Λ=Σ⁻¹) | Wishart |

### 优化
| 算法 | 步长/更新 |
|------|----------|
| GD | x ← x - η∇f(x)，η ≤ 2/L |
| Momentum | v ← γv + η∇f；x ← x - v |
| Newton | x ← x - H⁻¹∇f |
| KKT | ∇f + Σν∇h + Σλ∇g = 0, λ≥0, λg=0 |

### 回归
| 方法 | 解 |
|------|----|
| MLE (OLS) | θ = (XᵀX)⁻¹Xᵀy |
| Ridge | θ = (XᵀX + λI)⁻¹Xᵀy |
| 贝叶斯后验 | N(θ\|Σ_N Xᵀy/σ², Σ_N) |

### PCA
| 步骤 | 操作 |
|------|------|
| 1 | 中心化 X ← X - mean |
| 2 | SVD X = UΣVᵀ |
| 3 | 取 V_k (前k列) |
| 4 | 投影 Z = XV_k |
| 选择k | 累积解释方差 ≥ 95% |

### GMM/EM
| 步骤 | 公式 |
|------|------|
| E步 | γ_ik = π_k N(x_i\|μ_k,Σ_k) / Σ_j π_j N(x_i\|μ_j,Σ_j) |
| M步 | π_k = Σγ_ik/n；μ_k = Σγ_ik x_i/Σγ_ik；Σ_k = Σγ_ik(x_i-μ_k)(x_i-μ_k)ᵀ/Σγ_ik |

### SVM
| 形式 | 公式 |
|------|------|
| 原始 | min ½‖w‖² + C Σξ_i s.t. y_i(wᵀx_i+b)≥1-ξ_i |
| 对偶 | max Σα_i - ½ΣΣα_iα_j y_i y_j K(x_i,x_j) |
| 决策 | f(x) = sign(Σα_i y_i K(x_i,x) + b) |
| 核(RBF) | K(x,x') = exp(-γ‖x-x'‖²) |

## 常用检查
- [ ] 数据标准化？（PCA/SVM/RBF/梯度下降必须）
- [ ] 条件数 κ < 1e10？（否则正则化/截断 SVD）
- [ ] 梯度检查通过？（有限差分）
- [ ] 验证 loss 监控 + 早停？
- [ ] 测试集锁死、最后只评一次？

---

*MML 速查表 | 基于 Deisenroth/Faisal/Ong (2020) | 个人学习用*