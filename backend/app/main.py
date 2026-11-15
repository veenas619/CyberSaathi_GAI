from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import asyncio
import json
import time
from contextlib import asynccontextmanager
import websockets

from app.config import settings
from app.schemas import AnalyzeRequest, AnalyzeResponse, SpeechRequest
from app.services.catalog import MAX_SPEECH_CHARS, build_guide, speech_for_steps
from app.services.classifier import Classification, _merge as merge_classifications, classify, rules_classification
from app.services.guard import guard_text, script_matches
from app.services.local_reasoning import run_reasoning_loop, fallback_rules_analysis, generate_local_summaries, warm_up_models, _narration_signals
from app.services.guidance import select_guidance
from app.services.prisma import transcribe_audio
from app.services.timbre import synthesize_speech
from app.services.rag import retrieve_context, format_context, collection_status

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the local models in the background so the first real request is not slow.
    warm_task = asyncio.create_task(warm_up_models())
    yield
    warm_task.cancel()


app = FastAPI(
    title="CyberSaathi API",
    description="Voice-first cybersecurity prevention and incident-response prototype (guest mode).",
    version="1.1.0",
    lifespan=lifespan,
)

origins = [item.strip() for item in settings.frontend_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "CyberSaathi API is running.", "version": "1.0.0"}


@app.get("/api/rag/status")
def rag_status():
    try:
        return collection_status()
    except Exception as exc:
        return {
            "enabled": settings.rag_enabled,
            "collection_ready": False,
            "error": str(exc)[:250],
            "embedding_runtime": "local Ollama",
            "vector_database": "local Qdrant",
        }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "providers": {
            "gnani_speech_key_configured": bool(settings.gnani_api_key),
            "reasoning_provider": "local_ollama",
            "reasoning_model": settings.reasoning_model,
            "summary_provider": "local_qwen3",
            "rag_enabled": settings.rag_enabled,
        },
    }



CATALOG_DISCLAIMER = (
    "Prototype guidance only. This is not confirmation that a crime occurred. The steps are fixed, reviewed guidance; "
    "verify urgent steps with your bank or official authorities. Never share OTPs, PINs or passwords with this app."
)


def _guide_response(
    classification, engine: str, guide: dict, retrieved: list[dict], output_language: str, summary_provider: str,
    opening: str | None = None, speech: str | None = None, english: str | None = None,
    question: str | None = None, detailed: str = "", passes: int | None = None, reasoning: str | None = None,
) -> AnalyzeResponse:
    loss = classification.financial_loss_reported
    creds = classification.credentials_shared_reported
    danger = classification.physical_danger
    if loss or danger:
        status, risk, mode = "urgent_response", "critical" if loss else "high", "incident_response"
    elif creds:
        status, risk, mode = "urgent_protective_action", "high", "incident_response"
    elif guide["plan"] == "general":
        status, risk, mode = "needs_clarification", "low", "needs_clarification"
    elif guide["plan"] == "financial_prevention":
        status, risk, mode = "prevention", "low", "prevention"
    else:
        status, risk, mode = "prevention", "medium", "prevention"
    return AnalyzeResponse(
        engine=engine,
        incident_type=classification.incident_type,
        scenario=classification.scenario,
        mode=mode,
        category=classification.scenario,
        status=status,
        summary=speech if speech is not None else guide["speech_text"],
        events=[], confirmed_facts=[], claims_by_others=[], suspicious_indicators=[], unknowns=[], questions=[],
        financial_loss_reported=loss,
        credentials_shared_reported=creds,
        risk_level=risk,
        detailed_analysis=detailed,
        english_summary=english if english is not None else guide["english_speech_text"],
        localized_summary=speech if speech is not None else guide["speech_text"],
        short_reasoning=reasoning or "The model only classified the situation; the guidance comes from fixed, reviewed messages.",
        actions=guide["actions"],
        disclaimer=CATALOG_DISCLAIMER,
        rag_used=bool(retrieved),
        retrieved_sources=[
            {"source": r["source"], "url": r["url"], "topic": r["topic"], "score": r["score"]} for r in retrieved
        ],
        opening=opening if opening is not None else guide["opening"], steps=guide["steps"], closing=guide["closing"], links=guide["links"],
        question=question if question is not None else guide["question"], steps_signature=guide["signature"],
        language=guide["language"], language_fallback=guide["language_fallback"],
        summary_provider=summary_provider,
        output_language=output_language,
        reasoning_passes=passes if passes is not None else (1 if engine == "local_qwen_classifier" else 0),
    )


