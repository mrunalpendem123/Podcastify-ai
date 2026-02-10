from __future__ import annotations

import json
import os
import time
from typing import Optional, Tuple

from ..file_store import FileStore
from ..job_store import JobStore
from ..types import JobContext

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


class RewriteStage:
    def __init__(self, files: FileStore) -> None:
        self.files = files

    def _fallback_script(self, base: str, use_duo: bool) -> str:
        paragraphs = [p.strip() for p in base.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [base.strip()] if base.strip() else []

        if not use_duo:
            lines = ["Narrator: Let’s dive straight in."]
            for paragraph in paragraphs:
                lines.append(f"Narrator: {paragraph}")
            lines.append("Narrator: That’s the core idea, step by step.")
            return "\n\n".join(lines)

        lines = ["Speaker A: Let’s dive straight in."]
        for index, paragraph in enumerate(paragraphs):
            speaker = "Speaker A" if index % 2 == 0 else "Speaker B"
            lines.append(f"{speaker}: {paragraph}")
        lines.append("Speaker A: That’s the core idea, step by step.")
        return "\n\n".join(lines)

    def _word_count(self, text: str) -> int:
        return len([w for w in text.split() if w.strip()])

    def _normalize_speaker_labels(self, script: str, use_duo: bool) -> str:
        if not script:
            return script
        normalized_lines: list[str] = []
        for raw in script.splitlines():
            line = raw.strip()
            if not line:
                continue

            if use_duo:
                replacements = [
                    ("Speaker A:", "Host:"),
                    ("Speaker B:", "Guest:"),
                    ("Speaker A :", "Host:"),
                    ("Speaker B :", "Guest:"),
                    ("Co-host:", "Guest:"),
                    ("Cohost:", "Guest:"),
                    ("Co host:", "Guest:"),
                    ("Host 1:", "Host:"),
                    ("Host 2:", "Guest:"),
                    ("Host:", "Host:"),
                    ("Guest:", "Guest:"),
                ]
                for old, new in replacements:
                    if line.lower().startswith(old.lower()):
                        line = f"{new}{line[len(old):]}".strip()
                        break

                if not (line.lower().startswith("host:") or line.lower().startswith("guest:")):
                    line = f"Host: {line}"
            else:
                if line.lower().startswith("host:") or line.lower().startswith("guest:"):
                    line = f"Narrator: {line.split(':', 1)[1].strip()}"
                elif not line.lower().startswith("narrator:"):
                    line = f"Narrator: {line}"

            normalized_lines.append(line)
        return "\n".join(normalized_lines).strip()

    def _ensure_min_words(
        self,
        client: OpenAI,
        model: str,
        system_prompt: str,
        script: str,
        target_words: int,
        max_tokens: int,
    ) -> str:
        current_words = self._word_count(script)
        if current_words >= target_words:
            return script

        attempts = 0
        combined = script.strip()
        while current_words < target_words and attempts < 3:
            remaining = max(target_words - current_words, 200)
            continuation_prompt = (
                "Continue the script from where it left off. "
                "Keep the same speaker format and language. "
                "Do not repeat earlier content, and do not add any intro. "
                f"Add at least {remaining} new words of content. "
                "Output ONLY the continuation lines."
            )
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"{continuation_prompt}\n\nCurrent script:\n{combined}",
                    },
                ],
                temperature=0.6,
                max_tokens=max_tokens,
            )
            addition = response.choices[0].message.content.strip()
            if not addition:
                break
            combined = f"{combined}\n{addition}".strip()
            current_words = self._word_count(combined)
            attempts += 1

        return combined

    def _strip_cringe_opening(self, script: str) -> str:
        lines = [line for line in script.splitlines() if line.strip()]
        if not lines:
            return script
        cleaned: list[str] = []
        banned = (
            "welcome back",
            "thanks for having me",
            "today we have",
            "we have a guest",
            "on the show",
        )
        for idx, line in enumerate(lines):
            if idx < 6 and any(term in line.lower() for term in banned):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _run_openai_direct(self, text: str, ctx: JobContext) -> Tuple[str, dict]:
        if OpenAI is None:
            raise RuntimeError("OpenAI package not installed")

        api_key = ctx.llm_api_key or os.getenv("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)
        target_lang = ctx.language or "Hindi"
        use_duo = bool(ctx.voice_secondary and ctx.voice_secondary != ctx.voice)
        provider = (ctx.llm_provider or "").lower().strip()
        model = "gpt-4o"
        if ctx.llm_model:
            if provider == "openai" or ctx.llm_model.startswith("openai/"):
                model = ctx.llm_model.replace("openai/", "")
        
        # Determine detail level based on length param
        is_deep_dive = ctx.length == "full"
        desired_minutes = "10-15" if is_deep_dive else "2-5"
        min_words = (
            int(os.getenv("MIN_DEEPDIVE_WORDS", "1600")) if is_deep_dive else 350
        )
        detail_instruction = (
            "Cover the content in extreme detail. Do not miss any nuances, numbers, or technical facts. "
            f"This should be a deep dive of {desired_minutes} minutes of spoken audio "
            f"(roughly {min_words}+ words)."
            if is_deep_dive
            else "Summarize the key points concisely. Focus on the big picture."
        )

        if use_duo:
            speaker_rule = (
                "There are two speakers: 'Host' and 'Guest', but they are co-hosts. "
                "Do NOT introduce a guest, do NOT say 'we have a guest', "
                "and do NOT include staged greetings like 'thanks for having me'. "
                "Open with a short, natural hook like 'Today we're diving into…'."
            )
            format_rule = (
                "Each line MUST start with 'Host:' or 'Guest:'."
            )
            example_block = (
                "Host: Today we’re unpacking the core idea, step by step.\n"
                "Guest: Yes, and we’ll keep it grounded with clear examples."
            )
        else:
            speaker_rule = (
                "There is a single speaker: 'Narrator'. "
                "Start immediately with the topic. No intros, no meta talk."
            )
            format_rule = "Each line MUST start with 'Narrator:'."
            example_block = "Narrator: Let’s start with the core idea."

        system_prompt = (
            "You are an expert podcast scriptwriter. Your task is to read the provided text "
            f"and create a natural, engaging conversation in {target_lang}."
            "\n\nRules:"
            f"\n1. {speaker_rule}"
            "\n2. Avoid showy intros or 'welcome back'. No meta talk about being a podcast."
            f"\n4. CRITICAL: The entire conversation MUST be in {target_lang}."
            "\n5. Make it sound like a REAL conversation. Use short turns, clarifying questions, gentle interruptions, "
            "and natural filler words (e.g., 'hmm', 'yeah', 'right'). Avoid list-like recitations or reading tone."
            "\n6. Do not mention 'host', 'guest', or 'speaker' inside the spoken text."
            f"\n6. {detail_instruction}"
            "\n7. FORMATTING IS STRICT:"
            f"\n   - {format_rule}"
            "\n   - Do NOT use Markdown bolding (no **Host**)."
            "\n   - Do NOT include the speaker name inside the spoken text."
            "\n   - Example:"
            f"\n     {example_block}"
        )

        max_chars_env = os.getenv(
            "MAX_SCRIPT_SOURCE_CHARS_DEEP" if is_deep_dive else "MAX_SCRIPT_SOURCE_CHARS_BRIEF",
            "60000" if is_deep_dive else "25000",
        )
        try:
            max_chars = max(5000, int(max_chars_env))
        except ValueError:
            max_chars = 60000 if is_deep_dive else 25000

        user_prompt = (
            f"Here is the source text to convert into a {target_lang} podcast script.\n"
            f"Aim for {desired_minutes} minutes of spoken audio. Stay natural and grounded.\n\n"
            f"{text[:max_chars]}"
        )

        max_tokens = ctx.llm_max_tokens or (8192 if is_deep_dive else 3072)
        if is_deep_dive and max_tokens < 6000:
            max_tokens = 8192

        response = client.chat.completions.create(
            model=model, # Enhanced quality
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=max_tokens,
        )

        script = response.choices[0].message.content
        script = self._strip_cringe_opening(script)
        script = self._normalize_speaker_labels(script, use_duo)

        if is_deep_dive:
            if self._word_count(script) < min_words:
                script = self._ensure_min_words(
                    client=client,
                    model=model,
                    system_prompt=system_prompt,
                    script=script,
                    target_words=min_words,
                    max_tokens=max_tokens,
                )
                script = self._normalize_speaker_labels(script, use_duo)
        meta = {
            "model": model,
            "provider": "openai",
            "target_language": target_lang
        }
        return script.strip(), meta

    def run(self, ctx: JobContext, store: JobStore) -> None:
        base = ctx.summary or ctx.raw_text or ""
        start = time.time()
        meta: dict = {}
        use_duo = bool(ctx.voice_secondary and ctx.voice_secondary != ctx.voice)

        if True: # Always attempt OpenAI first as per new instruction
            try:
                script, meta = self._run_openai_direct(base, ctx)
            except Exception as exc:
                store.append_log(ctx.job_id, f"OpenAI script generation failed; using fallback: {exc}")
                script = self._fallback_script(base, use_duo)
                meta = {"openai_used": False, "error": str(exc)}

        meta["elapsed_seconds"] = round(time.time() - start, 2)
        script = self._normalize_speaker_labels(script, use_duo)
        meta["word_count"] = self._word_count(script)
        store.append_log(ctx.job_id, f"Script words: {meta['word_count']}")

        ctx.script = script
        script_path = self.files.save_text(ctx.job_id, "script.txt", script)
        meta_path = self.files.save_text(ctx.job_id, "rewrite_meta.json", json.dumps(meta, indent=2))
        store.set_artifact(ctx.job_id, "script_path", str(script_path))
        store.set_artifact(ctx.job_id, "rewrite_meta_path", str(meta_path))
