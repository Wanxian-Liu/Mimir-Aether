# MW-00: 生产环境开启 WM 预测器

> **Mimir 不能直接改 `.env`**，需刘哥在 shell 执行。

## 1. 添加 env 变量

```bash
echo 'MIMIR_WM_PREDICTOR=1' >> ~/.mimiraether/.env
```

## 2. 重启 gateway

```bash
cd ~/src/MimirAether && bash scripts/ensure_single_gateway.sh
```

## 3. 确认生效

```bash
grep MIMIR_WM_PREDICTOR ~/.mimiraether/.env
curl -s http://127.0.0.1:18999/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'pid={d[\"pid\"]}')"
```

## 行为变化

`MIMIR_WM_PREDICTOR=1` 生效后，Mimir 在每轮对话 **turn 0** 会调用 WM 预测器，输出 `<intent-context>` 辅助意图理解。

## 回滚

```bash
sed -i '/MIMIR_WM_PREDICTOR/d' ~/.mimiraether/.env
cd ~/src/MimirAether && bash scripts/ensure_single_gateway.sh
```