async def _safe_retrieve(narration: str) -> list[dict]:
    try:
        return await retrieve_context(narration)
    except Exception as rag_exc:
        print(f"[RAG] Retrieval unavailable; continuing without evidence: {str(rag_exc)[:250]}")
        return []


async def build_catalog_analysis(narration: str, output_language: str) -> AnalyzeResponse:
    """Classification-only model call + fixed multilingual guidance. Retrieval runs in parallel."""
    started = time.perf_counter()
    retrieval = asyncio.create_task(_safe_retrieve(narration))
    classification, engine = await classify(narration)
    classify_seconds = time.perf_counter() - started
    retrieved = await retrieval
    guide = build_guide(classification, output_language)
    print(f"[TIMING:catalog] classify={classify_seconds:.1f}s total={time.perf_counter() - started:.1f}s plan={guide['plan']} lang={guide['language']}")
    return _guide_response(classification, engine, guide, retrieved, output_language, summary_provider=engine)

def _fallback_response(narration: str, output_language: str, retrieved: list[dict]) -> AnalyzeResponse:
    """Model unavailable: show the reviewed guidance, honestly labelled 'Rules-based guidance' (never as AI output)."""
    classification = rules_classification(narration)
    guide = build_guide(classification, output_language)
    return _guide_response(
        classification, "fallback_rules_after_local_reasoning_error", guide, retrieved, output_language,
        summary_provider="rules_fallback", passes=0,
        reasoning="The local AI model could not answer in time; reviewed guidance is shown instead.",
    )


def _first_question(questions: list[str], output_language: str) -> str:
    for question in questions:
        question = question.strip()
        if question and script_matches(question, output_language):
            return question
    return ""


async def build_authored_analysis(narration: str, output_language: str) -> AnalyzeResponse:
    """The model writes a message tailored to this narration. Verified steps and links stay beside it.

    Safety rails (all in code, none of them replace the model's wording unless it is unusable):
    - invented links/phone numbers are removed;
    - the message must be in the requested script, otherwise the reviewed text for that language is used;
    - if money was lost, the spoken text always includes the reviewed 'call your bank / 1930' lines;
    - a model failure or timeout shows the reviewed guidance, labelled as such (or HTTP 503 if policy=error).
    """
    started = time.perf_counter()
    narration = narration[-8000:]
    retrieved = await _safe_retrieve(narration)
    rag_seconds = time.perf_counter() - started
    try:
        result, engine = await asyncio.wait_for(
            run_reasoning_loop(narration, output_language, format_context(retrieved), authored=True),
            timeout=settings.reasoning_budget_seconds,
        )
    except Exception as exc:
        reason = "timed out" if isinstance(exc, asyncio.TimeoutError) else f"{type(exc).__name__}: {str(exc)[:200]}"
        print(f"[AI] Local model failed ({reason}); policy={settings.model_failure_policy}")
        if settings.model_failure_policy.lower() == "error":
            raise HTTPException(
                status_code=503,
                detail="CyberSaathi's local AI model could not complete this analysis. Check that Ollama is running and the configured model is available, then retry.",
            ) from exc
        return _fallback_response(narration, output_language, retrieved)

    model_view = Classification(
        scenario=result.scenario, incident_type=result.incident_type or "unclear",
        financial_loss_reported=result.financial_loss_reported,
        credentials_shared_reported=result.credentials_shared_reported,
    )
    classification = merge_classifications(model_view, rules_classification(narration))  # rules may only raise urgency
    guide = build_guide(classification, output_language)

    # 1) pick the model's own message in the requested language, if it is usable
    wants_native = not output_language.lower().startswith("en")
    summary_provider = "local_qwen3"
    message = (result.localized_summary if wants_native else result.english_summary).strip()
    if wants_native and not script_matches(message, output_language):
        message = ""
    if not message:
        if wants_native and not guide["language_fallback"]:
            message = guide["opening"]            # reviewed text in the requested language
            summary_provider = "rules_fallback"
        else:
            message = result.english_summary.strip()
            if not message:
                message = guide["opening"]
                summary_provider = "rules_fallback"

    # 2) remove anything unverified, then guarantee the urgent lines when money was lost
    message, removed = guard_text(message, narration, retrieved)
    if removed:
        print(f"[GUARD] Removed {removed} unverified link(s)/number(s) from the model's message.")
    if classification.financial_loss_reported and "1930" not in message:
        message = " ".join(step.title + "." for step in guide["steps"][:2]) + " " + message

    english = guard_text(result.english_summary.strip(), narration, retrieved)[0] or guide["english_speech_text"]
    question = "" if "?" in message else (_first_question(result.questions, output_language) or guide["question"])
    # Read EVERYTHING that is shown: the model's message, every step with its detail, the link line, the question.
    fixed = " ".join(part for part in (message, guide["closing"], question) if part)
    steps_text = speech_for_steps(guide["steps"], guide["language"], budget=MAX_SPEECH_CHARS - len(fixed) - 10)
    speech = " ".join(part for part in (message, steps_text, guide["closing"], question) if part)
    print(f"[TIMING:authored] retrieval={rag_seconds:.1f}s total={time.perf_counter() - started:.1f}s plan={guide['plan']} provider={summary_provider}")
    return _guide_response(
        classification, engine, guide, retrieved, output_language, summary_provider=summary_provider,
        opening=message, speech=speech, english=english, question=question,
        detailed=result.detailed_analysis, passes=1,
        reasoning=result.short_reasoning or "The local model wrote this message; the steps and links are reviewed guidance.",
    )


