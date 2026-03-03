"""Rule evaluator - evaluates rules against transaction with explainability."""

from copy import deepcopy
from typing import Any

from crms.schemas.evaluation import (
    ConditionEval,
    Counterfactual,
    CounterfactualChange,
    EvaluationTrace,
    FiredRule,
    Obligation,
    RuleStep,
)


class _Missing:
    """Sentinel for missing path value in trace."""

    def __repr__(self):
        return "__MISSING__"


MISSING = _Missing()


def _get_path(obj: dict, path: str) -> Any:
    """Get nested value by dot path (e.g. transaction.jurisdiction)."""
    parts = path.split(".")
    current: Any = obj
    for p in parts:
        if isinstance(current, dict) and p in current:
            current = current[p]
        else:
            return None
    return current


def _get_path_traced(obj: dict, path: str, paths_read: set) -> Any:
    """Get path and record it; return MISSING if any key in path is absent."""
    paths_read.add(path)
    parts = path.split(".")
    current: Any = obj
    for p in parts:
        if not isinstance(current, dict) or p not in current:
            return MISSING
        current = current[p]
    return current


def _eval_condition(transaction: dict, cond: dict) -> bool:
    """Evaluate a single condition against transaction."""
    if "eq" in cond:
        path, expected = cond["eq"]
        val = _get_path(transaction, path)
        return val == expected
    if "neq" in cond:
        path, expected = cond["neq"]
        val = _get_path(transaction, path)
        return val != expected
    if "gt" in cond:
        path, expected = cond["gt"]
        val = _get_path(transaction, path)
        return val is not None and val > expected
    if "gte" in cond:
        path, expected = cond["gte"]
        val = _get_path(transaction, path)
        return val is not None and val >= expected
    if "lt" in cond:
        path, expected = cond["lt"]
        val = _get_path(transaction, path)
        return val is not None and val < expected
    if "lte" in cond:
        path, expected = cond["lte"]
        val = _get_path(transaction, path)
        return val is not None and val <= expected
    if "in" in cond:
        path, allowed = cond["in"]
        val = _get_path(transaction, path)
        return val in allowed if isinstance(allowed, (list, tuple)) else False
    if "exists" in cond:
        path = cond["exists"]
        if isinstance(path, list):
            path = path[0]
        val = _get_path(transaction, path)
        return val is not None and val != ""
    if "not_exists" in cond:
        path = cond["not_exists"]
        if isinstance(path, list):
            path = path[0]
        val = _get_path(transaction, path)
        return val is None or val == ""
    if "path_neq" in cond:
        path1, path2 = cond["path_neq"]
        v1 = _get_path(transaction, path1)
        v2 = _get_path(transaction, path2)
        return v1 is not None and v2 is not None and v1 != v2
    if "path_eq" in cond:
        path1, path2 = cond["path_eq"]
        v1 = _get_path(transaction, path1)
        v2 = _get_path(transaction, path2)
        return v1 is not None and v2 is not None and v1 == v2
    if "all" in cond:
        return all(_eval_condition(transaction, c) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(transaction, c) for c in cond["any"])
    return False


def _actual_for_trace(val: Any) -> Any:
    """Serialize actual value for trace (MISSING -> string)."""
    return "__MISSING__" if val is MISSING else val


