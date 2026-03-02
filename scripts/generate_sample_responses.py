#!/usr/bin/env python3
"""
Generate sample_responses.json from sample_requests.json.
Runs the rule evaluator in-memory (no DB/API needed).
Usage: python scripts/generate_sample_responses.py
"""

import json
import sys
from pathlib import Path
from uuid import uuid4

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from crms.engine.evaluator import evaluate_rules
from crms.utils.canonical import bundle_hash

from compliance_rulesets import COMPLIANCE_RULESETS

# Simple rulesets (US-TX, US-NY) - same as seed.py
SIMPLE_RULESETS = [
    {"jurisdiction": "US-TX", "tax_type": "SALES", "rules": [
        {"rule_id": "US-TX-SALES-001", "name": "TX SaaS/digital consumer taxable", "priority": 100, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-TX"]}, {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, {"eq": ["transaction.buyer.type", "CONSUMER"]}]}, "then": {"set": {"taxable": True, "rate": 0.0625}, "emit_obligations": []}, "because": "TX SaaS/digital sold to consumers taxable at 6.25%."},
        {"rule_id": "US-TX-SALES-002", "name": "TX B2B SaaS/digital exempt", "priority": 95, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-TX"]}, {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, {"eq": ["transaction.buyer.type", "BUSINESS"]}]}, "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []}, "because": "TX B2B SaaS/digital exempt."},
        {"rule_id": "US-TX-SALES-DEFAULT", "name": "Default fallback", "priority": 0, "when": {"eq": ["transaction.jurisdiction", "US-TX"]}, "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []}, "because": "Default: not taxable."},
    ]},
    {"jurisdiction": "US-NY", "tax_type": "SALES", "rules": [
        {"rule_id": "US-NY-SALES-001", "name": "NY SaaS consumer taxable", "priority": 100, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-NY"]}, {"eq": ["transaction.product.category", "SAAS"]}, {"eq": ["transaction.buyer.type", "CONSUMER"]}]}, "then": {"set": {"taxable": True, "rate": 0.04}, "emit_obligations": []}, "because": "NY SaaS sold to consumers taxable at 4%."},
        {"rule_id": "US-NY-SALES-DEFAULT", "name": "Default fallback", "priority": 0, "when": {"eq": ["transaction.jurisdiction", "US-NY"]}, "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []}, "because": "Default: not taxable."},
    ]},
]

# Build lookup: (jurisdiction, tax_type) -> (rules, bundle_hash)
RULESET_MAP = {}
for rs in COMPLIANCE_RULESETS + SIMPLE_RULESETS:
    rules = rs["rules"]
    bh = bundle_hash(rules)
    RULESET_MAP[(rs["jurisdiction"], rs["tax_type"])] = (rules, bh)


def main():
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    requests_path = examples_dir / "sample_requests.json"
    responses_path = examples_dir / "sample_responses.json"

    if not requests_path.exists():
        print(f"Error: {requests_path} not found")
        sys.exit(1)

    with open(requests_path) as f:
        requests = json.load(f)

    responses = []
    for req in requests:
        trans = req["transaction"]
        jur = trans.get("jurisdiction")
        tax = trans.get("tax_type")
        key = (jur, tax)

        if key not in RULESET_MAP:
            responses.append({
                "evaluation_id": str(uuid4()),
                "request_idempotency_key": req.get("idempotency_key"),
                "ruleset": {"jurisdiction": jur, "tax_type": tax},
                "error": f"No ruleset found for jurisdiction={jur}, tax_type={tax}",
            })
            continue

        rules, bundle_hash_val = RULESET_MAP[key]
        context = {"transaction": trans}
        amount = trans.get("amount", 0)
        result, fired = evaluate_rules(context, rules, amount)

        obligations = []
        for o in result["obligations"]:
            obl = {"type": o.type}
            if o.threshold is not None:
                obl["threshold"] = o.threshold
            if o.window_days is not None:
                obl["window_days"] = o.window_days
            if o.message:
                obl["message"] = o.message
            obligations.append(obl)

        result_dict = {
            "taxable": result["taxable"],
            "rate": result["rate"],
            "tax_amount": result["tax_amount"],
            "obligations": obligations,
        }
        if result.get("rate_components"):
            result_dict["rate_components"] = result["rate_components"]
        if result.get("risk_flags"):
            result_dict["risk_flags"] = result["risk_flags"]

        resp = {
            "evaluation_id": str(uuid4()),
            "request_idempotency_key": req.get("idempotency_key"),
            "ruleset": {"jurisdiction": jur, "tax_type": tax},
            "version": {"version": "1.1.0", "bundle_hash": bundle_hash_val},
            "result": result_dict,
            "explanation": {
                "fired_rules": [
                    {"rule_id": r.rule_id, "name": r.name, "because": r.because}
                    for r in fired
                ]
            },
        }
        responses.append(resp)

    with open(responses_path, "w") as f:
        json.dump(responses, f, indent=2)

    print(f"Generated {len(responses)} sample responses -> {responses_path}")


if __name__ == "__main__":
    main()
