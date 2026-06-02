# IQ55-12c: 工具延迟根因分析

> 源：`data/ops/tool-latency-profile.json` · `tool_quality.db`
> 状态：画像完成 — 5.5 门槛已满足（仅需画像，7.5 才需修）

---

## 总体情况

35 个工具中 **30/35 (86%) P95 < 10s**。P95 总延迟被**3 个长尾工具**拉高：

| 工具 | P95 | 占 P95 总量% | 标志 |
|------|:---:|:-----------:|:----:|
| `mimir_ops` | **98.7s** | 47% | CRITICAL |
| `terminal` | **85.0s** | 40% | CRITICAL |
| `web_extract` | **67.6s** | 32% | CRITICAL |
| `execute_code` | **12.2s** | — | WARN |
| `web_search` | **12.6s** | — | WARN |

### 健康检查中报告的 P95 91s 的来源

`mimir_ops` 的 `health_check` 调用是**主因**。R4/R5 阶段运行 `evolution_eval` / `brain_metrics_snapshot` 需要几分钟。这被计入 `tool_quality.db` 作为单次工具调用耗时。

**结论**：P95 91s 是这个工具的**正常行为**，不是故障。健康检查就是慢的（因为包含了 eval/快照）。

---

## 根因分类

### 1. 超时配置（terminal · 主因）

`terminal` 工具的默认 timeout=180s。这是设计如此——长命令（tier0、进化、长脚本）必须用大 timeout。**这不是缺陷**，是工具语义必然的结果。

### 2. 网络延迟（web_extract · web_search · browser_navigate）

`web_extract` 的慢是**外部**：远程 URL 响应慢 + LLM summarization 的额外延迟。`web_search` 类似，调用外部搜索 API。

**无 Mimir 侧修复**。这些速度由上游 API 决定。

### 3. 计算密集型（mimir_ops health_check）

R4 (evolution_eval) 和 R5 (brain_metrics_snapshot) 运行数据库查询 + 脚本调用 + 结果汇总。这是**预期行为**，不是故障。

### 4. 质量分=0 但延迟低（crash_tool · orphan_tool）

```
crash_tool:  call=332 · success=0% · P95=3.9ms
orphan_tool: call=331 · success=0% · P95=0.8ms
```

这两个工具**总是失败**但**极快**（<4ms）。说明它们是「快速失败」工具，不是延迟问题。

---

## 结论：P95 91s 是正常的

从 `tool_quality.db` 的数据看：

- **86% 工具** P95 < 10s
- **P95 91s** 被 3 个设计上就慢的工具拉高（health_check、terminal、web_extract）
- 这些工具的慢**不是代码缺陷**，是它们的功能语义决定的

### 5.5 门槛已满足

> IQ55-12a ✅ 画像文件 `data/ops/tool-latency-profile.json`
> IQ55-12b ✅ 标红：mimir_ops/terminal/web_extract P95>30s
> IQ55-12c ✅ 根因分析（本文档）
> IQ55-12d ⏭️ 7.5 门槛（P95<10s）——需逐项修复，非本波次

### 7.5 修复方向（如果做）

1. `health_check` 添加 `--quick` 模式（仅 R1-R5 不跑 eval）✅ **已存在**
2. `terminal` 无优化空间（长命令必须）
3. `web_extract` 可加本地缓存？但 R/O 并行即可缓解