def _eval_condition_traced(
    context: dict,
    cond: dict,
    paths_read: set,
    evals_out: list,
    missing_out: list,
) -> bool:
    """
    Evaluate condition and append ConditionEval(s) to evals_out, missing paths to missing_out.
    Returns whether the condition passed.
    """
    if "eq" in cond:
        path, expected = cond["eq"]
        val = _get_path_traced(context, path, paths_read)
        passed = val == expected
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="eq",
                path=path,
                expected=expected,
                actual=_actual_for_trace(val),
                passed=passed,
                reason=f"{path}={_actual_for_trace(val)} {'==' if passed else '!='} {expected}",
            )
        )
        return passed
    if "neq" in cond:
        path, expected = cond["neq"]
        val = _get_path_traced(context, path, paths_read)
        passed = val != expected
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="neq",
                path=path,
                expected=expected,
                actual=_actual_for_trace(val),
                passed=passed,
            )
        )
        return passed
    if "gte" in cond:
        path, expected = cond["gte"]
        val = _get_path_traced(context, path, paths_read)
        passed = val is not MISSING and val >= expected
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="gte",
                path=path,
                expected=expected,
                actual=_actual_for_trace(val),
                passed=passed,
            )
        )
        return passed
    if "gt" in cond:
        path, expected = cond["gt"]
        val = _get_path_traced(context, path, paths_read)
        passed = val is not MISSING and val > expected
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(node_type="leaf", op="gt", path=path, expected=expected, actual=_actual_for_trace(val), passed=passed)
        )
        return passed
    if "lt" in cond:
        path, expected = cond["lt"]
        val = _get_path_traced(context, path, paths_read)
        passed = val is not MISSING and val < expected
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(node_type="leaf", op="lt", path=path, expected=expected, actual=_actual_for_trace(val), passed=passed)
        )
        return passed
    if "lte" in cond:
        path, expected = cond["lte"]
        val = _get_path_traced(context, path, paths_read)
        passed = val is not MISSING and val <= expected
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(node_type="leaf", op="lte", path=path, expected=expected, actual=_actual_for_trace(val), passed=passed)
        )
        return passed
    if "in" in cond:
        path, allowed = cond["in"]
        val = _get_path_traced(context, path, paths_read)
        passed = val is not MISSING and (val in allowed if isinstance(allowed, (list, tuple)) else False)
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="in",
                path=path,
                expected=allowed,
                actual=_actual_for_trace(val),
                passed=passed,
            )
        )
        return passed
    if "exists" in cond:
        path = cond["exists"]
        if isinstance(path, list):
            path = path[0]
        val = _get_path_traced(context, path, paths_read)
        passed = val is not MISSING and val is not None and val != ""
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="exists",
                path=path,
                expected=True,
                actual=_actual_for_trace(val),
                passed=passed,
            )
        )
        return passed
    if "not_exists" in cond:
        path = cond["not_exists"]
        if isinstance(path, list):
            path = path[0]
        val = _get_path_traced(context, path, paths_read)
        passed = val is MISSING or val is None or val == ""
        if val is MISSING:
            missing_out.append(path)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="not_exists",
                path=path,
                expected=None,
                actual=_actual_for_trace(val),
                passed=passed,
            )
        )
        return passed
    if "path_eq" in cond:
        path1, path2 = cond["path_eq"]
        v1 = _get_path_traced(context, path1, paths_read)
        v2 = _get_path_traced(context, path2, paths_read)
        passed = v1 is not MISSING and v2 is not MISSING and v1 == v2
        if v1 is MISSING:
            missing_out.append(path1)
        if v2 is MISSING:
            missing_out.append(path2)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="path_eq",
                path=path1,
                path2=path2,
                expected="equal",
                actual=f"{_actual_for_trace(v1)} vs {_actual_for_trace(v2)}",
                passed=passed,
            )
        )
        return passed
    if "path_neq" in cond:
        path1, path2 = cond["path_neq"]
        v1 = _get_path_traced(context, path1, paths_read)
        v2 = _get_path_traced(context, path2, paths_read)
        passed = v1 is not MISSING and v2 is not MISSING and v1 != v2
        if v1 is MISSING:
            missing_out.append(path1)
        if v2 is MISSING:
            missing_out.append(path2)
        evals_out.append(
            ConditionEval(
                node_type="leaf",
                op="path_neq",
                path=path1,
                path2=path2,
                expected="not equal",
                actual=f"{_actual_for_trace(v1)} vs {_actual_for_trace(v2)}",
                passed=passed,
            )
        )
        return passed
    if "all" in cond:
        evals: list[ConditionEval] = []
        miss: list[str] = []
        results = []
        for c in cond["all"]:
            results.append(_eval_condition_traced(context, c, paths_read, evals, miss))
        passed = all(results)
        evals_out.append(
            ConditionEval(
                node_type="all",
                op="all",
                expected=len(cond["all"]),
                actual=sum(1 for r in results if r),
                passed=passed,
                reason=f"all({len(cond['all'])}) -> {passed}",
            )
        )
        evals_out.extend(evals)
        missing_out.extend(miss)
        return passed
    if "any" in cond:
        evals = []
        miss = []
        results = []
        for c in cond["any"]:
            results.append(_eval_condition_traced(context, c, paths_read, evals, miss))
        passed = any(results)
        evals_out.append(
            ConditionEval(
                node_type="any",
                op="any",
                expected=len(cond["any"]),
                actual=sum(1 for r in results if r),
                passed=passed,
                reason=f"any({len(cond['any'])}) -> {passed}",
            )
        )
        evals_out.extend(evals)
        missing_out.extend(miss)
        return passed
    return False


