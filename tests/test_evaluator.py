"""Unit tests for rule evaluator."""

import pytest

from crms.engine.evaluator import evaluate_rules


def test_eq_condition():
    """Test eq operator."""
    rules = [
        {
            "rule_id": "R1",
            "name": "Match CA",
            "priority": 10,
            "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
            "then": {"set": {"taxable": True, "rate": 0.0725}},
            "because": "CA taxable",
        },
    ]
    context = {"transaction": {"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100}}
    result, fired, _ = evaluate_rules(context, rules, 100)
    assert result["taxable"] is True
    assert result["rate"] == 0.0725
    assert len(fired) == 1
    assert fired[0].rule_id == "R1"


def test_all_condition():
    """Test all combinator."""
    rules = [
        {
            "rule_id": "R1",
            "name": "CA SaaS Consumer",
            "priority": 10,
            "when": {
                "all": [
                    {"eq": ["transaction.jurisdiction", "US-CA"]},
                    {"eq": ["transaction.product.category", "SAAS"]},
                    {"eq": ["transaction.buyer.type", "CONSUMER"]},
                ]
            },
            "then": {"set": {"taxable": True, "rate": 0.0725}},
            "because": "CA SaaS consumer taxable",
        },
    ]
    context = {
        "transaction": {
            "jurisdiction": "US-CA",
            "tax_type": "SALES",
            "amount": 100,
            "product": {"category": "SAAS"},
            "buyer": {"type": "CONSUMER"},
        }
    }
    result, fired, _ = evaluate_rules(context, rules, 100)
    assert result["taxable"] is True
    assert result["tax_amount"] == 7.25


def test_no_match_default():
    """Test default when no rule matches."""
    rules = [
        {
            "rule_id": "R1",
            "name": "Match CA",
            "priority": 10,
            "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
            "then": {"set": {"taxable": True, "rate": 0.0725}},
            "because": "CA taxable",
        },
    ]
    context = {"transaction": {"jurisdiction": "US-NY", "tax_type": "SALES", "amount": 100}}
    result, fired, _ = evaluate_rules(context, rules, 100)
    assert result["taxable"] is False
    assert result["rate"] == 0
    assert result["tax_amount"] == 0
    assert len(fired) == 0


def test_first_match_wins():
    """Test first match wins semantics (priority DESC)."""
    rules = [
        {
            "rule_id": "R1",
            "name": "High priority",
            "priority": 20,
            "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
            "then": {"set": {"taxable": True, "rate": 0.10}},
            "because": "High",
        },
        {
            "rule_id": "R2",
            "name": "Low priority",
            "priority": 5,
            "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
            "then": {"set": {"taxable": True, "rate": 0.05}},
            "because": "Low",
        },
    ]
    context = {"transaction": {"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100}}
    result, fired, _ = evaluate_rules(context, rules, 100)
    assert result["rate"] == 0.10
    assert fired[0].rule_id == "R1"


def test_emit_obligations():
    """Test emit_obligations in then."""
    rules = [
        {
            "rule_id": "R1",
            "name": "With obligations",
            "priority": 10,
            "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
            "then": {
                "set": {"taxable": True, "rate": 0.0725},
                "emit_obligations": [
                    {"type": "NEXUS_MONITOR", "threshold": 500000, "window_days": 365}
                ],
            },
            "because": "CA with nexus",
        },
    ]
    context = {"transaction": {"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100}}
    result, fired, _ = evaluate_rules(context, rules, 100)
    assert len(result["obligations"]) == 1
    assert result["obligations"][0].type == "NEXUS_MONITOR"
    assert result["obligations"][0].threshold == 500000


def test_not_exists_and_path_neq():
    """Test not_exists and path_neq operators."""
    rules = [
        {
            "rule_id": "R1",
            "name": "Conflicting evidence",
            "priority": 10,
            "when": {
                "all": [
                    {"exists": ["transaction.evidence.billing_country"]},
                    {"exists": ["transaction.evidence.ip_country"]},
                    {"path_neq": ["transaction.evidence.billing_country", "transaction.evidence.ip_country"]},
                ]
            },
            "then": {"set": {"taxable": True, "rate": 0.0725}, "add_risk_flags": [{"type": "CONFLICTING", "severity": "HIGH"}]},
            "because": "Conflicting evidence",
        },
        {
            "rule_id": "R2",
            "name": "No resale cert",
            "priority": 5,
            "when": {"all": [{"eq": ["transaction.buyer.type", "BUSINESS"]}, {"not_exists": ["transaction.doc.resale_cert_valid"]}]},
            "then": {"set": {"taxable": True, "rate": 0.0725, "rate_components": [{"name": "CA_BASE", "rate": 0.0725}]}},
            "because": "No cert",
        },
    ]
    context = {"transaction": {"jurisdiction": "US-CA", "amount": 100, "buyer": {"type": "BUSINESS"}, "evidence": {"billing_country": "US", "ip_country": "CA"}}}
    result, fired, _ = evaluate_rules(context, rules, 100)
    assert result["taxable"] is True
    assert result["rate"] == 0.0725
    assert len(result["risk_flags"]) == 1
    assert result["risk_flags"][0]["type"] == "CONFLICTING"
    assert fired[0].rule_id == "R1"

    context2 = {"transaction": {"jurisdiction": "US-CA", "amount": 100, "buyer": {"type": "BUSINESS"}}}
    result2, fired2, _ = evaluate_rules(context2, rules, 100)
    assert result2["taxable"] is True
    assert len(result2["rate_components"]) == 1
    assert result2["rate_components"][0]["name"] == "CA_BASE"


def test_trace_full():
    """With trace=True, returns auditable trace with winner, steps, evidence paths, confidence."""
    rules = [
        {
            "rule_id": "GUARD",
            "name": "Guardrail",
            "priority": 100,
            "when": {"any": [{"neq": ["transaction.jurisdiction", "US-CA"]}, {"neq": ["transaction.tax_type", "SALES"]}]},
            "then": {"set": {"taxable": False, "rate": 0.0}},
            "because": "Wrong ruleset",
        },
        {
            "rule_id": "SAAS",
            "name": "CA SaaS consumer",
            "priority": 50,
            "when": {
                "all": [
                    {"eq": ["transaction.jurisdiction", "US-CA"]},
                    {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]},
                    {"eq": ["transaction.buyer.type", "CONSUMER"]},
                ]
            },
            "then": {"set": {"taxable": True, "rate": 0.0725}},
            "because": "CA digital consumer",
        },
        {"rule_id": "FALLBACK", "name": "Fallback", "priority": 1, "when": {"exists": ["transaction.amount"]}, "then": {"set": {"taxable": False, "rate": 0.0}}, "because": "Default"},
    ]
    context = {
        "transaction": {
            "jurisdiction": "US-CA",
            "tax_type": "SALES",
            "amount": 100,
            "product": {"category": "SAAS"},
            "buyer": {"type": "CONSUMER"},
        }
    }
    result, fired, trace = evaluate_rules(
        context, rules, 100, trace=True, top_k_near_miss=2, max_counterfactuals=1
    )
    assert trace is not None
    assert trace.winner is not None
    assert trace.winner.rule_id == "SAAS"
    assert len(trace.steps) >= 2
    assert any(s.rule_id == "GUARD" and not s.matched for s in trace.steps)
    assert any(s.rule_id == "SAAS" and s.matched for s in trace.steps)
    assert "transaction.jurisdiction" in trace.evidence_paths_used
    assert "transaction.product.category" in trace.evidence_paths_used
    assert trace.confidence >= 0.0 and trace.confidence <= 1.0
    assert result["taxable"] is True
    assert len(fired) == 1
