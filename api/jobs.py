import uuid
import asyncio
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
import logging

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job:
    def __init__(self, job_type: str):
        self.id = str(uuid.uuid4())
        self.type = job_type
        self.status = JobStatus.PENDING
        self.logs: List[str] = []
        self.progress: float = 0.0
        self.created_at = datetime.now()
        self.result: Any = None
        self._new_log_event = asyncio.Event()

    def log(self, message: str):
        self.logs.append(message)
        self._new_log_event.set()
        # Reset event in loop? No, just set it. 
        # Consumers will need to clear it or check length.

    async def run(self, func, *args, **kwargs):
        self.status = JobStatus.RUNNING
        self.log(f"Job started: {self.type}")
        try:
            self.result = await func(self, *args, **kwargs)
            self.status = JobStatus.COMPLETED
            self.progress = 100.0
            self.log("Job completed successfully.")
        except Exception as e:
            self.status = JobStatus.FAILED
            self.log(f"Job failed: {str(e)}")
            logging.error(f"Job {self.id} failed", exc_info=True)
            # raise e # Don't raise, just mark as failed so API doesn't crash
        finally:
            self._new_log_event.set() # Wake up listeners

class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}

    def create_job(self, job_type: str) -> Job:
        job = Job(job_type)
        self.jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

manager = JobManager()
