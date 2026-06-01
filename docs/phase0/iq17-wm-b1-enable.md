# IQ-11: WM B1 VoE LEARNING 启用登记

> 日期：2026-06-01 · 参考：[wm-production-enablement.md](../proposals/wm-production-enablement.md) 步骤 1

## 状态：✅ 已启用

| 项 | 值 |
|----|-----|
| `.env` 变量 | `MIMIR_WM_VOE_LEARNING=1`（刘哥手动添加） |
| Gateway | 已重启（PID 144962） |
| `surprise_events.jsonl` | 存在（343 bytes，重启前事件） |
| `learned_surprises.json` | 暂不存在（重启后尚未触发 surprise） |

## .env 记录

```bash
grep MIMIR_WM_VOE_LEARNING ~/.mimiraether/.env
→ MIMIR_WM_VOE_LEARNING=1
```

## 验证命令

```bash
grep SURPRISE_DETECTED ~/.mimiraether/logs/agent.log | tail -3
ls -la ~/.mimiraether/data/wm_phase0/
```

## 回滚

```bash
# 删除 .env 行后重启 gateway
sed -i '/MIMIR_WM_VOE_LEARNING/d' ~/.mimiraether/.env
# 然后 shell 执行 ensure_single_gateway.sh（非飞书内）
```

## 备注

- 当前无 surprise 可记，**待退化触发后复验**（IQ-22 观察窗）
- 重启前产生的 SURPRISE_DETECTED（04:56）属旧 session，B1 功能已生效
