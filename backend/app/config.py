from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    gnani_api_key: str = ""
    gnani_stt_language: str = "indic-auto"
    gnani_stt_model: str = "prisma-v3.0"
    gnani_stt_format: str = "transcribe"
    gnani_tts_voice: str = "Shivani"
    gnani_tts_model: str = "timbre-v3.0"
    gnani_tts_language: str = "auto"
    catalog_followup_question: bool = False
    # Local reasoning model served by Ollama. Raw narration never leaves this machine.
    reasoning_model: str = "qwen3:4b"
    reasoning_timeout_seconds: int = 180
    reasoning_context_tokens: int = 8192
    # "authored": the model writes a message tailored to the narration; verified steps and links are shown with it.
    # "catalog": the model only classifies; fixed reviewed messages build the whole reply (fastest, safest).
    # "fast": compact prompt + short JSON. "detailed": the long full analysis.
    reasoning_mode: str = "authored"
    # What to do if the local model fails or runs out of time: "fallback" = show the reviewed safety guidance
    # (clearly labelled "Rules-based guidance"); "error" = return HTTP 503 and show nothing.
    model_failure_policy: str = "fallback"
    reasoning_budget_seconds: int = 120    # give up on the model after this long (guidance is already on screen)
    reasoning_num_predict_indic: int = 700  # Indic scripts need more tokens per word than English
    reasoning_keep_alive: str = "30m"      # keep the model in RAM between requests (avoids reload delays)
    reasoning_num_predict_fast: int = 450  # max output tokens in fast mode
    reasoning_num_predict_classify: int = 120  # max output tokens for the classification-only call
    reasoning_context_chars: int = 1500    # max characters of retrieved passages given to the model

    # Local RAG: Ollama creates embeddings; Qdrant stores vectors on this machine.
    rag_enabled: bool = True
    rag_collection: str = "cybersaathi_knowledge"
    rag_db_path: str = "data/qdrant"
    rag_top_k: int = 5
    rag_score_threshold: float = 0.35
    rag_embedding_model: str = "bge-m3"
    rag_embedding_timeout_seconds: int = 300
    rag_embedding_batch_size: int = 4      # chunks per Ollama request; smaller = safer on a CPU laptop
    ollama_base_url: str = "http://127.0.0.1:11434"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
