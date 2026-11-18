"""
Cron job storage and management for MimirAether
"""
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime
from threading import RLock

from mimir_constants import get_cron_jobs_lock_path, get_mimir_home

MIMIRAETHER_DIR = get_mimir_home()
CRON_DIR = MIMIRAETHER_DIR / "cron"
JOBS_FILE = CRON_DIR / "jobs.json"

# ============================================================================
# T91 / B3-R1+R2 写路径加固（2026-11-18 全面审计 C 节）：跨进程单写窗口 +
# 原子替换 + 损坏隔离。
# ----------------------------------------------------------------------------
# 互指：本模块与 cron/jobs.py 是**同一运行时文件** ``<home>/cron/jobs.json``
# 的两套存储实现，字段语义不同（本模块 next_run/last_run 为 float epoch；
# cron/jobs.py 为 ISO 串 + next_run_at/repeat），消费者各读自家字段 ⇒
# **保形不保合**：不合一代码，靠 mimir_constants.get_cron_jobs_lock_path()
# **同一把旁车锁文件**互斥（锁路径单源 ⇒ 两实现不可能漂移到不同锁）。
# 手法先例：旁车锁 = agent/persistent_store.py（ADR-001 方案 C，flock 锁旁车
# 文件不锁目标件）；原子写 = scripts/state_engine.py::_atomic_write_text
# （tmp→flush→fsync→os.replace）；损坏隔离 = .corrupt-<ts> 改名留盘。
# ============================================================================
_WRITE_LOCK_FILE = get_cron_jobs_lock_path()
_write_lock = RLock()
_write_depth = 0

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None


@contextmanager
def write_window():
    """跨进程单写窗口：同线程可重入 · 同进程跨线程串行 · 跨进程 flock。

    与 cron/jobs.write_window 同族但独立实现，锁的是同一旁车文件 ⇒ 跨实现
    互斥成立。load→modify→save 必须整体持窗（只锁 save 挡不住丢更新）。
    ⚠ 勿与 ``cron/jobs.write_window`` 嵌套（同线程双 fd flock 同一锁文件
    会自锁）——现仓无此调用路径，新增调用前先核对。
    """
    global _write_depth
    with _write_lock:
        lock_fh = None
        if _write_depth == 0:
            _WRITE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            fh = open(_WRITE_LOCK_FILE, "a+")
            try:
                if _fcntl is not None:
                    _fcntl.flock(fh, _fcntl.LOCK_EX)
            except BaseException:
                fh.close()
                raise
            lock_fh = fh
            _write_depth = 1
        else:
            _write_depth += 1
        try:
            yield
        finally:
            _write_depth -= 1
            if _write_depth == 0 and lock_fh is not None:
                try:
                    if _fcntl is not None:
                        _fcntl.flock(lock_fh, _fcntl.LOCK_UN)
                finally:
                    lock_fh.close()


def _atomic_write_json(path: Path, text: str) -> None:
    """tmp→flush→fsync→os.replace（先例 scripts/state_engine.py::_atomic_write_text）。"""
    d = path.parent
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{path.name}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _quarantine_corrupt(path: Path) -> None:
    """损坏件隔离改名 ``.corrupt-<ts>``（留盘可恢复，绝不就地清零）。"""
    target = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%dT%H%M%S%f')}")
    try:
        os.replace(path, target)
    except OSError:
        pass

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
    """加载所有任务

    T91/B3-R2：损坏件先改名 ``.corrupt-<ts>`` 留盘再返 ``[]``（旧实现裸
    except 吞掉损坏信号 → 下次 mark_job_run 回写 = 全部任务静默清零）；
    OSError 出声上抛（存储不可用不许静默当空）。
    """
    with write_window():
        ensure_dirs()
        if not JOBS_FILE.exists():
            return []
        try:
            text = JOBS_FILE.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            _quarantine_corrupt(JOBS_FILE)
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            _quarantine_corrupt(JOBS_FILE)
            return []
        # cron/jobs.py wraps jobs in {"jobs": [...]} format
        if isinstance(data, dict) and "jobs" in data:
            return data["jobs"]
        # scheduler/jobs.py expects a flat list
        if isinstance(data, list):
            return data
        return []

def save_jobs(jobs: List[Dict]):
    """保存任务列表

    ⚠ 必须写 ``{"jobs": [...]}`` 字典形（与 cron/jobs.py 一致）——曾写扁平 list：
    本模块能被生产文件 ``{"jobs": [...]}`` 读进来（load_jobs 双形容错），
    回写却把它毁成扁平 ⇒ 「读容忍 · 写破坏」。load_jobs 双形都能读，故本改动往返安全。

    T91/B3-R2：直写 ``open("w")`` 改原子替换（tmp→flush→fsync→os.replace）
    ——撕裂写曾与「损坏即全清」链成对出现；读者/崩溃都不再见到半份。
    """
    with write_window():
        ensure_dirs()
        _atomic_write_json(JOBS_FILE, json.dumps({"jobs": jobs}, indent=2, ensure_ascii=False))

def _get_cron_expr(job: Dict) -> Optional[str]:
    """从不同格式的任务字段中提取 cron 表达式"""
    # 格式1: {"schedule": {"type": "cron", "value": "..."}}
    sch = job.get("schedule", {})
    if isinstance(sch, dict) and sch.get("type") == "cron":
        return sch.get("value")
    # 格式2: {"schedule_display": "..."}
    if job.get("schedule_display"):
        return job["schedule_display"]
    # 格式3: {"cron": "..."}
    if job.get("cron"):
        return job["cron"]
    return None


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
        elif HAS_CRONITER:
            cron_expr = _get_cron_expr(job)
            if cron_expr:
                try:
                    cron = croniter(cron_expr, now)
                    next_run = cron.get_prev()  # 获取上次应该执行的时间
                    # 如果上次应该执行的时间在当前时间之前，说明任务应该执行
                    if next_run <= now:
                        due_jobs.append(job)
                except Exception as e:
                    print(f"Error parsing cron expression {cron_expr}: {e}")
                    # 如果cron解析失败，使用next_run字段
                    if job.get("next_run", 0) <= now:
                        due_jobs.append(job)
    
    return due_jobs

def mark_job_run(job_id: str, next_run: Optional[float] = None):
    """标记任务已执行"""
    with write_window():  # RMW 整体持窗（T91/B3-R1：防并发丢更新）
        jobs = load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job["last_run"] = time.time()
                if next_run:
                    job["next_run"] = next_run
                else:
                    cron_expr = _get_cron_expr(job)
                    if cron_expr:
                        # 如果有cron表达式，计算下次执行时间
                        try:
                            job["next_run"] = parse_cron_next_run(cron_expr, job["last_run"])
                        except Exception as e:
                            print(f"Error calculating next run for job {job_id}: {e}")
                            # 回退到24小时后
                            job["next_run"] = job["last_run"] + 86400
                    else:
                        # 没有cron表达式，使用默认的24小时间隔
                        job["next_run"] = job["last_run"] + 86400
                break
        save_jobs(jobs)