"""Evaluation request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Transaction input - flexible for rule path access."""

    model_config = {"extra": "allow"}

    jurisdiction: str
    tax_type: str
    currency: str = "USD"
    amount: float


class EvaluationRequest(BaseModel):
    """POST /v1/evaluations request."""

    idempotency_key: str | None = None
    effective_at: datetime
    transaction: Transaction


class Obligation(BaseModel):
    """Obligation emitted by rule."""

    type: str
    threshold: int | float | None = None
    window_days: int | None = None


class FiredRule(BaseModel):
    """Rule that fired with explanation."""

    rule_id: str
    name: str
    because: str


class EvaluationResult(BaseModel):
    """Result of evaluation."""

    taxable: bool
    rate: float
    tax_amount: float
    obligations: list[Obligation] = Field(default_factory=list)


class EvaluationExplanation(BaseModel):
    """Explanation of which rules fired."""

    fired_rules: list[FiredRule] = Field(default_factory=list)


class VersionInfo(BaseModel):
    """Version metadata in response."""

    version: str
    bundle_hash: str


class RulesetInfo(BaseModel):
    """Ruleset info in response."""

    jurisdiction: str
    tax_type: str


class EvaluationResponse(BaseModel):
    """POST /v1/evaluations response."""

    evaluation_id: str
    ruleset: RulesetInfo
    version: VersionInfo
    result: EvaluationResult
    explanation: EvaluationExplanation
