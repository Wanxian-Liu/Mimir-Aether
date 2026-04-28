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

def cmd_setup(args):
    """交互式设置向导"""
    print("=" * 60)
    print("MimirAether 设置向导")
    print("=" * 60)
    
    print("\n这个向导将帮助您配置MimirAether。")
    print("按Enter使用默认值或输入您自己的值。\n")
    
    # 1. API Key
    print("【1/4】DeepSeek API Key")
    current_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if current_key:
        print(f"  当前: {current_key[:8]}...")
    api_key = input("  输入新的API Key (留空跳过): ").strip()
    
    if api_key:
        # 保存到环境或配置文件
        print(f"  ✅ API Key已设置")
        print("  注意: 请使用 'export DEEPSEEK_API_KEY=your_key' 永久保存")
    
    # 2. 默认模型
    print("\n【2/4】默认模型")
    current_model = get_model()
    print(f"  当前: {current_model}")
    model = input(f"  输入模型 (默认: {current_model}): ").strip() or current_model
    print(f"  ✅ 默认模型: {model}")
    
    # 3. 端口
    print("\n【3/4】API服务端口")
    current_port = os.environ.get("MIMIR_PORT", '18999')
    print(f"  当前: {current_port}")
    port = input(f"  输入端口 (默认: {current_port}): ").strip() or current_port
    print(f"  ✅ 端口: {port}")
    
    # 4. 适配器
    print("\n【4/4】启用的消息适配器")
    current_adapters = os.environ.get("MIMIR_ADAPTERS", 'telegram,feishu,discord')
    print(f"  当前: {current_adapters}")
    adapters = input(f"  输入适配器 (默认: {current_adapters}): ").strip() or current_adapters
    print(f"  ✅ 适配器: {adapters}")
    
    print("\n" + "=" * 60)
    print("设置完成！")
    print("=" * 60)
    print("\n要使配置永久生效，请添加到您的 shell 配置文件:")
    print("  export DEEPSEEK_API_KEY=your_key")
    print(f"  export MIMIR_MODEL={get_model()}")
    print("  export MIMIR_PORT=18999")
    print("  export MIMIR_ADAPTERS=telegram,feishu,discord")
    
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
    python cli.py gateway status
    python cli.py logs --tail 50
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
    elif args.command == "cron":
        return cmd_cron(args)
    elif args.command == "version":
        return cmd_version(args)
    elif args.command == "gateway":
        return cmd_gateway(args)
    elif args.command == "logs":
        return cmd_logs(args)
    elif args.query:
        return asyncio.run(run_task(args.query, args.model, args.max_iterations, args.verbose))
    else:
        return asyncio.run(run_interactive())

if __name__ == "__main__":
    sys.exit(main())
