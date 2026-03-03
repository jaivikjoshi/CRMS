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


class ExplainOptions(BaseModel):
    """Request options for explanation level and trace."""

    explain: str = "none"  # none | winner | full
    near_miss: int = Field(default=3, ge=0, le=10)
    counterfactuals: int = Field(default=2, ge=0, le=5)


class EvaluationRequest(BaseModel):
    """POST /v1/evaluations request."""

    idempotency_key: str | None = None
    effective_at: datetime
    transaction: Transaction
    options: ExplainOptions | None = None


class Obligation(BaseModel):
    """Obligation emitted by rule."""

    type: str
    threshold: int | float | None = None
    window_days: int | None = None
    message: str | None = None


class FiredRule(BaseModel):
    """Rule that fired with explanation."""

    rule_id: str
    name: str
    because: str


class ConditionEval(BaseModel):
    """Single condition evaluation (leaf or compound)."""

    node_type: str = "leaf"  # leaf | all | any
    op: str = ""  # eq | neq | in | exists | not_exists | path_eq | path_neq | gt | gte | lt | lte
    path: str | None = None
    path2: str | None = None  # for path_eq / path_neq
    expected: Any = None
    actual: Any = None
    passed: bool = False
    reason: str | None = None


class RuleStep(BaseModel):
    """One rule evaluation step (matched or not)."""

    rule_id: str
    name: str
    priority: int
    matched: bool
    evaluated: list[ConditionEval] = Field(default_factory=list)
    missing_paths: list[str] = Field(default_factory=list)
    reason: str | None = None


class CounterfactualChange(BaseModel):
    """Suggested change to reach a different outcome."""

    path: str
    suggested_value: Any = None  # None means "provide this field"
    reason: str = ""


class Counterfactual(BaseModel):
    """Counterfactual guidance: what to change to get a different outcome."""

    goal: str  # non_taxable | lower_rate | taxable
    based_on_rule_id: str
    changes: list[CounterfactualChange] = Field(default_factory=list)
    outcome_preview: dict | None = None  # predicted result if changes applied


class EvaluationTrace(BaseModel):
    """Auditable reasoning trace."""

    winner: FiredRule | None = None
    steps: list[RuleStep] = Field(default_factory=list)
    evidence_paths_used: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    near_miss_rules: list[RuleStep] = Field(default_factory=list)
    counterfactuals: list[Counterfactual] = Field(default_factory=list)


class RiskFlag(BaseModel):
    """Risk flag from rule evaluation."""

    type: str
    severity: str = ""


class RateComponent(BaseModel):
    """Rate component for breakdown."""

    name: str
    rate: float


class EvaluationResult(BaseModel):
    """Result of evaluation."""

    taxable: bool
    rate: float
    tax_amount: float
    obligations: list[Obligation] = Field(default_factory=list)
    rate_components: list[RateComponent] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    matched_rule_id: str | None = None


class EvaluationExplanation(BaseModel):
    """Explanation of which rules fired."""

    fired_rules: list[FiredRule] = Field(default_factory=list)
    trace: EvaluationTrace | None = None


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
