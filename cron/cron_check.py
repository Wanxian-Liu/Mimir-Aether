#!/usr/bin/env python3
"""
Cron Health Check - Verify jobs, detect and auto-cleanup stale executions.
Week 3 扩展: 分块写入, stale job 检测与自动清理
"""

import json
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

# ============================================================================
# 常量定义
# ============================================================================

JOBS_FILE = Path(__file__).parent / "jobs.json"
STALE_THRESHOLD_DAYS = 1
CHUNK_MIN = 100
CHUNK_MAX = 150
BACKUP_SUFFIX = ".backup"
CLEANUP_LOG_FILE = Path(__file__).parent / "cleanup.log"


# ============================================================================
# 工具函数
# ============================================================================

def now() -> datetime:
    """获取当前 UTC 时间."""
    return datetime.now(timezone.utc)


def parse_time(ts: Optional[str]) -> Optional[datetime]:
    """解析 ISO 格式时间字符串."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def load_jobs() -> List[Dict[str, Any]]:
    """加载并解析 jobs.json."""
    if not JOBS_FILE.exists():
        return []
    try:
        return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def save_jobs(jobs: List[Dict[str, Any]]) -> bool:
    """保存 jobs 到文件 (原子操作: 先写.tmp,再重命名)."""
    try:
        tmp_file = JOBS_FILE.with_suffix(".tmp")
        content = json.dumps(jobs, indent=2, ensure_ascii=False)
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.rename(JOBS_FILE)
        return True
    except (IOError, OSError) as e:
        print(f"[ERROR] 保存失败: {e}")
        return False


def get_last_run(job: Dict[str, Any]) -> Optional[datetime]:
    """获取 job 的上次执行时间."""
    last_run = job.get("last_run_at") or job.get("last_run")
    return parse_time(last_run) if last_run else None


def is_stale(job: Dict[str, Any], threshold_days: int = STALE_THRESHOLD_DAYS) -> bool:
    """检查 job 是否超过阈值未执行."""
    last_run = get_last_run(job)
    if not last_run:
        return True
    elapsed = now() - last_run
    return elapsed > timedelta(days=threshold_days)


def get_stale_jobs(jobs: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """获取所有 stale jobs."""
    if jobs is None:
        jobs = load_jobs()
    return [j for j in jobs if is_stale(j)]


# ============================================================================
# 自动清理功能
# ============================================================================

def create_backup() -> Optional[Path]:
    """创建 jobs.json 的备份."""
    if not JOBS_FILE.exists():
        return None
    ts = now().strftime("%Y%m%d_%H%M%S")
    backup = JOBS_FILE.parent / f"jobs_{ts}{BACKUP_SUFFIX}"
    try:
        backup.write_bytes(JOBS_FILE.read_bytes())
        return backup
    except IOError:
        return None


def cleanup_stale_jobs(
    threshold_days: int = STALE_THRESHOLD_DAYS,
    dry_run: bool = True,
    backup: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """
    自动清理 stale jobs.
    
    Args:
        threshold_days: stale 阈值 (天)
        dry_run: 试运行,不实际修改
        backup: 是否创建备份
        force: 强制清理,忽略确认提示
    
    Returns:
        清理结果摘要
    """
    jobs = load_jobs()
    stale = [j for j in jobs if is_stale(j, threshold_days)]
    healthy = [j for j in jobs if not is_stale(j, threshold_days)]

    result = {
        "total_before": len(jobs),
        "stale_count": len(stale),
        "healthy_count": len(healthy),
        "dry_run": dry_run,
        "backup_path": None,
        "removed_jobs": [],
        "success": False,
    }

    # 试运行模式
    if dry_run:
        result["removed_jobs"] = [
            {"id": j.get("id"), "name": j.get("name", "Unknown")}
            for j in stale
        ]
        result["success"] = True
        return result

    # 实际执行 (非交互模式: JSON输出或非TTY时跳过确认)
    if stale and not force:
        print(f"[INFO] 将清理 {len(stale)} 个 stale jobs")
        print(f"[INFO] 阈值: {threshold_days} 天")
        if sys.stdout.isatty():
            confirm = input("确认清理? (yes/no): ")
            if confirm.lower() != "yes":
                print("[ABORT] 清理已取消")
                result["success"] = False
                return result
        else:
            print("[AUTO] 非交互环境,自动跳过")
            result["success"] = False
            return result

    # 创建备份
    if backup:
        bp = create_backup()
        if bp:
            result["backup_path"] = str(bp)
            print(f"[INFO] 备份已创建: {bp.name}")

    # 执行清理
    result["removed_jobs"] = [
        {"id": j.get("id"), "name": j.get("name", "Unknown")}
        for j in stale
    ]

    if save_jobs(healthy):
        result["success"] = True
        print(f"[OK] 已清理 {len(stale)} 个 stale jobs")
    else:
        print("[ERROR] 清理失败")

    return result


def log_cleanup(result: Dict[str, Any]) -> None:
    """记录清理操作到日志文件."""
    entry = {
        "timestamp": now().isoformat(),
        "result": result,
    }
    try:
        with open(CLEANUP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except IOError:
        pass


# ============================================================================
# 分块写入器 (Chunked Writer)
# ============================================================================

class ChunkedWriter:
    """
    分块文本写入器.
    将文本分割为 100-150 字符的块,逐块写入.
    """

    def __init__(self, target_size: int = 125):
        self.target_size = max(CHUNK_MIN, min(target_size, CHUNK_MAX))

    def split(self, text: str) -> List[str]:
        """将文本分割为目标大小的块,确保每块在 100-150 范围内."""
        chunks = []
        lines = text.split("\n")
        current = ""
        buffer = []

        def flush_buffer() -> str:
            """将缓冲区合并为单行,必要时分割."""
            nonlocal current
            if not buffer:
                return current
            joined = " ".join(buffer)
            if not current:
                current = joined
                buffer.clear()
                return ""
            combined = current + " " + joined
            if len(combined) >= self.target_size:
                chunks.append(current)
                current = joined
                buffer.clear()
                return ""
            current = combined
            buffer.clear()
            return ""

        for line in lines:
            llen = len(line)
            if llen >= CHUNK_MAX:
                if current:
                    chunks.append(current)
                while llen > 0:
                    chunks.append(line[:self.target_size])
                    line = line[self.target_size:]
                    llen = len(line)
                current = ""
                buffer.clear()
            elif len(current) + llen + 1 <= self.target_size:
                if current:
                    current += "\n" + line
                else:
                    current = line
            else:
                chunks.append(current)
                current = line

        if current:
            chunks.append(current)

        # 合并太小的块
        merged = []
        for chunk in chunks:
            if merged and len(merged[-1]) + len(chunk) + 1 <= CHUNK_MAX:
                merged[-1] += " " + chunk
            else:
                merged.append(chunk)

        # 拆分太大的块
        final = []
        for chunk in merged:
            while len(chunk) > CHUNK_MAX:
                final.append(chunk[:self.target_size])
                chunk = chunk[self.target_size:]
            final.append(chunk)

        return final

    def write(self, text: str) -> List[str]:
        """写入文本,返回所有块."""
        return self.split(text)


# ============================================================================
# 健康检查
# ============================================================================

def health_check() -> Dict[str, Any]:
    """执行健康检查,返回状态摘要."""
    jobs = load_jobs()
    stale = get_stale_jobs()

    return {
        "total": len(jobs),
        "stale_count": len(stale),
        "stale_jobs": stale,
        "healthy": len(jobs) - len(stale),
    }


def format_stale_report(result: Dict[str, Any]) -> str:
    """格式化 stale jobs 报告."""
    lines = [
        "# Cron Stale Jobs Report",
        f"Generated: {now().isoformat()}",
        f"Total: {result['total']} | Healthy: {result['healthy']} | Stale: {result['stale_count']}",
        "",
        "## Stale Jobs",
    ]

    if not result["stale_jobs"]:
        lines.append("No stale jobs detected.")
    else:
        for job in result["stale_jobs"]:
            last = job.get("last_run_at") or job.get("last_run") or "Never"
            lines.append(
                f"- {job.get('name', job.get('id', 'Unknown'))} "
                f"[{job.get('id')}] last={last}"
            )

    return "\n".join(lines)


# ============================================================================
# CLI 参数解析
# ============================================================================

def parse_args() -> argparse.Namespace:
    """解析命令行参数."""
    parser = argparse.ArgumentParser(
        description="Cron Health Check - 检测并自动清理 stale jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--check", "-c", action="store_true",
        help="执行健康检查,显示 stale jobs 报告"
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="自动清理 stale jobs (默认 dry-run)"
    )
    parser.add_argument(
        "--threshold", "-t", type=int, default=STALE_THRESHOLD_DAYS,
        help=f"Stale 阈值天数 (默认: {STALE_THRESHOLD_DAYS})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="试运行模式,不实际修改"
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="强制执行,跳过确认提示"
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="清理时不创建备份"
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="输出 JSON 格式结果"
    )

    return parser.parse_args()


def format_cleanup_result(result: Dict[str, Any], as_json: bool = False) -> str:
    """格式化清理结果."""
    if as_json:
        return json.dumps(result, indent=2, ensure_ascii=False)

    lines = [
        "# Cleanup Result",
        f"Total before: {result['total_before']}",
        f"Stale: {result['stale_count']} | Healthy: {result['healthy_count']}",
        f"Dry-run: {result['dry_run']}",
    ]

    if result.get("backup_path"):
        lines.append(f"Backup: {result['backup_path']}")

    lines.append("")
    if result["removed_jobs"]:
        lines.append("Removed jobs:")
        for job in result["removed_jobs"]:
            lines.append(f"  - [{job['id']}] {job['name']}")
    else:
        lines.append("No jobs removed.")

    lines.append("")
    lines.append(f"Success: {result['success']}")

    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================

def main():
    """主函数."""
    args = parse_args()

    # 默认行为: 健康检查
    if args.check or (not args.cleanup):
        result = health_check()
        report = format_stale_report(result)

        writer = ChunkedWriter(target_size=125)
        chunks = writer.write(report)

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            for i, chunk in enumerate(chunks, 1):
                print(f"[Chunk {i}/{len(chunks)}] {chunk}")

    # 清理模式
    elif args.cleanup:
        result = cleanup_stale_jobs(
            threshold_days=args.threshold,
            dry_run=args.dry_run,
            backup=not args.no_backup,
            force=args.force,
        )

        log_cleanup(result)

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            output = format_cleanup_result(result)
            writer = ChunkedWriter(target_size=125)
            chunks = writer.write(output)
            for i, chunk in enumerate(chunks, 1):
                print(f"[Chunk {i}/{len(chunks)}] {chunk}")


if __name__ == "__main__":
    main()
