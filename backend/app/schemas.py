from typing import Literal
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    narration: str = Field(min_length=5, max_length=8000)
    output_language: str = Field(default="en-IN", min_length=2, max_length=20)


class Event(BaseModel):
    type: str
    description: str
    sequence: int = 0
    confidence: Literal["high", "medium", "low"] = "medium"


class EvonAnalysis(BaseModel):
    incident_type: str = "unclear"
    scenario: Literal["general_prevention", "financial_fraud", "impersonation_scams", "phishing_communication", "identity_account_security", "other_cyber_incidents"] = "general_prevention"
    mode: Literal["prevention", "incident_response", "needs_clarification"] = "needs_clarification"
    events: list[Event] = Field(default_factory=list)
    confirmed_facts: list[str] = Field(default_factory=list)
    claims_by_others: list[str] = Field(default_factory=list)
    suspicious_indicators: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    financial_loss_reported: bool = False
    credentials_shared_reported: bool = False
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    detailed_analysis: str = ""
    english_summary: str = ""
    localized_summary: str = ""
    short_reasoning: str = ""


class GuidanceItem(BaseModel):
    title: str
    detail: str
    destination: str | None = None
    url: str | None = None
    urgency: Literal["urgent", "important", "informational"] = "informational"


class GuideStep(BaseModel):
    id: str
    title: str
    detail: str
    urgency: Literal["urgent", "important", "informational"] = "informational"
    destination: str | None = None
    url: str | None = None


class GuideLink(BaseModel):
    label: str
    url: str


class RetrievedSource(BaseModel):
    source: str
    url: str = ""
    topic: str = "general"
    score: float = 0.0


class AnalyzeResponse(BaseModel):
    engine: str
    incident_type: str = "unclear"
    scenario: str = "general_prevention"
    mode: Literal["prevention", "incident_response", "needs_clarification"] = "needs_clarification"
    category: str
    status: str
    summary: str
    events: list[Event]
    confirmed_facts: list[str]
    claims_by_others: list[str] = Field(default_factory=list)
    suspicious_indicators: list[str]
    unknowns: list[str]
    questions: list[str]
    financial_loss_reported: bool = False
    credentials_shared_reported: bool = False
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    detailed_analysis: str = ""
    english_summary: str = ""
    localized_summary: str = ""
    short_reasoning: str = ""
    actions: list[GuidanceItem]
    disclaimer: str
    rag_used: bool = False
    retrieved_sources: list[RetrievedSource] = Field(default_factory=list)
    # Fixed multilingual guidance (catalog mode): the app types these one by one.
    opening: str = ""
    steps: list[GuideStep] = Field(default_factory=list)
    closing: str = ""
    links: list[GuideLink] = Field(default_factory=list)
    question: str = ""
    steps_signature: str = ""
    language: str = "en-IN"
    language_fallback: bool = False
    summary_provider: str = "local_qwen3"
    output_language: str = "en-IN"
    reasoning_passes: int = 0


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str | None = None
    voice: str | None = None
