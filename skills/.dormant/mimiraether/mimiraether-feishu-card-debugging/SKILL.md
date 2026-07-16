# MimirAether 飞书卡片调试

HTML→飞书交互卡片的消息发送失败调试流程。

## 症状分类

| 症状 | 可能原因 |
|------|----------|
| 只看到纯文本 | 卡片转换失败，adapter fallback 到 text |
| 什么都看不到 | fallback 本身也失败（常见：没剥离 HTML 标记） |
| 飞书报错 230099/200907 | 卡片 JSON 不合规 |

## 调试四层

### 第1层：确认哪些消息失败
- 手动分类：成功的消息 vs 失败的消息
- 找共同特征：含 `<table>` 的崩？含 `<button>` 的崩？
- 缩小范围到具体 HTML 元素

### 第2层：追踪转换器输出
- `html_to_feishu_card.py` 的转换函数按元素类型分派
- 检查生成的卡片 JSON 是否符合飞书 API 规范
- 常见错误：`columns` 缺 `name` 字段（飞书表格必须）

### 第3层：追踪 fallback 路径
- `base.py:1459` 兜底逻辑
- 检查兜底内容是否剥离了 `<!-- MIMIR:HTML_OUTPUT -->`
- 如果没剥离 → 再次触发 conversion → 再次失败 → 无限循环

### 第4层：区分转换器错误 vs API 错误
- 转换器抛异常 → `convert_or_fallback()` 的 `except Exception` 会 catch
- 转换器返回了结构完整但语义不合规的 JSON → **不会抛异常**，飞书 API 在服务端才拒绝
- 这是静默失败的最常见根因

## 关键文件

| 文件 | 行号 | 角色 |
|------|------|------|
| `gateway/html_to_feishu_card.py` | 全文 | HTML→卡片 JSON 转换 |
| `gateway/platforms/feishu_adapter.py` | 527 | 触发转换的入口 |
| `gateway/base.py` | 1455-1462 | 发送失败兜底逻辑 |
