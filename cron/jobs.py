# =============================================================================
# Job Execution Support
# =============================================================================

from typing import List, Dict, Any, Optional

def get_due_jobs() -> List[Dict[str, Any]]:
    """Get all jobs that are due to run."""
    jobs = load_jobs()
    now_dt = now()
    due = []
    
    for job in jobs:
        if not job.get("enabled", True):
            continue
        
        next_run = job.get("next_run_at")
        if not next_run:
            continue
        
        try:
            next_dt = datetime.fromisoformat(next_run)
            if next_dt.tzinfo is None:
                next_dt = next_dt.astimezone()
            
            if next_dt <= now_dt:
                due.append(job)
        except (ValueError, TypeError):
            continue
    
    return due

def mark_job_run(job_id: str, status: str, error: Optional[str] = None):
    """Mark a job as run and update repeat count."""
    job = get_job(job_id)
    if not job:
        return
    
    repeat = job.get("repeat", {})
    completed = repeat.get("completed", 0) + 1
    max_times = repeat.get("times")
    
    # Check if job should be disabled
    disable = False
    if max_times is not None and completed >= max_times:
        disable = True
    
    # Compute next run
    schedule = job.get("schedule", {})
    next_run = None
    if not disable:
        next_run = compute_next_run(schedule, now().isoformat())
    
    update_job(job_id, {
        "last_run_at": now().isoformat(),
        "last_status": status,
        "last_error": error,
        "repeat.completed": completed,
        "enabled": not disable,
        "next_run_at": next_run,
        "state": "scheduled" if next_run else "completed"
    })

def save_job_output(job_id: str, output: str, metadata: Optional[Dict] = None):
    """Save job output to file."""
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    output_file = job_dir / f"{timestamp}.md"
    
    content = f"""# Cron Job Output

**Job ID:** {job_id}
**Timestamp:** {timestamp}
**Metadata:** {json.dumps(metadata or {}, indent=2)}

---

{output}
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(output_file)

def advance_next_run(job_id: str):
    """Advance a job to its next scheduled run."""
    job = get_job(job_id)
    if not job or not job.get("schedule"):
        return
    
    last_run = job.get("last_run_at") or now().isoformat()
    next_run = compute_next_run(job["schedule"], last_run)
    
    if next_run:
        update_job(job_id, {"next_run_at": next_run})
