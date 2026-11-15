"""Build the API response for catalog mode (no FastAPI import, so it is easy to test)."""
from __future__ import annotations

from typing import Any

from app.schemas import AnalyzeResponse, EvonAnalysis
from app.services.catalog import build_guide
from app.services.classifier import Classification
from app.services.guidance import select_guidance

DISCLAIMER = (
    "Prototype guidance only. This is not confirmation that a crime occurred. "
    "The system may misunderstand a narration. Verify urgent steps with your bank or official authorities. "
    "Never share OTPs, PINs, passwords or full banking credentials with this app."
)
INSTANT_DISCLAIMER = "Quick safety check only; the fuller analysis follows shortly."


def build_catalog_response(
    cls: Classification,
    engine: str,
    output_language: str,
    retrieved: list[dict[str, Any]] | None = None,
    interim: bool = False,
) -> AnalyzeResponse:
    guide = build_guide(cls, output_language)
    loss, creds = cls.financial_loss_reported, cls.credentials_shared_reported
    risk = "critical" if loss else ("high" if creds else ("low" if cls.scenario == "general_prevention" else "medium"))
    mode = "incident_response" if (loss or creds) else ("needs_clarification" if cls.scenario == "general_prevention" else "prevention")
    # Used only to pick the category/status labels; the visible text all comes from the catalog.
    probe = EvonAnalysis(
        incident_type=cls.incident_type, scenario=cls.scenario, mode=mode, risk_level=risk,
        financial_loss_reported=loss, credentials_shared_reported=creds,
    )
    category, status, _fallback_summary, _actions = select_guidance(probe)
    retrieved = retrieved or []
    return AnalyzeResponse(
        engine=engine,
        incident_type=cls.incident_type,
        scenario=cls.scenario,
        mode=mode,
        category=category,
        status=status,
        summary=guide["english_speech_text"],
        events=[], confirmed_facts=[], claims_by_others=[], suspicious_indicators=[], unknowns=[],
        questions=[guide["question"]] if guide["question"] else [],
        financial_loss_reported=loss,
        credentials_shared_reported=creds,
        risk_level=risk,
        detailed_analysis="",
        english_summary=guide["english_speech_text"],
        localized_summary=guide["speech_text"],          # what the voice speaks, in the language of the text
        short_reasoning=(
            "Instant rules-based safety check shown while the local model classifies the narration."
            if interim else "Situation classified locally; guidance comes from fixed, reviewed messages."
        ),
        actions=guide["actions"],
        disclaimer=INSTANT_DISCLAIMER if interim else DISCLAIMER,
        rag_used=bool(retrieved),
        retrieved_sources=[
            {"source": r["source"], "url": r["url"], "topic": r["topic"], "score": r["score"]} for r in retrieved
        ],
        summary_provider="catalog_reviewed",
        output_language=guide["language"],                # the language actually used, so TTS matches the text
        reasoning_passes=1 if engine == "local_qwen_classifier" else 0,
        opening=guide["opening"],
        steps=guide["steps"],
        closing=guide["closing"],
        links=guide["links"],
        question=guide["question"],
        language=guide["language"],
        language_fallback=guide["language_fallback"],
        steps_signature=guide["signature"],
    )