async def build_analysis(narration: str, output_language: str = "en-IN") -> AnalyzeResponse:
    mode = settings.reasoning_mode.lower()
    if mode == "catalog":
        return await build_catalog_analysis(narration, output_language)
    if mode in ("authored", "fast"):
        return await build_authored_analysis(narration, output_language)
    # Raw narration is used only by local retrieval and the local reasoning model.
    started = time.perf_counter()
    retrieved = []
    try:
        retrieved = await retrieve_context(narration)
    except Exception as rag_exc:
        print(f"[RAG] Retrieval unavailable; local reasoning will continue without evidence: {str(rag_exc)[:250]}")
    rag_seconds = time.perf_counter() - started

    try:
        model_result, engine = await run_reasoning_loop(
            narration,
            output_language,
            retrieved_context=format_context(retrieved),
        )
    except Exception as exc:
        import traceback
        print(
            f"[LOCAL_REASONING] {type(exc).__name__}: {exc!r}\n"
            f"{traceback.format_exc()}"
        )
        model_result = fallback_rules_analysis(narration)
        engine = "fallback_rules_after_local_reasoning_error"

    print(f"[TIMING:analysis] retrieval={rag_seconds:.1f}s reasoning+summaries={time.perf_counter() - started - rag_seconds:.1f}s total={time.perf_counter() - started:.1f}s")
    category, status, fallback_summary, actions = select_guidance(model_result)
    summary_provider = "rules_fallback" if engine == "fallback_rules_after_local_reasoning_error" else "local_qwen3"

    # Qwen3 performs a separate local summary/translation task after reasoning
    # and Python safety guidance. No narration or RAG passages leave this machine.
    if engine != "fallback_rules_after_local_reasoning_error" and (not model_result.english_summary.strip() or not model_result.localized_summary.strip()):
        try:
            english, localized = await generate_local_summaries(model_result, actions, output_language)
            model_result.english_summary = english
            model_result.localized_summary = localized
        except Exception as summary_exc:
            print(f"[LOCAL_SUMMARY] Qwen summary failed; retaining safe fallback: {str(summary_exc)[:250]}")
            summary_provider = "local_rules_summary_fallback"

    # Deterministic actions are always exposed as structured UI actions. For
    # urgent incidents, make sure the spoken English summary cannot omit them.
    english = model_result.english_summary or fallback_summary
    if model_result.financial_loss_reported:
        required = "Contact your bank immediately, call 1930 promptly, and file a complaint at https://cybercrime.gov.in/."
        if "1930" not in english or "cybercrime.gov.in" not in english:
            english = required + " " + english
    elif model_result.credentials_shared_reported:
        required = "Contact the affected bank or provider immediately through an independently verified official channel and ask it to secure the affected account."
        if "contact" not in english.lower() or "bank" not in english.lower() or "secure" not in english.lower():
            english = required + " " + english
    localized = model_result.localized_summary or english
    if model_result.financial_loss_reported and ("1930" not in localized or "cybercrime.gov.in" not in localized):
        # Fail safely rather than speak a translation that omits mandatory reporting.
        localized = english

    return AnalyzeResponse(
        engine=engine,
        incident_type=model_result.incident_type,
        scenario=model_result.scenario,
        mode=model_result.mode,
        category=category,
        status=status,
        summary=english,
        events=model_result.events,
        confirmed_facts=model_result.confirmed_facts,
        claims_by_others=model_result.claims_by_others,
        suspicious_indicators=model_result.suspicious_indicators,
        unknowns=model_result.unknowns,
        questions=model_result.questions,
        financial_loss_reported=model_result.financial_loss_reported,
        credentials_shared_reported=model_result.credentials_shared_reported,
        risk_level=model_result.risk_level,
        detailed_analysis=model_result.detailed_analysis,
        english_summary=english,
        localized_summary=localized,
        short_reasoning=model_result.short_reasoning,
        actions=actions,
        disclaimer=(
            "Prototype guidance only. This is not confirmation that a crime occurred. "
            "The system may misunderstand a narration. Verify urgent steps with your bank or official authorities. "
            "Never share OTPs, PINs, passwords or full banking credentials with this app."
        ),
        rag_used=bool(retrieved),
        retrieved_sources=[
            {"source": item["source"], "url": item["url"], "topic": item["topic"], "score": item["score"]}
            for item in retrieved
        ],
        summary_provider=summary_provider,
        output_language=output_language,
        reasoning_passes=2 if engine == "local_qwen_reasoning_loop" else 0,
    )

