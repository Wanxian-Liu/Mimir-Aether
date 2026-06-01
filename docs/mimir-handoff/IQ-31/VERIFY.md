# IQ-31 验证

## 1. tier0 回归

```bash
cd ~/src/MimirAether && ./run_ralph_tier0.sh
```

**期望**：现有 681+ PASS，无新增失败（代码改动小，不影响现有函数）。

## 2. 环境门控（默认关）

```bash
grep MIMIR_WM_PREDICTOR ~/.mimiraether/.env
# 应无输出，或输出 =0（默认关）
```

## 3. 启用后验证

```bash
# 刘哥 shell 执行
echo 'MIMIR_WM_PREDICTOR=1' >> ~/.mimiraether/.env
cd ~/src/MimirAether && bash scripts/ensure_single_gateway.sh

# 发一条任意消息后
grep 'wm_prediction' ~/.mimiraether/logs/agent.log | tail -3
```

**期望**：log 出现 `wm_prediction: Prediction(next_context_needs=..., ...)` 或 `<wm-prediction>` 在 cross-session context 中。

## 4. 回滚验证

```bash
sed -i '/MIMIR_WM_PREDICTOR/d' ~/.mimiraether/.env
# 重启 gateway 后 grep wm_prediction → 不再出现
```
