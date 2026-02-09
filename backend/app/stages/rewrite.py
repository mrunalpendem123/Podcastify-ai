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

    def _fallback_script(self, base: str) -> str:
        paragraphs = [p.strip() for p in base.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [base.strip()] if base.strip() else []

        lines = [
            "Host: Let’s walk through this carefully.",
        ]
        for index, paragraph in enumerate(paragraphs):
            speaker = "Host" if index % 2 == 0 else "Guest"
            lines.append(f"{speaker}: {paragraph}")
        lines.append("Host: That’s the core idea, step by step.")
        return "\n\n".join(lines)

    def _run_openai_direct(self, text: str, ctx: JobContext) -> Tuple[str, dict]:
        if OpenAI is None:
            raise RuntimeError("OpenAI package not installed")

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        target_lang = ctx.language or "Hindi"
        
        # Determine detail level based on length param
        is_deep_dive = ctx.length == "full"
        detail_instruction = (
            "Cover the content in extreme detail. Do not miss any nuances, numbers, or technical facts. "
            "This should be a deep dive."
            if is_deep_dive
            else "Summarize the key points concisely. Focus on the big picture."
        )

        system_prompt = (
            "You are an expert podcast scriptwriter. Your task is to read the provided text "
            f"and create a natural, engaging conversation in {target_lang}."
            "\n\nRules:"
            "\n1. There are two speakers: 'Host' and 'Guest'."
            "\n2. The Host introduces the topic and asks insightful questions."
            "\n3. The Guest explains the concepts clearly and naturally."
            f"\n4. CRITICAL: The entire conversation MUST be in {target_lang}."
            "\n5. Make it sound like a REAL conversation. Use natural transitions, agreements (e.g., 'Exactly', 'I see', 'Right')."
            f"\n6. {detail_instruction}"
            "\n7. FORMATTING IS STRICT:"
            "\n   - Each line MUST start with 'Host:' or 'Guest:'."
            "\n   - Do NOT use Markdown bolding (no **Host**)."
            "\n   - Do NOT include the speaker name inside the spoken text."
            "\n   - Example:"
            "\n     Host: Welcome back to the show."
            "\n     Guest: Thanks for having me."
        )

        user_prompt = f"Here is the source text to convert into a {target_lang} podcast script:\n\n{text[:15000]}" # Limit context

        response = client.chat.completions.create(
            model="gpt-4o", # Enhanced quality
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )

        script = response.choices[0].message.content
        meta = {
            "model": "gpt-4o",
            "provider": "openai",
            "target_language": target_lang
        }
        return script.strip(), meta

    def run(self, ctx: JobContext, store: JobStore) -> None:
        base = ctx.summary or ctx.raw_text or ""
        start = time.time()
        meta: dict = {}

        if True: # Always attempt OpenAI first as per new instruction
            try:
                script, meta = self._run_openai_direct(base, ctx)
            except Exception as exc:
                store.append_log(ctx.job_id, f"OpenAI script generation failed; using fallback: {exc}")
                script = self._fallback_script(base)
                meta = {"openai_used": False, "error": str(exc)}

        meta["elapsed_seconds"] = round(time.time() - start, 2)

        ctx.script = script
        script_path = self.files.save_text(ctx.job_id, "script.txt", script)
        meta_path = self.files.save_text(ctx.job_id, "rewrite_meta.json", json.dumps(meta, indent=2))
        store.set_artifact(ctx.job_id, "script_path", str(script_path))
        store.set_artifact(ctx.job_id, "rewrite_meta_path", str(meta_path))
