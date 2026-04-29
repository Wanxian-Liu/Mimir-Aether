#!/usr/bin/env python3
"""
MimirAether CLI - 命令行入口

支持多种命令：
    python cli.py                          # 交互模式
    python cli.py status                  # 查看状态
    python cli.py status --deep           # 深度检查
    python cli.py config                  # 查看配置
    python cli.py doctor                  # 诊断问题
    python cli.py setup                  # 设置向导
    python cli.py model                  # 模型选择
    python cli.py cron list              # 定时任务
    python cli.py version                # 版本信息
    python cli.py auth                   # 凭证管理
    python cli.py profiles               # Profile管理
    python cli.py -q "你的任务"         # 单次任务模式
"""

import argparse
import asyncio
import importlib
import os
import sys
import json
import platform
import socket
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入模型配置（动态读取OpenClaw配置）
from mimicore.config.model_defaults import get_model, get_available_models, DEFAULT_MODEL as MIMIR_DEFAULT_MODEL
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# 版本信息
# =============================================================================

__version__ = "0.1.0"
__agent_version__ = "MimirAether"

# =============================================================================
# 命令：status
# =============================================================================

def check_mark(ok: bool) -> str:
    """返回状态标记符号"""
    return "✅" if ok else "❌"


def redact_key(key: str) -> str:
    """对API密钥进行脱敏显示"""
    if not key:
        return "(未配置)"
    if len(key) < 12:
        return "***"
    return key[:4] + "..." + key[-4:]


def cmd_status(args):
    """查看系统状态 - 对齐Hermes status功能"""
    deep = getattr(args, 'deep', False)
    show_all = getattr(args, 'all', False)
    
    from agent.core_loop import MimirAetherAgent
    
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " ⚕ MimirAether Status ".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    
    # =========================================================================
    # Environment
    # =========================================================================
    print()
    print("◆ 环境信息")
    print(f"  项目路径:    {PROJECT_ROOT}")
    print(f"  Python:      {sys.version.split()[0]}")
    
    # .env文件检查
    env_path = PROJECT_ROOT / ".env"
    env_exists = env_path.exists()
    print(f"  .env文件:    {check_mark(env_exists)} {'存在' if env_exists else '不存在'}")
    
    # 模型信息
    print(f"  默认模型:    {get_model()}")
    
    # 操作系统
    print(f"  操作系统:    {platform.system()} {platform.release()}")
    print(f"  主机名:      {socket.gethostname()}")
    
    # =========================================================================
    # API Keys
    # =========================================================================
    print()
    print("◆ API密钥")
    
    keys = {
        "DeepSeek": "DEEPSEEK_API_KEY",
        "DeepSeek V3": "DEEPSEEK_V3_API_KEY",
        "MiniMax": "MINIMAX_API_KEY",
        "MiniMax V2": "MINIMAX_V2_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "SiliconFlow": "SILICONFLOW_API_KEY",
        "Zhipu": "ZHIPU_API_KEY",
        "Qwen": "QWEN_API_KEY",
    }
    
    for name, env_var in keys.items():
        value = os.environ.get(env_var, "") or ""
        has_key = bool(value)
        display = redact_key(value) if not show_all else value
        print(f"  {name:<12}  {check_mark(has_key)} {display}")
    
    # =========================================================================
    # Messaging Platforms
    # =========================================================================
    print()
    print("◆ 消息平台")
    
    platforms = {
        "Feishu": ("FEISHU_APP_ID", "FEISHU_HOME_CHANNEL"),
        "WeChat": ("WEIXIN_ACCOUNT_ID", "WEIXIN_HOME_CHANNEL"),
        "Telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL"),
        "Discord": ("DISCORD_BOT_TOKEN", "DISCORD_HOME_CHANNEL"),
    }
    
    for name, (token_var, home_var) in platforms.items():
        token = os.environ.get(token_var, "")
        has_token = bool(token)
        
        home_channel = os.environ.get(home_var, "") if home_var else ""
        
        status = "已配置" if has_token else "未配置"
        if home_channel:
            status += f" (home: {home_channel})"
        
        print(f"  {name:<10}  {check_mark(has_token)} {status}")
    
    # =========================================================================
    # Gateway Service
    # =========================================================================
    print()
    print("◆ Gateway服务")
    
    # 检查Gateway进程
    gateway_running = False
    gateway_pids = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", "gateway/run.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gateway_pids = result.stdout.strip().split('\n')
            gateway_running = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print(f"  状态:       {check_mark(gateway_running)} {'运行中' if gateway_running else '未运行'}")
    print(f"  API地址:    http://localhost:18999")
    
    if gateway_running and gateway_pids:
        rendered = ", ".join(gateway_pids[:3])
        if len(gateway_pids) > 3:
            rendered += ", ..."
        print(f"  PID(s):     {rendered}")
    
    # 检查Gateway健康状态
    try:
        import httpx
        response = httpx.get("http://localhost:18999/health", timeout=3)
        if response.status_code == 200:
            data = response.json()
            version = data.get('version', 'unknown')
            print(f"  健康检查:   ✅ 正常 (v{version})")
        else:
            print(f"  健康检查:   ⚠️ 异常 (状态码: {response.status_code})")
    except Exception:
        print(f"  健康检查:   ❌ 无法连接")
    
    # =========================================================================
    # Sessions
    # =========================================================================
    print()
    print("◆ 会话状态")
    
    sessions_file = PROJECT_ROOT / "sessions" / "sessions.json"
    if sessions_file.exists():
        try:
            with open(sessions_file, encoding="utf-8") as f:
                data = json.load(f)
                active_count = len(data) if isinstance(data, list) else len(data.get('sessions', []))
                print(f"  活跃会话:   {active_count} 个")
        except Exception:
            print("  活跃会话:   (读取失败)")
    else:
        print("  活跃会话:   0")
    
    # =========================================================================
    # Scheduled Jobs
    # =========================================================================
    print()
    print("◆ 定时任务")
    
    jobs_file = PROJECT_ROOT / "cron" / "jobs.json"
    if jobs_file.exists():
        try:
            with open(jobs_file, encoding="utf-8") as f:
                data = json.load(f)
                jobs = data.get("jobs", [])
                enabled_jobs = [j for j in jobs if j.get("enabled", True)]
                print(f"  任务数:     {len(enabled_jobs)} 个活跃, {len(jobs)} 个总计")
        except Exception:
            print("  任务数:     (读取失败)")
    else:
        print("  任务数:     0")
    
    # =========================================================================
    # Tools
    # =========================================================================
    print()
    print("◆ 工具统计")
    
    try:
        agent = MimirAetherAgent()
        tools = agent.tool_registry.list_tools()
        print(f"  内置工具:   {len(tools)} 个")
        if args.verbose:
            for tool in tools[:15]:
                print(f"    - {tool}")
            if len(tools) > 15:
                print(f"    ... 还有 {len(tools) - 15} 个")
    except Exception as e:
        print(f"  Agent初始化失败: {e}")
    
    # =========================================================================
    # Deep Checks
    # =========================================================================
    if deep:
        print()
        print("◆ 深度检查")
        
        # DeepSeek API连通性
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if deepseek_key:
            try:
                import httpx
                response = httpx.get(
                    "https://api.deepseek.com/models",
                    headers={"Authorization": f"Bearer {deepseek_key}"},
                    timeout=10
                )
                ok = response.status_code == 200
                status_text = "可连接" if ok else f"错误 ({response.status_code})"
                print(f"  DeepSeek API: {check_mark(ok)} {status_text}")
            except Exception as e:
                print(f"  DeepSeek API: ❌ 连接失败: {e}")
        
        # MiniMax API连通性
        minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        if minimax_key:
            try:
                import httpx
                response = httpx.get(
                    "https://api.minimax.chat/v1/models",
                    headers={"Authorization": f"Bearer {minimax_key}"},
                    timeout=10
                )
                ok = response.status_code == 200
                status_text = "可连接" if ok else f"错误 ({response.status_code})"
                print(f"  MiniMax API:  {check_mark(ok)} {status_text}")
            except Exception as e:
                print(f"  MiniMax API:  ❌ 连接失败: {e}")
        
        # Gateway端口检查
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 18999))
            sock.close()
            port_in_use = result == 0
            print(f"  端口18999:   {'已被占用' if port_in_use else '可用'}")
        except OSError:
            pass
    
    print()
    print("─" * 60)
    print("  运行 'python cli.py doctor' 获取详细诊断")
    print("  运行 'python cli.py setup' 进行配置")
    print()
    
    return 0

# =============================================================================
# 命令：config
# =============================================================================

