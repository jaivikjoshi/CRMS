#!/usr/bin/env python3
"""
Test API with frontend preset transactions.
Verifies the new compliance rulesets work end-to-end.
Usage: python scripts/test_api_presets.py [API_URL]
Default API_URL: https://crms-pu5p.onrender.com
"""

import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

API_URL = (sys.argv[1] if len(sys.argv) > 1 else "https://crms-pu5p.onrender.com").rstrip("/")
API_KEY = "sk_demo_crms_12345"
TIMEOUT = 60.0  # Render free tier may take ~30s to wake

# Same presets as frontend App.jsx
PRESETS = [
    ("CA SaaS → Consumer", {"jurisdiction": "US-CA", "tax_type": "SALES", "currency": "USD", "amount": 100, "product": {"category": "SAAS"}, "buyer": {"type": "CONSUMER"}}),
    ("CA SaaS → Business", {"jurisdiction": "US-CA", "tax_type": "SALES", "currency": "USD", "amount": 5000, "product": {"category": "SAAS"}, "buyer": {"type": "BUSINESS"}}),
    ("CA Tangible → Consumer", {"jurisdiction": "US-CA", "tax_type": "SALES", "currency": "USD", "amount": 250.5, "product": {"category": "TANGIBLE"}, "buyer": {"type": "CONSUMER"}}),
    ("CA Digital → Consumer", {"jurisdiction": "US-CA", "tax_type": "SALES", "currency": "USD", "amount": 19.99, "product": {"category": "DIGITAL_GOODS"}, "buyer": {"type": "CONSUMER"}}),
    ("TX SaaS → Consumer", {"jurisdiction": "US-TX", "tax_type": "SALES", "currency": "USD", "amount": 100, "product": {"category": "SAAS"}, "buyer": {"type": "CONSUMER"}}),
    ("TX Tangible → Business", {"jurisdiction": "US-TX", "tax_type": "SALES", "currency": "USD", "amount": 500, "product": {"category": "TANGIBLE"}, "buyer": {"type": "BUSINESS"}}),
    ("NY SaaS → Consumer", {"jurisdiction": "US-NY", "tax_type": "SALES", "currency": "USD", "amount": 99, "product": {"category": "SAAS"}, "buyer": {"type": "CONSUMER"}}),
    ("EU B2C Digital", {"jurisdiction": "EU", "tax_type": "VAT", "currency": "EUR", "amount": 50, "product": {"category": "SAAS"}, "buyer": {"type": "CONSUMER"}}),
    ("EU B2B Reverse Charge", {"jurisdiction": "EU", "tax_type": "VAT", "currency": "EUR", "amount": 500, "product": {"category": "SAAS"}, "buyer": {"type": "BUSINESS", "vat_id": "DE123456789", "vat_id_confidence": 0.95}}),
    ("CA-ON Digital Consumer", {"jurisdiction": "CA-ON", "tax_type": "HST", "currency": "CAD", "amount": 100, "product": {"category": "SAAS"}, "buyer": {"type": "CONSUMER"}}),
]

# Expected: (taxable, approximate_rate_or_none, rule_id_contains)
EXPECTED = {
    "CA SaaS → Consumer": (True, 0.0725, "211"),
    "CA SaaS → Business": (False, 0.0, "999"),
    "CA Tangible → Consumer": (False, 0.0, "999"),  # No ship_to_region; TANGIBLE not in digital list → fallback
    "CA Digital → Consumer": (True, 0.0725, "211"),
    "TX SaaS → Consumer": (True, 0.0625, "001"),
    "TX Tangible → Business": (False, 0.0, "DEFAULT"),
    "NY SaaS → Consumer": (True, 0.04, "001"),
    "EU B2C Digital": (True, 0.20, "200"),
    "EU B2B Reverse Charge": (True, 0.0, "100"),  # reverse charge = 0% collected
    "CA-ON Digital Consumer": (True, 0.13, "011"),  # or 010 if evidence - we don't have evidence, so 011
}

def main():
    print(f"Testing API: {API_URL}")
    print(f"(Render free tier may take ~30s to wake on first request)\n")

    passed = 0
    failed = 0

    for label, trans in PRESETS:
        body = {"effective_at": "2026-02-20T00:00:00Z", "transaction": trans}
        try:
            r = httpx.post(
                f"{API_URL}/v1/evaluations",
                json=body,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                timeout=TIMEOUT,
            )
            data = r.json()
        except Exception as e:
            print(f"❌ {label}: {e}")
            failed += 1
            continue

        if r.status_code != 200:
            print(f"❌ {label}: HTTP {r.status_code} — {data.get('detail', data)}")
            failed += 1
            continue

        result = data.get("result", {})
        explanation = data.get("explanation", {})
        fired = explanation.get("fired_rules", [])
        rule_id = fired[0]["rule_id"] if fired else ""

        exp_taxable, exp_rate, exp_rule = EXPECTED.get(label, (None, None, ""))

        ok = True
        if exp_taxable is not None and result.get("taxable") != exp_taxable:
            ok = False
        if exp_rate is not None and result.get("rate") != exp_rate:
            ok = False
        if exp_rule and exp_rule not in rule_id:
            ok = False

        if ok:
            print(f"✅ {label}: taxable={result.get('taxable')}, rate={result.get('rate')} → {rule_id}")
            passed += 1
        else:
            print(f"❌ {label}: expected taxable={exp_taxable}, rate={exp_rate}, rule~{exp_rule}")
            print(f"   got: taxable={result.get('taxable')}, rate={result.get('rate')}, rule={rule_id}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
