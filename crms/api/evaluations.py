"""Evaluation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crms.auth.middleware import TenantDep
from crms.database import get_db
from crms.engine.evaluator import evaluate_rules
from crms.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationResult,
    EvaluationExplanation,
    FiredRule,
    Obligation,
    RulesetInfo,
    VersionInfo,
)
from crms.storage.repositories import (
    get_ruleset_by_jurisdiction_tax,
    get_version_for_effective_at,
    get_evaluation_by_idempotency,
    create_evaluation,
    get_evaluation_by_id,
)
from crms.utils.canonical import request_hash

router = APIRouter()


@router.post("/evaluations", response_model=EvaluationResponse)
async def evaluate_transaction(
    body: EvaluationRequest,
    tenant: TenantDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Evaluate a transaction against the ruleset.
    Returns taxability, rate, obligations, and explanation.
    Idempotent when idempotency_key is provided.
    """
    trans = body.transaction
    ruleset = await get_ruleset_by_jurisdiction_tax(
        db, str(tenant.tenant_id), trans.jurisdiction, trans.tax_type
    )
    if not ruleset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ruleset not found for jurisdiction and tax type",
        )

    # Idempotency: return cached if exists
    if body.idempotency_key:
        existing = await get_evaluation_by_idempotency(
            db, str(tenant.tenant_id), body.idempotency_key
        )
        if existing:
            out = existing.output_json
            return EvaluationResponse(
                evaluation_id=str(existing.evaluation_id),
                ruleset=RulesetInfo(
                    jurisdiction=out["ruleset"]["jurisdiction"],
                    tax_type=out["ruleset"]["tax_type"],
                ),
                version=VersionInfo(
                    version=out["version"]["version"],
                    bundle_hash=out["version"]["bundle_hash"],
                ),
                result=EvaluationResult(**out["result"]),
                explanation=EvaluationExplanation(
                    fired_rules=[FiredRule(**r) for r in out["explanation"]["fired_rules"]]
                ),
            )

    version = await get_version_for_effective_at(
        db, str(ruleset.ruleset_id), body.effective_at
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published version effective at the given effective_at",
        )

    # Evaluate - wrap transaction so rule paths like "transaction.jurisdiction" work
    trans_dict = trans.model_dump()
    context = {"transaction": trans_dict}
    rules = version.bundle_json.get("rules", [])
    result, fired = evaluate_rules(context, rules, trans.amount)

    obligations = result["obligations"]  # Already Obligation instances from evaluator
    result_obj = EvaluationResult(
        taxable=result["taxable"],
        rate=result["rate"],
        tax_amount=result["tax_amount"],
        obligations=obligations,
    )
    explanation = EvaluationExplanation(
        fired_rules=[FiredRule(rule_id=r.rule_id, name=r.name, because=r.because) for r in fired]
    )

    req_hash = request_hash(body.model_dump())
    input_json = {
        "idempotency_key": body.idempotency_key,
        "effective_at": body.effective_at.isoformat(),
        "transaction": trans_dict,
    }

    ev = await create_evaluation(
        db=db,
        tenant_id=str(tenant.tenant_id),
        ruleset_id=str(ruleset.ruleset_id),
        version_id=str(version.version_id),
        input_json=input_json,
        output_json={},  # Set below
        idempotency_key=body.idempotency_key,
        request_hash=req_hash,
    )
    output_json = {
        "evaluation_id": str(ev.evaluation_id),
        "ruleset": {"jurisdiction": trans.jurisdiction, "tax_type": trans.tax_type},
        "version": {"version": version.version, "bundle_hash": version.bundle_hash},
        "result": result_obj.model_dump(),
        "explanation": explanation.model_dump(),
    }
    ev.output_json = output_json

    return EvaluationResponse(
        evaluation_id=str(ev.evaluation_id),
        ruleset=RulesetInfo(jurisdiction=trans.jurisdiction, tax_type=trans.tax_type),
        version=VersionInfo(version=version.version, bundle_hash=version.bundle_hash),
        result=result_obj,
        explanation=explanation,
    )


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation(
    evaluation_id: str,
    tenant: TenantDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get evaluation/audit record by ID (tenant-scoped)."""
    ev = await get_evaluation_by_id(db, evaluation_id, str(tenant.tenant_id))
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found",
        )
    return {
        "evaluation_id": str(ev.evaluation_id),
        "tenant_id": str(ev.tenant_id),
        "ruleset_id": str(ev.ruleset_id),
        "version_id": str(ev.version_id),
        "idempotency_key": ev.idempotency_key,
        "request_hash": ev.request_hash,
        "input_json": ev.input_json,
        "output_json": ev.output_json,
        "trace_id": ev.trace_id,
        "created_at": ev.created_at,
    }