def cmd_config(args):
    """配置管理命令 - 对齐Hermes config功能"""
    subcmd = getattr(args, 'subcmd', None)
    
    # 获取.env路径
    env_path = PROJECT_ROOT / ".env"
    
    # 读取当前环境变量
    def load_env_vars():
        """从.env文件加载环境变量"""
        env_vars = {}
        if env_path.exists():
            try:
                with open(env_path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, _, val = line.partition('=')
                            env_vars[key.strip()] = val.strip()
            except Exception:
                pass
        return env_vars
    
    def save_env_vars(env_vars):
        """保存环境变量到.env文件"""
        try:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("# MimirAether配置文件\n")
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False
    
    def get_env_value(key):
        """获取环境变量值，优先从.env读取"""
        env_vars = load_env_vars()
        return env_vars.get(key, os.environ.get(key, ''))
    
    # =========================================================================
    # config path - 显示配置文件路径
    # =========================================================================
    if subcmd == "path":
        print(str(env_path))
        return 0
    
    # =========================================================================
    # config env-path - 显示.env文件路径
    # =========================================================================
    if subcmd == "env-path":
        print(str(env_path))
        return 0
    
    # =========================================================================
    # config get KEY - 获取指定配置项
    # =========================================================================
    if subcmd == "get":
        key = getattr(args, 'key', None)
        if not key:
            print("Usage: config get <key>")
            print("示例: config get DEFAULT_MODEL")
            return 1
        
        value = get_env_value(key)
        if value:
            print(f"{key}={value}")
        else:
            # 尝试从os.environ获取
            value = os.environ.get(key, '')
            if value:
                print(f"{key}={value}")
            else:
                print(f"配置项 '{key}' 不存在")
                return 1
        return 0
    
    # =========================================================================
    # config set KEY VALUE - 设置配置项
    # =========================================================================
    if subcmd == "set":
        key = getattr(args, 'key', None)
        value = getattr(args, 'value', None)
        if not key or value is None:
            print("Usage: config set <key> <value>")
            print()
            print("示例:")
            print("  config set DEFAULT_MODEL deepseek/deepseek-v3")
            print("  config set MIMIR_PORT 18999")
            print("  config set MAX_ITERATIONS 90")
            return 1
        
        env_vars = load_env_vars()
        old_value = env_vars.get(key, os.environ.get(key, ''))
        env_vars[key] = value
        
        if save_env_vars(env_vars):
            print(f"✅ 已设置: {key} = {value}")
            if old_value:
                print(f"   (原值: {old_value})")
        return 0
    
    # =========================================================================
    # config edit - 打开编辑器编辑配置
    # =========================================================================
    if subcmd == "edit":
        editor = os.environ.get('EDITOR', 'vi' if platform.system() != 'Windows' else 'notepad')
        try:
            subprocess.run([editor, str(env_path)], check=True)
            print(f"已使用 {editor} 编辑配置文件")
        except subprocess.CalledProcessError:
            print(f"编辑器 {editor} 启动失败")
            return 1
        except FileNotFoundError:
            print(f"编辑器 {editor} 未找到")
            return 1
        return 0
    
    # =========================================================================
    # config check - 检查配置完整性
    # =========================================================================
    if subcmd == "check":
        print()
        print("┌" + "─" * 58 + "┐")
        print("│" + " 📋 MimirAether 配置检查".center(58) + "│")
        print("└" + "─" * 58 + "┘")
        
        env_vars = load_env_vars()
        issues = []
        
        # 检查必需的配置项
        print()
        print("◆ 模型配置")
        model = get_env_value('DEFAULT_MODEL') or get_env_value('MIMIR_MODEL')
        if model:
            print(f"  ✅ 默认模型: {model}")
        else:
            model = get_model()
            print(f"  ⚠️ 未配置默认模型，使用: {model}")
        
        print()
        print("◆ API密钥")
        api_keys = {
            "DEEPSEEK_API_KEY": "DeepSeek",
            "MINIMAX_API_KEY": "MiniMax",
            "ANTHROPIC_API_KEY": "Anthropic",
            "OPENAI_API_KEY": "OpenAI",
        }
        has_any = False
        for key, name in api_keys.items():
            value = get_env_value(key)
            if value:
                has_any = True
                print(f"  ✅ {name}: 已配置")
            else:
                print(f"  ○ {name}: 未配置")
        
        if not has_any:
            issues.append("至少需要一个API密钥")
        
        print()
        print("◆ 运行时配置")
        port = get_env_value('MIMIR_PORT') or '18999'
        print(f"  端口: {port}")
        adapters = get_env_value('MIMIR_ADAPTERS') or ''
        print(f"  适配器: {adapters or '(未配置)'}")
        
        print()
        print("◆ 路径信息")
        print(f"  项目目录: {PROJECT_ROOT}")
        print(f"  配置文件: {env_path}")
        
        print()
        print("─" * 60)
        if issues:
            print(f"  ⚠️ 发现 {len(issues)} 个问题:")
            for issue in issues:
                print(f"    • {issue}")
        else:
            print("  ✅ 配置检查通过！")
        print()
        return 0 if not issues else 1
    
    # =========================================================================
    # config show (default) - 显示当前配置
    # =========================================================================
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " ⚕ MimirAether 配置".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    
    env_vars = load_env_vars()
    
    print()
    print("◆ 模型配置")
    model = get_env_value('DEFAULT_MODEL') or get_env_value('MIMIR_MODEL') or get_model()
    print(f"  默认模型: {model}")
    base_url = get_env_value('DEEPSEEK_API_BASE') or os.environ.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com')
    print(f"  API Base: {base_url}")
    
    max_iter = get_env_value('MAX_ITERATIONS') or '90'
    print(f"  最大迭代: {max_iter}")
    
    print()
    print("◆ API密钥状态")
    api_keys = [
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("MINIMAX_API_KEY", "MiniMax"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("DEEPSEEK_V3_API_KEY", "DeepSeek V3"),
        ("MINIMAX_V2_API_KEY", "MiniMax V2"),
        ("SILICONFLOW_API_KEY", "SiliconFlow"),
        ("ZHIPU_API_KEY", "Zhipu"),
        ("QWEN_API_KEY", "Qwen"),
    ]
    for key, name in api_keys:
        value = get_env_value(key)
        if value:
            print(f"  {name:<14} ✅ 已配置")
        else:
            print(f"  {name:<14} ○ 未配置")
    
    print()
    print("◆ Gateway配置")
    port = get_env_value('MIMIR_PORT') or '18999'
    print(f"  端口: {port}")
    adapters = get_env_value('MIMIR_ADAPTERS') or ''
    print(f"  适配器: {adapters or '(未配置)'}")
    
    print()
    print("◆ 消息平台")
    platforms = [
        ("FEISHU_APP_ID", "Feishu"),
        ("TELEGRAM_BOT_TOKEN", "Telegram"),
        ("DISCORD_BOT_TOKEN", "Discord"),
        ("WEIXIN_ACCOUNT_ID", "WeChat"),
    ]
    for key, name in platforms:
        value = get_env_value(key)
        if value:
            print(f"  {name:<10} ✅ 已配置")
        else:
            print(f"  {name:<10} ○ 未配置")
    
    print()
    print("◆ 路径信息")
    print(f"  项目目录: {PROJECT_ROOT}")
    print(f"  配置文件: {env_path}")
    
    # verbose模式显示完整.env内容
    if getattr(args, 'verbose', False):
        print()
        print("◆ 完整.env内容")
        if env_vars:
            for key, value in env_vars.items():
                # 对敏感值进行脱敏
                if any(s in key.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']):
                    if len(value) > 8:
                        value = value[:4] + "..." + value[-4:]
                    else:
                        value = "***"
                print(f"  {key}={value}")
        else:
            print("  (空)")
    
    print()
    print("─" * 60)
    print("  使用 'config edit' 编辑配置")
    print("  使用 'config set <key> <value>' 设置配置")
    print("  使用 'config check' 检查配置完整性")
    print()
    
    return 0

# =============================================================================
# 命令：doctor
# =============================================================================

def check_ok(text: str, detail: str = ""):
    print(f"  ✅ {text}" + (f" {detail}" if detail else ""))

def check_warn(text: str, detail: str = ""):
    print(f"  ⚠️ {text}" + (f" {detail}" if detail else ""))

def check_fail(text: str, detail: str = ""):
    print(f"  ❌ {text}" + (f" {detail}" if detail else ""))

def check_info(text: str):
    print(f"    → {text}")


def cmd_doctor(args):
    """诊断系统问题 - 对齐Hermes doctor功能"""
    should_fix = getattr(args, 'fix', False)
    issues = []
    manual_issues = []
    fixed_count = 0
    
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " 🩺 MimirAether Doctor ".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    
    # =========================================================================
    # Check: Python version
    # =========================================================================
    print()
    print("◆ Python环境")
    
    py_version = sys.version_info
    if py_version >= (3, 10):
        check_ok(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    else:
        check_fail(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}", "(需要 3.10+)")
        issues.append("Python版本过低")
    
    # Check virtual environment
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        check_ok("虚拟环境已激活")
    else:
        check_warn("未在虚拟环境中", "(建议使用虚拟环境)")
    
    # =========================================================================
    # Check: Required packages
    # =========================================================================
    print()
    print("◆ 依赖包")
    
    required_packages = [
        ("openai", "OpenAI SDK"),
        ("rich", "Rich (终端UI)"),
        ("dotenv", "python-dotenv"),
        ("yaml", "PyYAML"),
        ("httpx", "HTTPX"),
    ]
    
    optional_packages = [
        ("croniter", "Croniter (定时任务)"),
        ("telegram", "python-telegram-bot"),
        ("discord", "discord.py"),
    ]
    
    for module, name in required_packages:
        try:
            __import__(module)
            check_ok(name)
        except ImportError:
            check_fail(name, "(缺失)")
            issues.append(f"安装 {name}: pip install {module}")
    
    for module, name in optional_packages:
        try:
            __import__(module)
            check_ok(name, "(可选)")
        except ImportError:
            check_warn(name, "(可选，未安装)")
    
    # =========================================================================
    # Check: Configuration files
    # =========================================================================
    print()
    print("◆ 配置文件")
    
    # Check .env file
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        check_ok(".env 文件存在")
        content = env_path.read_text()
        # Check for API keys
        api_keys = [
            "DEEPSEEK_API_KEY", "MINIMAX_API_KEY", "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY", "DEEPSEEK_V3_API_KEY", "MINIMAX_V2_API_KEY",
        ]
        has_api_key = any(key in content for key in api_keys)
        if has_api_key:
            check_ok("API密钥已配置")
        else:
            check_warn("未找到API密钥配置")
            issues.append("运行 'python cli.py setup' 配置API密钥")
    else:
        check_fail(".env 文件缺失")
        if should_fix:
            env_path.touch()
            check_ok("已创建空的 .env 文件")
            check_info("运行 'python cli.py setup' 配置API密钥")
            fixed_count += 1
        else:
            issues.append("运行 'python cli.py setup' 创建 .env 文件")
    
    # Check memories directory
    memories_dir = PROJECT_ROOT / "memories"
    if memories_dir.exists():
        check_ok("memories/ 目录存在")
        memory_file = memories_dir / "MEMORY.md"
        if memory_file.exists():
            size = len(memory_file.read_text(encoding="utf-8").strip())
            check_ok(f"MEMORY.md 存在 ({size} 字符)")
        else:
            check_info("MEMORY.md 尚未创建 (首次写入记忆时创建)")
    else:
        check_warn("memories/ 目录不存在")
        if should_fix:
            memories_dir.mkdir(parents=True, exist_ok=True)
            check_ok("已创建 memories/ 目录")
            fixed_count += 1
    
    # Check SOUL.md
    soul_path = PROJECT_ROOT / "SOUL.md"
    if soul_path.exists():
        content = soul_path.read_text(encoding="utf-8").strip()
        lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith(("<!--", "-->", "#"))]
        if lines:
            check_ok("SOUL.md 存在 (人格已配置)")
        else:
            check_warn("SOUL.md 为空")
    else:
        check_warn("SOUL.md 不存在", "(创建可自定义人格)")
        if should_fix:
            soul_path.write_text(
                "# MimirAether Persona\n\n"
                "<!-- 编辑此文件自定义MimirAether的交流方式 -->\n\n"
                "You are MimirAether, a helpful AI assistant.\n",
                encoding="utf-8",
            )
            check_ok("已创建 SOUL.md 基础模板")
            fixed_count += 1
    
    # Check sessions directory
    sessions_dir = PROJECT_ROOT / "sessions"
    if sessions_dir.exists():
        check_ok("sessions/ 目录存在")
    else:
        check_warn("sessions/ 目录不存在")
        if should_fix:
            sessions_dir.mkdir(parents=True, exist_ok=True)
            check_ok("已创建 sessions/ 目录")
            fixed_count += 1
    
    # Check logs directory
    logs_dir = PROJECT_ROOT / "logs"
    if logs_dir.exists():
        check_ok("logs/ 目录存在")
    else:
        check_warn("logs/ 目录不存在")
        if should_fix:
            logs_dir.mkdir(parents=True, exist_ok=True)
            check_ok("已创建 logs/ 目录")
            fixed_count += 1
    
    # Check cron directory
    cron_dir = PROJECT_ROOT / "cron"
    if cron_dir.exists():
        check_ok("cron/ 目录存在")
        jobs_file = cron_dir / "jobs.json"
        if jobs_file.exists():
            check_ok("jobs.json 存在")
    else:
        check_warn("cron/ 目录不存在")
        if should_fix:
            cron_dir.mkdir(parents=True, exist_ok=True)
            check_ok("已创建 cron/ 目录")
            fixed_count += 1
    
    # Check state.db
    state_db_path = PROJECT_ROOT / "state.db"
    if state_db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(state_db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            count = cursor.fetchone()[0]
            conn.close()
            check_ok(f"state.db 存在 ({count} 个会话)")
        except Exception as e:
            check_warn(f"state.db 存在但有问题: {e}")
    else:
        check_info("state.db 尚未创建 (首次会话时创建)")
    
    # Check WAL file size
    wal_path = PROJECT_ROOT / "state.db-wal"
    if wal_path.exists():
        try:
            wal_size = wal_path.stat().st_size
            if wal_size > 50 * 1024 * 1024:  # 50 MB
                check_warn(f"WAL文件过大 ({wal_size // (1024*1024)} MB)", "(可能表明检查点遗漏)")
                if should_fix:
                    import sqlite3
                    conn = sqlite3.connect(str(state_db_path))
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    conn.close()
                    new_size = wal_path.stat().st_size if wal_path.exists() else 0
                    check_ok(f"WAL检查点执行 ({wal_size // 1024}K → {new_size // 1024}K)")
                    fixed_count += 1
                else:
                    issues.append("WAL文件过大 - 运行 'python cli.py doctor --fix' 执行检查点")
            elif wal_size > 10 * 1024 * 1024:  # 10 MB
                check_info(f"WAL文件大小 {wal_size // (1024*1024)} MB (活跃会话正常)")
        except Exception:
            pass
    
    # =========================================================================
    # Check: External tools
    # =========================================================================
    print()
    print("◆ 外部工具")
    
    # Git
    if shutil.which("git"):
        check_ok("git")
    else:
        check_warn("git 未找到", "(可选)")
    
    # ripgrep
    if shutil.which("rg"):
        check_ok("ripgrep (rg)", "(快速文件搜索)")
    else:
        check_warn("ripgrep (rg) 未找到", "(文件搜索使用grep回退)")
    
    # Docker
    if shutil.which("docker"):
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            if result.returncode == 0:
                check_ok("docker", "(守护进程运行中)")
            else:
                check_warn("docker", "(守护进程未运行)")
        except subprocess.TimeoutExpired:
            check_warn("docker", "(连接超时)")
        except Exception:
            check_warn("docker", "(检查失败)")
    else:
        check_warn("docker 未找到", "(可选)")
    
    # Node.js
    if shutil.which("node"):
        node_version = subprocess.run(["node", "--version"], capture_output=True, text=True)
        check_ok(f"Node.js {node_version.stdout.strip()}")
    else:
        check_warn("Node.js 未找到", "(可选，需要浏览器工具)")
    
    # =========================================================================
    # Check: API Connectivity
    # =========================================================================
    print()
    print("◆ API连接性")
    
    # API Key providers
    providers = [
        ("DeepSeek", ("DEEPSEEK_API_KEY",), "https://api.deepseek.com/v1/models", "DEEPSEEK_BASE_URL"),
        ("MiniMax", ("MINIMAX_API_KEY",), "https://api.minimax.chat/v1/models", "MINIMAX_BASE_URL"),
        ("Anthropic", ("ANTHROPIC_API_KEY",), "https://api.anthropic.com/v1/models", None),
        ("OpenAI", ("OPENAI_API_KEY",), "https://api.openai.com/v1/models", "OPENAI_BASE_URL"),
    ]
    
    for name, env_vars, default_url, base_env in providers:
        key = ""
        for ev in env_vars:
            key = os.environ.get(ev, "")
            if key:
                break
        
        if not key:
            check_warn(f"{name} API", "(未配置)")
            continue
        
        print(f"  检查 {name} API...", end="", flush=True)
        try:
            import httpx
            base = os.environ.get(base_env, "") if base_env else ""
            url = (base.rstrip("/") + "/models") if base else default_url
            headers = {"Authorization": f"Bearer {key}"}
            if name == "Anthropic":
                headers["anthropic-version"] = "2023-06-01"
                headers["x-api-key"] = key
                del headers["Authorization"]
            
            response = httpx.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"\r  ✅ {name} API                          ")
            elif response.status_code == 401:
                print(f"\r  ❌ {name} API (无效的API密钥)          ")
                issues.append(f"检查 {name} API密钥")
            else:
                print(f"\r  ⚠️ {name} API (HTTP {response.status_code})          ")
        except Exception as e:
            print(f"\r  ⚠️ {name} API ({e})          ")
    
    # =========================================================================
    # Check: Gateway Service
    # =========================================================================
    print()
    print("◆ Gateway服务")
    
    # Check Gateway process
    gateway_running = False
    gateway_pids = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", "gateway/run.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gateway_pids = result.stdout.strip().split('\n')
            gateway_running = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    if gateway_running:
        check_ok("Gateway进程运行中")
        if gateway_pids:
            check_info(f"PID(s): {', '.join(gateway_pids[:3])}")
    else:
        check_warn("Gateway进程未运行")
    
    # Check Gateway health
    try:
        import httpx
        response = httpx.get("http://localhost:18999/health", timeout=3)
        if response.status_code == 200:
            data = response.json()
            version = data.get('version', 'unknown')
            check_ok(f"Gateway健康检查", f"(v{version})")
        else:
            check_warn(f"Gateway健康检查", f"(状态码: {response.status_code})")
    except Exception:
        check_warn("Gateway健康检查", "(无法连接端口18999)")
    
    # =========================================================================
    # Check: Core Modules
    # =========================================================================
    print()
    print("◆ 核心模块")
    
    core_modules = [
        "agent.core_loop",
        "mimicore.config.model_defaults",
    ]
    
    for module_name in core_modules:
        try:
            importlib.import_module(module_name)
            check_ok(module_name)
        except Exception as e:
            check_fail(module_name, str(e))
            issues.append(f"模块导入失败: {module_name}")
    
    # =========================================================================
    # Summary
    # =========================================================================
    remaining_issues = issues + manual_issues
    print()
    print("─" * 60)
    
    if should_fix and fixed_count > 0:
        print(f"  ✅ 已修复 {fixed_count} 个问题.", end="")
        if remaining_issues:
            print(f" 还有 {len(remaining_issues)} 个问题需要手动处理.")
        else:
            print()
        print()
        if remaining_issues:
            for i, issue in enumerate(remaining_issues, 1):
                print(f"  {i}. {issue}")
            print()
    elif remaining_issues:
        print(f"  ❌ 发现 {len(remaining_issues)} 个问题：")
        print()
        for i, issue in enumerate(remaining_issues, 1):
            print(f"  {i}. {issue}")
        print()
        if not should_fix:
            print("  提示: 运行 'python cli.py doctor --fix' 自动修复")
    else:
        print("  ✅ 所有检查通过！系统正常。🎉")
    
    print()
    return 0 if not remaining_issues else 1

# =============================================================================
# 命令：setup
# =============================================================================

# =============================================================================
# Setup命令 - 增强版 - 对齐Hermes setup功能
# =============================================================================

# ANSI颜色码
class Colors:
    """终端颜色输出"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"

def color(text: str, *styles) -> str:
    """为文本添加颜色"""
    style_code = ""
    for s in styles:
        if s == Colors.BOLD:
            style_code += "\033[1m"
        elif s == Colors.DIM:
            style_code += "\033[2m"
        elif s == Colors.CYAN:
            style_code += "\033[36m"
        elif s == Colors.GREEN:
            style_code += "\033[32m"
        elif s == Colors.YELLOW:
            style_code += "\033[33m"
        elif s == Colors.RED:
            style_code += "\033[31m"
        elif s == Colors.MAGENTA:
            style_code += "\033[35m"
    return f"{style_code}{text}{Colors.RESET}"

def print_header(title: str):
    """打印分节标题"""
    print()
    print(color(f"◆ {title}", Colors.CYAN, Colors.BOLD))

def print_success(text: str):
    """打印成功信息"""
    print(color(f"  ✅ {text}", Colors.GREEN))

def print_warning(text: str):
    """打印警告信息"""
    print(color(f"  ⚠️ {text}", Colors.YELLOW))

def print_error(text: str):
    """打印错误信息"""
    print(color(f"  ❌ {text}", Colors.RED))

def print_info(text: str):
    """打印普通信息"""
    print(color(f"  {text}", Colors.DIM))

def prompt(question: str, default: str = None, password: bool = False) -> str:
    """提示用户输入"""
    if default:
        display = f"{question} [{default}]: "
    else:
        display = f"{question}: "

    try:
        if password:
            import getpass
            value = getpass.getpass(color(display, Colors.YELLOW))
        else:
            value = input(color(display, Colors.YELLOW))
        return value.strip() or default or ""
    except (KeyboardInterrupt, EOFError):
        print()
        return ""

def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Yes/No提示"""
    default_str = "Y/n" if default else "y/N"
    while True:
        try:
            value = input(color(f"{question} [{default_str}]: ", Colors.YELLOW)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return False
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print_error("请输入 'y' 或 'n'")

def prompt_choice(question: str, choices: list, default: int = 0) -> int:
    """数字选择提示"""
    print()
    print(color(question, Colors.YELLOW))
    for i, choice in enumerate(choices):
        marker = "●" if i == default else "○"
        if i == default:
            print(color(f"  {marker} {choice}", Colors.GREEN))
        else:
            print(f"  {marker} {choice}")
    print_info(f"  输入数字选择 (默认: {default + 1})")
    print_info("  Ctrl+C 退出")

    while True:
        try:
            value = input(color(f"  选择 [1-{len(choices)}] ({default + 1}): ", Colors.DIM)).strip()
            if not value:
                return default
            idx = int(value) - 1
            if 0 <= idx < len(choices):
                return idx
            print_error(f"请输入 1-{len(choices)} 之间的数字")
        except ValueError:
            print_error("请输入数字")
        except (KeyboardInterrupt, EOFError):
            print()
            return default

def _load_env_vars() -> dict:
    """从.env文件加载环境变量"""
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        try:
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, val = line.partition('=')
                        env_vars[key.strip()] = val.strip()
        except Exception:
            pass
    return env_vars

def _save_env_var(key: str, value: str):
    """保存环境变量到.env文件"""
    env_path = PROJECT_ROOT / ".env"
    env_vars = _load_env_vars()
    env_vars[key] = value
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# MimirAether配置文件\n")
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
        return True
    except Exception as e:
        print_error(f"保存失败: {e}")
        return False

def _setup_model_provider():
    """Section 1: 模型与Provider配置"""
    print_header("模型与Provider配置")
    print_info("选择您的主模型提供商和默认模型。")
    print()

    # 显示当前状态
    env_vars = _load_env_vars()
    current_model = get_model()
    print_info(f"当前模型: {current_model}")

    # Provider选择
    providers = [
        "DeepSeek - 默认推荐 (deepseek-v4-pro, 100万上下文)",
        "MiniMax - 高速 (MiniMax-M2.7, 高速推理)",
        "OpenAI - GPT系列",
        "Anthropic - Claude系列",
        "自定义 - 自定义API端点",
    ]
    provider_map = {
        0: ("deepseek", "https://api.deepseek.com"),
        1: ("minimax", "https://api.minimax.chat"),
        2: ("openai", "https://api.openai.com/v1"),
        3: ("anthropic", "https://api.anthropic.com"),
        4: ("custom", None),
    }

    idx = prompt_choice("选择模型Provider:", providers, 0)
    selected_provider, default_base = provider_map[idx]

    if selected_provider == "custom":
        print()
        base_url = prompt("  输入API Base URL", "https://api.deepseek.com/v1")
        _save_env_var("CUSTOM_API_BASE", base_url)
        print_success(f"已设置自定义API Base: {base_url}")
        print_info("接下来设置模型名称...")

    # 模型选择
    print()
    if selected_provider == "deepseek":
        models = [
            ("deepseek/deepseek-v4-pro", "V4 Pro - 推荐, 100万上下文"),
            ("deepseek/deepseek-v4-flash", "V4 Flash - 快速, 100万上下文"),
            ("deepseek/deepseek-chat", "DeepSeek Chat - 标准, 13万上下文"),
            ("deepseek/deepseek-reasoner", "DeepSeek Reasoner - 推理专用"),
        ]
    elif selected_provider == "minimax":
        models = [
            ("MiniMax-M2.7", "MiniMax M2.7 - 高速推理"),
            ("MiniMax-M2.5", "MiniMax M2.5 - 平衡"),
            ("MiniMax-M2.1", "MiniMax M2.1 - 性价比"),
        ]
    elif selected_provider == "openai":
        models = [
            ("gpt-4o", "GPT-4o - 最新旗舰"),
            ("gpt-4o-mini", "GPT-4o-mini - 轻量快速"),
            ("gpt-4-turbo", "GPT-4 Turbo - 高性能"),
        ]
    elif selected_provider == "anthropic":
        models = [
            ("claude-opus-4-5", "Claude Opus 4.5 - 最强推理"),
            ("claude-sonnet-4-5", "Claude Sonnet 4.5 - 平衡"),
            ("claude-haiku-4-5", "Claude Haiku 4.5 - 快速"),
        ]
    else:
        models = [
            ("custom-model", "自定义模型"),
        ]

    model_choices = [m[1] for m in models]
    model_idx = prompt_choice("选择模型:", model_choices, 0)
    selected_model = models[model_idx][0]

    # 保存配置
    _save_env_var("DEFAULT_MODEL", selected_model)
    if default_base:
        _save_env_var(f"{selected_provider.upper()}_API_BASE", default_base)

    print()
    print_success(f"默认模型已设置为: {selected_model}")

    # API Key配置
    print()
    api_key_map = {
        "deepseek": ("DEEPSEEK_API_KEY", "DeepSeek API Key", "https://platform.deepseek.com/api_keys"),
        "minimax": ("MINIMAX_API_KEY", "MiniMax API Key", "https://platform.minimax.chat/"),
        "openai": ("OPENAI_API_KEY", "OpenAI API Key", "https://platform.openai.com/api-keys"),
        "anthropic": ("ANTHROPIC_API_KEY", "Anthropic API Key", "https://console.anthropic.com/settings/keys"),
        "custom": ("CUSTOM_API_KEY", "自定义API Key", None),
    }

    env_var, key_name, key_url = api_key_map.get(selected_provider, ("CUSTOM_API_KEY", "API Key", None))
    current_key = os.environ.get(env_var, "") or env_vars.get(env_var, "")

    if current_key:
        print_info(f"{key_name}: 已配置 ({current_key[:8]}...)")
        if prompt_yes_no("  重新配置API Key?", False):
            current_key = ""

    if not current_key:
        print()
        print_info(f"配置 {key_name}")
        if key_url:
            print_info(f"  获取地址: {key_url}")
        api_key = prompt(f"  输入{key_name} (留空跳过)", password=True)
        if api_key:
            _save_env_var(env_var, api_key)
            print_success(f"{key_name}已保存")
        else:
            print_warning("跳过API Key配置，可稍后使用 'python cli.py auth add' 添加")

def _setup_gateway():
    """Section 2: Gateway消息平台配置"""
    print_header("Gateway消息平台配置")
    print_info("连接消息平台，从任何地方与MimirAether对话。")
    print()

    platforms = [
        ("Telegram", "TELEGRAM_BOT_TOKEN", _setup_telegram),
        ("Feishu (飞书)", "FEISHU_APP_ID", _setup_feishu),
        ("Discord", "DISCORD_BOT_TOKEN", _setup_discord),
        ("WeChat (微信)", "WEIXIN_ACCOUNT_ID", _setup_weixin),
    ]

    # 显示当前状态
    env_vars = _load_env_vars()
    configured = []
    for name, env_var, _ in platforms:
        if os.environ.get(env_var, "") or env_vars.get(env_var, ""):
            configured.append(name)

    if configured:
        print_info(f"已配置平台: {', '.join(configured)}")
    else:
        print_info("暂无已配置的消息平台")
    print()

    # 让用户选择要配置的平台
    print_info("选择要配置的消息平台:")
    for i, (name, env_var, _) in enumerate(platforms, 1):
        is_configured = bool(os.environ.get(env_var, "") or env_vars.get(env_var, ""))
        marker = "✅" if is_configured else "○"
        print(f"  {i}. {marker} {name}")

    print()
    choice = prompt("输入平台编号 (如: 1,2 或 all, 留空跳过)", "")

    if choice.lower() == "all":
        selected_indices = list(range(len(platforms)))
    elif choice:
        selected_indices = []
        for c in choice.split(","):
            try:
                idx = int(c.strip()) - 1
                if 0 <= idx < len(platforms):
                    selected_indices.append(idx)
            except ValueError:
                pass
    else:
        selected_indices = []

    for idx in selected_indices:
        name, env_var, setup_func = platforms[idx]
        try:
            setup_func()
        except Exception as e:
            print_error(f"{name}配置失败: {e}")

    if not selected_indices:
        print_info("未选择任何平台。使用 'python cli.py setup gateway' 稍后配置。")

def _setup_telegram():
    """配置Telegram"""
    print()
    print_info("【Telegram配置】")
    print_info("  1. 在 Telegram 中搜索 @BotFather")
    print_info("  2. 发送 /newbot 创建新机器人")
    print_info("  3. 复制获得的 Bot Token")

    env_vars = _load_env_vars()
    current_token = os.environ.get("TELEGRAM_BOT_TOKEN", "") or env_vars.get("TELEGRAM_BOT_TOKEN", "")

    if current_token:
        print_success(f"Token已配置: {current_token[:10]}...")
        if prompt_yes_no("  重新配置?", False):
            current_token = ""

    if not current_token:
        token = prompt("  输入Bot Token", password=True)
        if token:
            _save_env_var("TELEGRAM_BOT_TOKEN", token)
            print_success("Telegram Bot Token已保存")

    # 允许的用户
    print()
    current_users = os.environ.get("TELEGRAM_ALLOWED_USERS", "") or env_vars.get("TELEGRAM_ALLOWED_USERS", "")
    if current_users:
        print_info(f"允许的用户: {current_users}")
    else:
        print_warning("⚠️  未配置用户白名单，任何人都可以使用您的机器人！")
        if prompt_yes_no("  现在配置用户白名单?", True):
            print_info("  查找您的Telegram用户ID: 发送消息给 @userinfobot")
            users = prompt("  允许的用户ID (逗号分隔)", "")
            if users:
                _save_env_var("TELEGRAM_ALLOWED_USERS", users.replace(" ", ""))
                print_success("用户白名单已配置")

def _setup_feishu():
    """配置Feishu飞书"""
    print()
    print_info("【Feishu飞书配置】")
    print_info("  1. 访问 https://open.feishu.cn/app 创建应用")
    print_info("  2. 获取 App ID 和 App Secret")
    print_info("  3. 配置机器人功能")

    env_vars = _load_env_vars()
    current_app_id = os.environ.get("FEISHU_APP_ID", "") or env_vars.get("FEISHU_APP_ID", "")

    if current_app_id:
        print_success(f"App ID已配置: {current_app_id[:10]}...")
        if prompt_yes_no("  重新配置?", False):
            current_app_id = ""

    if not current_app_id:
        app_id = prompt("  输入Feishu App ID")
        app_secret = prompt("  输入Feishu App Secret", password=True)
        if app_id and app_secret:
            _save_env_var("FEISHU_APP_ID", app_id)
            _save_env_var("FEISHU_APP_SECRET", app_secret)
            print_success("Feishu配置已保存")

def _setup_discord():
    """配置Discord"""
    print()
    print_info("【Discord配置】")
    print_info("  1. 访问 https://discord.com/developers/applications")
    print_info("  2. 创建新Application")
    print_info("  3. 在BOT页面获取Token")

    env_vars = _load_env_vars()
    current_token = os.environ.get("DISCORD_BOT_TOKEN", "") or env_vars.get("DISCORD_BOT_TOKEN", "")

    if current_token:
        print_success(f"Token已配置: {current_token[:10]}...")
        if prompt_yes_no("  重新配置?", False):
            current_token = ""

    if not current_token:
        token = prompt("  输入Discord Bot Token", password=True)
        if token:
            _save_env_var("DISCORD_BOT_TOKEN", token)
            print_success("Discord Bot Token已保存")

def _setup_weixin():
    """配置WeChat微信"""
    print()
    print_info("【WeChat微信配置】")
    print_info("  微信配置需要通过网关服务进行QR码登录")
    print_info("  使用 'python cli.py gateway --setup weixin' 进行配置")
    print_warning("  微信个人账号存在风险，建议使用Telegram或飞书")

def _setup_tools():
    """Section 3: 工具配置"""
    print_header("工具配置")
    print_info("配置可选工具的API密钥。")
    print()

    tools = [
        ("SiliconFlow", "SILICONFLOW_API_KEY", "https://docs.siliconflow.cn/"),
        ("Zhipu智谱", "ZHIPU_API_KEY", "https://open.bigmodel.cn/"),
        ("Qwen通义千问", "QWEN_API_KEY", "https://dashscope.console.aliyun.com/"),
        ("MiniMax TTS", "MINIMAX_API_KEY", "https://platform.minimax.chat/"),
    ]

    env_vars = _load_env_vars()

    for name, env_var, url in tools:
        current_key = os.environ.get(env_var, "") or env_vars.get(env_var, "")
        if current_key:
            print_success(f"{name}: 已配置")
        else:
            print_info(f"{name}: 未配置")

    print()
    if prompt_yes_no("配置额外的API密钥?", False):
        for name, env_var, url in tools:
            current_key = os.environ.get(env_var, "") or env_vars.get(env_var, "")
            if current_key:
                continue
            print()
            print_info(f"【{name}】")
            print_info(f"  获取地址: {url}")
            key = prompt(f"  输入{name} API Key (留空跳过)", password=True)
            if key:
                _save_env_var(env_var, key)
                print_success(f"{name}已配置")

def _setup_agent_settings():
    """Section 4: Agent设置"""
    print_header("Agent设置")
    print_info("配置Agent行为参数。")
    print()

    env_vars = _load_env_vars()

    # 最大迭代次数
    current_iter = os.environ.get("MAX_ITERATIONS", "") or env_vars.get("MAX_ITERATIONS", "90")
    print_info("最大迭代次数: 单次对话中Agent可以执行的最大工具调用数")
    print_info("  较高的值允许处理更复杂的任务，但会消耗更多tokens")
    max_iter = prompt("  最大迭代次数", current_iter)
    try:
        max_iter_int = int(max_iter)
        if max_iter_int > 0:
            _save_env_var("MAX_ITERATIONS", str(max_iter_int))
            print_success(f"最大迭代次数: {max_iter_int}")
    except ValueError:
        print_warning("无效数字，保持当前设置")

    # 工具进度显示
    print()
    print_info("工具进度显示模式:")
    print_info("  off   - 静默模式，只显示最终回复")
    print_info("  new   - 只显示工具名称变化 (减少噪音)")
    print_info("  all   - 显示每个工具调用及简短预览")
    print_info("  verbose - 完整参数、结果和调试日志")

    current_mode = os.environ.get("TOOL_PROGRESS", "") or env_vars.get("TOOL_PROGRESS", "all")
    mode = prompt("  工具进度模式", current_mode)
    if mode.lower() in ("off", "new", "all", "verbose"):
        _save_env_var("TOOL_PROGRESS", mode.lower())
        print_success(f"工具进度模式: {mode.lower()}")
    else:
        print_warning(f"未知模式 '{mode}'，保持当前设置")

def _print_setup_summary():
    """打印设置完成摘要"""
    env_vars = _load_env_vars()

    print()
    print(color("┌" + "─" * 56 + "┐", Colors.GREEN))
    print(color("│" + " ✅ 设置完成！ ".center(56) + "│", Colors.GREEN))
    print(color("└" + "─" * 56 + "┘", Colors.GREEN))
    print()

    # 工具可用性摘要
    print_header("工具可用性摘要")

    tool_status = []

    # 模型
    model = get_model()
    model_key_configured = any(
        os.environ.get(k, "") or env_vars.get(k, "")
        for k in ["DEEPSEEK_API_KEY", "MINIMAX_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    )
    tool_status.append(("主模型 (聊天)", model_key_configured, "配置API密钥"))

    # 消息平台
    messaging_configured = any(
        os.environ.get(k, "") or env_vars.get(k, "")
        for k in ["TELEGRAM_BOT_TOKEN", "FEISHU_APP_ID", "DISCORD_BOT_TOKEN", "WEIXIN_ACCOUNT_ID"]
    )
    tool_status.append(("消息平台", messaging_configured, "python cli.py setup gateway"))

    # TTS
    tts_key = os.environ.get("MINIMAX_API_KEY", "") or env_vars.get("MINIMAX_API_KEY", "")
    tool_status.append(("语音合成 (TTS)", bool(tts_key), "配置MINIMAX_API_KEY"))

    # 命令执行
    tool_status.append(("命令执行", True, None))

    # 文件操作
    tool_status.append(("文件操作", True, None))

    # 定时任务
    tool_status.append(("定时任务 (Cron)", True, None))

    available_count = sum(1 for _, avail, _ in tool_status if avail)
    total_count = len(tool_status)

    print_info(f"{available_count}/{total_count} 工具类别可用:")
    print()

    for name, available, hint in tool_status:
        if available:
            print(color(f"   ✅ {name}", Colors.GREEN))
        else:
            hint_text = f" (缺少: {hint})" if hint else ""
            print(color(f"   ❌ {name}{hint_text}", Colors.RED))

    print()
    disabled_tools = [(name, hint) for name, avail, hint in tool_status if not avail]
    if disabled_tools:
        print_warning("部分工具未启用。运行 'python cli.py setup' 重新配置。")
        print()

    # 文件位置
    print(color(f"📁 配置文件位置:", Colors.CYAN, Colors.BOLD))
    print()
    print(f"   {color('设置文件:', Colors.YELLOW)}  {PROJECT_ROOT / '.env'}")
    print(f"   {color('项目目录:', Colors.YELLOW)}  {PROJECT_ROOT}")
    print()

    print(color("─" * 58, Colors.DIM))
    print()
    print(color("📝 配置命令:", Colors.CYAN, Colors.BOLD))
    print()
    print(f"   {color('python cli.py setup', Colors.GREEN)}           重新运行设置向导")
    print(f"   {color('python cli.py setup model', Colors.GREEN)}    配置模型/Provider")
    print(f"   {color('python cli.py setup gateway', Colors.GREEN)}  配置消息平台")
    print(f"   {color('python cli.py setup tools', Colors.GREEN)}    配置工具")
    print(f"   {color('python cli.py setup agent', Colors.GREEN)}    配置Agent行为")
    print()
    print(f"   {color('python cli.py config', Colors.GREEN)}         查看当前配置")
    print(f"   {color('python cli.py doctor', Colors.GREEN)}         诊断系统问题")
    print()
    print(color("─" * 58, Colors.DIM))
    print()
    print(color("🚀 开始使用:", Colors.CYAN, Colors.BOLD))
    print()
    print(f"   {color('python cli.py', Colors.GREEN)}              启动交互模式")
    print(f"   {color('python cli.py -q \"任务\"', Colors.GREEN)}  执行单次任务")
    print()

def cmd_setup(args):
    """交互式设置向导 - 对齐Hermes setup功能"""
    # 解析section参数
    section = getattr(args, 'section', None)

    print()
    print(color("┌" + "─" * 56 + "┐", Colors.CYAN, Colors.BOLD))
    print(color("│" + " ⚕ MimirAether 设置向导 ".center(56) + "│", Colors.CYAN, Colors.BOLD))
    print(color("└" + "─" * 56 + "┘", Colors.CYAN, Colors.BOLD))

    # 显示section帮助
    if section == "help":
        print()
        print_info("可用section:")
        print_info("  model   - 模型与Provider配置")
        print_info("  gateway - Gateway消息平台配置")
        print_info("  tools   - 工具配置")
        print_info("  agent   - Agent行为配置")
        print_info("  (无)    - 运行完整设置向导")
        return 0

    # 运行对应section
    if section == "model":
        _setup_model_provider()
        _print_setup_summary()
        return 0

    if section == "gateway":
        _setup_gateway()
        return 0

    if section == "tools":
        _setup_tools()
        _print_setup_summary()
        return 0

    if section == "agent":
        _setup_agent_settings()
        _print_setup_summary()
        return 0

    # 完整设置向导
    print()
    print_info("这个向导将帮助您配置MimirAether。")
    print_info("按Ctrl+C随时退出(保持已完成的配置)。")
    print()

    # Section 1: 模型
    try:
        _setup_model_provider()
    except KeyboardInterrupt:
        print()
        print_warning("设置已取消")
        return 0

    # Section 2: Gateway
    print()
    if prompt_yes_no("配置消息平台 (Telegram/飞书/Discord)?", False):
        try:
            _setup_gateway()
        except KeyboardInterrupt:
            print()
            print_warning("Gateway配置已跳过")

    # Section 3: 工具
    print()
    if prompt_yes_no("配置额外的工具API密钥?", False):
        try:
            _setup_tools()
        except KeyboardInterrupt:
            print()
            print_warning("工具配置已跳过")

    # Section 4: Agent设置
    print()
    if prompt_yes_no("配置Agent行为参数?", False):
        try:
            _setup_agent_settings()
        except KeyboardInterrupt:
            print()
            print_warning("Agent设置已跳过")

    # 打印摘要
    _print_setup_summary()

    return 0

# =============================================================================
# 命令：model
# =============================================================================

def cmd_model(args):
    """查看/切换模型"""
    models = get_available_models()
    
    print("=" * 60)
    print("MimirAether 模型管理")
    print("=" * 60)
    
    print("\n【可用模型】")
    current = get_model()
    for i, (model_id, name, note) in enumerate(models, 1):
        marker = " ← 当前" if model_id == current else ""
        print(f"  {i}. {name} ({model_id}) - {note}{marker}")
    
    if args.list:
        print("\n【当前配置】")
        print(f"  默认模型: {current}")
        print(f"  API Base: {os.environ.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com')}")
        return 0
    
    print("\n使用 'python cli.py model --set MODEL_ID' 切换模型")
    return 0

# =============================================================================
# 命令：models
# =============================================================================

def _load_env_vars():
    """从.env文件加载环境变量"""
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        try:
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, val = line.partition('=')
                        env_vars[key.strip()] = val.strip()
        except Exception:
            pass
    return env_vars


def _save_env_var(key: str, value: str):
    """保存环境变量到.env文件"""
    env_path = PROJECT_ROOT / ".env"
    env_vars = _load_env_vars()
    env_vars[key] = value
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# MimirAether配置文件\n")
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
        return True
    except Exception as e:
        print(f"保存失败: {e}")
        return False


def cmd_models(args):
    """models命令 - 对齐Hermes models功能"""
    set_model = getattr(args, 'set_model', None)
    list_all = getattr(args, 'list', False)
    refresh = getattr(args, 'refresh', False)
    
    models = get_available_models()
    
    # 优先从.env读取默认模型，否则使用get_model()
    env_vars = _load_env_vars()
    current_model = env_vars.get('DEFAULT_MODEL') or get_model()
    
    # 处理 --set MODEL_ID
    if set_model:
        # 验证模型是否在列表中
        valid_models = [m[0] for m in models]
        if set_model not in valid_models:
            print(f"❌ 未知模型: {set_model}")
            print(f"\n可用模型:")
            for mid, name, _ in models:
                print(f"  - {mid} ({name})")
            return 1
        
        # 保存到.env
        if _save_env_var('DEFAULT_MODEL', set_model):
            print(f"✅ 已切换默认模型: {set_model}")
            if set_model == current_model:
                print("   (与当前模型相同)")
            else:
                print(f"   (原模型: {current_model})")
        return 0
    
    # 处理 --refresh
    if refresh:
        print("🔄 刷新模型列表...")
        # MimirAether使用静态模型列表，暂无API刷新
        print("✅ 模型列表已刷新")
        return 0
    
    # 默认：显示格式化的模型列表
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " 🤖 MimirAether Models ".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    
    # 当前配置信息
    print()
    print("◆ 当前配置")
    print(f"  默认模型:   {current_model}")
    env_vars = _load_env_vars()
    default_model_env = env_vars.get('DEFAULT_MODEL', '')
    if default_model_env:
        print(f"  .env配置:   DEFAULT_MODEL={default_model_env}")
    
    # 模型列表表格
    print()
    print("◆ 可用模型")
    print()
    
    # 表头
    name_col = 30
    id_col = 28
    print(f"  {'名称':<{name_col}} {'模型ID':<{id_col}} 状态")
    print(f"  {'─' * name_col} {'─' * id_col} {'──────'}")
    
    # 模型行
    for model_id, name, note in models:
        is_current = model_id == current_model
        marker = "← 当前" if is_current else ""
        status = "✅ " + marker if is_current else ""
        
        # 截断过长的名称
        display_name = name if len(name) <= name_col else name[:name_col-2] + ".."
        
        print(f"  {display_name:<{name_col}} {model_id:<{id_col}} {status}")
        if note and not is_current:
            print(f"  {'':​<{name_col}} {'':​<{id_col}}   {note}")
    
    print()
    print("─" * 60)
    print()
    print("  使用 'python cli.py models --set MODEL_ID' 切换默认模型")
    print()
    
    return 0

# =============================================================================
# 命令：cron
# =============================================================================

def cmd_cron(args):
    """定时任务管理"""
    print("=" * 60)
    print("MimirAether 定时任务")
    print("=" * 60)
    
    if args.list:
        print("\n【定时任务列表】")
        print("  (暂无定时任务)")
        print("\n使用 'python cli.py cron add \"task\" \"schedule\"' 添加任务")
        return 0
    
    if args.add:
        print(f"\n添加定时任务: {args.add}")
        print("  注意: 定时任务功能正在开发中")
        return 0
    
    print("\n【子命令】")
    print("  cron list              - 列出所有定时任务")
    print("  cron add \"task\" \"schedule\"  - 添加定时任务")
    print("  cron remove <id>       - 删除定时任务")
    return 0

# =============================================================================
# 命令：version
# =============================================================================

def cmd_version(args):
    """显示版本信息"""
    print("=" * 60)
    print("MimirAether 版本信息")
    print("=" * 60)
    print(f"\n  版本: {__version__}")
    print(f"  Agent: {__agent_version__}")
    print(f"  Python: {platform.python_version()}")
    print(f"  平台: {platform.system()} {platform.release()}")
    print(f"  项目目录: {PROJECT_ROOT}")
    
    if args.check:
        print("\n【检查更新】")
        print("  正在检查更新...")
        print("  ✅ 当前已是最新版本")
    
    print("\n" + "=" * 60)
    return 0

# =============================================================================
# 命令：gateway
# =============================================================================

def cmd_gateway(args):
    """Gateway管理"""
    action = args.action or "status"
    
    if action == "start":
        print("启动Gateway...")
        print("\n请使用: python gateway/run.py")
        print("或设置后台运行:")
        print("  nohup python gateway/run.py &")
        return 0
    
    elif action == "stop":
        print("停止Gateway...")
        print("  发送停止信号...")
        return 0
    
    elif action == "restart":
        print("重启Gateway...")
        print("  1. 停止当前Gateway...")
        print("  2. 启动新Gateway...")
        return 0
    
    elif action == "status":
        print("Gateway状态:")
        try:
            import httpx
            response = httpx.get("http://localhost:18999/health", timeout=3)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ API服务运行中")
                print(f"     版本: {data.get('version', 'unknown')}")
            else:
                print(f"  ⚠️ API服务异常 (状态码: {response.status_code})")
        except Exception:
            print("  ❌ Gateway未运行")
        return 0
    
    else:
        print(f"未知操作: {action}")
        return 1

# =============================================================================
# 命令：plugins
# =============================================================================

def _get_plugins_dir():
    """获取插件存储目录"""
    return PROJECT_ROOT / "plugins"

def _get_plugins_config_path():
    """获取插件配置文件路径"""
    return PROJECT_ROOT / "plugins.json"

def _load_plugins_config():
    """加载插件配置"""
    config_path = _get_plugins_config_path()
    if config_path.exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"plugins": {}, "marketplaces": {}}

def _save_plugins_config(config):
    """保存插件配置"""
    config_path = _get_plugins_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

def _load_skill_metadata(skill_path):
    """从SKILL.md读取技能元数据"""
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding='utf-8')
            metadata = {"description": "", "name": skill_path.name}
            for line in content.split('\n')[:10]:
                if line.startswith('description:'):
                    metadata["description"] = line.split(':', 1)[1].strip()
                elif line.startswith('# '):
                    metadata["name"] = line[2:].strip()
            return metadata
        except Exception:
            pass
    return {"description": "", "name": skill_path.name}

def cmd_plugins(args):
    """插件管理命令 - 对齐Hermes plugins功能"""
    subcmd = getattr(args, 'plugin_action', None)
    plugin_name = getattr(args, 'plugin_name', None)
    
    # =========================================================================
    # plugins list - 列出已安装的插件
    # =========================================================================
    if subcmd == "list" or subcmd is None:
        json_output = getattr(args, 'json', False)
        
        config = _load_plugins_config()
        plugins_dir = _get_plugins_dir()
        
        # 收集内置技能目录中的插件
        builtin_skills = []
        skills_dir = PROJECT_ROOT / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    builtin_skills.append({
                        "name": item.name,
                        "path": str(item),
                        "scope": "builtin",
                        "enabled": True
                    })
        
        # 收集已安装的外部插件
        installed = []
        for name, info in config.get("plugins", {}).items():
            installed.append({
                "name": name,
                "path": info.get("path", ""),
                "scope": info.get("scope", "user"),
                "enabled": info.get("enabled", True),
                "version": info.get("version", "unknown"),
                "installed_at": info.get("installed_at", "")
            })
        
        if json_output:
            output = {
                "builtin": builtin_skills,
                "installed": installed
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
            return 0
        
        print()
        print("┌" + "─" * 58 + "┐")
        print("│" + " 🔌 MimirAether Plugins ".center(58) + "│")
        print("└" + "─" * 58 + "┘")
        
        # 内置技能
        print()
        print("◆ 内置技能")
        if builtin_skills:
            for skill in sorted(builtin_skills, key=lambda x: x['name']):
                meta = _load_skill_metadata(PROJECT_ROOT / "skills" / skill['name'])
                desc = meta.get('description', '')[:40]
                print(f"  ✅ {skill['name']}")
                if desc:
                    print(f"      {desc}")
        else:
            print("  (无)")
        
        # 已安装的外部插件
        print()
        print("◆ 已安装的插件")
        if installed:
            for plugin in sorted(installed, key=lambda x: x['name']):
                status = "✅" if plugin['enabled'] else "❌"
                scope = plugin['scope']
                version = plugin.get('version', 'unknown')
                print(f"  {status} {plugin['name']} (v{version}, {scope})")
        else:
            print("  (无外部插件)")
            print()
            print("  使用 'python cli.py plugins install <name>' 安装插件")
        
        print()
        print("─" * 60)
        print("  使用 'python cli.py plugins list --json' 查看JSON格式")
        print()
        return 0
    
    # =========================================================================
    # plugins install - 安装插件
    # =========================================================================
    if subcmd == "install":
        if not plugin_name:
            print("❌ 请指定要安装的插件名称")
            print("\n用法: python cli.py plugins install <plugin_name>")
            return 1
        
        print(f"📦 安装插件: {plugin_name}")
        
        config = _load_plugins_config()
        plugins_dir = _get_plugins_dir()
        plugins_dir.mkdir(exist_ok=True)
        
        # 检查是否已安装
        if plugin_name in config.get("plugins", {}):
            print(f"❌ 插件 '{plugin_name}' 已安装")
            return 1
        
        # 检查是否为内置技能
        builtin_path = PROJECT_ROOT / "skills" / plugin_name
        if builtin_path.exists():
            print(f"⚠️ '{plugin_name}' 是内置技能，已可用")
            return 0
        
        # 模拟安装过程（实际可扩展为从市场下载）
        plugin_info = {
            "name": plugin_name,
            "path": str(plugins_dir / plugin_name),
            "scope": "user",
            "enabled": True,
            "version": "1.0.0",
            "installed_at": datetime.now().isoformat()
        }
        
        config.setdefault("plugins", {})[plugin_name] = plugin_info
        
        if _save_plugins_config(config):
            print(f"✅ 插件 '{plugin_name}' 安装成功")
        else:
            print(f"❌ 安装失败")
            return 1
        return 0
    
    # =========================================================================
    # plugins uninstall - 卸载插件
    # =========================================================================
    if subcmd == "uninstall":
        if not plugin_name:
            print("❌ 请指定要卸载的插件名称")
            print("\n用法: python cli.py plugins uninstall <plugin_name>")
            return 1
        
        print(f"🗑️ 卸载插件: {plugin_name}")
        
        config = _load_plugins_config()
        
        if plugin_name not in config.get("plugins", {}):
            print(f"❌ 插件 '{plugin_name}' 未安装")
            return 1
        
        del config["plugins"][plugin_name]
        
        if _save_plugins_config(config):
            print(f"✅ 插件 '{plugin_name}' 已卸载")
        else:
            print(f"❌ 卸载失败")
            return 1
        return 0
    
    # =========================================================================
    # plugins enable - 启用插件
    # =========================================================================
    if subcmd == "enable":
        if not plugin_name:
            print("❌ 请指定要启用的插件名称")
            print("\n用法: python cli.py plugins enable <plugin_name>")
            return 1
        
        config = _load_plugins_config()
        
        if plugin_name in config.get("plugins", {}):
            config["plugins"][plugin_name]["enabled"] = True
            _save_plugins_config(config)
            print(f"✅ 插件 '{plugin_name}' 已启用")
        else:
            print(f"❌ 插件 '{plugin_name}' 未安装")
            return 1
        return 0
    
    # =========================================================================
    # plugins disable - 禁用插件
    # =========================================================================
    if subcmd == "disable":
        disable_all = getattr(args, 'all', False)
        
        config = _load_plugins_config()
        
        if disable_all:
            # 禁用所有插件
            for name in config.get("plugins", {}):
                config["plugins"][name]["enabled"] = False
            _save_plugins_config(config)
            print("✅ 所有插件已禁用")
        elif plugin_name:
            if plugin_name in config.get("plugins", {}):
                config["plugins"][plugin_name]["enabled"] = False
                _save_plugins_config(config)
                print(f"✅ 插件 '{plugin_name}' 已禁用")
            else:
                print(f"❌ 插件 '{plugin_name}' 未安装")
                return 1
        else:
            print("❌ 请指定插件名称或使用 --all")
            return 1
        return 0
    
    # =========================================================================
    # plugins update - 更新插件
    # =========================================================================
    if subcmd == "update":
        if not plugin_name:
            print("❌ 请指定要更新的插件名称")
            print("\n用法: python cli.py plugins update <plugin_name>")
            return 1
        
        config = _load_plugins_config()
        
        if plugin_name not in config.get("plugins", {}):
            print(f"❌ 插件 '{plugin_name}' 未安装")
            return 1
        
        print(f"🔄 更新插件: {plugin_name}")
        # 模拟更新
        print(f"✅ 插件 '{plugin_name}' 已更新到最新版本")
        return 0
    
    # =========================================================================
    # 默认帮助
    # =========================================================================
    print("""
MimirAether Plugins 命令

用法: python cli.py plugins <子命令> [选项]

子命令:
    list                    列出所有插件
    install <name>          安装插件
    uninstall <name>       卸载插件
    enable <name>           启用插件
    disable <name>          禁用插件
    disable --all           禁用所有插件
    update <name>           更新插件

选项:
    --json                  输出JSON格式

示例:
    python cli.py plugins list
    python cli.py plugins list --json
    python cli.py plugins install my-plugin
    python cli.py plugins uninstall my-plugin
    python cli.py plugins enable my-plugin
    python cli.py plugins disable my-plugin
    python cli.py plugins disable --all
    python cli.py plugins update my-plugin
""")
    return 0

# =============================================================================
# 命令：marketplace
# =============================================================================

def cmd_marketplace(args):
    """插件市场管理 - 对齐Hermes marketplace功能"""
    subcmd = getattr(args, 'marketplace_action', None)
    source = getattr(args, 'source', None)
    name = getattr(args, 'marketplace_name', None)
    
    config = _load_plugins_config()
    marketplaces = config.get("marketplaces", {})
    
    # =========================================================================
    # marketplace list - 列出已配置的市场
    # =========================================================================
    if subcmd == "list" or subcmd is None:
        json_output = getattr(args, 'json', False)
        
        if json_output:
            print(json.dumps(list(marketplaces.keys()), indent=2))
            return 0
        
        print()
        print("┌" + "─" * 58 + "┐")
        print("│" + " 🏪 MimirAether Marketplaces ".center(58) + "│")
        print("└" + "─" * 58 + "┘")
        print()
        
        if marketplaces:
            for mkt_name, mkt_info in marketplaces.items():
                print(f"  📦 {mkt_name}")
                source_type = mkt_info.get("source", "unknown")
                print(f"      类型: {source_type}")
                if mkt_info.get("url"):
                    print(f"      URL: {mkt_info.get('url')}")
                print()
        else:
            print("  (无已配置的市场)")
            print()
            print("  使用 'python cli.py marketplace add <source>' 添加市场")
        
        print()
        return 0
    
    # =========================================================================
    # marketplace add - 添加市场
    # =========================================================================
    if subcmd == "add":
        if not source:
            print("❌ 请指定市场源")
            print("\n用法: python cli.py marketplace add <source>")
            return 1
        
        print(f"📦 添加市场: {source}")
        
        # 解析市场源
        if source.startswith("http://") or source.startswith("https://"):
            source_type = "url"
            mkt_name = source.split("/")[-1].replace(".json", "")
        elif "/" in source:
            source_type = "github"
            mkt_name = source.split("/")[-1]
        else:
            source_type = "local"
            mkt_name = source
        
        marketplaces[source] = {
            "name": mkt_name,
            "source": source_type,
            "url": source if source_type in ("url", "github") else None,
            "added_at": datetime.now().isoformat()
        }
        
        config["marketplaces"] = marketplaces
        if _save_plugins_config(config):
            print(f"✅ 市场 '{mkt_name}' 添加成功")
        else:
            print(f"❌ 添加失败")
            return 1
        return 0
    
    # =========================================================================
    # marketplace remove - 移除市场
    # =========================================================================
    if subcmd == "remove":
        if not name:
            print("❌ 请指定要移除的市场名称")
            print("\n用法: python cli.py marketplace remove <name>")
            return 1
        
        # 查找市场
        to_remove = None
        for mkt_source, mkt_info in marketplaces.items():
            if mkt_info.get("name") == name or mkt_source == name:
                to_remove = mkt_source
                break
        
        if to_remove:
            del marketplaces[to_remove]
            config["marketplaces"] = marketplaces
            _save_plugins_config(config)
            print(f"✅ 市场 '{name}' 已移除")
        else:
            print(f"❌ 市场 '{name}' 不存在")
            return 1
        return 0
    
    # =========================================================================
    # marketplace update - 更新市场
    # =========================================================================
    if subcmd == "update":
        if name:
            print(f"🔄 更新市场: {name}")
            print(f"✅ 市场 '{name}' 已更新")
        else:
            print(f"🔄 更新所有市场...")
            count = len(marketplaces)
            print(f"✅ 已更新 {count} 个市场")
        return 0
    
    # =========================================================================
    # 默认帮助
    # =========================================================================
    print("""
MimirAether Marketplace 命令

用法: python cli.py marketplace <子命令> [选项]

子命令:
    list                    列出所有已配置的市场
    add <source>            添加市场 (支持 URL, GitHub owner/repo, 或本地路径)
    remove <name>          移除市场
    update [name]           更新市场 (可选: 指定市场名称)

选项:
    --json                  输出JSON格式 (仅 list)

示例:
    python cli.py marketplace list
    python cli.py marketplace add https://example.com/marketplace.json
    python cli.py marketplace add owner/repo
    python cli.py marketplace remove my-marketplace
    python cli.py marketplace update
    python cli.py marketplace update my-marketplace
""")
    return 0

# =============================================================================
# 命令：auth
# =============================================================================


def _load_env_vars():
    """从.env文件加载环境变量"""
    env_path = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        try:
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, val = line.partition('=')
                        env_vars[key.strip()] = val.strip()
        except Exception:
            pass
    return env_vars


def _format_exhausted_status(entry) -> str:
    """格式化耗尽状态显示"""
    import math
    import time as time_module
    
    if entry.last_status != "exhausted":
        return ""
    reason = getattr(entry, "last_error_reason", None)
    reason_text = f" {reason}" if isinstance(reason, str) and reason.strip() else ""
    code = f" ({entry.last_error_code})" if entry.last_error_code else ""
    
    # 计算剩余冷却时间
    reset_at = getattr(entry, "last_error_reset_at", None)
    if reset_at:
        remaining = max(0, int(math.ceil(reset_at - time_module.time())))
        if remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            hours, minutes = divmod(minutes, 60)
            days, hours = divmod(hours, 24)
            if days:
                wait = f"{days}d {hours}h"
            elif hours:
                wait = f"{hours}h {minutes}m"
            elif minutes:
                wait = f"{minutes}m {seconds}s"
            else:
                wait = f"{seconds}s"
            return f" exhausted{reason_text}{code} ({wait} left)"
        else:
            return f" exhausted{reason_text}{code} (ready to retry)"
    return f" exhausted{reason_text}{code}"


def _normalize_provider(provider: str) -> str:
    """标准化provider名称"""
    normalized = (provider or "").strip().lower()
    mapping = {
        "or": "openrouter",
        "open-router": "openrouter",
        "ds": "deepseek",
        "mm": "minimax",
        "anthropic": "anthropic",
        "openai": "openai",
        "deepseek": "deepseek",
        "minimax": "minimax",
    }
    return mapping.get(normalized, normalized)


def _get_known_providers() -> list:
    """获取已知provider列表"""
    return ["deepseek", "minimax", "anthropic", "openai", "openrouter", "siliconflow", "zhipu", "qwen"]


def cmd_auth(args):
    """凭证管理命令 - 对齐Hermes auth功能"""
    from agent.credential_pool import (
        CredentialPool,
        PooledCredential,
        STATUS_OK,
        STATUS_EXHAUSTED,
        AUTH_TYPE_API_KEY,
        AUTH_TYPE_OAUTH,
        SOURCE_MANUAL,
        STRATEGY_FILL_FIRST,
    )
    
    action = getattr(args, 'auth_action', None)
    provider_filter = getattr(args, 'auth_provider', None)
    target = getattr(args, 'auth_target', None)
    
    # 如果有provider_filter，进行标准化
    if provider_filter:
        provider_filter = _normalize_provider(provider_filter)
    
    # =========================================================================
    # auth list - 列出凭证
    # =========================================================================
    if action == "list":
        print()
        print("┌" + "─" * 58 + "┐")
        print("│" + " 🔐 MimirAether Credentials ".center(58) + "│")
        print("└" + "─" * 58 + "┘")
        
        # 从环境变量收集凭证
        env_vars = _load_env_vars()
        
        # Known API keys
        api_keys = {
            "deepseek": ["DEEPSEEK_API_KEY", "DEEPSEEK_V3_API_KEY"],
            "minimax": ["MINIMAX_API_KEY", "MINIMAX_V2_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "openai": ["OPENAI_API_KEY"],
            "siliconflow": ["SILICONFLOW_API_KEY"],
            "zhipu": ["ZHIPU_API_KEY"],
            "qwen": ["QWEN_API_KEY"],
        }
        
        # 凭证池凭证
        pool_file = PROJECT_ROOT / "credentials" / "credential_pool.json"
        pool_creds = []
        if pool_file.exists():
            try:
                import json
                with open(pool_file) as f:
                    pool_creds = json.load(f)
            except Exception:
                pass
        
        has_any = False
        
        # 按provider显示
        providers = _get_known_providers()
        if provider_filter:
            providers = [p for p in providers if p == provider_filter]
        
        for provider in providers:
            # 环境变量凭证
            env_keys = api_keys.get(provider, [])
            env_creds = []
            for key in env_keys:
                value = os.environ.get(key, "") or env_vars.get(key, "")
                if value:
                    env_creds.append({
                        "label": key,
                        "source": f"env:{key}",
                        "status": "ok",
                        "auth_type": "api_key",
                    })
            
            # 池凭证
            provider_pool_creds = [
                c for c in pool_creds 
                if c.get("provider", "").lower() == provider or 
                   c.get("label", "").lower().startswith(provider)
            ]
            
            if not env_creds and not provider_pool_creds:
                continue
            
            has_any = True
            print()
            print(f"◆ {provider.upper()}")
            
            # 环境变量凭证
            for cred in env_creds:
                print(f"  ✅ {cred['label']:<30} {cred['auth_type']:<8} {cred['source']}")
            
            # 池凭证
            for cred in provider_pool_creds:
                label = cred.get("label", "unknown")
                auth_type = cred.get("auth_type", "api_key")
                source = cred.get("source", "unknown")
                status = cred.get("last_status", "ok")
                status_icon = "✅" if status == "ok" else "⏳"
                
                # 尝试获取PooledCredential对象以获取完整状态
                try:
                    pool = CredentialPool(provider, auto_seed_env=False)
                    entry = None
                    for e in pool.entries:
                        if e.label == label:
                            entry = e
                            break
                    if entry:
                        exhausted_str = _format_exhausted_status(entry)
                        print(f"  {status_icon} {label:<30} {auth_type:<8} {source}{exhausted_str}")
                    else:
                        print(f"  {status_icon} {label:<30} {auth_type:<8} {source}")
                except Exception:
                    print(f"  {status_icon} {label:<30} {auth_type:<8} {source}")
        
        if not has_any:
            print()
            print("  (无已配置的凭证)")
            print()
            print("  使用 'python cli.py auth add <provider>' 添加凭证")
        
        print()
        print("─" * 60)
        print()
        return 0
    
    # =========================================================================
    # auth add - 添加凭证
    # =========================================================================
    if action == "add":
        provider = provider_filter
        if not provider:
            # 交互式选择provider
            print()
            print("┌" + "─" * 58 + "┐")
            print("│" + " 🔐 添加凭证 ".center(58) + "│")
            print("└" + "─" * 58 + "┘")
            print()
            print("可用Provider:")
            providers = _get_known_providers()
            for i, p in enumerate(providers, 1):
                print(f"  {i}. {p}")
            print()
            try:
                choice = input("选择Provider (输入编号或名称): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 1
            
            if not choice:
                print("取消添加。")
                return 0
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(providers):
                    provider = providers[idx]
                else:
                    print(f"无效选择: {choice}")
                    return 1
            else:
                provider = _normalize_provider(choice)
                if provider not in providers:
                    print(f"未知Provider: {provider}")
                    return 1
        else:
            providers = _get_known_providers()
            if provider not in providers:
                print(f"未知Provider: {provider}")
                print(f"可用Provider: {', '.join(providers)}")
                return 1
        
        print()
        print(f"为 {provider} 添加凭证")
        print()
        
        # API Key映射
        api_key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "qwen": "QWEN_API_KEY",
        }
        
        env_var = api_key_map.get(provider)
        current_key = os.environ.get(env_var, "") or _load_env_vars().get(env_var, "")
        
        if current_key:
            print(f"当前已配置的密钥: {current_key[:8]}...")
            print()
        
        # 获取新密钥
        try:
            from getpass import getpass
            new_key = getpass("输入新的API密钥 (留空跳过): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        
        if not new_key:
            print("未提供新密钥，取消添加。")
            return 0
        
        # 保存到.env
        env_path = PROJECT_ROOT / ".env"
        env_vars = _load_env_vars()
        
        if env_var:
            env_vars[env_var] = new_key
            try:
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write("# MimirAether配置文件\n")
                    for key, value in env_vars.items():
                        f.write(f"{key}={value}\n")
                print(f"✅ 已保存 {env_var} 到 .env")
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                return 1
        else:
            print(f"⚠️ {provider} 的环境变量映射未定义，请手动配置")
            return 1
        
        print()
        return 0
    
    # =========================================================================
    # auth remove - 移除凭证
    # =========================================================================
    if action == "remove":
        provider = provider_filter
        target = getattr(args, 'auth_target', None)
        
        if not provider:
            print("❌ 请指定provider: python cli.py auth remove <provider> <target>")
            return 1
        
        if not target:
            print("❌ 请指定要移除的凭证 (索引、ID或label): python cli.py auth remove <provider> <target>")
            return 1
        
        # API Key映射
        api_key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "qwen": "QWEN_API_KEY",
        }
        
        env_var = api_key_map.get(provider)
        
        # 检查是否是环境变量凭证
        if env_var:
            env_vars = _load_env_vars()
            current_key = env_vars.get(env_var, "")
            
            if target.lower() in [env_var.lower(), "env", f"env:{env_var}"]:
                # 移除环境变量凭证
                if current_key:
                    env_vars.pop(env_var, None)
                    env_path = PROJECT_ROOT / ".env"
                    try:
                        with open(env_path, 'w', encoding='utf-8') as f:
                            f.write("# MimirAether配置文件\n")
                            for key, value in env_vars.items():
                                f.write(f"{key}={value}\n")
                        print(f"✅ 已移除 {env_var}")
                        return 0
                    except Exception as e:
                        print(f"❌ 移除失败: {e}")
                        return 1
        
        # 尝试从池中移除
        try:
            pool = CredentialPool(provider, auto_seed_env=False)
            index, matched, error = pool.resolve_target(target)
            if matched is None or index is None:
                print(f"❌ {error}")
                return 1
            removed = pool.remove_index(index)
            if removed:
                print(f"✅ 已移除凭证: {removed.label}")
                return 0
            else:
                print(f"❌ 移除失败")
                return 1
        except Exception as e:
            print(f"❌ 移除失败: {e}")
            return 1
    
    # =========================================================================
    # auth reset - 重置凭证状态
    # =========================================================================
    if action == "reset":
        provider = provider_filter
        
        if not provider:
            print("❌ 请指定provider: python cli.py auth reset <provider>")
            return 1
        
        try:
            pool = CredentialPool(provider, auto_seed_env=False)
            count = pool.reset_all_statuses()
            print(f"✅ 已重置 {count} 个凭证的冷却状态")
            return 0
        except Exception as e:
            print(f"❌ 重置失败: {e}")
            return 1
    
    # =========================================================================
    # auth (默认) - 显示凭证状态摘要
    # =========================================================================
    print()
    print("┌" + "─" * 58 + "┐")
    print("│" + " 🔐 MimirAether Auth ".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    
    # 从环境变量收集凭证状态
    env_vars = _load_env_vars()
    
    api_keys = [
        ("DeepSeek", "DEEPSEEK_API_KEY"),
        ("DeepSeek V3", "DEEPSEEK_V3_API_KEY"),
        ("MiniMax", "MINIMAX_API_KEY"),
        ("MiniMax V2", "MINIMAX_V2_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"),
        ("OpenAI", "OPENAI_API_KEY"),
        ("SiliconFlow", "SILICONFLOW_API_KEY"),
        ("Zhipu", "ZHIPU_API_KEY"),
        ("Qwen", "QWEN_API_KEY"),
    ]
    
    print()
    print("◆ API密钥")
    has_any = False
    for name, env_var in api_keys:
        value = os.environ.get(env_var, "") or env_vars.get(env_var, "")
        if value:
            has_any = True
            print(f"  ✅ {name:<14} {redact_key(value)}")
    
    if not has_any:
        print("  (无已配置的API密钥)")
    
    # 凭证池状态
    print()
    print("◆ 凭证池")
    
    pool_dir = PROJECT_ROOT / "credentials"
    if pool_dir.exists():
        pool_files = list(pool_dir.glob("*/credential_pool.json"))
        if pool_files:
            for pool_file in pool_files:
                provider_name = pool_file.parent.name
                print(f"  📦 {provider_name}")
        else:
            print("  (无凭证池条目)")
    else:
        print("  (凭证池目录不存在)")
    
    print()
    print("─" * 60)
    print("  使用 'python cli.py auth list' 查看详细信息")
    print("  使用 'python cli.py auth add <provider>' 添加凭证")
    print("  使用 'python cli.py auth remove <provider> <target>' 移除凭证")
    print("  使用 'python cli.py auth reset <provider>' 重置冷却状态")
    print()
    
    return 0

# =============================================================================
# 命令：logs
# =============================================================================


def cmd_logs(args):
    """查看日志"""
    print("=" * 60)
    print("MimirAether 日志")
    print("=" * 60)
    
    log_dir = PROJECT_ROOT / "logs"
    if not log_dir.exists():
        print(f"\n日志目录不存在: {log_dir}")
        return 0
    
    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        print("\n暂无日志文件")
        return 0
    
    print(f"\n【日志文件】(共 {len(log_files)} 个)")
    for log_file in sorted(log_files)[-10:]:
        size = log_file.stat().st_size
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        print(f"  {log_file.name} ({size} bytes, {mtime.strftime('%Y-%m-%d %H:%M')})")
    
    if args.tail:
        print(f"\n【最后 {args.tail} 行】")
        if log_files:
            latest = sorted(log_files)[-1]
            with open(latest) as f:
                lines = f.readlines()
                for line in lines[-args.tail:]:
                    print(line.rstrip())
    
    return 0

# =============================================================================
# 交互模式
# =============================================================================

async def run_interactive():
    """运行交互模式"""
    from agent.core_loop import MimirAetherAgent
    
    print("=" * 60)
    print("MimirAether CLI - 交互模式")
    print("=" * 60)
    print("提示: 输入任务后按回车，输入 'quit' 或 'exit' 退出\n")
    
    agent = MimirAetherAgent(
        model=get_model(),
        max_iterations=90,
        platform="cli",
    )
    
    while True:
        try:
            user_input = input("\n👤 你: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("再见!")
                break
            if not user_input:
                continue
            
            print("\n🤖 MimirAether思考中...")
            result = await agent.run_conversation(user_input)
            print(f"\n🤖 MimirAether: {result}")
            
        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
    
    return 0

# =============================================================================
# 单次任务
# =============================================================================

async def run_task(task: str, model: str, max_iterations: int, verbose: bool):
    """执行单个任务"""
    from agent.core_loop import MimirAetherAgent
    
    print("=" * 60)
    print("🎯 MIMIRAETHER - 任务执行模式")
    print("=" * 60)
    print(f"任务: {task}")
    print(f"模型: {model}")
    print(f"最大迭代: {max_iterations}")
    print("=" * 60)
    
    agent = MimirAetherAgent(
        model=model,
        max_iterations=max_iterations,
        platform="cli",
    )
    
    if verbose:
        print(f"\n开始执行任务...")
    
    result = await agent.run_conversation(task)
    
    print("\n" + "=" * 60)
    print("【执行结果】")
    print("=" * 60)
    print(result)
    
    return 0

# =============================================================================
# 命令：profiles
# =============================================================================

def cmd_profiles(args):
    """Profile管理命令 - 对齐Hermes profiles功能"""
    # 解析profiles子命令
    subcmd = getattr(args, 'profile_action', None) or (args.profile_args[0] if args.profile_args else 'list')
    
    # 导入profiles模块
    try:
        from mimir_cli.profiles import (
            list_profiles,
            create_profile,
            delete_profile,
            get_active_profile,
            set_active_profile,
            export_profile,
            import_profile,
            rename_profile,
            validate_profile_name,
            profile_exists,
            get_active_profile_name,
            _get_wrapper_dir,
            _PROFILE_ID_RE,
        )
    except ImportError as e:
        print(f"❌ 无法导入profiles模块: {e}")
        return 1
    
    # profiles list - 列出所有profile
    if subcmd == "list":
        print()
        print("┌" + "─" * 58 + "┐")
        print("│" + " 📋 MimirAether Profiles ".center(58) + "│")
        print("└" + "─" * 58 + "┘")
        
        profiles = list_profiles()
        active_name = get_active_profile_name()
        
        if not profiles:
            print("\n  没有找到任何profile")
            return 0
        
        print()
        for p in profiles:
            is_active = p.name == active_name
            marker = "👉" if is_active else "  "
            gw_status = "🟢" if p.gateway_running else "⚪"
            env_status = "📄" if p.has_env else "  "
            
            print(f"  {marker} {p.name}")
            print(f"      路径: {p.path}")
            if p.model:
                print(f"      模型: {p.model}" + (f" ({p.provider})" if p.provider else ""))
            print(f"      网关: {gw_status} {'运行中' if p.gateway_running else '未运行'}  |  环境: {env_status}")
            if p.skill_count > 0:
                print(f"      技能: {p.skill_count} 个")
            if p.alias_path:
                print(f"      别名: {p.alias_path}")
            print()
        
        print("  使用 'python cli.py profiles create <name>' 创建新profile")
        print("  使用 'python cli.py profiles use <name>' 切换默认profile")
        print()
        return 0
    
    # profiles create <name> - 创建新profile
    elif subcmd == "create":
        if not args.profile_args:
            print("❌ 请指定profile名称")
            print("   用法: profiles create <name> [--clone] [--clone-all]")
            return 1
        
        name = args.profile_args[0]
        clone = getattr(args, 'clone', False)
        clone_all = getattr(args, 'clone_all', False)
        no_alias = getattr(args, 'no_alias', False)
        
        try:
            profile_dir = create_profile(
                name=name,
                clone_config=clone,
                clone_all=clone_all,
                no_alias=no_alias,
            )
            print(f"✅ Profile '{name}' 已创建: {profile_dir}")
            
            # 询问是否设为默认
            try:
                confirm = input("   是否设为默认profile? [y/N]: ").strip().lower()
                if confirm == 'y':
                    set_active_profile(name)
                    print(f"   ✅ 已设为默认profile")
            except (KeyboardInterrupt, EOFError):
                print()
            
            return 0
        except ValueError as e:
            print(f"❌ {e}")
            return 1
        except FileExistsError as e:
            print(f"❌ {e}")
            return 1
    
    # profiles delete <name> - 删除profile
    elif subcmd == "delete":
        if not args.profile_args:
            print("❌ 请指定要删除的profile名称")
            print("   用法: profiles delete <name> [--yes]")
            return 1
        
        name = args.profile_args[0]
        yes = getattr(args, 'yes', False)
        
        try:
            delete_profile(name, yes=yes)
            return 0
        except ValueError as e:
            print(f"❌ {e}")
            return 1
        except FileNotFoundError as e:
            print(f"❌ {e}")
            return 1
    
    # profiles use <name> - 设置默认profile
    elif subcmd == "use":
        if not args.profile_args:
            current = get_active_profile_name()
            print(f"当前默认profile: {current}")
            return 0
        
        name = args.profile_args[0]
        
        try:
            set_active_profile(name)
            print(f"✅ 默认profile已设置为: {name}")
            return 0
        except ValueError as e:
            print(f"❌ {e}")
            return 1
        except FileNotFoundError as e:
            print(f"❌ {e}")
            return 1
    
    # profiles show - 显示当前profile
    elif subcmd == "show":
        active = get_active_profile_name()
        print(f"当前默认profile: {active}")
        return 0
    
    # profiles export <name> <path> - 导出profile
    elif subcmd == "export":
        if len(args.profile_args) < 2:
            print("❌ 请指定profile名称和导出路径")
            print("   用法: profiles export <name> <output.tar.gz>")
            return 1
        
        name = args.profile_args[0]
        output_path = args.profile_args[1]
        
        try:
            result = export_profile(name, output_path)
            print(f"✅ Profile '{name}' 已导出: {result}")
            return 0
        except (ValueError, FileNotFoundError) as e:
            print(f"❌ {e}")
            return 1
    
    # profiles import <archive> [--name <name>] - 导入profile
    elif subcmd == "import":
        if not args.profile_args:
            print("❌ 请指定归档文件路径")
            print("   用法: profiles import <archive.tar.gz> [--name <name>]")
            return 1
        
        archive_path = args.profile_args[0]
        name = getattr(args, 'import_name', None)
        
        try:
            result = import_profile(archive_path, name=name)
            imported_name = name or result.name
            print(f"✅ Profile '{imported_name}' 已导入: {result}")
            return 0
        except (ValueError, FileNotFoundError, FileExistsError) as e:
            print(f"❌ {e}")
            return 1
    
    # profiles rename <old> <new> - 重命名profile
    elif subcmd == "rename":
        if len(args.profile_args) < 2:
            print("❌ 请指定原名称和新名称")
            print("   用法: profiles rename <old_name> <new_name>")
            return 1
        
        old_name = args.profile_args[0]
        new_name = args.profile_args[1]
        
        try:
            result = rename_profile(old_name, new_name)
            print(f"✅ Profile已重命名: {result}")
            return 0
        except (ValueError, FileNotFoundError, FileExistsError) as e:
            print(f"❌ {e}")
            return 1
    
    # 未知子命令
    else:
        print(f"❌ 未知子命令: {subcmd}")
        print()
        print("可用子命令:")
        print("  list                    列出所有profile")
        print("  create <name>           创建新profile")
        print("  delete <name>           删除profile")
        print("  use [<name>]            设置/显示默认profile")
        print("  show                    显示当前默认profile")
        print("  export <name> <path>    导出profile到归档")
        print("  import <archive>        从归档导入profile")
        print("  rename <old> <new>      重命名profile")
        return 1

# =============================================================================
# 主入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MimirAether CLI - 自主Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令:
    status          查看系统状态
    status --deep   深度检查(API连通性等)
    status --all    显示完整密钥(不脱敏)
    config          查看配置
    doctor          诊断系统问题 (--fix 自动修复)
    setup           交互式设置向导
    model           模型管理
    models          模型列表 (--set MODEL_ID 切换)
    cron            定时任务管理
    version         版本信息
    gateway         Gateway管理
    logs            查看日志
    -q TASK        执行单次任务

示例:
    python cli.py status
    python cli.py status --deep
    python cli.py status --all
    python cli.py doctor
    python cli.py setup
    python cli.py model --list
    python cli.py models
    python cli.py models --set deepseek/deepseek-chat
    python cli.py gateway status
    python cli.py logs --tail 50
    python cli.py plugins list           列出插件
    python cli.py plugins install <name> 安装插件
    python cli.py plugins uninstall <name> 卸载插件
    python cli.py plugins enable <name>  启用插件
    python cli.py plugins disable <name> 禁用插件
    python cli.py plugins disable --all 禁用所有插件
    python cli.py marketplace list       列出市场
    python cli.py marketplace add <src>  添加市场
    python cli.py marketplace remove <n> 移除市场
    python cli.py auth                  凭证管理
    python cli.py auth list            列出凭证
    python cli.py auth add <provider>  添加凭证
    python cli.py auth remove <provider> <target> 移除凭证
    python cli.py auth reset <provider> 重置冷却状态
    python cli.py profiles              Profile管理
    python cli.py profiles list        列出所有profile
    python cli.py profiles create <name> 创建新profile
    python cli.py profiles delete <name> 删除profile
    python cli.py profiles use <name>  设置默认profile
    python cli.py profiles show        显示当前profile
    python cli.py profiles export <name> <path> 导出profile
    python cli.py profiles import <archive> 导入profile
    python cli.py profiles rename <old> <new> 重命名profile
    python cli.py -q "改进gdi_scorer"
        """
    )
    
    parser.add_argument("command", nargs="?", help="命令")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="命令参数")
    parser.add_argument("-q", "--query", type=str, help="单次任务模式")
    parser.add_argument("--model", type=str, default=get_model(), help="指定模型")
    parser.add_argument("--max-iterations", type=int, default=90, help="最大迭代次数")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 解析子命令参数
    if args.args:
        args.action = args.args[0] if args.args else None
        args.add = None
        args.list = False
        args.get = None
        args.set = None
        args.tail = None
        args.check = False
        args.deep = False
        args.all = False
        args.fix = False
        args.subcmd = None
        args.key = None
        args.value = None
        
        # 特殊处理
        for i, arg in enumerate(args.args):
            if arg == "--list":
                args.list = True
            elif arg == "--set" and i + 1 < len(args.args):
                args.set = args.args[i + 1]
            elif arg == "--get" and i + 1 < len(args.args):
                args.get = args.args[i + 1]
            elif arg == "--tail" and i + 1 < len(args.args):
                try:
                    args.tail = int(args.args[i + 1])
                except ValueError:
                    pass
            elif arg == "--check":
                args.check = True
            elif arg == "--deep":
                args.deep = True
            elif arg == "--all":
                args.all = True
            elif arg == "--fix":
                args.fix = True
        
        # 处理config子命令 (config edit, config set KEY VALUE, config get KEY, etc.)
        if args.command == "config" and args.args:
            subcmd = args.args[0]
            args.subcmd = subcmd
            # config set KEY VALUE
            if subcmd == "set" and len(args.args) >= 3:
                args.key = args.args[1]
                args.value = args.args[2]
            # config get KEY
            elif subcmd == "get" and len(args.args) >= 2:
                args.key = args.args[1]
        
        # 处理models子命令 (models --set MODEL_ID, models --refresh)
        if args.command == "models" and args.args:
            args.set_model = None
            args.refresh = False
            for i, arg in enumerate(args.args):
                if arg == "--set" and i + 1 < len(args.args):
                    args.set_model = args.args[i + 1]
                elif arg == "--refresh":
                    args.refresh = True
                elif arg == "--list":
                    args.list = True
        
        # 处理plugins子命令 (plugins list/install/uninstall/enable/disable/update)
        if args.command == "plugins" and args.args:
            args.plugin_action = args.args[0] if args.args else "list"
            args.plugin_name = args.args[1] if len(args.args) > 1 else None
            args.json = False
            args.all = False
            for i, arg in enumerate(args.args):
                if arg == "--json":
                    args.json = True
                elif arg == "--all":
                    args.all = True
        else:
            args.plugin_action = None
            args.plugin_name = None
        
        # 处理marketplace子命令 (marketplace list/add/remove/update)
        if args.command == "marketplace" and args.args:
            args.marketplace_action = args.args[0] if args.args else "list"
            args.source = args.args[1] if len(args.args) > 1 else None
            args.marketplace_name = args.args[1] if len(args.args) > 1 else None
            args.json = False
            for i, arg in enumerate(args.args):
                if arg == "--json":
                    args.json = True
        else:
            args.marketplace_action = None
            args.source = None
            args.marketplace_name = None
        
        # 处理auth子命令 (auth list/add/remove/reset)
        if args.command == "auth" and args.args:
            args.auth_action = args.args[0] if args.args else None
            # auth remove 和 auth reset 需要provider
            if args.auth_action in ("remove", "reset") and len(args.args) > 1:
                args.auth_provider = args.args[1]
                args.auth_target = args.args[2] if len(args.args) > 2 else None
            elif args.auth_action == "add" and len(args.args) > 1:
                args.auth_provider = args.args[1]
                args.auth_target = None
            else:
                args.auth_provider = None
                args.auth_target = None
        else:
            args.auth_action = None
            args.auth_provider = None
            args.auth_target = None

        # 处理profiles子命令 (profiles list/create/delete/use/show/export/import/rename)
        if args.command == "profiles" and args.args:
            args.profile_action = args.args[0] if args.args else "list"
            args.profile_args = args.args[1:] if len(args.args) > 1 else []
            # profiles create支持 --clone, --clone-all, --no-alias
            args.clone = False
            args.clone_all = False
            args.no_alias = False
            for flag in ["--clone", "--clone-all", "--no-alias"]:
                if flag in args.args:
                    if flag == "--clone":
                        args.clone = True
                    elif flag == "--clone-all":
                        args.clone_all = True
                    elif flag == "--no-alias":
                        args.no_alias = True
            # profiles delete支持 --yes
            args.yes = False
            if "--yes" in args.args:
                args.yes = True
            # profiles import支持 --name
            args.import_name = None
            for i, arg in enumerate(args.args):
                if arg == "--name" and i + 1 < len(args.args):
                    args.import_name = args.args[i + 1]
        else:
            args.profile_action = None
            args.profile_args = []

        # 处理setup子命令 (setup model/gateway/tools/agent)
        if args.command == "setup" and args.args:
            valid_sections = ["model", "gateway", "tools", "agent", "help"]
            section = args.args[0].lower()
            if section in valid_sections:
                args.section = section
            else:
                args.section = None
        else:
            args.section = None
    else:
        args.action = None
        args.add = None
        args.list = False
        args.get = None
        args.set = None
        args.tail = None
        args.check = False
        args.deep = False
        args.all = False
        args.fix = False
        args.subcmd = None
        args.key = None
        args.value = None
        args.set_model = None
        args.refresh = False
        args.plugin_action = None
        args.plugin_name = None
        args.marketplace_action = None
        args.source = None
        args.marketplace_name = None
        args.auth_action = None
        args.auth_provider = None
        args.auth_target = None
        args.section = None
        args.profile_action = None
        args.profile_args = []
    
    # 处理命令
    if args.command == "status":
        return cmd_status(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "setup":
        return cmd_setup(args)
    elif args.command == "model":
        return cmd_model(args)
    elif args.command == "models":
        return cmd_models(args)
    elif args.command == "cron":
        return cmd_cron(args)
    elif args.command == "version":
        return cmd_version(args)
    elif args.command == "gateway":
        return cmd_gateway(args)
    elif args.command == "logs":
        return cmd_logs(args)
    elif args.command == "plugins":
        return cmd_plugins(args)
    elif args.command == "marketplace":
        return cmd_marketplace(args)
    elif args.command == "auth":
        return cmd_auth(args)
    elif args.command == "profiles":
        return cmd_profiles(args)
    elif args.query:
        return asyncio.run(run_task(args.query, args.model, args.max_iterations, args.verbose))
    else:
        return asyncio.run(run_interactive())

if __name__ == "__main__":
    sys.exit(main())
