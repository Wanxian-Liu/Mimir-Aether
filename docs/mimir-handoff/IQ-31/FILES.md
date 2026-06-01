# IQ-31 改动文件

| 文件 | 改动 | 行 |
|------|------|:--:|
| `agent/agent_loop.py` | import + context_snapshot 构建 + predict 调用 + cross-session 渲染 | ~+20 |
| `agent/world_model_spike.py` | **不改** — 已有完整 API | 0 |
| `tests/agent/test_world_model_spike.py` | **不改** — 单测已覆盖 | 0 |

## 总览

| 类型 | 值 |
|------|:--:|
| 总改动 | **1 文件** |
| 新增行 | **~+20** |
| 删除行 | **0** |
| 新依赖 | 无 |
| 环境变量 | `MIMIR_WM_PREDICTOR=1`（默认关） |
