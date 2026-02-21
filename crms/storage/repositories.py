"""Repository functions for rulesets, versions, evaluations."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crms.models import Evaluation, Rule, Ruleset, RulesetVersion


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


async def get_ruleset_by_jurisdiction_tax(
    db: AsyncSession, tenant_id: str, jurisdiction: str, tax_type: str
) -> Ruleset | None:
    """Find ruleset by tenant + jurisdiction + tax_type."""
    result = await db.execute(
        select(Ruleset).where(
            Ruleset.tenant_id == tenant_id,
            Ruleset.jurisdiction == jurisdiction,
            Ruleset.tax_type == tax_type,
        )
    )
    return result.scalar_one_or_none()


async def get_version_for_effective_at(
    db: AsyncSession, ruleset_id: str, effective_at: datetime
) -> RulesetVersion | None:
    """
    Resolve version where effective_from <= effective_at < effective_to
    (or effective_to is null).
    """
    result = await db.execute(
        select(RulesetVersion)
        .where(RulesetVersion.ruleset_id == ruleset_id)
        .where(RulesetVersion.effective_from <= effective_at)
        .where(
            (RulesetVersion.effective_to.is_(None))
            | (RulesetVersion.effective_to > effective_at)
        )
        .order_by(RulesetVersion.effective_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_evaluation_by_idempotency(
    db: AsyncSession, tenant_id: str, idempotency_key: str
) -> Evaluation | None:
    """Find existing evaluation for idempotency."""
    result = await db.execute(
        select(Evaluation).where(
            Evaluation.tenant_id == tenant_id,
            Evaluation.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def get_evaluation_by_id(
    db: AsyncSession, evaluation_id: str, tenant_id: str
) -> Evaluation | None:
    """Get evaluation by ID (tenant-scoped)."""
    result = await db.execute(
        select(Evaluation).where(
            Evaluation.evaluation_id == evaluation_id,
            Evaluation.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_evaluation(
    db: AsyncSession,
    tenant_id: str,
    ruleset_id: str,
    version_id: str,
    input_json: dict,
    output_json: dict,
    idempotency_key: str | None = None,
    request_hash: str | None = None,
    trace_id: str | None = None,
) -> Evaluation:
    """Create evaluation audit record."""
    ev = Evaluation(
        evaluation_id=str(uuid4()),
        tenant_id=tenant_id,
        ruleset_id=ruleset_id,
        version_id=version_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        input_json=input_json,
        output_json=output_json,
        trace_id=trace_id,
        created_at=_now_iso(),
    )
    db.add(ev)
    await db.flush()
    return ev
