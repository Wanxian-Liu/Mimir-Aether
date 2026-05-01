# =============================================================================
# Cron job storage and scheduling (JSON file backend)
# =============================================================================
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS_FILE = PROJECT_ROOT / "cron" / "jobs.json"
OUTPUT_DIR = PROJECT_ROOT / "cron" / "output"


def now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_dirs() -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_jobs() -> List[Dict[str, Any]]:
    ensure_dirs()
    if not JOBS_FILE.exists():
        return []
    try:
        data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if isinstance(jobs, list):
        return jobs
    return []


def save_jobs(jobs: List[Dict[str, Any]]) -> None:
    ensure_dirs()
    payload = {"jobs": jobs, "updated_at": now().isoformat()}
    JOBS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _job_match(job: Dict[str, Any], job_id: str) -> bool:
    jid = str(job.get("id", ""))
    return jid == job_id or jid.startswith(job_id)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    for job in load_jobs():
        if _job_match(job, job_id):
            return job
    return None


def list_jobs(include_disabled: bool = True) -> List[Dict[str, Any]]:
    jobs = load_jobs()
    if include_disabled:
        return list(jobs)
    return [j for j in jobs if j.get("enabled", True)]


def remove_job(job_id: str) -> bool:
    jobs = load_jobs()
    new_jobs = [j for j in jobs if not _job_match(j, job_id)]
    if len(new_jobs) == len(jobs):
        return False
    save_jobs(new_jobs)
    return True


def update_job(job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    jobs = load_jobs()
    for i, job in enumerate(jobs):
        if not _job_match(job, job_id):
            continue
        merged: Dict[str, Any] = dict(job)
        schedule_touched = False
        for k, v in updates.items():
            if k == "repeat.completed":
                r = dict(merged.get("repeat") or {})
                r["completed"] = v
                merged["repeat"] = r
            elif k == "schedule":
                merged["schedule"] = v
                schedule_touched = True
            else:
                merged[k] = v
        if schedule_touched and merged.get("state") != "paused":
            sch = merged.get("schedule") or {}
            nr = compute_next_run(sch, now().isoformat())
            merged["next_run_at"] = nr
        jobs[i] = merged
        save_jobs(jobs)
        return merged
    return None


def parse_schedule(schedule: str) -> Dict[str, Any]:
    s = (schedule or "").strip()
    if not s:
        raise ValueError("empty schedule")

    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}T", s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return {"type": "once", "value": dt.isoformat(), "display": s}
    except ValueError:
        pass

    m = re.match(
        r"^every\s+(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
        s,
        re.I,
    )
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        unit = "minutes" if u.startswith("m") else "hours" if u.startswith("h") else "days"
        return {"type": "interval", "value": {"n": n, "unit": unit}, "display": s}

    m = re.match(r"^(\d+)\s*(m|min|mins|h|hr|hrs|d|day|days)\s*$", s, re.I)
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        unit = "minutes" if u.startswith("m") else "hours" if u.startswith("h") else "days"
        return {"type": "interval", "value": {"n": n, "unit": unit}, "display": s}

    parts = s.split()
    if len(parts) == 5:
        return {"type": "cron", "value": s, "display": s}

    raise ValueError(f"unrecognized schedule: {schedule!r}")


def compute_next_run(schedule: Dict[str, Any], after_iso: Optional[str] = None) -> Optional[str]:
    base = now()
    if after_iso:
        try:
            base = datetime.fromisoformat(after_iso.replace("Z", "+00:00"))
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            base = now()

    st = schedule.get("type")
    if st == "once":
        ts = schedule.get("value")
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
        return dt.isoformat() if dt > base else None

    if st == "interval":
        v = schedule.get("value") or {}
        try:
            n = int(v.get("n", 1))
        except (TypeError, ValueError):
            n = 1
        unit = str(v.get("unit", "minutes"))
        delta = {
            "minutes": timedelta(minutes=n),
            "hours": timedelta(hours=n),
            "days": timedelta(days=n),
        }.get(unit, timedelta(minutes=n))
        return (base + delta).isoformat()

    if st == "cron":
        expr = schedule.get("value")
        if not expr:
            return None
        try:
            from croniter import croniter  # type: ignore
        except ImportError:
            return None
        it = croniter(str(expr), base)
        nxt = it.get_next(datetime)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=timezone.utc)
        return nxt.isoformat()

    return None


