"""
Comprehensive tests for ALL rulesets and rules.
Tests the evaluator directly (no DB needed) against every compliance ruleset.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from crms.engine.evaluator import evaluate_rules
from compliance_rulesets import COMPLIANCE_RULESETS

CA_RULES = next(r for r in COMPLIANCE_RULESETS if r["jurisdiction"] == "US-CA")["rules"]
EU_RULES = next(r for r in COMPLIANCE_RULESETS if r["jurisdiction"] == "EU")["rules"]
ON_RULES = next(r for r in COMPLIANCE_RULESETS if r["jurisdiction"] == "CA-ON")["rules"]

# Simple TX/NY rules (from seed.py)
TX_RULES = [
    {"rule_id": "US-TX-SALES-001", "name": "TX SaaS/digital consumer taxable", "priority": 100, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-TX"]}, {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, {"eq": ["transaction.buyer.type", "CONSUMER"]}]}, "then": {"set": {"taxable": True, "rate": 0.0625}}, "because": "TX SaaS/digital consumer taxable at 6.25%."},
    {"rule_id": "US-TX-SALES-002", "name": "TX B2B SaaS/digital exempt", "priority": 95, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-TX"]}, {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, {"eq": ["transaction.buyer.type", "BUSINESS"]}]}, "then": {"set": {"taxable": False, "rate": 0}}, "because": "TX B2B SaaS/digital exempt."},
    {"rule_id": "US-TX-SALES-DEFAULT", "name": "Default fallback", "priority": 0, "when": {"eq": ["transaction.jurisdiction", "US-TX"]}, "then": {"set": {"taxable": False, "rate": 0}}, "because": "Default."},
]

NY_RULES = [
    {"rule_id": "US-NY-SALES-001", "name": "NY SaaS consumer taxable", "priority": 100, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-NY"]}, {"eq": ["transaction.product.category", "SAAS"]}, {"eq": ["transaction.buyer.type", "CONSUMER"]}]}, "then": {"set": {"taxable": True, "rate": 0.04}}, "because": "NY SaaS consumer taxable at 4%."},
    {"rule_id": "US-NY-SALES-DEFAULT", "name": "Default fallback", "priority": 0, "when": {"eq": ["transaction.jurisdiction", "US-NY"]}, "then": {"set": {"taxable": False, "rate": 0}}, "because": "Default."},
]


def _ctx(trans: dict) -> dict:
    return {"transaction": trans}


# =============================================================================
# US-CA / SALES — Compliance-grade ruleset
# =============================================================================

class TestUSCA:
    def test_guardrail_wrong_jurisdiction(self):
        ctx = _ctx({"jurisdiction": "US-TX", "tax_type": "SALES", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-000"
        assert result["taxable"] is False
        assert any(o.type == "INVALID_INPUT" for o in result["obligations"])

    def test_guardrail_wrong_tax_type(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "VAT", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-000"

    def test_refund_event(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "event": {"type": "REFUND"}, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-005"
        assert result["taxable"] is True
        assert result["rate"] == 0.0725
        assert any(o.type == "CREDIT_NOTE_REQUIRED" for o in result["obligations"])

    def test_chargeback_event(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 50, "event": {"type": "CHARGEBACK"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 50)
        assert fired[0].rule_id == "US-CA-SALES-005"
        assert result["tax_amount"] == round(50 * 0.0725, 2)

    def test_marketplace_facilitated(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "marketplace": {"is_facilitated": True}, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-010"
        assert result["taxable"] is False
        assert any(o.type == "MARKETPLACE_FACILITATOR" for o in result["obligations"])

    def test_low_evidence_confidence(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "evidence": {"resolved_confidence": 0.5}, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-020"
        assert result["taxable"] is True
        assert len(result["risk_flags"]) == 1
        assert result["risk_flags"][0]["type"] == "LOW_LOCATION_CONFIDENCE"

    def test_conflicting_evidence(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "evidence": {"billing_country": "US", "ip_country": "DE"}, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-030"
        assert result["risk_flags"][0]["severity"] == "HIGH"

    def test_resale_cert_valid_b2b_physical(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 1000, "buyer": {"type": "BUSINESS"}, "product": {"category": "PHYSICAL_GOODS"}, "doc": {"resale_cert_valid": True}})
        result, fired = evaluate_rules(ctx, CA_RULES, 1000)
        assert fired[0].rule_id == "US-CA-SALES-100"
        assert result["taxable"] is False
        assert any(o.type == "DOCUMENT_RETENTION" for o in result["obligations"])

    def test_resale_cert_missing_b2b_physical(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 1000, "buyer": {"type": "BUSINESS"}, "product": {"category": "TANGIBLE"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 1000)
        assert fired[0].rule_id == "US-CA-SALES-110"
        assert result["taxable"] is True
        assert result["rate"] == 0.0725
        assert len(result["rate_components"]) == 1
        assert result["rate_components"][0]["name"] == "CA_BASE"

    def test_resale_cert_invalid_b2b_physical(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 500, "buyer": {"type": "BUSINESS"}, "product": {"category": "PHYSICAL_GOODS"}, "doc": {"resale_cert_valid": False}})
        result, fired = evaluate_rules(ctx, CA_RULES, 500)
        assert fired[0].rule_id == "US-CA-SALES-110"
        assert result["taxable"] is True

    def test_consumer_physical_shipped_to_ca(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 200, "buyer": {"type": "CONSUMER"}, "product": {"category": "PHYSICAL_GOODS"}, "fulfillment": {"ship_to_region": "CA"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 200)
        assert fired[0].rule_id == "US-CA-SALES-200"
        assert result["taxable"] is True
        assert result["tax_amount"] == 14.5

    def test_digital_saas_consumer_with_evidence(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}, "evidence": {"resolved_country": "US", "resolved_region": "CA", "resolved_confidence": 0.95}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-210"
        assert result["taxable"] is True
        assert result["rate"] == 0.0725
        assert any(o.type == "LOCATION_EVIDENCE_RETENTION" for o in result["obligations"])

    def test_digital_saas_consumer_no_evidence(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 50, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 50)
        assert fired[0].rule_id == "US-CA-SALES-211"
        assert result["taxable"] is True
        assert result["rate"] == 0.0725
        assert result["tax_amount"] == round(50 * 0.0725, 2)

    def test_services_consumer_no_evidence(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SERVICES"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-211"

    def test_district_tax_la_city(self):
        """District tax rule (7600) fires only when no higher-priority consumer/digital rule matches.
        Since buyer=CONSUMER + product=SAAS matches rule 211 (priority 7750) first,
        we test with a product that doesn't match digital/SaaS/services."""
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "evidence": {"locality_code": "LA_CITY"}, "buyer": {"type": "BUSINESS"}, "product": {"category": "OTHER"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-250"
        assert result["rate"] == 0.095
        assert len(result["rate_components"]) == 2
        assert result["rate_components"][0]["name"] == "CA_BASE"
        assert result["rate_components"][1]["name"] == "CA_DISTRICT"

    def test_district_tax_sf_city(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 200, "evidence": {"locality_code": "SF_CITY"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 200)
        assert fired[0].rule_id == "US-CA-SALES-250"
        assert result["tax_amount"] == 19.0

    def test_nexus_threshold_reached(self):
        """Nexus rule (7000) fires only when no higher-priority rule matches.
        Use a non-digital business product so consumer/digital rules don't match first."""
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "metrics": {"ca_revenue_t12m": 600000}, "buyer": {"type": "BUSINESS"}, "product": {"category": "OTHER"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-300"
        assert any(o.type == "NEXUS_THRESHOLD_REACHED" for o in result["obligations"])
        assert any(o.type == "FILING_CALENDAR" for o in result["obligations"])

    def test_fallback_non_taxable(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "SALES", "amount": 100, "buyer": {"type": "BUSINESS"}, "product": {"category": "SERVICES"}})
        result, fired = evaluate_rules(ctx, CA_RULES, 100)
        assert fired[0].rule_id == "US-CA-SALES-999"
        assert result["taxable"] is False


# =============================================================================
# EU / VAT — Compliance-grade ruleset
# =============================================================================

class TestEU:
    def test_guardrail_wrong_jurisdiction(self):
        ctx = _ctx({"jurisdiction": "US-CA", "tax_type": "VAT", "amount": 100})
        result, fired = evaluate_rules(ctx, EU_RULES, 100)
        assert fired[0].rule_id == "EU-VAT-000"

    def test_guardrail_wrong_tax_type(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "SALES", "amount": 100})
        result, fired = evaluate_rules(ctx, EU_RULES, 100)
        assert fired[0].rule_id == "EU-VAT-000"

    def test_refund(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 100, "event": {"type": "REFUND"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 100)
        assert fired[0].rule_id == "EU-VAT-010"
        assert result["rate"] == 0.20
        assert any(o.type == "CREDIT_NOTE_REQUIRED" for o in result["obligations"])

    def test_b2b_valid_vat_reverse_charge(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 500, "buyer": {"type": "BUSINESS", "vat_id": "DE123456789", "vat_id_confidence": 0.95}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 500)
        assert fired[0].rule_id == "EU-VAT-100"
        assert result["taxable"] is True
        assert result["rate"] == 0.0
        assert result["tax_amount"] == 0.0
        assert any(o.type == "REVERSE_CHARGE_APPLIED" for o in result["obligations"])
        assert any(o.type == "INVOICE_TEXT" for o in result["obligations"])
        assert any(o.type == "VAT_ID_RETENTION" for o in result["obligations"])

    def test_b2b_missing_vat_id_treated_as_b2c(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 200, "buyer": {"type": "BUSINESS"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 200)
        assert fired[0].rule_id == "EU-VAT-120"
        assert result["taxable"] is True
        assert result["rate"] == 0.20
        assert result["risk_flags"][0]["type"] == "B2B_WITHOUT_VAT_ID"

    def test_b2b_low_vat_confidence(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 300, "buyer": {"type": "BUSINESS", "vat_id": "XX000", "vat_id_confidence": 0.3}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 300)
        assert fired[0].rule_id == "EU-VAT-120"
        assert result["rate"] == 0.20

    def test_b2c_digital_services(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 50, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 50)
        assert fired[0].rule_id == "EU-VAT-200"
        assert result["taxable"] is True
        assert result["rate"] == 0.20
        assert result["tax_amount"] == 10.0
        assert any(o.type == "EVIDENCE_REQUIRED" for o in result["obligations"])

    def test_b2c_digital_goods(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 25, "buyer": {"type": "CONSUMER"}, "product": {"category": "DIGITAL_GOODS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 25)
        assert fired[0].rule_id == "EU-VAT-200"
        assert result["tax_amount"] == 5.0

    def test_conflicting_evidence(self):
        """Conflicting evidence rule (8900) is lower priority than B2C digital (9000).
        Use a non-digital product so rule 200 doesn't match first."""
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 100, "evidence": {"billing_country": "DE", "ip_country": "FR"}, "buyer": {"type": "CONSUMER"}, "product": {"category": "PHYSICAL_GOODS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 100)
        assert fired[0].rule_id == "EU-VAT-210"
        assert result["risk_flags"][0]["type"] == "CONFLICTING_LOCATION_EVIDENCE"
        assert result["risk_flags"][0]["severity"] == "HIGH"

    def test_oss_threshold_reached(self):
        """OSS rule (8000) is lower priority than B2C digital (9000).
        Use a non-digital product so rule 200 doesn't match first."""
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 100, "metrics": {"eu_b2c_revenue_t12m": 15000}, "buyer": {"type": "CONSUMER"}, "product": {"category": "PHYSICAL_GOODS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 100)
        assert fired[0].rule_id == "EU-VAT-300"
        assert any(o.type == "REGISTRATION_MONITOR" for o in result["obligations"])
        assert any(o.threshold == 10000 for o in result["obligations"] if o.threshold)

    def test_fallback(self):
        ctx = _ctx({"jurisdiction": "EU", "tax_type": "VAT", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "PHYSICAL_GOODS"}})
        result, fired = evaluate_rules(ctx, EU_RULES, 100)
        assert fired[0].rule_id == "EU-VAT-999"
        assert result["taxable"] is False


# =============================================================================
# CA-ON / HST — Ontario
# =============================================================================

class TestCAON:
    def test_digital_saas_consumer_with_evidence(self):
        ctx = _ctx({"jurisdiction": "CA-ON", "tax_type": "HST", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}, "evidence": {"resolved_region": "ON"}})
        result, fired = evaluate_rules(ctx, ON_RULES, 100)
        assert fired[0].rule_id == "CA-ON-HST-010"
        assert result["taxable"] is True
        assert result["rate"] == 0.13
        assert result["tax_amount"] == 13.0
        assert any(o.type == "EVIDENCE_RETENTION" for o in result["obligations"])

    def test_digital_goods_consumer_with_evidence(self):
        ctx = _ctx({"jurisdiction": "CA-ON", "tax_type": "HST", "amount": 50, "buyer": {"type": "CONSUMER"}, "product": {"category": "DIGITAL_GOODS"}, "evidence": {"resolved_region": "ON"}})
        result, fired = evaluate_rules(ctx, ON_RULES, 50)
        assert fired[0].rule_id == "CA-ON-HST-010"
        assert result["tax_amount"] == 6.5

    def test_services_consumer_no_evidence(self):
        ctx = _ctx({"jurisdiction": "CA-ON", "tax_type": "HST", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SERVICES"}})
        result, fired = evaluate_rules(ctx, ON_RULES, 100)
        assert fired[0].rule_id == "CA-ON-HST-011"
        assert result["rate"] == 0.13

    def test_conflicting_evidence(self):
        """Conflicting evidence (8800) is lower than digital consumer rules (9000/8950).
        Use a non-digital product so those don't match first."""
        ctx = _ctx({"jurisdiction": "CA-ON", "tax_type": "HST", "amount": 100, "evidence": {"billing_country": "CA", "ip_country": "US"}, "buyer": {"type": "CONSUMER"}, "product": {"category": "PHYSICAL_GOODS"}})
        result, fired = evaluate_rules(ctx, ON_RULES, 100)
        assert fired[0].rule_id == "CA-ON-HST-050"
        assert result["risk_flags"][0]["type"] == "CONFLICTING_LOCATION_EVIDENCE"

    def test_registration_threshold(self):
        """Registration monitor (8000) is lower than digital consumer (9000/8950).
        Use a non-digital product."""
        ctx = _ctx({"jurisdiction": "CA-ON", "tax_type": "HST", "amount": 100, "metrics": {"ca_revenue_t12m": 50000}, "buyer": {"type": "BUSINESS"}, "product": {"category": "PHYSICAL_GOODS"}})
        result, fired = evaluate_rules(ctx, ON_RULES, 100)
        assert fired[0].rule_id == "CA-ON-HST-200"
        assert any(o.type == "REGISTRATION_MONITOR" for o in result["obligations"])

    def test_fallback(self):
        ctx = _ctx({"jurisdiction": "CA-ON", "tax_type": "HST", "amount": 100, "buyer": {"type": "BUSINESS"}, "product": {"category": "PHYSICAL_GOODS"}})
        result, fired = evaluate_rules(ctx, ON_RULES, 100)
        assert fired[0].rule_id == "CA-ON-HST-999"
        assert result["taxable"] is False


# =============================================================================
# US-TX / SALES — Simple ruleset
# =============================================================================

class TestUSTX:
    def test_saas_consumer_taxable(self):
        ctx = _ctx({"jurisdiction": "US-TX", "tax_type": "SALES", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, TX_RULES, 100)
        assert fired[0].rule_id == "US-TX-SALES-001"
        assert result["taxable"] is True
        assert result["rate"] == 0.0625
        assert result["tax_amount"] == 6.25

    def test_digital_consumer_taxable(self):
        ctx = _ctx({"jurisdiction": "US-TX", "tax_type": "SALES", "amount": 200, "buyer": {"type": "CONSUMER"}, "product": {"category": "DIGITAL_GOODS"}})
        result, fired = evaluate_rules(ctx, TX_RULES, 200)
        assert result["taxable"] is True
        assert result["tax_amount"] == 12.5

    def test_b2b_saas_exempt(self):
        ctx = _ctx({"jurisdiction": "US-TX", "tax_type": "SALES", "amount": 1000, "buyer": {"type": "BUSINESS"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, TX_RULES, 1000)
        assert fired[0].rule_id == "US-TX-SALES-002"
        assert result["taxable"] is False

    def test_fallback(self):
        ctx = _ctx({"jurisdiction": "US-TX", "tax_type": "SALES", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "TANGIBLE"}})
        result, fired = evaluate_rules(ctx, TX_RULES, 100)
        assert fired[0].rule_id == "US-TX-SALES-DEFAULT"
        assert result["taxable"] is False


# =============================================================================
# US-NY / SALES — Simple ruleset
# =============================================================================

class TestUSNY:
    def test_saas_consumer_taxable(self):
        ctx = _ctx({"jurisdiction": "US-NY", "tax_type": "SALES", "amount": 100, "buyer": {"type": "CONSUMER"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, NY_RULES, 100)
        assert fired[0].rule_id == "US-NY-SALES-001"
        assert result["taxable"] is True
        assert result["rate"] == 0.04
        assert result["tax_amount"] == 4.0

    def test_fallback_business(self):
        ctx = _ctx({"jurisdiction": "US-NY", "tax_type": "SALES", "amount": 100, "buyer": {"type": "BUSINESS"}, "product": {"category": "SAAS"}})
        result, fired = evaluate_rules(ctx, NY_RULES, 100)
        assert fired[0].rule_id == "US-NY-SALES-DEFAULT"
        assert result["taxable"] is False


# =============================================================================
# Cross-cutting: operator tests
# =============================================================================

class TestOperators:
    def test_neq(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"neq": ["transaction.jurisdiction", "US-CA"]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "neq", "name": "neq"}]
        result, fired = evaluate_rules(_ctx({"jurisdiction": "US-TX", "amount": 100}), rules, 100)
        assert fired[0].rule_id == "R1"

    def test_gt(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"gt": ["transaction.amount", 50]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "gt", "name": "gt"}]
        result, _ = evaluate_rules(_ctx({"amount": 100}), rules, 100)
        assert result["taxable"] is True
        result2, _ = evaluate_rules(_ctx({"amount": 30}), rules, 30)
        assert result2["taxable"] is False

    def test_gte(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"gte": ["transaction.amount", 100]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "gte", "name": "gte"}]
        result, _ = evaluate_rules(_ctx({"amount": 100}), rules, 100)
        assert result["taxable"] is True

    def test_lt(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"lt": ["transaction.amount", 50]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "lt", "name": "lt"}]
        result, _ = evaluate_rules(_ctx({"amount": 30}), rules, 30)
        assert result["taxable"] is True

    def test_lte(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"lte": ["transaction.amount", 50]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "lte", "name": "lte"}]
        result, _ = evaluate_rules(_ctx({"amount": 50}), rules, 50)
        assert result["taxable"] is True

    def test_in_operator(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "in", "name": "in"}]
        result, _ = evaluate_rules(_ctx({"product": {"category": "SAAS"}, "amount": 100}), rules, 100)
        assert result["taxable"] is True
        result2, _ = evaluate_rules(_ctx({"product": {"category": "TANGIBLE"}, "amount": 100}), rules, 100)
        assert result2["taxable"] is False

    def test_exists(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"exists": "transaction.buyer.vat_id"}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "exists", "name": "exists"}]
        result, _ = evaluate_rules(_ctx({"buyer": {"vat_id": "DE123"}, "amount": 100}), rules, 100)
        assert result["taxable"] is True
        result2, _ = evaluate_rules(_ctx({"buyer": {}, "amount": 100}), rules, 100)
        assert result2["taxable"] is False

    def test_not_exists(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"not_exists": ["transaction.doc.resale_cert_valid"]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "not_exists", "name": "not_exists"}]
        result, _ = evaluate_rules(_ctx({"amount": 100}), rules, 100)
        assert result["taxable"] is True
        result2, _ = evaluate_rules(_ctx({"doc": {"resale_cert_valid": True}, "amount": 100}), rules, 100)
        assert result2["taxable"] is False

    def test_path_neq(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"path_neq": ["transaction.evidence.billing_country", "transaction.evidence.ip_country"]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "path_neq", "name": "path_neq"}]
        result, _ = evaluate_rules(_ctx({"evidence": {"billing_country": "US", "ip_country": "DE"}, "amount": 100}), rules, 100)
        assert result["taxable"] is True
        result2, _ = evaluate_rules(_ctx({"evidence": {"billing_country": "US", "ip_country": "US"}, "amount": 100}), rules, 100)
        assert result2["taxable"] is False

    def test_any_combinator(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"any": [{"eq": ["transaction.buyer.type", "CONSUMER"]}, {"eq": ["transaction.buyer.type", "BUSINESS"]}]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "any", "name": "any"}]
        result, _ = evaluate_rules(_ctx({"buyer": {"type": "CONSUMER"}, "amount": 100}), rules, 100)
        assert result["taxable"] is True

    def test_all_combinator(self):
        rules = [{"rule_id": "R1", "priority": 10, "when": {"all": [{"eq": ["transaction.buyer.type", "CONSUMER"]}, {"gt": ["transaction.amount", 50]}]}, "then": {"set": {"taxable": True, "rate": 0.1}}, "because": "all", "name": "all"}]
        result, _ = evaluate_rules(_ctx({"buyer": {"type": "CONSUMER"}, "amount": 100}), rules, 100)
        assert result["taxable"] is True
        result2, _ = evaluate_rules(_ctx({"buyer": {"type": "CONSUMER"}, "amount": 10}), rules, 10)
        assert result2["taxable"] is False

    def test_first_match_wins(self):
        rules = [
            {"rule_id": "HIGH", "priority": 100, "when": {"eq": ["transaction.amount", 100]}, "then": {"set": {"taxable": True, "rate": 0.99}}, "because": "high", "name": "high"},
            {"rule_id": "LOW", "priority": 1, "when": {"exists": "transaction.amount"}, "then": {"set": {"taxable": False, "rate": 0}}, "because": "low", "name": "low"},
        ]
        result, fired = evaluate_rules(_ctx({"amount": 100}), rules, 100)
        assert fired[0].rule_id == "HIGH"
        assert result["rate"] == 0.99
