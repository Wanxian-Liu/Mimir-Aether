# GOD 拆分 — 精确边界

> 来源: gateway/run.py (9,273行)
> 策略: Mixin 类，每个独立文件，GatewayRunner 多重继承
> 每段: 创建文件 → 移动方法 → tier0绿 → 下一段

## 6 模块边界

| # | 文件 | 行范围 | 方法数 | 估计行数 |
|---|------|--------|--------|----------|
| 1 | `gateway/voice_mixin.py` | 714-772, 4878-5208 | 11 | ~450 |
| 2 | `gateway/cron_mixin.py` | 5344-5673, 6690-7032, 8809-9164 | 8 | ~600 |
| 3 | `gateway/health_mixin.py` | 1025-1120, 1391-1539, 1837-1858, 1978-2104 | 14 | ~500 |
| 4 | `gateway/session_mixin.py` | 773-891, 907-996, 1398-1426, 1859-1977, 7033-7057, 7390-7461 | 12 | ~700 |
| 5 | `gateway/router_mixin.py` | 2381-2501, 2502-3982, 3983-6597 | 35 | ~2300 |
| 6 | `gateway/agent_mixin.py` | 7058-8808 | 5 | ~1400 |

## 执行顺序

1. voice_mixin (最小,自包含) → 验证模式
2. cron_mixin → 验证定时任务正常
3. health_mixin → 验证监控心跳
4. session_mixin → 验证会话管理
5. router_mixin (最大) → 验证消息路由
6. agent_mixin → 验证Agent生命周期

每段后: run_ralph_tier0.sh 确保 162 passed
