from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class JobContext:
    job_id: str
    source_type: str
    source_text: Optional[str]
    source_url: Optional[str]
    filename: Optional[str]
    language: str
    voice: str
    voice_secondary: Optional[str]
    length: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_max_tokens: Optional[int] = None
    sarvam_api_key: Optional[str] = None
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    script: Optional[str] = None
    translated_script: Optional[str] = None
    audio_path: Optional[str] = None
    episode_path: Optional[str] = None
