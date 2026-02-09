from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

try:
    from llama_index.core import Document, SimpleDirectoryReader
except Exception:  # pragma: no cover - compatibility shim
    from llama_index.core import SimpleDirectoryReader  # type: ignore
    from llama_index.core.schema import Document  # type: ignore

try:
    from llama_index.readers.web import SimpleWebPageReader
except Exception:  # pragma: no cover - optional dependency guard
    SimpleWebPageReader = None

import requests # Standard library check

from ..file_store import FileStore
from ..job_store import JobStore
from ..types import JobContext

MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
NUM_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,4}|[IVXLC]+)\s*[.)]\s+(.*)$")
ALLCAPS_HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9\s\-,:;]{4,}$")
SETEXT_RE = re.compile(r"^(=+|-+)$")


class IngestionStage:
    def __init__(self, files: FileStore) -> None:
        self.files = files

    def _load_documents_from_file(self, path: Path) -> List[Document]:
        reader = SimpleDirectoryReader(input_files=[str(path)])
        return reader.load_data()

    def _load_documents_from_url(self, url: str) -> List[Document]:
        # 1. Try Jina Reader (Free, robust markdown extraction)
        try:
            print(f"Attempting to scrape via Jina: {url}")
            response = requests.get(f"https://r.jina.ai/{url}", timeout=30)
            if response.status_code == 200:
                print("Jina scrape successful")
                return [Document(text=response.text, metadata={"source": url, "scraped_by": "jina"})]
        except Exception as e:
            print(f"Jina scrape failed: {e}")

        # 2. Fallback to SimpleWebPageReader
        if SimpleWebPageReader is None:
            raise RuntimeError("SimpleWebPageReader unavailable. Install llama-index-readers-web.")
        reader = SimpleWebPageReader(html_to_text=True)
        return reader.load_data([url])

    def _metadata_source(self, doc: Document, fallback: str) -> str:
        metadata: Dict[str, str] = getattr(doc, "metadata", {}) or {}
        return (
            metadata.get("file_name")
            or metadata.get("file_path")
            or metadata.get("url")
            or metadata.get("source")
            or fallback
        )

    def _sectionize(self, text: str) -> List[Dict[str, object]]:
        lines = text.splitlines()
        sections: List[Dict[str, object]] = []
        current_title: Optional[str] = None
        current_level = 0
        current_lines: List[str] = []

        def flush() -> None:
            nonlocal current_lines, current_title, current_level
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(
                    {
                        "title": current_title,
                        "level": current_level,
                        "content": content,
                    }
                )
            current_lines = []

        index = 0
        while index < len(lines):
            raw_line = lines[index]
            line = raw_line.strip()
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""

            if line and next_line and SETEXT_RE.match(next_line):
                flush()
                current_title = line
                current_level = 1 if next_line.startswith("=") else 2
                index += 2
                continue

            match = MD_HEADING_RE.match(line)
            if match:
                flush()
                current_level = len(match.group(1))
                current_title = match.group(2).strip()
                index += 1
                continue

            match = NUM_HEADING_RE.match(line)
            if match and len(line.split()) <= 12:
                flush()
                current_level = min(match.group(1).count(".") + 1, 6)
                current_title = match.group(2).strip()
                index += 1
                continue

            if ALLCAPS_HEADING_RE.match(line) and len(line.split()) <= 8:
                flush()
                current_level = 2
                current_title = line
                index += 1
                continue

            current_lines.append(raw_line)
            index += 1

        flush()
        return sections

    def _build_structured_text(self, sections: List[Dict[str, object]]) -> str:
        blocks: List[str] = []
        for section in sections:
            title = section.get("title")
            level = int(section.get("level") or 0)
            content = str(section.get("content") or "")
            if title:
                prefix = "#" * min(max(level, 1), 6)
                blocks.append(f"{prefix} {title}")
            if content:
                blocks.append(content)
            blocks.append("")
        return "\n".join(blocks).strip()

    def run(self, ctx: JobContext, store: JobStore) -> None:
        documents: List[Document] = []
        if ctx.source_type == "file" and ctx.filename:
            path = self.files.get_path(ctx.job_id, ctx.filename)
            documents = self._load_documents_from_file(path)
        elif ctx.source_type == "url" and ctx.source_url:
            documents = self._load_documents_from_url(ctx.source_url)
        else:
            documents = [Document(text=ctx.source_text or "", metadata={"source": "direct_text"})]

        if not documents:
            raise RuntimeError("No documents loaded for ingestion")

        structured_sections: List[Dict[str, object]] = []
        for doc in documents:
            text = getattr(doc, "text", None)
            if text is None and hasattr(doc, "get_text"):
                text = doc.get_text()
            text = (text or "").strip()
            if not text:
                continue
            sections = self._sectionize(text)
            if not sections:
                sections = [{"title": None, "level": 0, "content": text}]

            source = self._metadata_source(doc, ctx.filename or ctx.source_url or "input")
            for order, section in enumerate(sections):
                structured_sections.append(
                    {
                        "order": len(structured_sections) + 1,
                        "title": section.get("title"),
                        "level": section.get("level"),
                        "content": section.get("content"),
                        "source": source,
                    }
                )

        structured_text = self._build_structured_text(structured_sections)
        if not structured_text:
            structured_text = ""

        ctx.raw_text = structured_text

        raw_path = self.files.save_text(ctx.job_id, "raw.txt", structured_text)
        structured_path = self.files.save_text(
            ctx.job_id,
            "structured.json",
            json.dumps({"sections": structured_sections}, indent=2, ensure_ascii=False),
        )

        store.set_artifact(ctx.job_id, "raw_text_path", str(raw_path))
        store.set_artifact(ctx.job_id, "structured_path", str(structured_path))
