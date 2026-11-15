"""Fixed, reviewed multilingual guidance.

The language model only decides WHICH situation applies (see classifier.py). The words the user
reads and hears come from app/content/messages.json, so they are fast, consistent and reviewable.
Supported languages: en-IN, hi-IN, mr-IN, ta-IN, gu-IN. Anything else falls back to English.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from app.config import settings
from app.schemas import GuideLink, GuideStep, GuidanceItem

CATALOG_PATH = Path(__file__).resolve().parents[1] / "content" / "messages.json"
DEFAULT_LANGUAGE = "en-IN"
MAX_SPEECH_CHARS = 3500  # safety cap for one spoken message (the replay endpoint accepts up to 4000)

SCENARIO_TO_PLAN = {
    "impersonation_scams": "impersonation",
    "phishing_communication": "phishing",
    "identity_account_security": "identity",
    "other_cyber_incidents": "other",
    "financial_fraud": "financial_prevention",
}


def _catalog_file() -> Path:
    """messages.json, or (if a download renamed it, e.g. 'messages (1).json') the first messages*.json beside it."""
    if CATALOG_PATH.exists():
        return CATALOG_PATH
    candidates = sorted(CATALOG_PATH.parent.glob("messages*.json"))
    return candidates[0] if candidates else CATALOG_PATH


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    return json.loads(_catalog_file().read_text(encoding="utf-8"))


def pick_language(code: str | None) -> tuple[str, bool]:
    """Return (supported language, fell_back). e.g. 'mr' -> ('mr-IN', False); 'kn-IN' -> ('en-IN', True)."""
    languages = load_catalog()["languages"]
    code = (code or DEFAULT_LANGUAGE).strip()
    if code in languages:
        return code, False
    prefix = code.split("-")[0].lower()
    for language in languages:
        if language.split("-")[0].lower() == prefix:
            return language, False
    return DEFAULT_LANGUAGE, True


def choose_plan(scenario: str, financial_loss: bool, credentials_shared: bool) -> str:
    if financial_loss:
        return "loss"
    if credentials_shared:
        return "credentials"
    return SCENARIO_TO_PLAN.get(scenario, "general")


def _text(entry: dict[str, str], language: str) -> str:
    return entry.get(language) or entry[DEFAULT_LANGUAGE]


_URGENCY_DROP_ORDER = {"informational": 0, "important": 1, "urgent": 2}  # details of the least urgent steps go first


def speech_for_steps(steps: list[GuideStep], language: str, budget: int = MAX_SPEECH_CHARS) -> str:
    """Everything the screen shows for the steps, read aloud: 'Step 1: title. detail.' for EVERY step.

    Only if the whole text would exceed `budget` characters (a very long message) are the details of the
    least urgent steps dropped, last step first, until it fits. Titles are always spoken."""
    label = _text(load_catalog()["labels"]["step"], language)
    keep_detail = [True] * len(steps)

    def render() -> str:
        parts = []
        for number, step in enumerate(steps, 1):
            parts.append(f"{label} {number}: {step.title}.")
            if keep_detail[number - 1] and step.detail:
                parts.append(step.detail)
        return " ".join(parts)

    text = render()
    drop_order = sorted(range(len(steps)), key=lambda i: (_URGENCY_DROP_ORDER[steps[i].urgency], -i))
    for index in drop_order:
        if len(text) <= budget:
            break
        keep_detail[index] = False
        text = render()
    return text


def _speech(steps: list[GuideStep], opening: str, closing: str, question: str, language: str) -> str:
    fixed = " ".join(part for part in (opening, closing, question) if part)
    steps_text = speech_for_steps(steps, language, budget=MAX_SPEECH_CHARS - len(fixed) - 10)
    return " ".join(part for part in (opening, steps_text, closing, question) if part)


def build_guide(classification, output_language: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    """Build everything the UI types and the voice speaks, from a Classification."""
    catalog = load_catalog()
    language, fell_back = pick_language(output_language)
    plan_name = choose_plan(
        classification.scenario, classification.financial_loss_reported, classification.credentials_shared_reported
    )
    plan = catalog["plans"][plan_name]

    step_ids = list(plan["steps"])
    if classification.physical_danger:
        step_ids.insert(0, "emergency_112")
    if plan_name in ("loss", "credentials") and classification.scenario in ("impersonation_scams", "phishing_communication"):
        if "chakshu" not in step_ids:
            step_ids.append("chakshu")

    def build_steps(lang: str) -> list[GuideStep]:
        result = []
        for step_id in step_ids:
            raw = catalog["steps"][step_id]
            result.append(GuideStep(
                id=step_id, title=_text(raw["title"], lang), detail=_text(raw["detail"], lang),
                urgency=raw["urgency"], destination=raw.get("destination"), url=raw.get("url"),
            ))
        return result

    def texts(lang: str) -> tuple[str, str, str]:
        return (
            _text(catalog["openings"][plan["opening"]], lang),
            _text(catalog["closings"][plan["closing"]], lang),
            _text(catalog["questions"][plan["question"]], lang) if settings.catalog_followup_question else "",
        )

    steps = build_steps(language)
    opening, closing, question = texts(language)
    en_steps = build_steps(DEFAULT_LANGUAGE)
    en_opening, en_closing, en_question = texts(DEFAULT_LANGUAGE)
    links = [GuideLink(**catalog["link_defs"][key]) for key in catalog["closing_links"][plan["closing"]]]

    return {
        "plan": plan_name,
        "language": language,
        "language_fallback": fell_back,
        "opening": opening,
        "steps": steps,
        "closing": closing,
        "links": links,
        "question": question,
        "speech_text": _speech(steps, opening, closing, question, language),
        "english_speech_text": _speech(en_steps, en_opening, en_closing, en_question, DEFAULT_LANGUAGE),
        "signature": f"{plan_name}|{language}|{'+'.join(step_ids)}",
        "actions": [
            GuidanceItem(title=s.title, detail=s.detail, destination=s.destination, url=s.url, urgency=s.urgency)
            for s in steps
        ],
    }
