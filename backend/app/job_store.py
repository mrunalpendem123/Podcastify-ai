from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from .models import JobStatusResponse, StepStatus


PIPELINE_STEPS = [
    "Parsing document",
    "Structuring sections",
    "Making conversational",
    "Generating audio",
    "Assembling episode",
]


@dataclass
class JobRecord:
    job_id: str
    status: str
    source_type: str
    source_text: Optional[str]
    source_url: Optional[str]
    filename: Optional[str]
    language: str
    voice: str
    voice_secondary: Optional[str]
    length: str
    llm_provider: Optional[str]
    llm_model: Optional[str]
    llm_api_key: Optional[str]
    llm_max_tokens: Optional[int]
    sarvam_api_key: Optional[str]
    created_at: datetime
    updated_at: datetime
    current_step: Optional[str] = None
    steps: Dict[str, StepStatus] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = Lock()

    def create_job(
        self,
        source_type: str,
        source_text: Optional[str],
        source_url: Optional[str],
        filename: Optional[str],
        language: str,
        voice: str,
        voice_secondary: Optional[str],
        length: str,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_max_tokens: Optional[int] = None,
        sarvam_api_key: Optional[str] = None,
    ) -> JobRecord:
        job_id = str(uuid4())
        now = datetime.utcnow()
        steps = {name: StepStatus(name=name, status="pending") for name in PIPELINE_STEPS}
        record = JobRecord(
            job_id=job_id,
            status="queued",
            source_type=source_type,
            source_text=source_text,
            source_url=source_url,
            filename=filename,
            language=language,
            voice=voice,
            voice_secondary=voice_secondary,
            length=length,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            llm_max_tokens=llm_max_tokens,
            sarvam_api_key=sarvam_api_key,
            created_at=now,
            updated_at=now,
            steps=steps,
        )
        with self._lock:
            self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id]

    def set_status(self, job_id: str, status: str, current_step: Optional[str] = None) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = status
            record.current_step = current_step
            record.updated_at = datetime.utcnow()

    def update_step(self, job_id: str, step_name: str, status: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            step = record.steps[step_name]
            if status == "running":
                step.started_at = datetime.utcnow()
            if status in {"done", "failed"}:
                step.finished_at = datetime.utcnow()
            step.status = status
            record.current_step = step_name
            record.updated_at = datetime.utcnow()

    def append_log(self, job_id: str, message: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.logs.append(message)
            record.updated_at = datetime.utcnow()

    def set_artifact(self, job_id: str, key: str, value: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.artifacts[key] = value
            record.updated_at = datetime.utcnow()

    def to_response(self, job_id: str) -> JobStatusResponse:
        record = self.get(job_id)
        steps = list(record.steps.values())
        return JobStatusResponse(
            job_id=record.job_id,
            status=record.status,
            current_step=record.current_step,
            steps=steps,
            logs=record.logs,
            artifacts=record.artifacts,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
