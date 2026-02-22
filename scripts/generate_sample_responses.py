#!/usr/bin/env python3
"""
Generate sample_responses.json from sample_requests.json.
Runs the rule evaluator in-memory (no DB/API needed).
Usage: python scripts/generate_sample_responses.py
"""

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crms.engine.evaluator import evaluate_rules
from crms.utils.canonical import bundle_hash

# Same rules as seed (US-CA/SALES)
RULES = [
    {
        "rule_id": "US-CA-SALES-001",
        "name": "CA SaaS consumer taxable",
        "priority": 10,
        "when": {
            "all": [
                {"eq": ["transaction.jurisdiction", "US-CA"]},
                {"eq": ["transaction.product.category", "SAAS"]},
                {"eq": ["transaction.buyer.type", "CONSUMER"]},
            ]
        },
        "then": {
            "set": {"taxable": True, "rate": 0.0725},
            "emit_obligations": [
                {"type": "NEXUS_MONITOR", "threshold": 500000, "window_days": 365}
            ],
        },
        "because": "CA SaaS sold to consumers taxable.",
    },
    {
        "rule_id": "US-CA-SALES-002",
        "name": "CA B2B SaaS exempt",
        "priority": 5,
        "when": {
            "all": [
                {"eq": ["transaction.jurisdiction", "US-CA"]},
                {"eq": ["transaction.product.category", "SAAS"]},
                {"eq": ["transaction.buyer.type", "BUSINESS"]},
            ]
        },
        "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []},
        "because": "CA B2B SaaS exempt.",
    },
    {
        "rule_id": "US-CA-SALES-DEFAULT",
        "name": "Default fallback",
        "priority": 0,
        "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
        "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []},
        "because": "Default: not taxable.",
    },
]

BUNDLE_HASH = bundle_hash(RULES)


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
        context = {"transaction": trans}
        amount = trans.get("amount", 0)
        result, fired = evaluate_rules(context, RULES, amount)

        obligations = [
            {"type": o.type, "threshold": o.threshold, "window_days": o.window_days}
            for o in result["obligations"]
        ]
        fired_rules = [
            {"rule_id": r.rule_id, "name": r.name, "because": r.because}
            for r in fired
        ]

        resp = {
            "evaluation_id": str(uuid4()),
            "request_idempotency_key": req.get("idempotency_key"),
            "ruleset": {"jurisdiction": trans["jurisdiction"], "tax_type": trans["tax_type"]},
            "version": {"version": "1.0.0", "bundle_hash": BUNDLE_HASH},
            "result": {
                "taxable": result["taxable"],
                "rate": result["rate"],
                "tax_amount": result["tax_amount"],
                "obligations": obligations,
            },
            "explanation": {"fired_rules": fired_rules},
        }
        responses.append(resp)

    with open(responses_path, "w") as f:
        json.dump(responses, f, indent=2)

    print(f"Generated {len(responses)} sample responses -> {responses_path}")


if __name__ == "__main__":
    main()
