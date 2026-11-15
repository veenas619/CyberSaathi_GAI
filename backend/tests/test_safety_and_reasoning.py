import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas import EvonAnalysis
from app.services.guidance import select_guidance
from app.services.local_reasoning import _narration_signals, _apply_safety_overrides

class SafetyAndReasoningTests(unittest.TestCase):
    def test_otp_shared_triggers_credential_flag(self):
        signals = _narration_signals("I shared an OTP with the caller but no money was debited.")
        self.assertTrue(signals["credentials_shared"])
        self.assertFalse(signals["financial_loss"])

    def test_actual_debit_triggers_loss_flag(self):
        signals = _narration_signals("₹5000 was debited from my account.")
        self.assertTrue(signals["financial_loss"])

    def test_shared_credential_gets_urgent_guidance(self):
        assessment = EvonAnalysis(incident_type="otp_phishing", mode="prevention", risk_level="medium", credentials_shared_reported=True)
        _, status, _, actions = select_guidance(assessment)
        self.assertEqual(status, "urgent_protective_action")
        self.assertIn("Contact your bank immediately", [action.title for action in actions])

    def test_financial_loss_guidance_contains_official_channels(self):
        assessment = EvonAnalysis(incident_type="upi_fraud", mode="incident_response", risk_level="critical", financial_loss_reported=True)
        _, _, _, actions = select_guidance(assessment)
        destinations = [action.destination for action in actions if action.destination]
        urls = [action.url for action in actions if action.url]
        self.assertIn("1930", destinations)
        self.assertIn("https://cybercrime.gov.in/", urls)

if __name__ == "__main__":
    unittest.main()