def instant_analysis(narration: str, output_language: str = "en-IN") -> AnalyzeResponse:
    """Rules-only safety response in milliseconds. Shown at once while the local model works.

    Uses the same conservative signals and fixed guidance as the fallback; it never calls a model.
    """
    if settings.reasoning_mode.lower() != "detailed":
        classification = rules_classification(narration)
        guide = build_guide(classification, output_language)
        return _guide_response(classification, "instant_rules", guide, [], output_language, summary_provider="instant_rules")
    base = fallback_rules_analysis(narration)
    signals = _narration_signals(narration)
    if signals["financial_loss"]:
        text = ("It sounds like money may have left your account. Contact your bank now through its official number, "
                "call 1930 and report at cybercrime.gov.in. A fuller analysis is on its way.")
    elif signals["credentials_shared"] or signals["remote_access"] or signals["clicked_or_installed"]:
        text = ("You may have exposed a credential or approved something. Contact your bank or the provider now through an official "
                "channel and ask them to secure your account. A fuller analysis is on its way.")
    else:
        text = ("While I analyse this in detail: do not share any OTP, PIN or password, and do not send money to anyone who contacted you. "
                "Verify through official contact details.")
    base.english_summary = text
    base.localized_summary = text
    base.detailed_analysis = ""
    base.short_reasoning = "Instant rules-based safety check shown while the local model analyses the narration."
    category, status, _summary, actions = select_guidance(base)
    return AnalyzeResponse(
        engine="instant_rules",
        incident_type=base.incident_type,
        scenario=base.scenario,
        mode=base.mode,
        category=category,
        status=status,
        summary=text,
        events=[],
        confirmed_facts=[],
        claims_by_others=[],
        suspicious_indicators=[],
        unknowns=[],
        questions=[],
        financial_loss_reported=base.financial_loss_reported,
        credentials_shared_reported=base.credentials_shared_reported,
        risk_level=base.risk_level,
        detailed_analysis="",
        english_summary=text,
        localized_summary=text,
        short_reasoning=base.short_reasoning,
        actions=actions,
        disclaimer="Quick safety check only; the fuller analysis follows shortly.",
        rag_used=False,
        retrieved_sources=[],
        summary_provider="instant_rules",
        output_language=output_language,
        reasoning_passes=0,
    )


