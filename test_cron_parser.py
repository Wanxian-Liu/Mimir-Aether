#!/usr/bin/env python3
"""测试cron表达式解析功能"""
import sys
import os
import time

# 添加mimicore到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mimicore.scheduler.jobs import parse_cron_next_run, HAS_CRONITER

def test_cron_parsing():
    """测试cron表达式解析"""
    print("=== Cron表达式解析测试 ===")
    print(f"croniter库可用: {HAS_CRONITER}")
    
    if not HAS_CRONITER:
        print("警告: croniter库未安装，将使用24小时回退逻辑")
        print("请安装: pip install croniter")
    
    # 测试时间点
    test_time = time.time()
    print(f"\n测试基准时间: {time.ctime(test_time)}")
    
    # 测试不同的cron表达式
    test_crons = [
        ("*/5 * * * *", "每5分钟"),
        ("0 * * * *", "每小时整点"),
        ("0 4 * * *", "每天凌晨4点"),
        ("0 9 * * 1-5", "工作日早上9点"),
        ("0 0 1 * *", "每月1号凌晨"),
        ("0 12 * * 0", "每周日中午12点"),
    ]
    
    for cron_expr, description in test_crons:
        print(f"\n表达式: {cron_expr} ({description})")
        try:
            next_run = parse_cron_next_run(cron_expr, test_time)
            next_run_str = time.ctime(next_run)
            print(f"下次执行时间: {next_run_str}")
            
            # 计算距离现在的时间差
            delta = next_run - test_time
            hours = delta / 3600
            print(f"距离现在: {delta:.0f}秒 ({hours:.2f}小时)")
        except Exception as e:
            print(f"错误: {e}")
    
    # 测试get_due_jobs函数
    print("\n=== 测试get_due_jobs函数 ===")
    
    # 创建测试任务
    test_jobs = [
        {
            "id": "test_job_1",
            "name": "测试任务1 - 每5分钟",
            "cron": "*/5 * * * *",
            "enabled": True,
            "next_run": 0,  # 立即到期
            "last_run": 0
        },
        {
            "id": "test_job_2",
            "name": "测试任务2 - 每天4点",
            "cron": "0 4 * * *",
            "enabled": True,
            "next_run": test_time + 3600,  # 1小时后
            "last_run": test_time - 86400  # 昨天
        },
        {
            "id": "test_job_3",
            "name": "测试任务3 - 禁用",
            "cron": "*/10 * * * *",
            "enabled": False,
            "next_run": 0,
            "last_run": 0
        }
    ]
    
    # 保存测试任务
    from mimicore.scheduler.jobs import save_jobs, get_due_jobs
    save_jobs(test_jobs)
    
    # 获取到期任务
    due_jobs = get_due_jobs()
    print(f"到期任务数量: {len(due_jobs)}")
    for job in due_jobs:
        print(f"  - {job['name']} (ID: {job['id']})")
    
    # 清理测试文件
    jobs_file = os.path.expanduser("~/.mimiraether/cron/jobs.json")
    if os.path.exists(jobs_file):
        os.remove(jobs_file)
        print(f"\n清理测试文件: {jobs_file}")

if __name__ == "__main__":
    test_cron_parsing()