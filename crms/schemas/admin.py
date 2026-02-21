"""Admin API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateRulesetRequest(BaseModel):
    """POST /v1/admin/rulesets request."""

    jurisdiction: str
    tax_type: str
    name: str


class RuleWhen(BaseModel):
    """Rule condition - supports all, any, eq, neq, etc."""

    pass  # Flexible - validated at runtime


class RuleThen(BaseModel):
    """Rule action - set taxable, rate, emit_obligations."""

    pass  # Flexible - validated at runtime


class CreateRuleRequest(BaseModel):
    """POST /v1/admin/rulesets/{id}/rules - rule payload."""

    rule_id: str
    name: str
    priority: int
    when: dict[str, Any]
    then: dict[str, Any]
    because: str = ""


class PublishRequest(BaseModel):
    """POST /v1/admin/rulesets/{id}/publish request."""

    effective_from: datetime
    change_summary: str | None = None
