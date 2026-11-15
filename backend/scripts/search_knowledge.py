"""Quick local RAG retrieval check.
Run from backend/: python scripts/search_knowledge.py "UPI PIN refund request"
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
from app.services.rag import retrieve_context  # noqa: E402

async def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "What should I do after an unauthorised UPI debit?"
    matches = await retrieve_context(query)
    if not matches:
        print("No passages retrieved. Check Ollama, bge-m3 and whether documents were indexed.")
        return
    for index, item in enumerate(matches, 1):
        print(f"\n[{index}] {item['source']} | score={item['score']:.3f}")
        print(item['url'])
        print(item['text'][:1200])

if __name__ == "__main__":
    asyncio.run(main())
