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
    result, fired = evaluate_rules(context, rules, 100)
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
    result, fired = evaluate_rules(context, rules, 100)
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
    result, fired = evaluate_rules(context, rules, 100)
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
    result, fired = evaluate_rules(context, rules, 100)
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
    result, fired = evaluate_rules(context, rules, 100)
    assert len(result["obligations"]) == 1
    assert result["obligations"][0].type == "NEXUS_MONITOR"
    assert result["obligations"][0].threshold == 500000
