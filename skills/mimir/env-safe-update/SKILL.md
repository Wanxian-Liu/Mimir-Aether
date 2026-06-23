# `update_env_var()` — 安全更新 .env 文件

## 问题

`write_file` 会**整文件覆盖**，导致 `.env` 中的密钥（FEISHU_APP_SECRET, DEEPSEEK_API_KEY 等）被误删。

## 正确流程

不要直接 `write_file` 写整份 `.env`。用以下 Python 流程：

```python
from hermes_tools import read_file, write_file

path = "~/.mimiraether/.env"

# 1. 先读
content = read_file(path)["content"]

# 2. 只改目标行
lines = content.splitlines()
new_line = "MIMIR_WM_PREDICTOR=1"
found = False
for i, line in enumerate(lines):
    if line.startswith("MIMIR_WM_PREDICTOR="):
        lines[i] = new_line
        found = True
        break
if not found:
    lines.append(new_line)

# 3. 写前备份
import shutil, os
real_path = os.path.expanduser(path)
shutil.copy2(real_path, real_path + ".bak")

# 4. 写回（仅改过的行）
result = write_file(path, "\n".join(lines) + "\n")

# 5. 验证关键行没有被误删
verify = read_file(path)["content"]
assert "FEISHU_APP_SECRET" in verify, "❌ FEISHU_APP_SECRET 被误删了！"
assert "DEEPSEEK_API_KEY" in verify, "❌ DEEPSEEK_API_KEY 被误删了！"
```

## 两条硬规则

1. **绝对不要**对 `.env` 用裸 `write_file`。永远用 `update_env_var()` 流程。
2. 写后**必须**验证关键密钥没有丢失（FEISHU_APP_SECRET, DEEPSEEK_API_KEY, TAVILY_API_KEY）。
