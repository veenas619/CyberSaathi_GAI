"""Index PDFs, Markdown and text files into CyberSaathi's local Qdrant store.

Run from backend/: python scripts/ingest_documents.py
Drop trusted source documents into knowledge_base/raw/ before running.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from pypdf import PdfReader  # noqa: E402
from app.services.rag import index_documents  # noqa: E402

RAW_DIR = BACKEND_DIR / "knowledge_base" / "raw"
SUPPORTED = {".pdf", ".md", ".txt"}


def read_document(path: Path) -> dict:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        page_texts = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append(f"[Page {page_number}] {text}")
        text = "\n\n".join(page_texts)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")

    url_match = re.search(r"^Source URL:\s*(\S+)", text, flags=re.MULTILINE | re.IGNORECASE)
    topic_match = re.search(r"^Topic:\s*(.+)$", text, flags=re.MULTILINE | re.IGNORECASE)
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    source = title_match.group(1).strip() if title_match else path.stem.replace("_", " ").title()
    topic = topic_match.group(1).strip() if topic_match else path.parent.name
    url = url_match.group(1).strip() if url_match else ""
    return {
        "source_id": str(path.relative_to(RAW_DIR)).replace("\\", "/"),
        "source": source,
        "url": url,
        "topic": topic,
        "published": "Review the linked official source before production use",
        "text": text,
    }


async def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in RAW_DIR.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    if not files:
        print(f"No supported documents found in {RAW_DIR}")
        return
    documents = [read_document(path) for path in files]
    print(f"Found {len(documents)} documents. Creating local embeddings; this may take a few minutes...")
    result = await index_documents(documents)
    print(f"Indexed {result['chunks']} chunks from {result['documents']} documents.")
    print("Local Qdrant collection: cybersaathi_knowledge (or your configured RAG_COLLECTION)")


if __name__ == "__main__":
    asyncio.run(main())
