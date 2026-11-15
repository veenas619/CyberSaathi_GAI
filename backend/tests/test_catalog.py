"""Catalog mode: the model only classifies; fixed, reviewed messages build the reply."""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import backend.app.main as main
import app.services.classifier as classifier
from app.config import settings
from app.services.catalog import build_guide, load_catalog, pick_language
from app.services.classifier import Classification, rules_classification

LANGS = ["en-IN", "hi-IN", "mr-IN", "ta-IN", "gu-IN"]
ALLOWED_URLS = {"https://cybercrime.gov.in/", "https://sancharsaathi.gov.in/"}
ALLOWED_DESTINATIONS = {"1930", "112", "National Cyber Crime Reporting Portal", "Chakshu on Sanchar Saathi"}


def _all_texts(catalog):
    for group in ("openings", "closings", "questions"):
        for key, entry in catalog[group].items():
            for lang, text in entry.items():
                yield f"{group}.{key}.{lang}", lang, text
    for sid, step in catalog["steps"].items():
        for part in ("title", "detail"):
            for lang, text in step[part].items():
                yield f"steps.{sid}.{part}.{lang}", lang, text


def test_every_string_exists_in_every_language_with_the_right_script():
    catalog = load_catalog()
    for name, lang, text in _all_texts(catalog):
        assert text.strip(), name
        assert "{" not in text and "}" not in text, name
    for group in ("openings", "closings", "questions"):
        for key, entry in catalog[group].items():
            assert set(entry) == set(LANGS), f"{group}.{key}"
    for sid, step in catalog["steps"].items():
        for part in ("title", "detail"):
            assert set(step[part]) == set(LANGS), f"{sid}.{part}"
    for name, lang, text in _all_texts(catalog):
        if lang in ("hi-IN", "mr-IN"):
            assert re.search("[\u0900-\u097F]", text), name
        if lang == "ta-IN":
            assert re.search("[\u0B80-\u0BFF]", text), name
        if lang == "gu-IN":
            assert re.search("[\u0A80-\u0AFF]", text), name


def test_only_verified_numbers_links_and_destinations_appear():
    catalog = load_catalog()
    for name, lang, text in _all_texts(catalog):
        for number in re.findall(r"(?<!\d)\d{3,}(?!\d)", text):
            assert number in {"1930", "112"}, f"{name}: unexpected number {number}"
        assert "http" not in text and "www." not in text, name
    for sid, step in catalog["steps"].items():
        assert step["urgency"] in {"urgent", "important", "informational"}
        assert step.get("url", "https://cybercrime.gov.in/") in ALLOWED_URLS, sid
        assert step.get("destination", "1930") in ALLOWED_DESTINATIONS, sid
    for link in catalog["link_defs"].values():
        assert link["url"] in ALLOWED_URLS


def test_every_plan_points_at_things_that_exist():
    catalog = load_catalog()
    for name, plan in catalog["plans"].items():
        assert plan["opening"] in catalog["openings"], name
        assert plan["closing"] in catalog["closings"], name
        assert plan["question"] in catalog["questions"], name
        for sid in plan["steps"]:
            assert sid in catalog["steps"], f"{name}:{sid}"


def test_language_picking_and_fallback():
    assert pick_language("mr-IN") == ("mr-IN", False)
    assert pick_language("mr") == ("mr-IN", False)
    assert pick_language("gu-IN") == ("gu-IN", False)
    assert pick_language("kn-IN") == ("en-IN", True)      # Kannada is not in the catalog yet
    assert pick_language(None) == ("en-IN", False)


def test_loss_in_marathi_is_ordered_ends_with_both_links_and_speaks_a_short_script():
    cls = Classification(scenario="financial_fraud", financial_loss_reported=True)
    guide = build_guide(cls, "mr-IN")
    ids = [s.id for s in guide["steps"]]
    assert ids[:3] == ["bank_block", "call_1930", "portal"]
    assert [l.label for l in guide["links"]] == ["National Cyber Crime Reporting Portal", "Sanchar Saathi"]
    assert re.search("[\u0900-\u097F]", guide["speech_text"])
    assert guide["speech_text"].count("पायरी") == 3          # only 3 step titles are spoken
    assert guide["english_speech_text"].startswith("I'm sorry")


