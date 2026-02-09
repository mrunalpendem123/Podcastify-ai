from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .file_store import FileStore
from .job_store import JobStore
from .models import JobCreateResponse, JobStatusResponse
from .pipeline import PipelineRunner


from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


app = FastAPI(title="Create-to-Listen API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = JobStore()
files = FileStore(BASE_DIR / "storage")
pipeline = PipelineRunner(store, files)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/jobs", response_model=JobCreateResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    source_type: str = Form(...),
    language: str = Form("Hindi"),
    voice: str = Form("Shubh"),
    voice_secondary: Optional[str] = Form(None),
    length: str = Form("full"),
    llm_provider: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
    llm_api_key: Optional[str] = Form(None),
    llm_max_tokens: Optional[int] = Form(None),
    sarvam_api_key: Optional[str] = Form(None),
    source_text: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> JobCreateResponse:
    if source_type not in {"file", "text", "url"}:
        raise HTTPException(status_code=400, detail="Invalid source_type")

    if source_type == "file" and file is None:
        raise HTTPException(status_code=400, detail="File required for source_type=file")
    if source_type == "text" and not source_text:
        raise HTTPException(status_code=400, detail="source_text required for source_type=text")
    if source_type == "url" and not source_url:
        raise HTTPException(status_code=400, detail="source_url required for source_type=url")

    filename = file.filename if file is not None else None

    record = store.create_job(
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
    )

    if file is not None and filename is not None:
        files.save_upload(record.job_id, file)

    background_tasks.add_task(pipeline.run_job, record.job_id)
    return JobCreateResponse(job_id=record.job_id)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    try:
        return store.to_response(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/jobs/{job_id}/artifact")
def get_artifact(job_id: str, name: str) -> FileResponse:
    try:
        path = files.get_path(job_id, name)
    except Exception:
        raise HTTPException(status_code=404, detail="Artifact not found")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(path)
