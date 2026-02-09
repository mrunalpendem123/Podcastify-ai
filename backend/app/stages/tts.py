from __future__ import annotations

import base64
import io
import os
import re
import wave
from typing import Iterable, List, Optional, Tuple

import requests

from ..file_store import FileStore
from ..job_store import JobStore
from ..types import JobContext

try:
    from sarvamai import SarvamAI
    from sarvamai.play import save
except ImportError:
    SarvamAI = None

SARVAM_MODEL = "bulbul:v3"
MAX_CHARS = 2500
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_PACE = 1.0
DEFAULT_TEMPERATURE = 0.6

import sys

def debug_log(msg: str):
    print(f"[TTS_DEBUG] {msg}", file=sys.stderr, flush=True)

LANGUAGE_CODE_MAP = {
    "hindi": "hi-IN",
    "telugu": "te-IN",
    "tamil": "ta-IN",
    "bengali": "bn-IN",
    "gujarati": "gu-IN",
    "kannada": "kn-IN",
    "malayalam": "ml-IN",
    "marathi": "mr-IN",
    "punjabi": "pa-IN",
    "odia": "od-IN",
    "english": "en-IN",
    "en": "en-IN",
}

SPEAKER_ALIASES = {
    "host": "primary",
    "guest": "secondary",
    "speaker a": "primary",
    "speaker b": "secondary",
    "narrator": "primary",
}


def _normalize_language(language: str) -> str:
    key = language.strip().lower()
    if key in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[key]
    if "-" in key:
        return language
    return "hi-IN"


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _chunk_text(text: str, max_chars: int = MAX_CHARS) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
                current = ""
            if len(sentence) > max_chars:
                for idx in range(0, len(sentence), max_chars):
                    chunks.append(sentence[idx : idx + max_chars])
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks


def _extract_segments(text: str) -> List[Tuple[Optional[str], str]]:
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []
    segments: List[Tuple[Optional[str], str]] = []
    for paragraph in paragraphs:
        # Check if line starts with Speaker: Text
        match = re.match(r"^(\**)?(Host|Guest|Speaker A|Speaker B|Narrator)(\**)?\s*:\s*(.*)$", paragraph, re.I | re.S)
        if match:
            label = (match.group(2) or "Host").strip().lower()
            text_content = match.group(4).strip()
            
            # Additional cleaning: If text_content starts with "Host:" again (hallucination), strip it
            # e.g. "Host: Host: Hello" -> "Hello"
            # Remove any prefix like "Host: " or "Guest: " from the start of content
            clean_match = re.match(r"^(Host|Guest|Speaker A|Speaker B|Narrator)\s*:\s*(.*)$", text_content, re.I | re.S)
            if clean_match:
               text_content = clean_match.group(2).strip()

            segments.append((label, text_content))
        else:
            # Fallback for untagged paragraphs (usually continuous speech from previous speaker)
            # Or if regex fails. Treat as continuation or try to guess.
            # Best is to treat as None label (default speaker) or check context. 
            # For simplicity, treat as default speaker (None -> Host/Primary)
            segments.append((None, paragraph))
    return segments


def _combine_wav(segments: Iterable[bytes], pause_seconds: float = 0.35) -> bytes:
    segments = list(segments)
    if not segments:
        return b""

    output = io.BytesIO()
    params = None
    frames: List[bytes] = []

    for idx, audio_bytes in enumerate(segments):
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_in:
            if params is None:
                params = wav_in.getparams()
            else:
                if wav_in.getparams()[:3] != params[:3]:
                    raise ValueError("Inconsistent WAV params across segments")
            frames.append(wav_in.readframes(wav_in.getnframes()))

        if pause_seconds > 0 and idx < len(segments) - 1:
            silence_frames = int(params.framerate * pause_seconds)
            silence = b"\x00" * silence_frames * params.nchannels * params.sampwidth
            frames.append(silence)

    with wave.open(output, "wb") as wav_out:
        wav_out.setparams(params)
        for chunk in frames:
            wav_out.writeframes(chunk)

    return output.getvalue()


