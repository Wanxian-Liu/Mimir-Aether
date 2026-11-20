# E7 单点迁移 · 可追溯补件（2026-09-16）

**事由**：Loki E-14 反对①（严重）——「13 件迁移」不在 commit `56b9eca` 中，且 home 仓 `.gitignore` 第 8 行 `*` 忽略 `scripts/` ⇒ **迁移修改不可追溯**。

**为什么会有这个洞**：迁移对象是 `~/.mimiraether/scripts/` 下的 **home 侧**脚本（repo 侧无同名文件），该目录整体被 gitignore（`git check-ignore -v scripts/audit_send_paths.py` → `.gitignore:8:*`）。commit `56b9eca` 只含 repo 侧的 3 个文件（审计脚本 + `buzz_send.py` + 闸测试）⇒ 真正被改的 13 件**没有任何版本痕迹**。

**本目录做什么**：把「改了什么」变成**可从受控仓重建**的件——
- `MANIFEST.json`：每件 pre/post **sha256** + 行数 + 增删行数 + 触及标识符
- `diffs/<name>.diff`：由备份 pre-image 与**现行** post-image **现算**的 unified diff（不是抄报告）
- `verify.py`：复现闸 —— 现行文件 sha256 必须等于 MANIFEST 的 `post_sha256`，且 `audit_send_paths.py` 必须 `VERDICT: PASS`（writer 面 = 0）

**复现**：
```bash
python3 ~/src/MimirAether/scripts/migrations/20260916_e7_single_path/verify.py
```

**已知局限（不粉饰）**：
1. 这是**事后补件**，不是迁移当时的原子提交 —— 时点不可回溯，只能证明「现状 == 记录的迁移结果 + 与 pre-image 的差异」。
2. `pre_images` 是迁移前的**工作副本**，非 git 对象；其完整性由本 MANIFEST 记录的 `pre_sha256` 约束。
3. 根因（home `scripts/` 被 gitignore）**未修** —— 这是单独的治理问题（会影响所有 home 侧脚本的可审计性），不在 E7 范围内擅自扩大。
