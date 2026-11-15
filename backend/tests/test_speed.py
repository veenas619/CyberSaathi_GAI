"""Speed-related behaviour. Ollama is faked; nothing here needs a model or the network."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.local_reasoning as lr
from app.config import settings


class _FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self._content}, "eval_count": 120, "eval_duration": 12_000_000_000,
                "prompt_eval_count": 900, "prompt_eval_duration": 3_000_000_000, "load_duration": 0}


def _fake_client(captured, content='{"incident_type":"x"}'):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            captured["url"], captured["payload"] = url, json
            return _FakeResponse(content)

    return FakeClient


def test_fast_prompt_is_small():
    assert len(lr.FAST_SYSTEM_PROMPT) < 3200          # about 800 tokens
    assert len(lr.SYSTEM_PROMPT) > 3 * len(lr.FAST_SYSTEM_PROMPT)


def test_worst_case_fast_prompt_fits_the_context_window(monkeypatch):
    # Latin text ~4 chars/token; Indic scripts can be ~1.5 chars/token, so test that case on the narration too.
    tokens = (len(lr._fast_system()) + settings.reasoning_context_chars + 400) / 4 + 3000 / 1.5 + settings.reasoning_num_predict_fast
    assert tokens < 4096


def test_chat_payload_disables_thinking_and_keeps_model_loaded(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(lr.httpx, "AsyncClient", _fake_client(captured))
    asyncio.run(lr._chat([{"role": "user", "content": "hi"}], num_predict=300, label="t"))
    p = captured["payload"]
    assert p["think"] is False
    assert p["keep_alive"] == settings.reasoning_keep_alive
    assert p["options"]["num_predict"] == 300 and p["options"]["num_ctx"] <= 4096
    out = capsys.readouterr().out
    assert "[TIMING:t]" in out and "10.0 tok/s" in out


def test_fast_mode_makes_one_short_call_and_safety_overrides_still_apply(monkeypatch):
    calls = []

    async def fake_chat(messages, num_predict=1400, label="chat"):
        calls.append((messages, num_predict, label))
        return ('{"incident_type":"upi_scam","scenario":"general_prevention","mode":"prevention","risk_level":"low",'
                '"financial_loss_reported":false,"credentials_shared_reported":false,"questions":[],'
                '"english_summary":"Stay calm.","localized_summary":""}')

    monkeypatch.setattr(lr, "_chat", fake_chat)
    monkeypatch.setattr(settings, "reasoning_mode", "fast")
    result, engine = asyncio.run(lr.run_reasoning_loop("₹5000 was debited from my account.", "en-IN", "ctx"))
    assert len(calls) == 1 and calls[0][1] == settings.reasoning_num_predict_fast and calls[0][2] == "fast"
    assert result.financial_loss_reported and result.risk_level == "critical"      # model said no loss; Python overrides
    assert "1930" in result.english_summary and result.localized_summary            # English: copied, loss steps enforced


def test_long_narration_is_clipped_not_dropped():
    clipped = lr._clip_narration("A" * 100 + "M" * 5000 + "Z" * 100, 3000)
    assert len(clipped) <= 3010 and clipped.startswith("A") and clipped.endswith("Z")


def test_instant_analysis_needs_no_model_legacy_fast_mode(monkeypatch):
    import backend.app.main as main
    monkeypatch.setattr(settings, "reasoning_mode", "fast")

    async def boom(*a, **k):
        raise AssertionError("instant_analysis must not call the model")

    monkeypatch.setattr(lr, "_chat", boom)
    loss = main.instant_analysis("₹5000 was debited from my account.")
    assert loss.engine == "instant_rules" and loss.financial_loss_reported
    assert any(a.destination == "1930" for a in loss.actions)
    other = main.instant_analysis("someone sent me a strange message")
    assert "OTP" in other.english_summary
