from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StepStatus(BaseModel):
    name: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobCreateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: Optional[str] = None
    steps: List[StepStatus] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    artifacts: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
