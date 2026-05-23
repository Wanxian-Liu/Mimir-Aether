"""CLI task execution helpers (extracted from legacy ``cli.py`` · E-008)."""

from __future__ import annotations

from mimicore.config.model_defaults import get_model


async def run_interactive():
    """Run interactive chat in the terminal."""
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


async def run_task(
    task: str,
    model: str,
    max_iterations: int,
    verbose: bool,
    llm_backend=None,
    tool_backend=None,
    session_backend=None,
    session_db_factory=None,
    checkpoint_backend=None,
    kernel_overrides=None,
):
    """Execute a single task (``mimir chat -q`` / legacy ``cli.py -q``)."""
    from agent.core_loop import MimirAetherAgent

    print("=" * 60)
    print("🎯 MIMIRAETHER - 任务执行模式")
    print("=" * 60)
    print(f"任务: {task}")
    print(f"模型: {model}")
    print(f"最大迭代: {max_iterations}")
    print("=" * 60)

    kwargs = dict(
        model=model,
        max_iterations=max_iterations,
        platform="cli",
    )
    if kernel_overrides is not None:
        b = kernel_overrides
        if b.llm_backend is not None:
            kwargs["llm_backend"] = b.llm_backend
        if b.tool_backend is not None:
            kwargs["tool_backend"] = b.tool_backend
        if b.session_backend is not None:
            kwargs["session_backend"] = b.session_backend
        if b.session_db_factory is not None:
            kwargs["session_db_factory"] = b.session_db_factory
        if b.checkpoint_backend is not None:
            kwargs["checkpoint_backend"] = b.checkpoint_backend
    if llm_backend is not None:
        kwargs["llm_backend"] = llm_backend
    if tool_backend is not None:
        kwargs["tool_backend"] = tool_backend
    if session_backend is not None:
        kwargs["session_backend"] = session_backend
    if session_db_factory is not None:
        kwargs["session_db_factory"] = session_db_factory
    if checkpoint_backend is not None:
        kwargs["checkpoint_backend"] = checkpoint_backend

    agent = MimirAetherAgent(**kwargs)

    if verbose:
        print("\n开始执行任务...")

    result = await agent.run_conversation(task)

    print("\n" + "=" * 60)
    print("【执行结果】")
    print("=" * 60)
    print(result)

    return 0
