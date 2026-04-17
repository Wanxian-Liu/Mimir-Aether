#!/usr/bin/env python3
"""
MimirAether CLI - 命令行入口

类似Hermes的CLI：
    python cli.py -q "你的任务"

Usage:
    python cli.py                          # 交互模式
    python cli.py -q "你的任务"            # 单次任务模式
    python cli.py --chat "你的任务"        # 交互聊天模式
    python cli.py --model deepseek/deepseek-chat  # 指定模型
    python cli.py --verbose                # 详细输出
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
MIMIR_AETHER_PATH = Path('/home/rayliu/.openclaw/projects/MimirAether')
sys.path.insert(0, str(MIMIR_AETHER_PATH))


def main():
    parser = argparse.ArgumentParser(
        description="MimirAether CLI - 自主Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python cli.py -q "改进MimirCore的gdi_scorer"
    python cli.py -q "审计sindris skill"
    python cli.py --chat "帮我写一个Hello World"
    python cli.py --model anthropic/claude-3-5-sonnet  # 指定模型
        """
    )
    
    parser.add_argument("-q", "--query", type=str, help="单次任务模式")
    parser.add_argument("--chat", type=str, dest="chat_mode", help="交互聊天模式")
    parser.add_argument("--model", type=str, default="kimi-k2.5", help="指定模型(Moonshot Kimi K2.5)")
    parser.add_argument("--max-iterations", type=int, default=30, help="最大迭代次数")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--save-trajectories", action="store_true", help="保存轨迹")
    
    args = parser.parse_args()
    
    # 如果有query或chat_mode，直接执行单次任务
    if args.query or args.chat_mode:
        task = args.query or args.chat_mode
        result = asyncio.run(run_task(
            task=task,
            model=args.model,
            max_iterations=args.max_iterations,
            verbose=args.verbose,
            save_trajectories=args.save_trajectories
        ))
        print("\n" + "=" * 70)
        print("【MimirAether执行结果】")
        print("=" * 70)
        print(result)
        return 0
    
    # 交互模式
    print("=" * 70)
    print("MimirAether CLI - 交互模式")
    print("=" * 70)
    print("提示: 输入任务后按回车，输 'quit' 或 'exit' 退出\n")
    
    agent = asyncio.run(init_agent(
        model=args.model,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
        save_trajectories=args.save_trajectories
    ))
    
    while True:
        try:
            user_input = input("\n👤 你: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("再见!")
                break
            if not user_input:
                continue
            
            print("\n🤖 MimirAether思考中...")
            result = asyncio.run(agent.run_conversation(user_input))
            if isinstance(result, dict):
                result_text = result.get("response", "")
            else:
                result_text = str(result)
            print(f"\n🤖 MimirAether: {result_text}")
            
        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


async def init_agent(model: str, max_iterations: int, verbose: bool, save_trajectories: bool):
    """初始化Agent"""
    from agent.core_loop import MimirAetherAgent
    
    agent = MimirAetherAgent(
        model=model,
        max_iterations=max_iterations,
        platform="cli",
        save_trajectories=save_trajectories,
    )
    
    if verbose:
        print(f"✅ Agent初始化完成")
        print(f"   模型: {model}")
        print(f"   最大迭代: {max_iterations}")
        print(f"   工具数: {len(agent.tool_registry.list_tools())}")
    
    return agent


async def run_task(task: str, model: str, max_iterations: int, verbose: bool, save_trajectories: bool) -> str:
    """执行单个任务"""
    print("=" * 70)
    print("🎯 MIMIRAETHER - 任务执行模式")
    print("=" * 70)
    print(f"任务: {task}")
    print(f"模型: {model}")
    print(f"最大迭代: {max_iterations}")
    print("=" * 70)
    
    agent = await init_agent(model, max_iterations, verbose, save_trajectories)
    
    if verbose:
        print(f"\n开始执行任务...")
    
    result = await agent.run_conversation(task)
    return result


if __name__ == "__main__":
    sys.exit(main())
