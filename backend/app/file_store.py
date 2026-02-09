from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import UploadFile


class FileStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        path = self.base_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_upload(self, job_id: str, upload: UploadFile) -> Path:
        job_path = self.job_dir(job_id)
        filename = upload.filename or "input"
        target = job_path / filename
        with target.open("wb") as f:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return target

    def save_text(self, job_id: str, name: str, content: str) -> Path:
        job_path = self.job_dir(job_id)
        target = job_path / name
        target.write_text(content, encoding="utf-8")
        return target

    def save_bytes(self, job_id: str, name: str, content: bytes) -> Path:
        job_path = self.job_dir(job_id)
        target = job_path / name
        target.write_bytes(content)
        return target

    def get_path(self, job_id: str, name: str) -> Path:
        return self.job_dir(job_id) / name
