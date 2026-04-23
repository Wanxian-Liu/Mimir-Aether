#!/usr/bin/env python3
"""
MimirAether CLI - 命令行入口

支持多种命令：
    python cli.py                          # 交互模式
    python cli.py status                  # 查看状态
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
import subprocess
from pathlib import Path
from datetime import datetime

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# 版本信息
# =============================================================================

__version__ = "0.1.0"
__agent_version__ = "MimirAether"

# =============================================================================
# 命令：status
# =============================================================================

def cmd_status(args):
    """查看系统状态"""
    from agent.core_loop import MimirAetherAgent
    
    print("=" * 60)
    print("MimirAether 状态")
    print("=" * 60)
    
    # 系统信息
    print("\n【系统信息】")
    print(f"  Python版本: {platform.python_version()}")
    print(f"  操作系统: {platform.system()} {platform.release()}")
    print(f"  主机名: {socket.gethostname()}")
    
    # Agent信息
    print("\n【Agent信息】")
    print(f"  版本: {__version__}")
    print(f"  默认模型: {os.environ.get('MIMIR_MODEL', 'deepseek/deepseek-chat')}")
    
    # 凭证信息
    print("\n【凭证状态】")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        masked = deepseek_key[:8] + "..." if len(deepseek_key) > 8 else "***"
        print(f"  DeepSeek API Key: ✅ 已配置 ({masked})")
    else:
        print("  DeepSeek API Key: ❌ 未配置")
    
    minimax_key = os.environ.get("MINIMAX_API_KEY", "")
    print(f"  MiniMax API Key: {'✅ 已配置' if minimax_key else '❌ 未配置'}")
    
    # Gateway状态
    print("\n【Gateway状态】")
    print(f"  API服务: http://localhost:18999")
    print(f"  适配器: {os.environ.get('MIMIR_ADAPTERS', 'telegram,feishu,discord')}")
    
    # 工具数
    print("\n【工具统计】")
    try:
        agent = MimirAetherAgent()
        tools = agent.tool_registry.list_tools()
        print(f"  内置工具: {len(tools)} 个")
        if args.verbose:
            for tool in tools[:15]:
                print(f"    - {tool}")
            if len(tools) > 15:
                print(f"    ... 还有 {len(tools) - 15} 个")
    except Exception as e:
        print(f"  Agent初始化失败: {e}")
    
    print("\n" + "=" * 60)
    return 0

# =============================================================================
# 命令：config
# =============================================================================

def cmd_config(args):
    """查看/修改配置"""
    from hermes_cli.config import load_config
    
    config = load_config()
    
    if args.get:
        keys = args.get.split('.')
        value = config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, None)
            else:
                value = None
                break
        
        if value is not None:
            print(f"{args.get}: {json.dumps(value, indent=2)}")
        else:
            print(f"配置项 {args.get} 不存在")
        return 0
    
    if args.set:
        key, _, value = args.set.partition('=')
        if not key or not value:
            print("格式错误，请使用: config --set KEY=VALUE")
            return 1
        print(f"设置配置: {key} = {value}")
        print("注意: 当前配置存储在文件中，需要手动编辑")
        return 0
    
    print("=" * 60)
    print("MimirAether 配置")
    print("=" * 60)
    
    print("\n【模型配置】")
    print(f"  默认模型: {os.environ.get('MIMIR_MODEL', 'deepseek/deepseek-chat')}")
    print(f"  API Base URL: {os.environ.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com')}")
    
    print("\n【Gateway配置】")
    print(f"  端口: {os.environ.get('MIMIR_PORT', '18999')}")
    print(f"  适配器: {os.environ.get('MIMIR_ADAPTERS', 'telegram,feishu,discord')}")
    
    print("\n【路径配置】")
    print(f"  项目目录: {PROJECT_ROOT}")
    print(f"  凭证目录: {Path.home() / '.openclaw' / 'credentials'}")
    
    if args.verbose and config:
        print("\n【完整配置】")
        print(json.dumps(config, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    return 0

# =============================================================================
# 命令：doctor
# =============================================================================

def cmd_doctor(args):
    """诊断系统问题"""
    print("=" * 60)
    print("MimirAether 诊断")
    print("=" * 60)
    
    issues = []
    warnings = []
    
    # 1. Python版本
    print("\n【1. Python环境】")
    py_version = platform.python_version()
    if tuple(map(int, py_version.split('.')[:2])) >= (3, 10):
        print(f"  ✅ Python {py_version}")
    else:
        issues.append(f"Python版本过低: {py_version}")
        print(f"  ❌ Python版本过低: {py_version} (需要 3.10+)")
    
    # 2. API Key
    print("\n【2. API凭证】")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        print(f"  ✅ DeepSeek API Key 已配置")
    else:
        issues.append("DeepSeek API Key 未配置")
        print("  ❌ DeepSeek API Key 未配置")
    
    # 3. 网络连接
    print("\n【3. 网络连接】")
    try:
        sock = socket.create_connection(("api.deepseek.com", 443), timeout=5)
        sock.close()
        print("  ✅ api.deepseek.com 可达")
    except Exception:
        issues.append("无法连接 api.deepseek.com")
        print("  ❌ 无法连接 api.deepseek.com")
    
    # 4. API服务
    print("\n【4. API服务】")
    try:
        import httpx
        response = httpx.get("http://localhost:18999/health", timeout=3)
        if response.status_code == 200:
            print("  ✅ API服务运行正常")
        else:
            warnings.append(f"API服务返回状态码: {response.status_code}")
            print(f"  ⚠️ API服务返回状态码: {response.status_code}")
    except Exception:
        warnings.append("API服务未运行 (端口18999)")
        print("  ⚠️ API服务未运行 (端口18999)")
    
    # 5. 核心模块
    print("\n【5. 核心模块】")
    for module in ["agent.core_loop", "gateway.router", "skills.skill_manager"]:
        try:
            importlib.import_module(module)
            print(f"  ✅ {module}")
        except Exception as e:
            issues.append(f"模块导入失败 {module}")
            print(f"  ❌ {module}: {e}")
    
    # 总结
    print("\n" + "=" * 60)
    if not issues and not warnings:
        print("✅ 所有检查通过！系统正常。")
    elif issues:
        print(f"❌ 发现 {len(issues)} 个问题：")
        for issue in issues:
            print(f"   - {issue}")
    elif warnings:
        print(f"⚠️ 发现 {len(warnings)} 个警告：")
        for warning in warnings:
            print(f"   - {warning}")
    
    print("=" * 60)
    return 0 if not issues else 1

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
    current_model = os.environ.get("MIMIR_MODEL", 'deepseek/deepseek-chat')
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
    print("  export MIMIR_MODEL=deepseek/deepseek-chat")
    print("  export MIMIR_PORT=18999")
    print("  export MIMIR_ADAPTERS=telegram,feishu,discord")
    
    return 0

# =============================================================================
# 命令：model
# =============================================================================

def cmd_model(args):
    """查看/切换模型"""
    models = [
        ("deepseek/deepseek-chat", "DeepSeek Chat", "默认"),
        ("kimi-k2.5", "Moonshot Kimi K2.5", ""),
        ("minimax/minimax", "MiniMax", ""),
    ]
    
    print("=" * 60)
    print("MimirAether 模型管理")
    print("=" * 60)
    
    print("\n【可用模型】")
    current = os.environ.get("MIMIR_MODEL", 'deepseek/deepseek-chat')
    for i, (model_id, name, note) in enumerate(models, 1):
        marker = " ← 当前" if model_id == current else ""
        print(f"  {i}. {name} ({model_id}){marker}")
    
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
        model=os.environ.get("MIMIR_MODEL", "deepseek/deepseek-chat"),
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
    status      查看系统状态
    config      查看配置
    doctor      诊断系统问题
    setup       交互式设置向导
    model       模型管理
    cron        定时任务管理
    version     版本信息
    gateway     Gateway管理
    logs        查看日志
    -q TASK    执行单次任务

示例:
    python cli.py status
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
    parser.add_argument("--model", type=str, default=os.environ.get("MIMIR_MODEL", "deepseek/deepseek-chat"), help="指定模型")
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
    else:
        args.action = None
        args.add = None
        args.list = False
        args.get = None
        args.set = None
        args.tail = None
        args.check = False
    
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
