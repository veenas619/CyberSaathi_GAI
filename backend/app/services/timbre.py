import httpx
from fastapi import HTTPException
from app.config import settings

TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

async def synthesize_speech(text: str, language: str | None = None, voice: str | None = None) -> bytes:
    if not settings.gnani_api_key:
        raise HTTPException(status_code=503, detail="Add GNANI_API_KEY to backend/.env.")
    payload = {
        "text": text, "voice": voice or settings.gnani_tts_voice,
        "model": settings.gnani_tts_model, "language": language or settings.gnani_tts_language,
        "speed": 1.0,
        "audio_config": {"sample_rate": 48000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "wav"}
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(TTS_URL, headers={"X-API-Key-ID": settings.gnani_api_key}, json=payload)
            response.raise_for_status()
            return response.content
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Timbre API error ({exc.response.status_code}): {exc.response.text[:400]}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Timbre: {exc}") from exc
