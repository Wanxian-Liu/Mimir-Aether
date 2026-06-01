# §13 MW 收官 — 刘哥可选生产开关（shell 执行）

> Mimir **不能**改 `~/.mimiraether/.env`。以下 **默认均为关**；逐项开启、观察、可回滚。  
> **禁止**在飞书对话 turn 内 `kill` gateway / `ensure_single_gateway`。

## 通用：改 env 后重启

```bash
cd ~/src/MimirAether && bash scripts/ensure_single_gateway.sh
curl -s http://127.0.0.1:18999/health | python3 -m json.tool | head -5
```

---

## 1. 规则 WM 预测（IQ-31 · 先要数据）

```bash
grep -q '^MIMIR_WM_PREDICTOR=1' ~/.mimiraether/.env || echo 'MIMIR_WM_PREDICTOR=1' >> ~/.mimiraether/.env
```

- log：`wm_prediction needs=`（`agent.log`）
- 回滚：`sed -i '/^MIMIR_WM_PREDICTOR=/d' ~/.mimiraether/.env` + 重启 gateway
- 详见 [`mw-00-prod-env.md`](./mw-00-prod-env.md)

**不做**：`MIMIR_WM_LLM_PREDICTOR` / WM-B5 — [`wm-b5-llm-predictor-deferred.md`](./wm-b5-llm-predictor-deferred.md)

---

## 2. 并行只读工具（MW-02）

```bash
grep -q '^MIMIR_PARALLEL_TOOLS=1' ~/.mimiraether/.env || echo 'MIMIR_PARALLEL_TOOLS=1' >> ~/.mimiraether/.env
```

- log：`parallel dispatch: N read-only, M serial`
- 仅白名单只读工具并行；`write_file` / `terminal` / `memory` 仍串行
- 回滚：`sed -i '/^MIMIR_PARALLEL_TOOLS=/d' ~/.mimiraether/.env` + 重启

---

## 3. 周期 nudge（MW-04）

```bash
# 默认代码里 N=3；显式写入便于调参。0=关闭
grep -q '^MIMIR_NUDGE_INTERVAL=' ~/.mimiraether/.env || echo 'MIMIR_NUDGE_INTERVAL=3' >> ~/.mimiraether/.env
```

- log：`interval nudge (interval=N)`
- **行为**：每会话 **至多 1 次**（turn>0 且 turn%N==0 时）；非每 N 轮重复
- 回滚：`MIMIR_NUDGE_INTERVAL=0` 或删除该行 + 重启

---

## 建议启用顺序

1. `MIMIR_WM_PREDICTOR=1` — 观察 3～7 天  
2. `MIMIR_PARALLEL_TOOLS=1` — 飞书多工具只读场景试一轮  
3. `MIMIR_NUDGE_INTERVAL=3` — 长对话会话再开  

VoE 阶梯（与 WM 无关但常一起开）：`MIMIR_WM_VOE_LEARNING=1` → 见 [`wm-production-enablement.md`](../proposals/wm-production-enablement.md)
