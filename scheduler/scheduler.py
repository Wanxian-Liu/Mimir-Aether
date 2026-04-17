"""
MimirAether调度器
"""
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path
import os
import json
from .jobs import get_due_jobs, mark_job_run

logger = logging.getLogger(__name__)

# 文件锁路径
_LOCK_FILE = Path.home() / ".mimiraether" / "cron" / ".tick.lock"

# 尝试导入fcntl（Unix系统）
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    fcntl = None
    HAS_FCNTL = False

def run_job(job):
    """执行任务命令"""
    command = job.get('command', '')
    if not command:
        return {'error': 'No command'}
    
    try:
        # 设置工作目录为项目根目录
        cwd = Path("/home/rayliu/.openclaw/projects/MimirAether")
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd
        )
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {'error': 'Timeout (120s)'}
    except Exception as e:
        return {'error': str(e)}

class Scheduler:
    def __init__(self, tick_interval: int = 60):
        self.tick_interval = tick_interval
        self.running = False
        
    def _acquire_lock(self):
        """获取文件锁"""
        try:
            # 确保锁文件目录存在
            _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # 打开锁文件
            lock_fd = open(_LOCK_FILE, "w")
            
            if HAS_FCNTL:
                # Unix系统使用fcntl
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return lock_fd
                except (IOError, BlockingIOError):
                    # 锁被占用
                    lock_fd.close()
                    return None
            else:
                # Windows系统使用msvcrt
                try:
                    import msvcrt
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LOCK_NB, 1)
                    return lock_fd
                except (ImportError, OSError):
                    # msvcrt不可用或锁被占用
                    lock_fd.close()
                    return None
                    
        except Exception as e:
            logger.warning(f"获取文件锁失败: {e}")
            return None
    
    def _release_lock(self, lock_fd):
        """释放文件锁"""
        try:
            if lock_fd:
                if HAS_FCNTL:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                else:
                    try:
                        import msvcrt
                        msvcrt.locking(lock_fd.fileno(), msvcrt.LOCK_UN, 1)
                    except ImportError:
                        pass
                lock_fd.close()
                # 删除锁文件
                if _LOCK_FILE.exists():
                    _LOCK_FILE.unlink()
        except Exception as e:
            logger.warning(f"释放文件锁失败: {e}")
    
    def _save_job_result(self, job_id, result):
        """保存任务执行结果到output目录"""
        try:
            output_dir = Path("/home/rayliu/.openclaw/projects/MimirAether") / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"job_{job_id}_{timestamp}.json"
            filepath = output_dir / filename
            
            # 保存结果
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'job_id': job_id,
                    'timestamp': timestamp,
                    'result': result
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"任务结果已保存到: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存任务结果失败: {e}")
            return None
        
    def tick(self):
        """检查并执行到期任务"""
        # 获取文件锁
        lock_fd = self._acquire_lock()
        if not lock_fd:
            logger.info("跳过本次tick（锁被占用）")
            return
            
        try:
            due_jobs = get_due_jobs()
            for job in due_jobs:
                logger.info(f"执行任务: {job['name']}")
                
                # 执行真正的任务命令
                result = run_job(job)
                
                # 保存执行结果
                self._save_job_result(job['id'], result)
                
                # 记录执行结果
                if 'error' in result:
                    logger.error(f"任务执行失败: {job['name']} - {result['error']}")
                else:
                    logger.info(f"任务执行完成: {job['name']} - 返回码: {result['returncode']}")
                    if result['stdout']:
                        logger.debug(f"任务输出: {result['stdout'][:200]}...")
                    if result['stderr']:
                        logger.warning(f"任务错误: {result['stderr'][:200]}...")
                
                # 计算下次运行时间（简单的24小时循环）
                mark_job_run(job['id'], datetime.now().timestamp() + 86400)
        finally:
            # 确保释放锁
            self._release_lock(lock_fd)
            
    def run_continuous(self, max_iterations: int = None):
        """持续运行调度器"""
        self.running = True
        iteration = 0
        while self.running:
            self.tick()
            iteration += 1
            if max_iterations and iteration >= max_iterations:
                break
            time.sleep(self.tick_interval)
            
    def stop(self):
        """停止调度器"""
        self.running = False