def _apply_then(context: dict, rule: dict, amount: float) -> dict:
    """Apply rule's 'then' to result dict. Mutates context['_result']-like; returns result dict."""
    result = {
        "taxable": False,
        "rate": 0.0,
        "tax_amount": 0.0,
        "obligations": [],
        "rate_components": [],
        "risk_flags": [],
    }
    then = rule.get("then") or {}
    set_vals = then.get("set") or {}
    if "taxable" in set_vals:
        result["taxable"] = bool(set_vals["taxable"])
    if "rate" in set_vals:
        result["rate"] = float(set_vals["rate"])
    if "rate_components" in set_vals:
        result["rate_components"] = list(set_vals["rate_components"])
    result["tax_amount"] = round(result["rate"] * amount, 2)
    for obl in then.get("emit_obligations") or []:
        result["obligations"].append(
            Obligation(
                type=obl.get("type", ""),
                threshold=obl.get("threshold"),
                window_days=obl.get("window_days"),
                message=obl.get("message"),
            )
        )
    for rf in then.get("add_risk_flags") or []:
        result["risk_flags"].append({"type": rf.get("type", ""), "severity": rf.get("severity", "")})
    return result


def evaluate_rules(
    context: dict,
    rules: list[dict],
    amount: float,
    *,
    trace: bool = False,
    top_k_near_miss: int = 3,
    max_counterfactuals: int = 2,
) -> tuple[dict, list[FiredRule], EvaluationTrace | None]:
    """
    Evaluate rules in priority order (DESC). First match wins.
    Returns (result_dict, fired_rules, trace_or_none).
    When trace=True, returns full auditable trace with steps, evidence paths, confidence, near-miss, counterfactuals.
    """
    # API passes context = {"transaction": trans_dict}; rules use paths like "transaction.jurisdiction"
    transaction = context  # _eval_condition expects the same object for path lookups
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)

    result = {
        "taxable": False,
        "rate": 0.0,
        "tax_amount": 0.0,
        "obligations": [],
        "rate_components": [],
        "risk_flags": [],
    }
    fired: list[FiredRule] = []
    trace_out: EvaluationTrace | None = None

    if trace:
        paths_read: set[str] = set()
        steps: list[RuleStep] = []
        near_miss: list[tuple[int, RuleStep]] = []  # (distance, step)
        winner_step: RuleStep | None = None
        winner_rule: dict | None = None

        for rule in sorted_rules:
            when = rule.get("when") or {}
            evals_list: list[ConditionEval] = []
            missing_paths: list[str] = []
            matched = _eval_condition_traced(
                context, when, paths_read, evals_list, missing_paths
            )

            step = RuleStep(
                rule_id=rule.get("rule_id", ""),
                name=rule.get("name", ""),
                priority=rule.get("priority", 0),
                matched=matched,
                evaluated=evals_list,
                missing_paths=missing_paths,
                reason=f"Rule {'matched' if matched else 'did not match'}",
            )
            steps.append(step)

            if matched:
                winner_step = step
                winner_rule = rule
                result = _apply_then(context, rule, amount)
                fired.append(
                    FiredRule(
                        rule_id=rule.get("rule_id", ""),
                        name=rule.get("name", ""),
                        because=rule.get("because", ""),
                    )
                )
                break

            # Near-miss: distance = failed leaf count + 2 * missing paths
            failed_leaves = sum(1 for e in evals_list if e.node_type == "leaf" and not e.passed)
            distance = failed_leaves + 2 * len(missing_paths)
            near_miss.append((distance, step))
            near_miss.sort(key=lambda x: x[0])
            if len(near_miss) > top_k_near_miss:
                near_miss = near_miss[:top_k_near_miss]

        # Build trace
        evidence_paths_used = sorted(paths_read)
        missing_evidence = list(winner_step.missing_paths) if winner_step else []
        confidence = max(0.0, 1.0 - 0.15 * len(missing_evidence))

        near_miss_steps = [s for _, s in near_miss]
        counterfactuals_list: list[Counterfactual] = []
        if max_counterfactuals > 0 and near_miss_steps and winner_rule:
            for step in near_miss_steps[:max_counterfactuals]:
                changes: list[CounterfactualChange] = []
                for e in step.evaluated:
                    if e.node_type != "leaf" or e.passed:
                        continue
                    if e.actual == "__MISSING__":
                        changes.append(
                            CounterfactualChange(
                                path=e.path or "",
                                suggested_value=None,
                                reason=f"Provide {e.path} to satisfy {e.op}",
                            )
                        )
                    else:
                        changes.append(
                            CounterfactualChange(
                                path=e.path or "",
                                suggested_value=e.expected,
                                reason=f"Set {e.path} to {e.expected} (was {e.actual})",
                            )
                        )
                if not changes:
                    continue
                # Outcome preview: apply changes and re-evaluate (only when we have a concrete value)
                ctx_copy = deepcopy(context)
                for ch in changes[:5]:
                    if ch.suggested_value is None:
                        continue
                    parts = ch.path.split(".")
                    if len(parts) < 2:
                        continue
                    cur = ctx_copy
                    for p in parts[:-1]:
                        if p not in cur:
                            cur[p] = {}
                        cur = cur[p]
                    cur[parts[-1]] = ch.suggested_value
                try:
                    res_preview, _, _ = evaluate_rules(
                        ctx_copy, rules, amount, trace=False
                    )
                    outcome_preview = {
                        "taxable": res_preview["taxable"],
                        "rate": res_preview["rate"],
                        "tax_amount": res_preview["tax_amount"],
                    }
                except Exception:
                    outcome_preview = None
                goal = "non_taxable" if result.get("taxable") else "lower_rate"
                counterfactuals_list.append(
                    Counterfactual(
                        goal=goal,
                        based_on_rule_id=step.rule_id,
                        changes=changes[:5],
                        outcome_preview=outcome_preview,
                    )
                )

        trace_out = EvaluationTrace(
            winner=(
                FiredRule(
                    rule_id=winner_rule.get("rule_id", ""),
                    name=winner_rule.get("name", ""),
                    because=winner_rule.get("because", ""),
                )
                if winner_rule
                else None
            ),
            steps=steps,
            evidence_paths_used=evidence_paths_used,
            missing_evidence=missing_evidence,
            confidence=round(confidence, 2),
            near_miss_rules=near_miss_steps,
            counterfactuals=counterfactuals_list,
        )
        return result, fired, trace_out

    # Non-trace path (original behavior)
    for rule in sorted_rules:
        when = rule.get("when") or {}
        if not _eval_condition(transaction, when):
            continue
        result = _apply_then(context, rule, amount)
        fired.append(
            FiredRule(
                rule_id=rule.get("rule_id", ""),
                name=rule.get("name", ""),
                because=rule.get("because", ""),
            )
        )
        break

    return result, fired, None
