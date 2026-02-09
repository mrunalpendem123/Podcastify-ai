from __future__ import annotations

import json
import re
import wave
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..file_store import FileStore
from ..job_store import JobStore
from ..types import JobContext

try:
    from podcastfy.text_to_speech import TextToSpeech
except Exception:  # pragma: no cover - optional dependency
    TextToSpeech = None

SPEAKER_TAG_RE = re.compile(r"^(Host|Guest|Speaker A|Speaker B|Narrator)\s*:\s*(.*)$", re.I | re.S)


def _split_segments(script: str) -> List[Dict[str, str]]:
    segments: List[Dict[str, str]] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", script) if p.strip()]
    for paragraph in paragraphs:
        match = SPEAKER_TAG_RE.match(paragraph)
        if match:
            speaker = match.group(1).title()
            text = match.group(2).strip()
        else:
            speaker = "Narrator"
            text = paragraph
        if text:
            segments.append({"speaker": speaker, "text": text})
    return segments


def _duration_seconds(audio_path: Optional[str]) -> Optional[float]:
    if not audio_path:
        return None
    try:
        with wave.open(audio_path, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
        if rate:
            return round(frames / float(rate), 2)
    except Exception:
        return None
    return None


class AssemblyStage:
    def __init__(self, files: FileStore) -> None:
        self.files = files

    def _podcastfy_split(self, script: str) -> Optional[List[Tuple[str, str]]]:
        if TextToSpeech is None:
            return None
        try:
            tts = TextToSpeech()
            if hasattr(tts, "split_qa"):
                return tts.split_qa(script)
        except Exception:
            return None
        return None

    def run(self, ctx: JobContext, store: JobStore) -> None:
        script_path = self.files.get_path(ctx.job_id, "script.txt")
        script = script_path.read_text(encoding="utf-8") if script_path.exists() else ctx.script or ""

        segments = _split_segments(script)
        podcastfy_segments = self._podcastfy_split(script)
        duration = _duration_seconds(ctx.audio_path)

        episode = {
            "title": "Create-to-Listen Episode",
            "language": ctx.language,
            "voice_primary": ctx.voice,
            "voice_secondary": ctx.voice_secondary,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "audio_path": ctx.audio_path,
            "script_path": str(script_path),
            "duration_seconds": duration,
            "segments": segments,
        }

        if podcastfy_segments:
            episode["podcastfy_segments"] = podcastfy_segments

        episode_path = self.files.save_text(ctx.job_id, "episode.json", json.dumps(episode, indent=2, ensure_ascii=False))
        segments_path = self.files.save_text(ctx.job_id, "segments.json", json.dumps(segments, indent=2, ensure_ascii=False))
        ctx.episode_path = str(episode_path)
        store.set_artifact(ctx.job_id, "episode_path", str(episode_path))
        store.set_artifact(ctx.job_id, "segments_path", str(segments_path))
