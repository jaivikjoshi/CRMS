"""Rule evaluator - evaluates rules against transaction with explainability."""

from typing import Any

from crms.schemas.evaluation import FiredRule, Obligation


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
        val = _get_path(transaction, path)
        return val is not None and val != ""
    if "all" in cond:
        return all(_eval_condition(transaction, c) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(transaction, c) for c in cond["any"])
    return False


def evaluate_rules(
    transaction: dict,
    rules: list[dict],
    amount: float,
) -> tuple[dict, list[FiredRule]]:
    """
    Evaluate rules in priority order (DESC). First match wins.
    Returns (result_dict, fired_rules).
    """
    # Sort by priority DESC (higher first)
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)

    result = {
        "taxable": False,
        "rate": 0.0,
        "tax_amount": 0.0,
        "obligations": [],
    }
    fired: list[FiredRule] = []

    for rule in sorted_rules:
        when = rule.get("when") or {}
        if not _eval_condition(transaction, when):
            continue

        # Rule matched - apply then and stop (first match wins)
        then = rule.get("then") or {}
        set_vals = then.get("set") or {}
        if "taxable" in set_vals:
            result["taxable"] = bool(set_vals["taxable"])
        if "rate" in set_vals:
            result["rate"] = float(set_vals["rate"])
        result["tax_amount"] = round(result["rate"] * amount, 2)

        obligations = then.get("emit_obligations") or []
        for obl in obligations:
            result["obligations"].append(
                Obligation(
                    type=obl.get("type", ""),
                    threshold=obl.get("threshold"),
                    window_days=obl.get("window_days"),
                )
            )

        fired.append(
            FiredRule(
                rule_id=rule.get("rule_id", ""),
                name=rule.get("name", ""),
                because=rule.get("because", ""),
            )
        )
        break  # First match wins

    return result, fired
