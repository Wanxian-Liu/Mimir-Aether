# IQ-55 执行工作流（Mimir 主执行 · 单粒循环）

> 对齐 [`MIMIR_IQ55_ROADMAP.md`](./MIMIR_IQ55_ROADMAP.md) · Ralph：`./run_ralph_tier0.sh` 每粒后绿  
> **Cursor**：规划、勘误、刘哥 env、tier0 抽检；**大块 agent 代码由 Mimir 提交**。

## 1. 取下一粒

```bash
cd ~/src/MimirAether
./scripts/mimir_iq55_run_next.sh --dry-run
```

输出 `NEXT_TASK=IQ55-xx` 后，在 `MIMIR_TASK_QUEUE.md` §14 找到对应行，在 roadmap 找子粒表。

## 2. 单粒 DoD

1. **范围**：只改该 ID 声明的文件；不顺手重构。
2. **验证**：子粒表中的 pytest / 脚本 / audit JSON。
3. **tier0**：`./run_ralph_tier0.sh` exit 0（合并前）。
4. **M6**：触达 `agent/`/`gateway/`/`tools/` 时 `./scripts/record_m6_evolution.sh "IQ55-xx: …"`。
5. **队列**：同 commit 将 §14 该行 `[ ]` → `[x]`。
6. **推送**：`git push`（`BRAIN_AUTONOMY` / PRIMARY_EXECUTOR）。

## 3. 粒型模板

### 文档粒（IQ55-00/01）

- 只改 `docs/`；验证：链接存在、数字与脚本输出一致。

### 代码粒（IQ55-10b 等）

- 先 failing test（若已有契约则扩展）。
- 实现 → tier0 → M6 一行。

### 运维粒（IQ55-OPS-*）

- **Mimir 不改** `~/.mimiraether/.env`。
- 写 `docs/phase0/iq55-ops-*.md` 记录刘哥执行结果与 log 摘录（无密钥）。

### 观察粒（IQ55-OPS-04 / IQ55-22）

- 跑脚本，附输出路径；无代码亦可 `[x]`。

## 4. 停止条件

- `./scripts/mimir_iq55_run_next.sh` → `NEXT_TASK=NONE` 且 **IQ55-10e + IQ55-11e + IQ55-20** 均已 [x] → 可宣称 **5.5 达标候选**（须刘哥确认 audit 数字）。
- 未达 5.5：**禁止**更新 IQ 到 6+ 或 MAINLINE「已进化」。

## 5. 与 Ralph / Ralph 模式

用户要求 Ralph 模式时：每轮 **问题→修复→`run_ralph_tier0.sh`**，连续 3 次全绿。

## 6. 修订

| 日期 | 摘要 |
|------|------|
| 2026-06-02 | 初版：§14 链 · P0/P1/P2 映射 · Mimir 主执行 |
