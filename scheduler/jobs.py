"""
Cron job storage and management for MimirAether
"""
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

MIMIRAETHER_DIR = Path.home() / ".mimiraether"
CRON_DIR = MIMIRAETHER_DIR / "cron"
JOBS_FILE = CRON_DIR / "jobs.json"

# 检查croniter库是否可用
try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

def ensure_dirs():
    """确保目录存在"""
    CRON_DIR.mkdir(parents=True, exist_ok=True)

def load_jobs() -> List[Dict]:
    """加载所有任务"""
    ensure_dirs()
    if not JOBS_FILE.exists():
        return []
    try:
        with open(JOBS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_jobs(jobs: List[Dict]):
    """保存任务列表"""
    ensure_dirs()
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)

def parse_cron_next_run(cron_expr, from_time=None):
    """解析cron表达式，返回下次执行时间戳"""
    if not HAS_CRONITER:
        # 回退到简单24小时
        return (from_time or time.time()) + 86400
    
    if from_time is None:
        from_time = time.time()
    cron = croniter(cron_expr, from_time)
    return cron.get_next()

def get_due_jobs() -> List[Dict]:
    """获取到期的任务"""
    jobs = load_jobs()
    now = time.time()
    due_jobs = []
    
    for job in jobs:
        if not job.get("enabled", True):
            continue
            
        # 检查任务是否到期
        if job.get("next_run", 0) <= now:
            due_jobs.append(job)
        # 如果任务有cron表达式，检查是否应该执行
        elif "cron" in job and HAS_CRONITER:
            try:
                cron_expr = job["cron"]
                cron = croniter(cron_expr, now)
                next_run = cron.get_prev()  # 获取上次应该执行的时间
                # 如果上次应该执行的时间在当前时间之前，说明任务应该执行
                if next_run <= now:
                    due_jobs.append(job)
            except Exception as e:
                print(f"Error parsing cron expression {job.get('cron')}: {e}")
                # 如果cron解析失败，使用next_run字段
                if job.get("next_run", 0) <= now:
                    due_jobs.append(job)
    
    return due_jobs

def mark_job_run(job_id: str, next_run: Optional[float] = None):
    """标记任务已执行"""
    jobs = load_jobs()
    for job in jobs:
        if job["id"] == job_id:
            job["last_run"] = time.time()
            if next_run:
                job["next_run"] = next_run
            elif "cron" in job:
                # 如果有cron表达式，计算下次执行时间
                try:
                    job["next_run"] = parse_cron_next_run(job["cron"], job["last_run"])
                except Exception as e:
                    print(f"Error calculating next run for job {job_id}: {e}")
                    # 回退到24小时后
                    job["next_run"] = job["last_run"] + 86400
            else:
                # 没有cron表达式，使用默认的24小时间隔
                job["next_run"] = job["last_run"] + 86400
            break
    save_jobs(jobs)