class TTSStage:
    def __init__(self, files: FileStore) -> None:
        self.files = files

    def _call_sarvam(self, api_key: str, text: str, language_code: str, speaker: Optional[str]) -> bytes:
        if SarvamAI is None:
            raise RuntimeError("sarvamai package not installed. run 'pip install sarvamai'")

        client = SarvamAI(api_subscription_key=api_key)
        
        try:
            debug_log(f"Calling Sarvam SDK with text len={len(text)}, speaker={speaker}")
            # The SDK returns a response object that can be played or saved
            audio_response = client.text_to_speech.convert(
                text=text,
                target_language_code=language_code,
                model=SARVAM_MODEL,
                speaker=speaker.lower().strip() if speaker else None,
                pace=float(os.getenv("SARVAM_PACE", DEFAULT_PACE)),
                speech_sample_rate=DEFAULT_SAMPLE_RATE
            )
            
            # Since the SDK doesn't have a direct 'get bytes' method documented in the snippet,
            # we'll save to a temporary buffer/file to get the bytes, or check if it has a content attribute.
            # Based on common SDK patterns and the 'save' function existence:
            # We can use a BytesIO buffer if 'save' supports file-like objects, 
            # OR we can inspect the response object. 
            # Given user snippet `save(response, "output.wav")`, let's try to get bytes.
            
            # Investigation of SarvamAI SDK (assuming it returns an object with audio bytes or similar)
            # If `audio_response` is the audio bytes itself (some clients do this), we return it.
            if isinstance(audio_response, bytes):
                return audio_response

            # If it's a response object, let's try to find the audio content.
            # Warning: specific attribute depends on SDK implementation. 
            # If `save` writes to file, we can write to temp file and read back.
            # This is the fail-safe method without knowing exact object structure.
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_path = tmp.name
            
            try:
                save(audio_response, temp_path)
                with open(temp_path, "rb") as f:
                    audio_bytes = f.read()
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
            return audio_bytes

        except Exception as e:
            debug_log(f"Sarvam SDK error: {e}")
            raise RuntimeError(f"Sarvam SDK failed: {e}")

    def run(self, ctx: JobContext, store: JobStore) -> None:
        api_key = ctx.sarvam_api_key or os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError("SARVAM_API_KEY is not set")

        transcript = ctx.translated_script or ctx.script or ""
        language_code = _normalize_language(ctx.language)
        use_secondary = bool(ctx.voice_secondary and ctx.voice_secondary != ctx.voice)
        debug_log(f"Starting TTS run. Language: {language_code}, Transcript len: {len(transcript)}")
        segments = _extract_segments(transcript)
        debug_log(f"Extracted {len(segments)} segments")

        if not segments:
            segments = [(None, transcript)] if transcript else []

        audio_segments: List[bytes] = []
        for index, (label, segment_text) in enumerate(segments):
            if not segment_text:
                continue
            if label:
                speaker_choice = SPEAKER_ALIASES.get(label, "primary")
                speaker = ctx.voice if speaker_choice == "primary" else ctx.voice_secondary or ctx.voice
            else:
                if use_secondary and index % 2 == 1:
                    speaker = ctx.voice_secondary
                else:
                    speaker = ctx.voice

            for chunk in _chunk_text(segment_text):
                store.append_log(
                    ctx.job_id,
                    f"TTS chunk ({speaker}) {len(chunk)} chars using {SARVAM_MODEL}",
                )
                store.append_log(
                    ctx.job_id,
                    f"TTS chunk ({speaker}) {len(chunk)} chars using {SARVAM_MODEL}",
                )
                debug_log(f"Processing chunk {index}: {len(chunk)} chars, speaker: {speaker}")
                try:
                    audio_segments.append(self._call_sarvam(api_key, chunk, language_code, speaker))
                    debug_log("Chunk processed successfully")
                except Exception as e:
                    debug_log(f"Chunk failed: {e}")
                    raise e

        combined_audio = _combine_wav(audio_segments)
        audio_path = self.files.save_bytes(ctx.job_id, "audio.wav", combined_audio)
        ctx.audio_path = str(audio_path)