def create_job(
    prompt: str = "",
    schedule: str = "",
    name: Optional[str] = None,
    repeat: Optional[int] = None,
    deliver: Optional[str] = None,
    origin: Optional[Dict[str, Any]] = None,
    skills: Optional[List[str]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    script: Optional[str] = None,
) -> Dict[str, Any]:
    parsed = parse_schedule(schedule)
    jid = uuid.uuid4().hex[:12]
    schedule_display = str(parsed.get("display", schedule))
    now_s = now().isoformat()
    repeat_o: Dict[str, Any] = {}
    if repeat is not None and repeat > 0:
        repeat_o["times"] = repeat
        repeat_o["completed"] = 0
    next_run = compute_next_run(parsed, now_s)
    job: Dict[str, Any] = {
        "id": jid,
        "name": name or f"job-{jid}",
        "prompt": prompt,
        "schedule": parsed,
        "schedule_display": schedule_display,
        "enabled": True,
        "state": "scheduled",
        "next_run_at": next_run,
        "created_at": now_s,
        "deliver": deliver or "local",
    }
    if origin:
        job["origin"] = origin
    if repeat_o:
        job["repeat"] = repeat_o
    if skills:
        job["skills"] = skills
        job["skill"] = skills[0]
    if model:
        job["model"] = model
    if provider:
        job["provider"] = provider
    if base_url:
        job["base_url"] = base_url
    if script:
        job["script"] = script

    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)
    return job


def pause_job(job_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    updates: Dict[str, Any] = {
        "enabled": False,
        "state": "paused",
        "paused_at": now().isoformat(),
    }
    if reason:
        updates["paused_reason"] = reason
    out = update_job(job_id, updates)
    if not out:
        raise ValueError(f"job not found: {job_id}")
    return out


def resume_job(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise ValueError(f"job not found: {job_id}")
    sch = job.get("schedule") or {}
    nr = compute_next_run(sch, now().isoformat())
    out = update_job(
        job_id,
        {
            "enabled": True,
            "state": "scheduled",
            "next_run_at": nr,
            "paused_at": None,
            "paused_reason": None,
        },
    )
    if not out:
        raise ValueError(f"job not found: {job_id}")
    return out


def trigger_job(job_id: str) -> Dict[str, Any]:
    out = update_job(
        job_id,
        {
            "next_run_at": now().isoformat(),
            "enabled": True,
            "state": "scheduled",
        },
    )
    if not out:
        raise ValueError(f"job not found: {job_id}")
    return out


# =============================================================================
# Job execution support
# =============================================================================


def get_due_jobs() -> List[Dict[str, Any]]:
    jobs = load_jobs()
    now_dt = now()
    due: List[Dict[str, Any]] = []

    for job in jobs:
        if not job.get("enabled", True):
            continue
        next_run = job.get("next_run_at")
        if not next_run:
            continue
        try:
            next_dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=timezone.utc)
            if next_dt <= now_dt:
                due.append(job)
        except (ValueError, TypeError):
            continue

    return due


def mark_job_run(job_id: str, status: str, error: Optional[str] = None):
    job = get_job(job_id)
    if not job:
        return

    repeat = job.get("repeat", {})
    completed = int(repeat.get("completed", 0)) + 1
    max_times = repeat.get("times")

    disable = False
    if max_times is not None and completed >= int(max_times):
        disable = True

    schedule = job.get("schedule", {})
    next_run = None
    if not disable:
        next_run = compute_next_run(schedule, now().isoformat())

    update_job(
        job_id,
        {
            "last_run_at": now().isoformat(),
            "last_status": status,
            "last_error": error,
            "repeat.completed": completed,
            "enabled": not disable,
            "next_run_at": next_run,
            "state": "scheduled" if next_run else "completed",
        },
    )


def save_job_output(job_id: str, output: str, metadata: Optional[Dict] = None):
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
    output_file.write_text(content, encoding="utf-8")
    return str(output_file)


def advance_next_run(job_id: str):
    job = get_job(job_id)
    if not job or not job.get("schedule"):
        return
    last_run = job.get("last_run_at") or now().isoformat()
    next_run = compute_next_run(job["schedule"], last_run)
    if next_run:
        update_job(job_id, {"next_run_at": next_run})
