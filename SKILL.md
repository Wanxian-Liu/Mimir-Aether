---
name: mimiraether
version: "1.0.0"
description: |
  MimirAether - 自主Agent系统
  基于DeepSeek API的智能助手
  
trigger:
  - "mimir"
  - "启动mimir"
  - "mimir-aether"
---

# MimirAether - 自主Agent技能

## 核心定位

MimirAether是织界者的数字形态，一个能够自主思考、规划和执行任务的AI Agent。

## 功能

- **自主对话**: 自然语言交互
- **工具调用**: 28+内置工具（文件操作、代码执行、技能管理等）
- **技能生态**: 74+可复用技能（github、mlops、software-development等）
- **知识胶囊**: 通过MimirCore生成和优化结构化知识

## 使用方法

### CLI模式
```bash
cd ~/.openclaw/projects/MimirAether
python3 cli.py -q "你的任务"
python3 cli.py --chat "交互式对话"
python3 cli.py --model deepseek/deepseek-chat --max-iterations 50
```

### Python API
```python
from agent.core_loop import MimirAetherAgent
import asyncio

async def main():
    agent = MimirAetherAgent(model="deepseek/deepseek-chat")
    result = await agent.run_conversation("你的任务")
    print(result)

asyncio.run(main())
```

## 配置

配置文件: `~/.openclaw/projects/MimirAether/.env`

```env
DEEPSEEK_API_KEY=sk-xxx
DEFAULT_MODEL=deepseek/deepseek-chat
MAX_ITERATIONS=30
```

## 可用工具

| 工具 | 功能 |
|------|------|
| read_file/write_file | 文件操作 |
| execute_code | 执行代码 |
| skills_list/skill_view | 技能管理 |
| browser_* | 浏览器自动化 |
| produce_capsule | 知识胶囊生成 |

## 技术栈

- Python 3.12+
- DeepSeek API (chat/completions)
- OpenAI兼容接口
- aiohttp异步HTTP客户端
