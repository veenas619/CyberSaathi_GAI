# CyberSaathi — local reasoning, local summarisation, RAG and Gnani speech

CyberSaathi is a React + Tailwind frontend and FastAPI backend for multilingual cyber-safety prevention and incident response. The original teal dashboard and side-by-side text/voice layout are retained. The response-language selector remains available.

## Architecture

- **Gnani Prisma:** speech-to-text for uploaded and live voice input, with automatic language detection.
- **Local Qwen3 4B:** performs a two-pass incident reasoning and verification loop, then a separate summarisation task. It creates an English summary and a faithful localized summary for the selected response language.
- **Local RAG:** Ollama `bge-m3` embeddings and embedded Qdrant retrieve relevant passages from the local knowledge base.
- **Python safety engine:** selects official reporting destinations and mandatory protective actions. The model cannot invent or override these destinations.
- **Gnani Timbre:** text-to-speech only. It speaks the localized text produced by Qwen3; it is not relied upon to translate English text.
- **Live voice:** transcript segments are accumulated until the user presses **Analyse & respond**. Analysis and Timbre run separately from the Prisma receive loop.

Raw narration and retrieved passages stay on the local machine for reasoning and summarisation. Prisma and Timbre still process audio through Gnani services, so voice features are not fully offline.

## Windows setup

### 1. Install Ollama and download models

Install Ollama: https://ollama.com/download/windows

```powershell
ollama pull qwen3:4b
ollama pull bge-m3
ollama list
```

Keep Ollama running.

### 2. Configure backend

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and add your Gnani key:

```env
GNANI_API_KEY=YOUR_GNANI_API_KEY
GNANI_STT_LANGUAGE=indic-auto
GNANI_STT_MODEL=prisma-v3.0
GNANI_TTS_MODEL=timbre-v3.0
GNANI_TTS_VOICE=Shivani
GNANI_TTS_LANGUAGE=auto

REASONING_MODEL=qwen3:4b
REASONING_TIMEOUT_SECONDS=180
REASONING_CONTEXT_TOKENS=8192
OLLAMA_BASE_URL=http://127.0.0.1:11434

RAG_ENABLED=true
RAG_COLLECTION=cybersaathi_knowledge
RAG_DB_PATH=data/qdrant
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.35
RAG_EMBEDDING_MODEL=bge-m3
RAG_EMBEDDING_TIMEOUT_SECONDS=90
```

No Qwen3 local summarisation API key or cloud LLM API is required. Do not commit `.env` or put secrets in frontend environment variables.

### 3. Index the knowledge base

The five starter Markdown notes are in `backend/knowledge_base/raw/`. They are project-authored summaries with reference URLs, not official circulars. Verify sources and add current official material before production use.

From `backend/` run:

```powershell
python scripts/ingest_documents.py
```

Check `http://127.0.0.1:8000/api/rag/status` and confirm `collection_ready: true`.

### 4. Run the application

Backend terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Important limitations

- Qwen3 can make mistakes, including translation mistakes. Review localized emergency guidance carefully before production use.
- Critical official phone numbers and URLs are checked by deterministic backend rules; if a localized summary omits required identifiers, the English summary is used rather than dropping them.
- Prisma and Timbre send audio to Gnani services.
- RAG retrieval does not guarantee correctness. The starter notes are not official legal or regulatory documents; replace/augment them with current primary sources and evaluate retrieval quality.
- The guest-mode incident history is stored in browser localStorage, not an authenticated private account.

## API routes

- `GET /health` — local reasoning, summary and RAG configuration status.
- `GET /api/rag/status` — local collection status.
- `POST /api/incidents/analyze` — text to local RAG, Qwen reasoning, Python safety and Qwen summarisation.
- `POST /api/audio/transcribe` — Prisma transcription.
- `POST /api/speech/synthesize` — Timbre speech generation.
- `WS /api/live` — live Prisma transcription followed by local analysis and Timbre speech.


## Agent configuration and live speech
The local Qwen system prompt now incorporates CyberSaathi's supplied persona, all-fraud scope,
general_prevention starting scenario, scenario-routing criteria, Indian reporting channels,
conversation style, guardrails, and RAG trust rules. Qwen performs the reasoning and verification
passes with locally retrieved Qdrant passages. The verified assessment is then summarised locally.

Timbre begins speaking immediately after the live analysis is sent to the browser. For typed
and uploaded-audio analysis, the frontend automatically requests Timbre playback as soon as the
analysis response is ready. The response-language selector remains active; Qwen generates the
localized text before Timbre synthesizes speech.

---

## Speed update (local Qwen reasoning)

**Why it was slow**
- The system prompt was ~2,900 tokens and a worst-case prompt (prompt + narration + retrieved passages) was ~5,000 tokens, but the model's context window (`num_ctx`) was 4,096, so Ollama truncated the prompt and re-processed thousands of tokens on every request.
- One call asked the model for up to 1,400 tokens of JSON (events, facts, claims, indicators, unknowns, long analysis, two summaries). On a CPU laptop, generating tokens is the slow part.
- The model could unload between requests, and Qwen3 "thinking" could add hidden tokens.

**What changed**
- `REASONING_MODE=fast` (default): compact ~670-token prompt, small JSON (scenario, flags, risk, one question, summaries), at most 450 output tokens. For English, `localized_summary` is no longer generated (copied from English). Set `REASONING_MODE=detailed` to get the old long analysis.
- Retrieved passages given to the model are capped at `REASONING_CONTEXT_CHARS` (1,500) and long narrations are clipped (start + end) instead of overflowing.
- `think:false` and `keep_alive=30m` are sent to Ollama; both models are warmed up when the backend starts (the same prompt prefix is reused between requests).
- **Instant safety check in live mode:** a rules-only result (fixed steps, 1930/bank advice if loss or exposure is mentioned) appears on screen immediately, then the model's analysis replaces it. No model call is needed for it.
- **Timing logs** in the backend terminal, e.g. `[TIMING:fast] total=… prompt_tokens=… prefill=… output_tokens=… generate=… (N tok/s)` and `[TIMING:analysis] retrieval=… reasoning+summaries=…`. These show exactly where the time goes on your machine.

**If it is still too slow:** read the `tok/s` in `[TIMING:fast]`. Below ~5 tok/s, use a smaller model (for example `qwen3:1.7b`, set `REASONING_MODEL`), or run Ollama with GPU support if your laptop has a GPU. Tests: `python -m pytest -q tests`.
