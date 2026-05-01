# =============================================================================
# 命令：cron - 定时任务管理
# =============================================================================

def cmd_cron(args):
    """定时任务管理 - 完整实现"""
    from cron.jobs import (
        list_jobs, get_job, create_job, remove_job,
        pause_job, resume_job, trigger_job, parse_schedule
    )
    
    subcmd = args.cron_action or "list"
    
    if subcmd == "list":
        return cron_list(args)
    elif subcmd == "create" or subcmd == "add":
        return cron_create(args)
    elif subcmd == "delete" or subcmd == "remove":
        return cron_delete(args)
    elif subcmd == "pause":
        return cron_pause(args)
    elif subcmd == "resume":
        return cron_resume(args)
    elif subcmd == "trigger":
        return cron_trigger(args)
    elif subcmd == "info":
        return cron_info(args)
    elif subcmd == "run":
        return cron_run(args)
    else:
        print(f"未知子命令: {subcmd}")
        print("\n【Cron子命令】")
        print("  cron list              - 列出所有任务")
        print("  cron create <prompt> <schedule>  - 创建任务")
        print("  cron delete <id>       - 删除任务")
        print("  cron pause <id>        - 暂停任务")
        print("  cron resume <id>       - 恢复任务")
        print("  cron trigger <id>      - 手动触发任务")
        print("  cron info <id>         - 查看任务详情")
        print("  cron run               - 运行调度器")
        print("\n【Schedule格式】")
        print("  30m, 2h, 1d           - 一次性延迟")
        print("  every 30m, every 2h   - 循环间隔")
        print("  0 9 * * *             - Cron表达式")
        print("  2026-05-01T09:00      - 指定时间")
        return 1

def cron_list(args):
    """列出所有定时任务"""
    jobs = list_jobs(include_disabled=args.verbose)
    
    print("=" * 60)
    print("MimirAether 定时任务")
    print("=" * 60)
    
    if not jobs:
        print("\n  暂无定时任务")
        print("\n  创建第一个任务:")
        print("    python cli.py cron create \"任务描述\" \"every 1h\"")
        print("\n" + "=" * 60)
        return 0
    
    print(f"\n  共 {len(jobs)} 个任务:\n")
    print(f"  {'ID':<14} {'名称':<20} {'计划':<15} {'状态':<10} {'下次运行'}")
    print("  " + "-" * 70)
    
    for job in jobs:
        sid = job.get("id", "?")[:12]
        name = job.get("name", "")[:18]
        schedule = job.get("schedule_display", "")[:13]
        enabled = "运行中" if job.get("enabled", True) else "已暂停"
        next_run = job.get("next_run_at", "N/A")
        if next_run and next_run != "N/A":
            try:
                dt = datetime.fromisoformat(next_run)
                next_run = dt.strftime("%m-%d %H:%M")
            except:
                pass
        
        status_icon = "✅" if job.get("enabled", True) else "⏸️"
        print(f"  {status_icon} {sid:<12} {name:<20} {schedule:<15} {enabled:<8} {next_run}")
    
    print("\n" + "=" * 60)
    if args.verbose:
        print("\n  详细模式: 显示所有任务 (包括已暂停)")
    return 0

def cron_create(args):
    """创建定时任务"""
    from cron.jobs import create_job
    
    prompt = args.cron_args[0] if args.cron_args else args.cron_prompt
    schedule = args.cron_args[1] if len(args.cron_args) > 1 else args.cron_schedule
    
    if not prompt:
        print("  ❌ 错误: 需要提供任务描述")
        print("  用法: python cli.py cron create \"任务描述\" \"every 1h\"")
        return 1
    
    if not schedule:
        print("  ❌ 错误: 需要提供执行计划")
        print("  用法: python cli.py cron create \"任务描述\" \"every 1h\"")
        return 1
    
    try:
        # 验证schedule
        parse_schedule(schedule)
        
        # 创建任务
        job = create_job(
            prompt=prompt,
            schedule=schedule,
            name=args.cron_name,
            repeat=args.cron_repeat,
            skill=args.cron_skill,
            model=args.cron_model,
            deliver=args.cron_deliver
        )
        
        print("=" * 60)
        print("  ✅ 定时任务已创建")
        print("=" * 60)
        print(f"  ID:       {job['id']}")
        print(f"  名称:     {job['name']}")
        print(f"  计划:     {job['schedule_display']}")
        print(f"  下次运行: {job.get('next_run_at', 'N/A')}")
        
        if job.get("skills"):
            print(f"  技能:     {', '.join(job['skills'])}")
        if job.get("model"):
            print(f"  模型:     {job['model']}")
        if job.get("repeat", {}).get("times"):
            print(f"  重复:     {job['repeat']['times']} 次")
        
        print("\n  手动触发测试:")
        print(f"    python cli.py cron trigger {job['id']}")
        print("\n  查看列表:")
        print(f"    python cli.py cron list")
        print("=" * 60)
        return 0
        
    except ValueError as e:
        print(f"  ❌ 创建失败: {e}")
        return 1
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return 1

