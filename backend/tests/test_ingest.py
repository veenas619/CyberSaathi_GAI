import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.rag as rag
from app.config import settings


def test_embedding_retries_after_a_timeout_then_succeeds(monkeypatch):
    calls = {"n": 0}

    async def flaky(texts):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("slow")
        return [[0.1, 0.2] for _ in texts]

    async def no_sleep(_s):
        pass

    monkeypatch.setattr(rag, "embed_texts", flaky)
    monkeypatch.setattr(rag.asyncio, "sleep", no_sleep)
    assert asyncio.run(rag.embed_with_retry(["a", "b"])) == [[0.1, 0.2], [0.1, 0.2]]
    assert calls["n"] == 2


def test_persistent_timeout_gives_a_clear_message(monkeypatch):
    async def always(texts):
        raise httpx.ReadTimeout("slow")

    async def no_sleep(_s):
        pass

    monkeypatch.setattr(rag, "embed_texts", always)
    monkeypatch.setattr(rag.asyncio, "sleep", no_sleep)
    try:
        asyncio.run(rag.embed_with_retry(["a"]))
        assert False, "should have raised"
    except RuntimeError as exc:
        assert "RAG_EMBEDDING_TIMEOUT_SECONDS" in str(exc)


def test_failed_embedding_leaves_the_existing_index_untouched(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "rag_db_path", str(tmp_path / "q"))
    monkeypatch.setattr(settings, "rag_embedding_batch_size", 2)
    rag.get_qdrant.cache_clear() if hasattr(rag.get_qdrant, "cache_clear") else None
    sizes = []

    async def ok(texts):
        sizes.append(len(texts))
        return [[float(i), 1.0, 0.0] for i, _ in enumerate(texts)]

    monkeypatch.setattr(rag, "embed_texts", ok)
    docs = [{"source_id": "d1", "source": "Doc one", "text": "word " * 900, "url": "", "topic": "t"}]
    first = asyncio.run(rag.index_documents(docs))
    assert first["chunks"] >= 2 and max(sizes) <= 2           # small batches

    async def boom(texts):
        raise httpx.ReadTimeout("slow")

    async def no_sleep(_s):
        pass

    monkeypatch.setattr(rag, "embed_texts", boom)
    monkeypatch.setattr(rag.asyncio, "sleep", no_sleep)
    try:
        asyncio.run(rag.index_documents(docs))
    except RuntimeError:
        pass
    client = rag.get_qdrant()
    assert client.count(settings.rag_collection).count == first["chunks"]   # old chunks still there
