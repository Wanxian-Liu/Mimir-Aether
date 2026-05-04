# M4 HTTP 错误形状（静态 fixture）

与 **`docs/m4_auxiliary_http_slice.md`**、**`docs/ralph_roadmap_milestones.md` M4** 对齐：本目录存放**脱敏、无真实 key** 的 JSON 样本，供 `agent/test_m4_auxiliary_http_slice.py` 加载，证明「401 / 429 / 超时 / 连接」等形态在**分类层**有稳定断言。

## 约束

- **CI**：不访问外网；fixture 仅本地 JSON。
- **内容**：可从供应商公开错误文档摘录或自行脱敏；勿提交 token、私有 URL。

## 文件

| 文件 | 说明 |
|------|------|
| `error_shapes.json` | 数组；每条含 `id`、`payment`、`connection`（期望分类）与 `exc` 描述 |

## 如何刷新 / 新增形状

1. 编辑 **`error_shapes.json`**，追加对象；`exc` 的 `kind` 见测试内 `_exc_from_fixture` 支持集合。
2. 运行校验：

   ```bash
   ./scripts/refresh_m4_http_fixtures.sh
   ```

   或完整门禁：`./run_ralph_tier0.sh`

3. 在 PR 描述中注明「M4 fixture 更新」及来源（文档链接或「手工构造」）。

## 与「录播 / mock 服务」的关系

本仓库 M4 **最小绿**：**离线分类 + 静态 fixture + 刷新脚本**。全量 VCR、常驻 mock 服务可作为后续增强，**不**阻塞 M4 工程表标绿（见路线图 M4 小节说明）。
