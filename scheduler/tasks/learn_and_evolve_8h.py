#!/usr/bin/env python3
"""
MimirAether 学一段+进化一段 持续8小时版

Not the Gateway evolution SoT (ADR-008 path D). Batch research script only;
production skill writes use post_close → skill_evolution.

- 学完一个Hermes模块 → 用大模型生成MimirAether需要的代码 → 写入文件
- 直接调用API，不依赖MimirAether自身

启动:
    python3 learn_and_evolve_8h.py
"""

import sys
import os
import json
import time
import signal
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

MIMIRAETHER_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MIMIRAETHER_DIR))
from mimir_constants import get_mimir_home  # noqa: E402

MIMIRAETHER_HOME = get_mimir_home()
LEARNINGS_DIR = MIMIRAETHER_HOME / "learnings"
EVOLUTION_LOG = LEARNINGS_DIR / "evolution_log_8h.json"
HERMES_DIR = Path(
    os.environ.get("HERMES_AGENT_HOME", str(Path.home() / "hermes-agent"))
)

HERMES_TOPICS = [
    {"file": "agent/insights.py", "name": "InsightsEngine"},
    {"file": "hermes_state.py", "name": "SessionDB"},
    {"file": "hermes_cli/main.py", "name": "CLI"},
    {"file": "mcp_serve.py", "name": "MCPServer"},
    {"file": "agent/prompt_builder.py", "name": "PromptBuilder"},
    {"file": "agent/context_compressor.py", "name": "ContextCompressor"},
    {"file": "agent/credential_pool.py", "name": "CredentialPool"},
]

_running = True
_stop_time = None

# DeepSeek API配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

def signal_handler(signum, frame):
    global _running
    print(f"\n[{time_str()}] 收到停止信号，完成当前模块后退出...")
    _running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def time_str():
    return datetime.now().strftime('%H:%M:%S')

def log(msg):
    print(f"[{time_str()}] {msg}")

def load_state():
    state_file = LEARNINGS_DIR / "learn_evolve_8h_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"index": 0, "evolved": [], "start_time": datetime.now().isoformat()}

def save_state(state):
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    state_file = LEARNINGS_DIR / "learn_evolve_8h_state.json"
    state_file.write_text(json.dumps(state, indent=2))

def call_deepseek(prompt, max_tokens=2000):
    """调用DeepSeek API生成代码"""
    if not DEEPSEEK_API_KEY:
        log("⚠️ 未配置DEEPSEEK_API_KEY，跳过AI生成")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(data).encode(),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        log(f"❌ API错误 {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        log(f"❌ API调用失败: {e}")
        return None

def read_hermes_code(file_path):
    """读取Hermes源码"""
    full_path = HERMES_DIR / file_path
    if not full_path.exists():
        return None
    return full_path.read_text()

def generate_evolution_code(hermes_file, hermes_code, mimiraether_file):
    """用大模型生成MimirAether的进化代码"""
    log(f"🤖 调用AI生成进化代码...")
    
    prompt = f"""你是MimirAether的代码生成专家。

## 任务
将Hermes的代码适配到MimirAether。

## Hermes源文件: {hermes_file}

```python
{hermes_code[:4000]}
```

## 要求
1. 分析Hermes代码的核心逻辑和函数
2. 提取可复用的部分，适配到MimirAether风格
3. 直接输出完整的Python代码文件
4. 保持相同的函数签名和接口

## 输出
只输出```python...```包裹的代码，不要任何解释。
"""
    
    return call_deepseek(prompt)

def apply_evolution(hermes_file, generated_code):
    """应用进化代码到MimirAether"""
    mimiraether_file = MIMIRAETHER_DIR / hermes_file
    
    if generated_code and "```python" in generated_code:
        code_start = generated_code.find("```python") + 9
        code_end = generated_code.rfind("```")
        if code_end > code_start:
            code = generated_code[code_start:code_end].strip()
            
            # 备份原文件
            if mimiraether_file.exists():
                backup_file = mimiraether_file.with_suffix('.py.bak')
                mimiraether_file.rename(backup_file)
                log(f"📦 已备份: {backup_file.name}")
            
            # 写入新代码
            mimiraether_file.write_text(code)
            log(f"✅ 已写入: {hermes_file} ({len(code)}字符)")
            return True
    
    log(f"⚠️ 未生成有效代码，跳过")
    return False

def learn_and_evolve_one(topic):
    """学习一个模块并进化"""
    hermes_file = topic["file"]
    name = topic["name"]
    
    log(f"")
    log(f"={'='*50}")
    log(f"📚 学习: {name} ({hermes_file})")
    
    # 1. 读取Hermes代码
    hermes_code = read_hermes_code(hermes_file)
    if not hermes_code:
        log(f"⚠️ Hermes文件不存在: {hermes_file}")
        return False
    
    lines = hermes_code.split('\n')
    funcs = [l.strip() for l in lines if l.strip().startswith('def ') and not l.strip().startswith('def _')]
    classes = [l.strip() for l in lines if l.strip().startswith('class ') and not l.strip().startswith('class _')]
    
    log(f"   {len(classes)}类, {len(funcs)}函数")
    
    # 2. 检查MimirAether是否有这个文件
    mimiraether_file = MIMIRAETHER_DIR / hermes_file
    if mimiraether_file.exists():
        log(f"   MimirAether已有此文件")
        ma_code = mimiraether_file.read_text()
        ma_funcs = set([l.strip() for l in ma_code.split('\n') if l.strip().startswith('def ') and not l.strip().startswith('def _')])
        hermes_funcs = set(funcs)
        missing = hermes_funcs - ma_funcs
        
        if missing:
            log(f"   缺失 {len(missing)} 个函数，尝试补全...")
        else:
            log(f"   ✅ 完全匹配，无需进化")
            return True
    
    # 3. 用AI生成进化代码
    generated = generate_evolution_code(hermes_file, hermes_code, str(mimiraether_file))
    
    if generated:
        success = apply_evolution(hermes_file, generated)
        save_evolution_log(name, "success" if success else "failed", hermes_file)
        return success
    else:
        save_evolution_log(name, "no_code_generated", hermes_file)
        return False

def save_evolution_log(topic, status, file_path):
    """保存进化日志"""
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    logs = []
    if EVOLUTION_LOG.exists():
        try:
            logs = json.loads(EVOLUTION_LOG.read_text())
        except:
            logs = []
    
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "status": status,
        "hermes_file": file_path
    })
    
    EVOLUTION_LOG.write_text(json.dumps(logs, indent=2, ensure_ascii=False))