@app.post("/api/incidents/analyze", response_model=AnalyzeResponse)
async def analyze_incident(request: AnalyzeRequest):
    return await build_analysis(request.narration, request.output_language)


@app.post("/api/audio/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language_code: str | None = Form(default=None),
):
    return await transcribe_audio(file, language_code)


@app.post("/api/speech/synthesize")
async def speak(request: SpeechRequest):
    audio_bytes = await synthesize_speech(request.text, request.language, request.voice)
    return Response(content=audio_bytes, media_type="audio/wav")


@app.post("/api/incidents/voice")
async def voice_incident(
    file: UploadFile = File(...),
    language_code: str | None = Form(default=None),
):
    transcription = await transcribe_audio(file, language_code)
    analysis = await build_analysis(transcription["transcript"], "en-IN")
    return {
        "transcript": transcription["transcript"],
        "analysis": analysis.model_dump(),
    }


@app.websocket("/api/live")
async def live_voice(websocket: WebSocket):
    """Stream Prisma STT while a tracked task analyses a completed turn and streams Timbre audio."""
    output_language = websocket.query_params.get("output_language", "en-IN")
    await websocket.accept()
    if not settings.gnani_api_key:
        await websocket.send_json({"type": "error", "message": "GNANI_API_KEY is missing in backend/.env."})
        await websocket.close(code=1011)
        return

    stt_headers = {
        "x-api-key-id": settings.gnani_api_key,
        "language_code": settings.gnani_stt_language,
        "model": settings.gnani_stt_model,
        "format": settings.gnani_stt_format,
        "x-sample-rate": "16000",
        "x-vad-threshold": "0.55",
        "x-min-silence-ms": "650",
        "x-min-speech-ms": "100",
        "x-idle-timeout-sec": "120",
    }
    transcript_parts: list[str] = []
    transcript_lock = asyncio.Lock()
    send_lock = asyncio.Lock()
    analysis_lock = asyncio.Lock()
    turn_requested = False
    client_disconnected = asyncio.Event()
    process_task: asyncio.Task | None = None

    async def send(payload: dict) -> bool:
        """Return False instead of letting a closed browser socket crash background work."""
        if client_disconnected.is_set():
            return False
        async with send_lock:
            if client_disconnected.is_set():
                return False
            try:
                await websocket.send_json(payload)
                return True
            except (WebSocketDisconnect, RuntimeError):
                client_disconnected.set()
                return False

    async def process_turn():
        nonlocal turn_requested
        try:
            async with analysis_lock:
                async with transcript_lock:
                    narration = " ".join(part.strip() for part in transcript_parts if part.strip()).strip()
                    transcript_parts.clear()
                if len(narration) < 5:
                    await send({"type": "turn_error", "message": "I didn't receive enough speech. Please try again."})
                    return
                narration = narration[:8000]
                if not await send({"type": "analysis_started", "message": "Analysing your complete narration…"}):
                    return
                if not await send({"type": "interim", "transcript": narration, "analysis": instant_analysis(narration, output_language).model_dump()}):
                    return
                analysis = await build_analysis(narration, output_language)
                if not await send({"type": "analysis", "transcript": narration, "analysis": analysis.model_dump()}):
                    return
                if not await send({"type": "speech_started", "message": "CyberSaathi is preparing your spoken guidance…"}):
                    return

                tts_headers = {"X-API-Key-ID": settings.gnani_api_key}
                try:
                    async with websockets.connect(
                        "wss://api.vachana.ai/api/v1/tts",
                        additional_headers=tts_headers,
                        max_size=2**22,
                        open_timeout=30,
                        close_timeout=10,
                    ) as timbre:
                        await timbre.send(json.dumps({
                            "text": analysis.localized_summary or analysis.english_summary,
                            "voice": settings.gnani_tts_voice,
                            "model": settings.gnani_tts_model,
                            "language": output_language or settings.gnani_tts_language,
                            "speed": 1.0,
                            "audio_config": {"sample_rate": 48000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "raw"},
                        }))
                        async for tts_raw in timbre:
                            if client_disconnected.is_set():
                                break
                            try:
                                tts_event = json.loads(tts_raw)
                            except (json.JSONDecodeError, TypeError):
                                continue
                            if tts_event.get("type") == "audio":
                                data = tts_event.get("data", {})
                                if not await send({"type": "audio", "audio": data.get("audio", ""), "chunk_index": data.get("chunk_index", 0), "sample_rate": 48000}):
                                    break
                            elif tts_event.get("type") == "complete":
                                await send({"type": "audio_complete"})
                                break
                            elif tts_event.get("type") == "error":
                                await send({"type": "tts_error", "message": tts_event.get("message", "Timbre synthesis failed")})
                                break
                except asyncio.CancelledError:
                    raise
                except Exception as tts_exc:
                    await send({"type": "tts_error", "message": f"Timbre could not speak the response: {type(tts_exc).__name__}: {str(tts_exc)[:180]}"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            import traceback
            print(f"[LIVE_TURN] {type(exc).__name__}: {exc!r}\n{traceback.format_exc()}")
            await send({"type": "error", "message": f"Analysis failed: {type(exc).__name__}: {str(exc)[:180]}"})
        finally:
            turn_requested = False

    try:
        async with websockets.connect(
            "wss://api.vachana.ai/stt/v3/stream",
            additional_headers=stt_headers,
            max_size=2**22,
            ping_interval=20,
            open_timeout=30,
            close_timeout=10,
        ) as prisma:
            await send({"type": "ready", "message": "Prisma connected. Describe the complete incident, then select Analyse & respond.", "provider": "Prisma v3.0"})

            async def browser_to_prisma():
                nonlocal turn_requested, process_task
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        client_disconnected.set()
                        break
                    audio = message.get("bytes")
                    if audio:
                        await prisma.send(audio)
                    elif message.get("text"):
                        try:
                            command = json.loads(message["text"])
                        except json.JSONDecodeError:
                            continue
                        if command.get("type") == "finish_turn" and not turn_requested:
                            turn_requested = True
                            process_task = asyncio.create_task(process_turn(), name="cybersaathi-process-turn")
                        elif command.get("type") == "stop":
                            await prisma.close()
                            break

            async def prisma_to_browser():
                async for raw in prisma:
                    try:
                        event = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if event.get("type") == "transcript" and event.get("text", "").strip():
                        transcript = event["text"].strip()
                        async with transcript_lock:
                            if transcript_parts and transcript.startswith(transcript_parts[-1]):
                                transcript_parts[-1] = transcript
                            elif transcript_parts and transcript_parts[-1].startswith(transcript):
                                pass
                            elif not transcript_parts or transcript != transcript_parts[-1]:
                                transcript_parts.append(transcript)
                            combined = " ".join(transcript_parts)
                        if not await send({"type": "transcript", "text": transcript, "combined_text": combined, "language": event.get("detected_language_code"), "latency_ms": event.get("latency")}):
                            break
                    elif event.get("type") in ("connected", "speech_start", "processing"):
                        if not await send({"type": event["type"]}):
                            break
                    elif event.get("type") == "error":
                        if not await send({"type": "error", "message": event.get("message", "Prisma stream error")}):
                            break

            sender = asyncio.create_task(browser_to_prisma(), name="cybersaathi-browser-to-prisma")
            receiver = asyncio.create_task(prisma_to_browser(), name="cybersaathi-prisma-to-browser")
            done, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                if not task.cancelled():
                    exception = task.exception()
                    if exception:
                        raise exception
    except WebSocketDisconnect:
        client_disconnected.set()
    except asyncio.CancelledError:
        client_disconnected.set()
        raise
    except Exception as exc:
        print(f"[LIVE_SESSION] {type(exc).__name__}: {exc!r}")
        await send({"type": "error", "message": f"Live session failed: {type(exc).__name__}: {str(exc)[:250]}"})
    finally:
        client_disconnected.set()
        if process_task and not process_task.done():
            process_task.cancel()
            await asyncio.gather(process_task, return_exceptions=True)
        try:
            await websocket.close()
        except Exception:
            pass

