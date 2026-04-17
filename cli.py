#!/usr/bin/env python3
"""
MimirAether CLI - 命令行入口

类似Hermes的CLI，支持多种命令：
    python cli.py                          # 交互模式
    python cli.py status                  # 查看状态
    python cli.py config                  # 查看配置
    python cli.py -q "你的任务"          # 单次任务模式
    python cli.py doctor                  # 诊断问题
    python cli.py gateway start           # 启动Gateway

Usage:
    python cli.py                          # 交互模式
    python cli.py status                   # 查看状态
    python cli.py config [--get KEY]       # 查看/设置配置
    python cli.py doctor                   # 诊断检查
    python cli.py gateway [start|stop]     # Gateway管理
    python cli.py -q "你的任务"           # 单次任务模式
    python cli.py --model deepseek/deepseek-chat  # 指定模型
"""

import argparse
import asyncio
import os
import sys
import json
import platform
import socket
from pathlib import Path

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
        print(f"  DeepSeek API Key: {'✅ 已配置 (' + deepseek_key[:8] + '...)' if len(deepseek_key) > 8 else '❌'}")
    else:
        print("  DeepSeek API Key: ❌ 未配置")
    
    minimax_key = os.environ.get("MINIMAX_API_KEY", "")
    if minimax_key:
        print(f"  MiniMax API Key: ✅ 已配置")
    else:
        print("  MiniMax API Key: ❌ 未配置")
    
    # Gateway状态
    print("\n【Gateway状态】")
    print(f"  运行状态: 检查中...")
    print(f"  API服务: http://localhost:18999")
    
    # 工具数
    print("\n【工具统计】")
    try:
        agent = MimirAetherAgent()
        tools = agent.tool_registry.list_tools()
        print(f"  内置工具: {len(tools)} 个")
        if args.verbose:
            for tool in tools[:10]:
                print(f"    - {tool}")
            if len(tools) > 10:
                print(f"    ... 还有 {len(tools) - 10} 个")
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
        # 获取特定配置
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
    
    # 打印所有配置
    print("=" * 60)
    print("MimirAether 配置")
    print("=" * 60)
    
    # 关键配置
    print("\n【模型配置】")
    print(f"  默认模型: {os.environ.get('MIMIR_MODEL', 'deepseek/deepseek-chat')}")
    print(f"  API Base URL: {os.environ.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com')}")
    
    print("\n【Gateway配置】")
    print(f"  端口: {os.environ.get('MIMIR_PORT', '18999')}")
    print(f"  适配器: {os.environ.get('MIMIR_ADAPTERS', 'telegram,feishu,discord')}")
    
    print("\n【路径配置】")
    print(f"  项目目录: {PROJECT_ROOT}")
    print(f"  凭证目录: {Path.home() / '.openclaw' / 'credentials'}")
    
    if args.verbose:
        print("\n【完整配置】")
        print(json.dumps(config, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    return 0

# =============================================================================
# 命令：doctor
# =============================================================================

def cmd_doctor(args):
    """诊断系统问题"""
    import httpx
    
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
        import socket
        socket.create_connection(("api.deepseek.com", 443), timeout=5)
        print("  ✅ api.deepseek.com 可达")
    except Exception as e:
        issues.append(f"无法连接 api.deepseek.com: {e}")
        print(f"  ❌ 无法连接 api.deepseek.com")
    
    # 4. API服务
    print("\n【4. API服务】")
    try:
        response = httpx.get("http://localhost:18999/health", timeout=3)
        if response.status_code == 200:
            print("  ✅ API服务运行正常")
        else:
            warnings.append(f"API服务返回状态码: {response.status_code}")
            print(f"  ⚠️ API服务返回状态码: {response.status_code}")
    except Exception as e:
        warnings.append(f"API服务未运行: {e}")
        print(f"  ⚠️ API服务未运行 (端口18999)")
    
    # 5. 模块导入
    print("\n【5. 核心模块】")
    modules_ok = True
    for module in ["agent.core_loop", "gateway.router", "skills.skill_manager"]:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            modules_ok = False
            issues.append(f"模块导入失败 {module}: {e}")
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
# 命令：gateway
# =============================================================================

def cmd_gateway(args):
    """Gateway管理"""
    if args.action == "start":
        print("启动Gateway...")
        print("使用: python gateway/run.py")
        return 0
    elif args.action == "stop":
        print("停止Gateway...")
        return 0
    elif args.action == "status":
        print("Gateway状态:")
        print("  运行中: 检查端口18999...")
        return 0
    else:
        print(f"未知操作: {args.action}")
        return 1

# =============================================================================
# 交互模式
# =============================================================================

async def run_interactive():
    """运行交互模式"""
    from agent.core_loop import MimirAetherAgent
    
    print("=" * 60)
    print("MimirAether CLI - 交互模式")
    print("=" * 60)
    print("提示: 输入任务后按回车，输 'quit' 或 'exit' 退出\n")
    
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
    gateway     Gateway管理
    -q TASK    执行单次任务

示例:
    python cli.py status
    python cli.py config --get model
    python cli.py doctor
    python cli.py -q "改进gdi_scorer"
        """
    )
    
    parser.add_argument("command", nargs="?", help="命令 (status/config/doctor/gateway)")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="命令参数")
    parser.add_argument("-q", "--query", type=str, help="单次任务模式")
    parser.add_argument("--model", type=str, default=os.environ.get("MIMIR_MODEL", "deepseek/deepseek-chat"), help="指定模型")
    parser.add_argument("--max-iterations", type=int, default=90, help="最大迭代次数")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 处理命令
    if args.command == "status":
        return cmd_status(args)
    elif args.command == "config":
        args.get = None
        for i, arg in enumerate(args.args):
            if arg == "--get" and i + 1 < len(args.args):
                args.get = args.args[i + 1]
        return cmd_config(args)
    elif args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "gateway":
        action = args.args[0] if args.args else "status"
        args.action = action
        return cmd_gateway(args)
    elif args.query:
        return asyncio.run(run_task(args.query, args.model, args.max_iterations, args.verbose))
    else:
        # 交互模式
        return asyncio.run(run_interactive())

if __name__ == "__main__":
    sys.exit(main())
