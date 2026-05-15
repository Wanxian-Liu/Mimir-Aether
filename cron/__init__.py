"""
Cron job scheduling system for MimirAether.

Provides:
- create_job, get_job, list_jobs, update_job, remove_job
- pause_job, resume_job, trigger_job
- parse_schedule for interval/cron/once schedules
- tick() for scheduler execution

Jobs persisted at ``JOBS_FILE`` (``<repo>/cron/jobs.json``). Legacy flat-list
scheduler under ``MIMIR_AETHER_HOME``: ``scheduler.jobs.JOBS_FILE``.
"""

from cron.jobs import (
    create_job, get_job, list_jobs, remove_job,
    update_job, pause_job, resume_job, trigger_job,
    parse_schedule, compute_next_run,
    load_jobs, save_jobs, ensure_dirs,
    JOBS_FILE, OUTPUT_DIR
)

__all__ = [
    "create_job", "get_job", "list_jobs", "remove_job",
    "update_job", "pause_job", "resume_job", "trigger_job",
    "parse_schedule", "compute_next_run",
    "load_jobs", "save_jobs", "ensure_dirs",
    "JOBS_FILE", "OUTPUT_DIR",
]
