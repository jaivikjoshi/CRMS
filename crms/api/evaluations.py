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
    EvaluationTrace,
    FiredRule,
    Obligation,
    RateComponent,
    RiskFlag,
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

    **Explanation levels** (via body.options):
    - options.explain = "none" (default): no trace.
    - options.explain = "winner": only fired rule (same as today).
    - options.explain = "full": auditable trace with steps, condition evals, evidence_paths_used,
      missing_evidence, confidence, near-miss rules, and counterfactual guidance
      ("what to change to get a different outcome" with optional outcome_preview).

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
            expl = out.get("explanation") or {}
            fired_rules = [FiredRule(**r) for r in expl.get("fired_rules", [])]
            trace_data = expl.get("trace")
            explanation = EvaluationExplanation(
                fired_rules=fired_rules,
                trace=EvaluationTrace.model_validate(trace_data) if isinstance(trace_data, dict) else None,
            )
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
                explanation=explanation,
            )

    version = await get_version_for_effective_at(
        db, str(ruleset.ruleset_id), body.effective_at
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published version effective at the given effective_at",
        )

    trans_dict = trans.model_dump()
    context = {"transaction": trans_dict}
    rules = version.bundle_json.get("rules", [])
    options = body.options
    explain = (options.explain if options else "none") or "none"
    trace_requested = explain == "full"
    top_k = (options.near_miss if options else 3) if trace_requested else 0
    max_cf = (options.counterfactuals if options else 2) if trace_requested else 0

    result, fired, trace_out = evaluate_rules(
        context,
        rules,
        trans.amount,
        trace=trace_requested,
        top_k_near_miss=top_k,
        max_counterfactuals=max_cf,
    )

    obligations = result["obligations"]
    rate_components = [RateComponent(**rc) for rc in result.get("rate_components", [])]
    risk_flags = [RiskFlag(**rf) for rf in result.get("risk_flags", [])]
    matched_rule_id = fired[0].rule_id if fired else None
    result_obj = EvaluationResult(
        taxable=result["taxable"],
        rate=result["rate"],
        tax_amount=result["tax_amount"],
        obligations=obligations,
        rate_components=rate_components,
        risk_flags=risk_flags,
        matched_rule_id=matched_rule_id,
    )
    explanation = EvaluationExplanation(
        fired_rules=[FiredRule(rule_id=r.rule_id, name=r.name, because=r.because) for r in fired],
        trace=trace_out,
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
    explanation_dump = explanation.model_dump()
    # Pydantic serializes trace (EvaluationTrace) in explanation; include in output for audit
    output_json = {
        "evaluation_id": str(ev.evaluation_id),
        "ruleset": {"jurisdiction": trans.jurisdiction, "tax_type": trans.tax_type},
        "version": {"version": version.version, "bundle_hash": version.bundle_hash},
        "result": result_obj.model_dump(),
        "explanation": explanation_dump,
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
