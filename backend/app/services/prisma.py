from pathlib import Path
import httpx
from fastapi import HTTPException, UploadFile
from app.config import settings

PRISMA_URL = "https://api.vachana.ai/stt/v3"

async def transcribe_audio(audio: UploadFile, language_code: str | None = None) -> dict:
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
    if not settings.gnani_api_key:
        raise HTTPException(status_code=503, detail="Add GNANI_API_KEY to backend/.env.")
    filename = audio.filename or "recording.wav"
    headers = {"X-API-Key-ID": settings.gnani_api_key}
    data = {"model": settings.gnani_stt_model, "language_code": language_code or settings.gnani_stt_language, "format": settings.gnani_stt_format}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(PRISMA_URL, headers=headers, data=data, files={"audio_file": (filename, content, audio.content_type or "application/octet-stream")})
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise HTTPException(status_code=502, detail=f"Prisma API error ({exc.response.status_code}): {detail}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Prisma: {exc}") from exc
    return {"transcript": body.get("transcript", ""), "detected_language_code": body.get("detected_language_code"), "provider": "Gnani Prisma REST", "truncated": body.get("truncated", False)}
