# 术语表

| 术语 | 英文 | 定义/公式 | 章节 |
|------|------|-----------|------|
| 向量空间 | Vector Space | 满足加法封闭、数乘封闭、含零向量、加法逆元的集合 | Ch2 |
| 基 | Basis | 线性无关且张成空间的一组向量 | Ch2 |
| 线性映射 | Linear Map | 保持加法和数乘的映射 f: V→W | Ch2 |
| 秩 | Rank | 列空间维数 = 行空间维数 | Ch2 |
| 特征值 | Eigenvalue | Av = λv 中的 λ | Ch2, Ch4 |
| 特征向量 | Eigenvector | Av = λv 中的 v | Ch2, Ch4 |
| 奇异值分解 | SVD | A = UΣVᵀ，U,V 正交，Σ 对角非负 | Ch4 |
| 内积 | Inner Product | ⟨x, y⟩ = xᵀAy (A≻0) | Ch3 |
| 范数 | Norm | ‖x‖ = √⟨x, x⟩ | Ch3 |
| 正交投影 | Orthogonal Projection | π_U(x) = A(AᵀA)⁻¹Aᵀx | Ch3 |
| 格拉姆-施密特 | Gram-Schmidt | 从任意基构造标准正交基 | Ch3 |
| 梯度 | Gradient | ∇f(x) ∈ R^n，f: R^n→R | Ch5 |
| 雅可比矩阵 | Jacobian | J_f(x) ∈ R^{m×n}，f: R^n→R^m | Ch5 |
| 海森矩阵 | Hessian | H_f(x) ∈ R^{n×n}，二阶导数矩阵 | Ch5 |
| 自动微分 | Automatic Diff | 计算图反向累积梯度 | Ch5 |
| 贝叶斯定理 | Bayes Theorem | p(θ|D) = p(D|θ)p(θ)/p(D) | Ch6 |
| 指数族 | Exponential Family | p(x|η) = h(x)exp(ηᵀT(x) - A(η)) | Ch6 |
| 共轭先验 | Conjugate Prior | 先验∈指数族 ⇒ 后验同族 | Ch6 |
| 凸集 | Convex Set | ∀x,y∈C, λ∈[0,1]: λx+(1-λ)y∈C | Ch7 |
| 凸函数 | Convex Function | f(λx+(1-λ)y) ≤ λf(x)+(1-λ)f(y) | Ch7 |
| 强凸 | Strong Convexity | f(x) - (μ/2)‖x‖² 凸 (μ>0) | Ch7 |
| Lipschitz 梯度 | L-Lipschitz Gradient | ‖∇f(x)-∇f(y)‖ ≤ L‖x-y‖ | Ch7 |
| KKT 条件 | KKT Conditions | 约束优化必要条件 | Ch7 |
| 经验风险 | Empirical Risk | R_emp(θ) = (1/n) Σ L(f_θ(x_i), y_i) | Ch8 |
| 期望风险 | Expected Risk | R(θ) = E[L(f_θ(x), y)] | Ch8 |
| 泛化间隙 | Generalization Gap | R(θ) - R_emp(θ) | Ch8 |
| 正则化 | Regularization | R_emp(θ) + λΩ(θ) | Ch8 |
| 最大似然估计 | MLE | max_θ p(D|θ) | Ch9 |
| 最大后验估计 | MAP | max_θ p(θ|D) | Ch9 |
| 贝叶斯线性回归 | Bayesian Linear Regression | 后验 p(θ|D) 高斯，预测分布解析 | Ch9 |
| 模型证据 | Model Evidence | p(D) = ∫ p(D|θ)p(θ)dθ | Ch9 |
| 主成分 | Principal Component | 协方差矩阵特征向量 | Ch10 |
| 解释方差比 | Explained Variance Ratio | λ_k / Σ λ_i | Ch10 |
| 混合高斯 | GMM | p(x) = Σ π_k N(x|μ_k, Σ_k) | Ch11 |
| EM 算法 | EM Algorithm | E步计算责任，M步更新参数 | Ch11 |
| 支持向量 | Support Vector | α_i > 0 的训练样本 | Ch12 |
| 核函数 | Kernel Function | K(x,x') = ⟨φ(x), φ(x')⟩ | Ch12 |
| 核技巧 | Kernel Trick | 隐式高维映射，仅需核矩阵 | Ch12 |
| 铰链损失 | Hinge Loss | max(0, 1 - y f(x)) | Ch12 |