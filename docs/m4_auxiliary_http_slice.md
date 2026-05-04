# M4 最小切片：辅助 HTTP 错误分类（离线）

## 本 PR 范围

对应里程碑 **[M4：Tier-2 HTTP（可选）](ralph_roadmap_milestones.md#m4tier-2-http可选)** 的**分类层**子集：锁定 `agent/auxiliary_client.py` 中 **`_is_payment_error`** 与 **`_is_connection_error`** 的启发式行为（401 vs 计费相关 429 vs 超时/连接类异常），**不**改动 `call_llm` 全栈或提供商路由。

**产出物（工程表 M4 绿）**

- 静态错误形状目录：**`fixtures/m4_http/`**（含 **`error_shapes.json`**、**`README.md`** — 如何刷新与约束）。
- 校验脚本：**`scripts/refresh_m4_http_fixtures.sh`**（无网；跑本切片 pytest）。

## 自动化验收（无网、无真实 key）

测试文件：`agent/test_m4_auxiliary_http_slice.py`

运行：

```bash
python3 -m pytest -q agent/test_m4_auxiliary_http_slice.py
```

纳入默认门禁：`./run_ralph_tier0.sh`（Gate2 列表）。

## 非目标（本切片不做）

- 无 VCR、无 live HTTP、无常驻 mock server 进程。
- 不扩展 respx / 全量录制回放；不改变 Tier-0 以外的 HTTP 客户端实现策略。

可选后续（增强，非 M4 绿必要条件）：VCR、本地 `httpx` mock 服务、更广提供商响应体 — 仍见 **`docs/ralph_roadmap_milestones.md`** 正文与 **`fixtures/m4_http/README.md`**。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-04 | `fixtures/m4_http/*` + `scripts/refresh_m4_http_fixtures.sh`；JSON 驱动分类断言；MAINLINE M4 标绿。 |
| 2026-05-01 | 初版：分类函数离线断言 + Gate2 纳入。 |