def test_impersonation_ends_with_the_click_the_link_for_sanchar_saathi_line():
    guide = build_guide(Classification(scenario="impersonation_scams"), "en-IN")
    assert "click the link below for Sanchar Saathi" in guide["closing"]
    assert [l.url for l in guide["links"]] == ["https://sancharsaathi.gov.in/"]
    hindi = build_guide(Classification(scenario="impersonation_scams"), "hi-IN")
    assert "संचार साथी" in hindi["closing"]
    tamil = build_guide(Classification(scenario="phishing_communication"), "ta-IN")
    assert "சஞ்சார் சாத்தி" in tamil["closing"]


def test_physical_danger_adds_112_first_and_credentials_plan_is_urgent():
    guide = build_guide(Classification(scenario="other_cyber_incidents", physical_danger=True), "en-IN")
    assert guide["steps"][0].id == "emergency_112" and guide["steps"][0].destination == "112"
    creds = build_guide(Classification(scenario="financial_fraud", credentials_shared_reported=True), "en-IN")
    assert creds["plan"] == "credentials" and creds["steps"][0].urgency == "urgent"


def test_rules_classification_and_merge_never_lower_urgency():
    assert rules_classification("₹5000 was debited from my account").financial_loss_reported
    merged = classifier._merge(Classification(scenario="general_prevention"), Classification(scenario="phishing_communication", financial_loss_reported=True))
    assert merged.financial_loss_reported and merged.scenario == "phishing_communication"


def test_classification_call_is_tiny_and_bad_output_falls_back_to_rules(monkeypatch):
    seen = {}

    async def fake_chat(messages, num_predict=1400, label="chat"):
        seen["num_predict"] = num_predict
        return "this is not json at all"                       # e.g. a model that rambled in Gujarati

    monkeypatch.setattr(classifier, "_chat", fake_chat)
    cls, engine = asyncio.run(classifier.classify("₹5000 was debited from my account"))
    assert seen["num_predict"] <= 150
    assert engine == "rules_classifier" and cls.financial_loss_reported


def test_api_returns_typed_steps_links_and_language_fallback(monkeypatch):
    monkeypatch.setattr(settings, "reasoning_mode", "catalog")

    async def fake_classify(narration):
        return Classification(scenario="impersonation_scams"), "local_qwen_classifier"

    async def fake_retrieve(_q, limit=None):
        return []

    monkeypatch.setattr(main, "classify", fake_classify)
    monkeypatch.setattr(main, "retrieve_context", fake_retrieve)
    client = TestClient(main.app)
    body = client.post("/api/incidents/analyze", json={"narration": "Someone says my brother had an accident", "output_language": "ta-IN"}).json()
    assert body["engine"] == "local_qwen_classifier" and body["language"] == "ta-IN" and not body["language_fallback"]
    assert [s["id"] for s in body["steps"]][:2] == ["dont_pay_share", "verify_directly"]
    assert body["links"][0]["label"] == "Sanchar Saathi" and body["opening"] and body["closing"] and body["steps_signature"]
    gujarati = client.post("/api/incidents/analyze", json={"narration": "Someone says my brother had an accident", "output_language": "kn-IN"}).json()
    assert gujarati["language"] == "en-IN" and gujarati["language_fallback"] is True


def test_instant_analysis_uses_the_catalog_and_no_model(monkeypatch):
    monkeypatch.setattr(settings, "reasoning_mode", "catalog")

    async def boom(*a, **k):
        raise AssertionError("instant analysis must not call the model")

    monkeypatch.setattr(classifier, "_chat", boom)
    result = main.instant_analysis("₹5000 was debited from my account", "hi-IN")
    assert result.engine == "instant_rules" and result.status == "urgent_response"
    assert result.steps and result.steps[0].id == "bank_block" and result.language == "hi-IN"


def test_gujarati_guidance_is_complete_and_speaks_in_gujarati():
    guide = build_guide(Classification(scenario="impersonation_scams"), "gu-IN")
    assert guide["language"] == "gu-IN" and not guide["language_fallback"]
    assert re.search("[\u0A80-\u0AFF]", guide["speech_text"]) and "સંચાર સાથી" in guide["closing"]
    assert guide["speech_text"].count("પગલું") == 3
    loss = build_guide(Classification(scenario="financial_fraud", financial_loss_reported=True), "gu-IN")
    assert [s.id for s in loss["steps"]][:2] == ["bank_block", "call_1930"]
