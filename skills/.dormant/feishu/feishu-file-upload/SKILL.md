---
description: "使用 lark-cli 发送文件到飞书聊天（无需写代码拼API）"
auto_load: false
---

# 飞书文件上传 (lark-cli)

## 前置条件
1. `lark-cli` 已安装：`npm install -g @larksuite/cli`
2. 已绑定 bot-only 身份：`lark-cli config init` → select bot-only
3. 已登录：`lark-cli auth login`（走 .env 凭据）

## 发送文件到飞书聊天

```bash
lark-cli im +messages-send \
  --chat-id "oc_xxx" \
  --file /path/to/file.docx \
  --file-name "display_name.docx"
```

### 参数说明
- `--chat-id`：飞书 chat ID（oc_ 开头），从 Gateway 日志或飞书 API 获取
- `--file`：本地文件绝对路径
- `--file-name`：飞书中显示的文件名（可选，默认为本地文件名）

## 查找 chat_id
从 Gateway 运行日志中看到的消息格式：
```
feishu_adapter: received message from chat oc_xxxxx
```
复制 `oc_` 开头的 ID 即可。

## 验证文件已送达
用户飞书消息中出现文件卡片即可确认。如文件超过 20MB 需考虑分片，但 lark-cli 自动处理。

## 故障排除
| 错误 | 原因 | 修复 |
|:----|:----|:----:|
| `Error: Not authenticated` | 未登录 | `lark-cli auth login` |
| `Error: chat not found` | chat_id 错误 | 从日志重新获取正确 chat_id |
| `Error: file not found` | 文件路径错误 | 使用绝对路径 + 确认文件存在 |

## 替代方案
如果 lark-cli 不可用，gateway 内置 `feishu_adapter.send_file()` 方法（commit a2befee）也支持文件上传。
