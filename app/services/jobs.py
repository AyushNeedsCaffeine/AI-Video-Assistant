from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    source: str
    source_label: str
    language: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    message: str = "Queued"
    error: str | None = None
    result: dict[str, Any] | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    finished_at: str | None = None


class JobStore:
    """In-memory job store for the single-user v2 application.

    Jobs are intentionally not persisted across server restarts yet; the
    SRS tracks durable storage as a later improvement.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = RLock()

    def create(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields: Any) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            return job

    def add_message(self, job_id: str, role: str, content: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.messages.append({"role": role, "content": content})
            return job

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "id": job.id,
                "status": job.status,
                "stage": job.stage,
                "progress": job.progress,
                "message": job.message,
                "error": job.error,
            }


store = JobStore()
