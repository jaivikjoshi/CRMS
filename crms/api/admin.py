"""Admin endpoints - rulesets, rules, publish."""

from datetime import datetime
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crms.auth.middleware import TenantDep
from crms.database import get_db
from crms.models import Rule, Ruleset, RulesetVersion
from crms.schemas.admin import CreateRulesetRequest, CreateRuleRequest, PublishRequest
from crms.utils.canonical import bundle_hash

router = APIRouter()


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "exists", "all", "any"}


def _validate_rule_when(when: dict) -> None:
    """Validate rule 'when' structure and operators."""
    if not when:
        return
    for key in when:
        if key not in ALLOWED_OPERATORS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid operator: {key}. Allowed: {ALLOWED_OPERATORS}",
            )
        if key in ("all", "any"):
            for cond in when[key]:
                _validate_rule_when(cond)
        elif key == "in":
            if not isinstance(when[key], (list, tuple)) or len(when[key]) != 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="'in' requires [path, list]",
                )
        elif key in ("eq", "neq", "gt", "gte", "lt", "lte"):
            if not isinstance(when[key], (list, tuple)) or len(when[key]) != 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"'{key}' requires [path, value]",
                )
        elif key == "exists":
            if not isinstance(when[key], str):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="'exists' requires path string",
                )


@router.post("/rulesets")
async def create_ruleset(
    body: CreateRulesetRequest,
    tenant: TenantDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new ruleset."""
    # Check unique (tenant_id, jurisdiction, tax_type)
    result = await db.execute(
        select(Ruleset).where(
            Ruleset.tenant_id == tenant.tenant_id,
            Ruleset.jurisdiction == body.jurisdiction,
            Ruleset.tax_type == body.tax_type,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ruleset already exists for this jurisdiction and tax type",
        )
    ruleset = Ruleset(
        ruleset_id=str(uuid4()),
        tenant_id=str(tenant.tenant_id),
        jurisdiction=body.jurisdiction,
        tax_type=body.tax_type,
        name=body.name,
        created_at=_now_iso(),
    )
    db.add(ruleset)
    await db.commit()
    await db.refresh(ruleset)
    return {
        "ruleset_id": str(ruleset.ruleset_id),
        "jurisdiction": ruleset.jurisdiction,
        "tax_type": ruleset.tax_type,
        "name": ruleset.name,
        "created_at": ruleset.created_at,
    }


@router.post("/rulesets/{ruleset_id}/rules")
async def create_or_update_rule(
    ruleset_id: str,
    body: CreateRuleRequest,
    tenant: TenantDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create or update a draft rule."""
    result = await db.execute(
        select(Ruleset).where(
            Ruleset.ruleset_id == ruleset_id,
            Ruleset.tenant_id == tenant.tenant_id,
        )
    )
    ruleset = result.scalar_one_or_none()
    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    _validate_rule_when(body.when)

    if not isinstance(body.priority, int):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="priority must be an integer",
        )

    rule_json = {
        "rule_id": body.rule_id,
        "name": body.name,
        "priority": body.priority,
        "when": body.when,
        "then": body.then,
        "because": body.because,
    }

    # Upsert: find existing by rule_id
    result = await db.execute(
        select(Rule).where(
            Rule.ruleset_id == ruleset_id,
            Rule.rule_id == body.rule_id,
        )
    )
    existing = result.scalar_one_or_none()
    now = _now_iso()
    if existing:
        existing.name = body.name
        existing.priority = body.priority
        existing.rule_json = rule_json
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        return {"rule_pk": str(existing.rule_pk), "rule_id": body.rule_id, "state": "updated"}
    else:
        rule = Rule(
            rule_pk=str(uuid4()),
            ruleset_id=ruleset_id,
            rule_id=body.rule_id,
            name=body.name,
            priority=body.priority,
            rule_json=rule_json,
            state="draft",
            updated_at=now,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return {"rule_pk": str(rule.rule_pk), "rule_id": body.rule_id, "state": "created"}


@router.post("/rulesets/{ruleset_id}/publish")
async def publish_ruleset(
    ruleset_id: str,
    body: PublishRequest,
    tenant: TenantDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Publish a new version of the ruleset."""
    result = await db.execute(
        select(Ruleset).where(
            Ruleset.ruleset_id == ruleset_id,
            Ruleset.tenant_id == tenant.tenant_id,
        )
    )
    ruleset = result.scalar_one_or_none()
    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    # Load all draft rules
    result = await db.execute(
        select(Rule).where(
            Rule.ruleset_id == ruleset_id,
            Rule.state == "draft",
        )
    )
    draft_rules = result.scalars().all()
    if not draft_rules:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No draft rules to publish",
        )

    # Check duplicate rule_id
    rule_ids = [r.rule_id for r in draft_rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate rule_id within ruleset",
        )

    # Build bundle: sorted by priority DESC
    rules = [r.rule_json for r in sorted(draft_rules, key=lambda x: x.priority, reverse=True)]
    bundle = {"rules": rules}
    bh = bundle_hash(rules)

    # Determine version number
    result = await db.execute(
        select(RulesetVersion).where(RulesetVersion.ruleset_id == ruleset_id)
    )
    versions = result.scalars().all()
    if versions:
        # Parse semver and increment patch
        last_ver = versions[0].version
        parts = last_ver.split(".")
        if len(parts) == 3:
            try:
                patch = int(parts[2]) + 1
                new_ver = f"{parts[0]}.{parts[1]}.{patch}"
            except ValueError:
                new_ver = "1.0.1"
        else:
            new_ver = "1.0.0"
    else:
        new_ver = "1.0.0"

    now = _now_iso()

    # Close overlapping previous version
    for v in versions:
        if v.effective_to is None or v.effective_to > body.effective_from:
            v.effective_to = body.effective_from
            await db.flush()

    version = RulesetVersion(
        version_id=str(uuid4()),
        ruleset_id=ruleset_id,
        version=new_ver,
        effective_from=body.effective_from,
        effective_to=None,
        bundle_hash=bh,
        bundle_json=bundle,
        published_at=datetime.utcnow(),
        change_summary=body.change_summary,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)

    return {
        "version_id": str(version.version_id),
        "version": version.version,
        "effective_from": version.effective_from.isoformat() if version.effective_from else None,
        "bundle_hash": version.bundle_hash,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "change_summary": version.change_summary,
    }