def main():
    global _running, _stop_time
    
    _stop_time = datetime.now() + timedelta(hours=8)
    
    log(f"")
    log(f"██████████████████████████████████████████")
    log(f"  🚀 MimirAether 学一段+进化一段 开始")
    log(f"  ⏰ 运行至: {_stop_time.strftime('%H:%M:%S')} (约8小时)")
    log(f"██████████████████████████████████████████")
    log(f"")
    
    if not DEEPSEEK_API_KEY:
        log(f"⚠️ 警告: 未设置DEEPSEEK_API_KEY，将跳过AI代码生成")
        log(f"   只做学习分析，不生成代码")
    else:
        log(f"✅ API已配置，将生成进化代码")
    
    log(f"")
    log(f"按 Ctrl+C 停止")
    log(f"")
    
    state = load_state()
    index = state.get("index", 0)
    evolved = state.get("evolved", [])
    
    if index > 0:
        log(f"📍 从第 {index + 1} 个模块继续")
    
    round_count = 0
    
    while _running and datetime.now() < _stop_time:
        if index >= len(HERMES_TOPICS):
            round_count += 1
            log(f"")
            log(f"🔄 完成第 {round_count} 轮，休息10秒...")
            time.sleep(10)
            index = 0
        
        topic = HERMES_TOPICS[index]
        topic_name = topic["name"]
        
        success = learn_and_evolve_one(topic)
        
        if success:
            evolved.append(topic_name)
        index += 1
        
        save_state({
            "index": index,
            "evolved": evolved,
            "start_time": state.get("start_time", datetime.now().isoformat())
        })
        
        remaining = (_stop_time - datetime.now()).total_seconds()
        if remaining <= 0:
            break
        
        log(f"")
        log(f"⏱️ 剩余: {int(remaining/60)}分钟 | 已进化: {len(evolved)}模块")
        
        time.sleep(3)
    
    elapsed = datetime.now() - datetime.fromisoformat(state.get("start_time", datetime.now().isoformat()))
    log(f"")
    log(f"██████████████████████████████████████████")
    log(f"  🛑 已停止")
    log(f"  📊 共进化: {len(evolved)} 个模块")
    log(f"  ⏱️ 运行时间: {elapsed}")
    log(f"██████████████████████████████████████████")

if __name__ == "__main__":
    main()
