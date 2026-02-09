from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from llama_index.core import Document, SummaryIndex, Settings
except Exception:  # pragma: no cover - compatibility shim
    from llama_index.core import SummaryIndex, Settings  # type: ignore
    from llama_index.core.schema import Document  # type: ignore

try:
    from llama_index.core.node_parser import SentenceSplitter
except Exception:  # pragma: no cover - optional
    SentenceSplitter = None

try:
    from llama_index.llms.anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None

from ..file_store import FileStore
from ..job_store import JobStore
from ..types import JobContext

SUMMARY_RATIO_DEFAULT = 0.7
MIN_CHARS_FOR_SUMMARY = 800


class SummarizationStage:
    def __init__(self, files: FileStore) -> None:
        self.files = files

    def _load_structured_sections(self, path: Path) -> List[Dict[str, object]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        sections = data.get("sections") if isinstance(data, dict) else None
        if not isinstance(sections, list):
            return []
        return [section for section in sections if isinstance(section, dict)]

    def _build_documents(self, sections: List[Dict[str, object]], fallback: str) -> List[Document]:
        documents: List[Document] = []
        if not sections:
            documents.append(Document(text=fallback))
            return documents

        for section in sorted(sections, key=lambda item: item.get("order", 0)):
            title = (section.get("title") or "").strip()
            content = (section.get("content") or "").strip()
            if not content:
                continue
            if title:
                text = f"{title}\n{content}"
            else:
                text = content
            documents.append(
                Document(
                    text=text,
                    metadata={
                        "title": title,
                        "level": section.get("level"),
                        "order": section.get("order"),
                        "source": section.get("source"),
                    },
                )
            )

        if not documents:
            documents.append(Document(text=fallback))
        return documents

    def _ratio_for_length(self, length: str) -> float:
        if length == "slightly-shorter":
            return float(os.getenv("SUMMARY_RATIO", SUMMARY_RATIO_DEFAULT))
        return 1.0

    def _summarize_with_llamaindex(self, documents: List[Document], ratio: float, ctx_api_key: Optional[str] = None) -> str:
        if SentenceSplitter is not None:
            Settings.node_parser = SentenceSplitter(chunk_size=1200, chunk_overlap=100)

        # Configure LLM if Anthropic is available and key is present
        api_key = ctx_api_key or os.getenv("ANTHROPIC_API_KEY")
        if Anthropic is not None and api_key:
            model = os.getenv("CREWAI_MODEL", "claude-3-5-sonnet-20241022").replace("anthropic/", "")
            Settings.llm = Anthropic(model=model, api_key=api_key)

        index = SummaryIndex.from_documents(documents)

        summary_request = (
            "Summarize ONLY to improve listening flow. "
            "Never remove factual or technical content. "
            "Retain all facts, numbers, definitions, and cause-effect relationships. "
            "Preserve the order of ideas. If unsure, keep original phrasing. "
            f"Target length about {int(ratio * 100)}% of the original."
        )

        try:
            query_engine = index.as_query_engine(response_mode="tree_summarize")
        except TypeError:
            query_engine = index.as_query_engine()

        response = query_engine.query(summary_request)
        return str(response).strip()

    def _evaluate_summary(self, original: str, summary: str, ratio: float) -> Tuple[bool, float]:
        if not summary:
            return False, 0.0
        original_len = max(len(original), 1)
        summary_len = len(summary)
        actual_ratio = summary_len / original_len
        if ratio >= 0.95:
            return False, actual_ratio
        if actual_ratio > 1.0:
            return False, actual_ratio
        if actual_ratio < 0.35:
            return False, actual_ratio
        return True, actual_ratio

    def run(self, ctx: JobContext, store: JobStore) -> None:
        original = ctx.raw_text or ""
        ratio = self._ratio_for_length(ctx.length)

        if ratio >= 0.95 or len(original) < MIN_CHARS_FOR_SUMMARY:
            summary = original
            accepted = True
            actual_ratio = 1.0
        else:
            structured_path = self.files.get_path(ctx.job_id, "structured.json")
            sections = self._load_structured_sections(structured_path)
            documents = self._build_documents(sections, original)

            try:
                summary = self._summarize_with_llamaindex(documents, ratio, ctx.llm_api_key)
                accepted, actual_ratio = self._evaluate_summary(original, summary, ratio)
                if not accepted:
                    summary = original
            except Exception as exc:
                store.append_log(ctx.job_id, f"Summarization skipped: {exc}")
                summary = original
                accepted = False
                actual_ratio = 1.0

        ctx.summary = summary
        summary_path = self.files.save_text(ctx.job_id, "summary.txt", summary)
        meta = {
            "target_ratio": ratio,
            "actual_ratio": actual_ratio,
            "accepted": accepted,
            "original_chars": len(original),
            "summary_chars": len(summary),
        }
        meta_path = self.files.save_text(ctx.job_id, "summary_meta.json", json.dumps(meta, indent=2))

        store.set_artifact(ctx.job_id, "summary_path", str(summary_path))
        store.set_artifact(ctx.job_id, "summary_meta_path", str(meta_path))
