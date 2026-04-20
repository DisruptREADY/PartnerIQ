"""Background job system for long-running data fetches."""
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, Optional

log = logging.getLogger("data_portal")

# In-memory job store
_jobs: Dict[str, Dict[str, Any]] = {}


def create_job() -> str:
    """Create a new pending job, return its ID."""
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Queued...",
        "result": None,
        "error": None,
        "created_at": time.time(),
    }
    return job_id


def update_job(job_id: str, progress: int = None, message: str = None, status: str = None):
    """Update job progress/status."""
    job = _jobs.get(job_id)
    if not job:
        return
    if progress is not None:
        job["progress"] = progress
    if message is not None:
        job["message"] = message
    if status is not None:
        job["status"] = status


def complete_job(job_id: str, result: Any):
    """Mark job as completed with result."""
    job = _jobs.get(job_id)
    if not job:
        return
    job["status"] = "completed"
    job["progress"] = 100
    job["message"] = "Done"
    job["result"] = result


def fail_job(job_id: str, error: str):
    """Mark job as failed."""
    job = _jobs.get(job_id)
    if not job:
        return
    job["status"] = "failed"
    job["error"] = error
    job["message"] = f"Error: {error}"


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status."""
    return _jobs.get(job_id)
