from __future__ import annotations

import time

from .file_store import FileStore
from .job_store import JobStore, PIPELINE_STEPS
from .stages.ingestion import IngestionStage
from .stages.summarization import SummarizationStage
from .stages.rewrite import RewriteStage
from .stages.tts import TTSStage
from .stages.assembly import AssemblyStage
from .types import JobContext


class PipelineRunner:
    def __init__(self, store: JobStore, files: FileStore) -> None:
        self.store = store
        self.files = files
        self.stages = [
            IngestionStage(files),
            SummarizationStage(files),
            RewriteStage(files),
            TTSStage(files),
            AssemblyStage(files),
        ]

    def run_job(self, job_id: str) -> None:
        record = self.store.get(job_id)
        ctx = JobContext(
            job_id=record.job_id,
            source_type=record.source_type,
            source_text=record.source_text,
            source_url=record.source_url,
            filename=record.filename,
            language=record.language,
            voice=record.voice,
            voice_secondary=record.voice_secondary,
            length=record.length,
            llm_provider=record.llm_provider,
            llm_model=record.llm_model,
            llm_api_key=record.llm_api_key,
            llm_max_tokens=record.llm_max_tokens,
            sarvam_api_key=record.sarvam_api_key,
        )
        self.store.set_status(job_id, "running")

        try:
            for step_name, stage in zip(PIPELINE_STEPS, self.stages):
                self.store.update_step(job_id, step_name, "running")
                self.store.append_log(job_id, f"{step_name} started")
                stage.run(ctx, self.store)
                time.sleep(0.4)
                self.store.update_step(job_id, step_name, "done")
                self.store.append_log(job_id, f"{step_name} completed")

            if ctx.script:
                self.store.set_artifact(job_id, "transcript_preview", ctx.script[:2000])
            if ctx.audio_path:
                self.store.set_artifact(job_id, "audio_path", ctx.audio_path)
            if ctx.episode_path:
                self.store.set_artifact(job_id, "episode_path", ctx.episode_path)

            self.store.set_status(job_id, "completed")
        except Exception as exc:
            self.store.append_log(job_id, f"Pipeline failed: {exc}")
            self.store.set_status(job_id, "failed")
