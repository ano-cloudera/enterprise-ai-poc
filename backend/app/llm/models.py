from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisDriver(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1200)
    evidence: str = Field(min_length=1, max_length=1200)


class StructuredAnalysis(StrictModel):
    summary: str = Field(min_length=1, max_length=3000)
    drivers: list[AnalysisDriver] = Field(max_length=12)
    recommended_actions: list[str] = Field(max_length=12)
    caveats: list[str] = Field(max_length=12)


class TrustedAnalysisPayload(StrictModel):
    question: str
    language: Literal["id", "en", "auto"]
    intent: dict[str, Any]
    business_context: dict[str, Any]
    query_result: dict[str, Any]
    conversation_history: list[dict[str, str]] = []


class IntentClassification(StrictModel):
    intent: Literal["analytical", "conversational"]


class ModelTelemetry(StrictModel):
    trace_id: str
    provider: str
    model: str
    latency_ms: int
    retry_count: int
    success: bool
    fallback_used: bool = False
    http_status: int | None = None
    structured_validation_success: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error_code: str | None = None


class AnalysisResult(StrictModel):
    analysis: StructuredAnalysis
    telemetry: ModelTelemetry


class IntentClassificationResult(StrictModel):
    classification: IntentClassification
    telemetry: ModelTelemetry


class ConversationalReply(StrictModel):
    message: str = Field(min_length=1, max_length=1200)


class ConversationalReplyResult(StrictModel):
    reply: ConversationalReply
    telemetry: ModelTelemetry


class ModelHealth(StrictModel):
    mode: Literal["mock", "remote"]
    status: Literal["mock", "ok", "unavailable", "auth_required", "unknown"]
    provider: str
    model: str