def cron_delete(args):
    """删除定时任务"""
    from cron.jobs import get_job, remove_job
    
    if not args.cron_args:
        print("  ❌ 错误: 需要提供任务ID")
        print("  用法: python cli.py cron delete <job_id>")
        return 1
    
    job_id = args.cron_args[0]
    job = get_job(job_id)
    
    if not job:
        print(f"  ❌ 未找到任务: {job_id}")
        return 1
    
    name = job.get("name", job_id)
    
    if args.cron_force or input(f"  确认删除任务 '{name}'? (y/N): ").lower() == 'y':
        if remove_job(job_id):
            print(f"  ✅ 任务已删除: {name}")
            return 0
        else:
            print(f"  ❌ 删除失败")
            return 1
    else:
        print("  取消删除")
        return 0

def cron_pause(args):
    """暂停定时任务"""
    from cron.jobs import get_job, pause_job
    
    if not args.cron_args:
        print("  ❌ 错误: 需要提供任务ID")
        return 1
    
    job_id = args.cron_args[0]
    job = pause_job(job_id, args.cron_reason)
    
    if job:
        print(f"  ✅ 任务已暂停: {job.get('name', job_id)}")
        return 0
    else:
        print(f"  ❌ 未找到任务: {job_id}")
        return 1

def cron_resume(args):
    """恢复定时任务"""
    from cron.jobs import get_job, resume_job
    
    if not args.cron_args:
        print("  ❌ 错误: 需要提供任务ID")
        return 1
    
    job_id = args.cron_args[0]
    job = resume_job(job_id)
    
    if job:
        print(f"  ✅ 任务已恢复: {job.get('name', job_id)}")
        print(f"  下次运行: {job.get('next_run_at', 'N/A')}")
        return 0
    else:
        print(f"  ❌ 未找到任务: {job_id}")
        return 1

def cron_trigger(args):
    """手动触发定时任务"""
    from cron.jobs import get_job, trigger_job, get_due_jobs
    
    if not args.cron_args:
        # 触发所有到期任务
        due = get_due_jobs()
        print(f"  触发所有到期任务 ({len(due)} 个)")
        for job in due:
            trigger_job(job["id"])
            print(f"    ✅ {job.get('name', job['id'])}")
        return 0
    
    job_id = args.cron_args[0]
    job = trigger_job(job_id)
    
    if job:
        print(f"  ✅ 任务已触发: {job.get('name', job_id)}")
        return 0
    else:
        print(f"  ❌ 未找到任务: {job_id}")
        return 1

def cron_info(args):
    """查看任务详情"""
    from cron.jobs import get_job
    
    if not args.cron_args:
        print("  ❌ 错误: 需要提供任务ID")
        return 1
    
    job_id = args.cron_args[0]
    job = get_job(job_id)
    
    if not job:
        print(f"  ❌ 未找到任务: {job_id}")
        return 1
    
    print("=" * 60)
    print(f"  任务详情: {job.get('name', job_id)}")
    print("=" * 60)
    print(f"  ID:           {job.get('id')}")
    print(f"  状态:         {'运行中' if job.get('enabled') else '已暂停'}")
    print(f"  计划:         {job.get('schedule_display')}")
    print(f"  创建时间:     {job.get('created_at', 'N/A')}")
    print(f"  上次运行:     {job.get('last_run_at', '从未')}")
    print(f"  下次运行:     {job.get('next_run_at', 'N/A')}")
    print(f"  上次状态:     {job.get('last_status', 'N/A')}")
    print(f"  上次错误:     {job.get('last_error') or '无'}")
    print(f"  投递方式:     {job.get('deliver', 'local')}")
    
    repeat = job.get("repeat", {})
    times = repeat.get("times")
    completed = repeat.get("completed", 0)
    if times:
        print(f"  重复:         {completed}/{times} 次")
    else:
        print(f"  重复:         无限 ({completed} 次已完成)")
    
    if job.get("skills"):
        print(f"  技能:         {', '.join(job['skills'])}")
    if job.get("model"):
        print(f"  模型:         {job['model']}")
    
    print(f"\n  任务描述:")
    print(f"  {job.get('prompt', '')[:100]}...")
    print("=" * 60)
    return 0

def cron_run(args):
    """运行调度器"""
    from cron.scheduler import start_scheduler
    
    interval = args.cron_interval or 60
    print("=" * 60)
    print("  启动定时任务调度器")
    print(f"  检查间隔: {interval} 秒")
    print("  按 Ctrl+C 停止")
    print("=" * 60)
    
    start_scheduler(interval=interval)
    return 0

