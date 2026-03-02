#!/usr/bin/env python3
"""
Seed script: creates tenant, API key, compliance-grade rulesets (US-CA, EU, CA-ON, US-TX, US-NY).
Run after migrations: python scripts/seed.py
See docs/TRANSACTION_SCHEMA.md for transaction field assumptions.
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from crms.database import get_engine_url_and_connect_args
from crms.auth.middleware import hash_api_key
from crms.utils.canonical import bundle_hash

# Load compliance rulesets from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compliance_rulesets import COMPLIANCE_RULESETS


API_KEY = "sk_demo_crms_12345"  # Demo API key - print this for user

# Simple rulesets (US-TX, US-NY) for backward compat
SIMPLE_RULESETS = [
    {"jurisdiction": "US-TX", "tax_type": "SALES", "name": "TX Sales Tax", "rules": [
        {"rule_id": "US-TX-SALES-001", "name": "TX SaaS/digital consumer taxable", "priority": 100, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-TX"]}, {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, {"eq": ["transaction.buyer.type", "CONSUMER"]}]}, "then": {"set": {"taxable": True, "rate": 0.0625}, "emit_obligations": []}, "because": "TX SaaS/digital sold to consumers taxable at 6.25%."},
        {"rule_id": "US-TX-SALES-002", "name": "TX B2B SaaS/digital exempt", "priority": 95, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-TX"]}, {"in": ["transaction.product.category", ["SAAS", "DIGITAL_GOODS"]]}, {"eq": ["transaction.buyer.type", "BUSINESS"]}]}, "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []}, "because": "TX B2B SaaS/digital exempt."},
        {"rule_id": "US-TX-SALES-DEFAULT", "name": "Default fallback", "priority": 0, "when": {"eq": ["transaction.jurisdiction", "US-TX"]}, "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []}, "because": "Default: not taxable."},
    ]},
    {"jurisdiction": "US-NY", "tax_type": "SALES", "name": "NY Sales Tax", "rules": [
        {"rule_id": "US-NY-SALES-001", "name": "NY SaaS consumer taxable", "priority": 100, "when": {"all": [{"eq": ["transaction.jurisdiction", "US-NY"]}, {"eq": ["transaction.product.category", "SAAS"]}, {"eq": ["transaction.buyer.type", "CONSUMER"]}]}, "then": {"set": {"taxable": True, "rate": 0.04}, "emit_obligations": []}, "because": "NY SaaS sold to consumers taxable at 4%."},
        {"rule_id": "US-NY-SALES-DEFAULT", "name": "Default fallback", "priority": 0, "when": {"eq": ["transaction.jurisdiction", "US-NY"]}, "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []}, "because": "Default: not taxable."},
    ]},
]

RULESETS = COMPLIANCE_RULESETS + SIMPLE_RULESETS


async def seed():
    url, connect_args = get_engine_url_and_connect_args()
    engine = create_async_engine(url, connect_args=connect_args)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        tenant_id = str(uuid4())
        api_key_hash = hash_api_key(API_KEY)
        now = datetime.now(UTC)

        # Check if tenant exists
        result = await session.execute(
            text("SELECT tenant_id FROM tenants WHERE api_key_hash = :hash"),
            {"hash": api_key_hash},
        )
        row = result.fetchone()
        if row:
            tenant_id = str(row[0])
            print("Tenant already exists, using existing.")
        else:
            await session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, name, api_key_hash, created_at)
                    VALUES (:tid, :name, :hash, :now)
                """),
                {"tid": tenant_id, "name": "Demo Tenant", "hash": api_key_hash, "now": now},
            )
            await session.commit()

        # Seed each ruleset
        for rs_def in RULESETS:
            jur, tax_type, rs_name = rs_def["jurisdiction"], rs_def["tax_type"], rs_def["name"]
            result = await session.execute(
                text("""
                    SELECT ruleset_id FROM rulesets
                    WHERE tenant_id = :tid AND jurisdiction = :jur AND tax_type = :tax
                """),
                {"tid": tenant_id, "jur": jur, "tax": tax_type},
            )
            row = result.fetchone()
            if row:
                ruleset_id = str(row[0])
                print(f"Ruleset {jur}/{tax_type} exists, re-seeding rules.")
            else:
                ruleset_id = str(uuid4())
                await session.execute(
                    text("""
                        INSERT INTO rulesets (ruleset_id, tenant_id, jurisdiction, tax_type, name, created_at)
                        VALUES (:rid, :tid, :jur, :tax, :name, :now)
                    """),
                    {"rid": ruleset_id, "tid": tenant_id, "jur": jur, "tax": tax_type, "name": rs_name, "now": now},
                )
                await session.commit()

            await session.execute(
                text("DELETE FROM rules WHERE ruleset_id = :rsid"),
                {"rsid": ruleset_id},
            )
            await session.commit()

            for r in rs_def["rules"]:
                rule_json = {**r, "rule_id": r["rule_id"], "name": r["name"], "priority": r["priority"]}
                await session.execute(
                    text("""
                        INSERT INTO rules (rule_pk, ruleset_id, rule_id, name, priority, rule_json, state, updated_at)
                        VALUES (:pk, :rsid, :rid, :name, :prio, CAST(:json AS jsonb), 'draft', :now)
                    """),
                    {
                        "pk": str(uuid4()),
                        "rsid": ruleset_id,
                        "rid": r["rule_id"],
                        "name": r["name"],
                        "prio": r["priority"],
                        "json": json.dumps(rule_json),
                        "now": now,
                    },
                )
            await session.commit()

            result = await session.execute(
                text("""
                    SELECT rule_json FROM rules
                    WHERE ruleset_id = :rsid AND state = 'draft'
                    ORDER BY priority DESC
                """),
                {"rsid": ruleset_id},
            )
            rules = [row[0] for row in result.fetchall()]
            if not rules:
                print(f"No draft rules for {jur}/{tax_type}.")
                continue

            bh = bundle_hash(rules)
            version_id = str(uuid4())
            eff_from = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)

            # Check if we need 1.0.0 (fresh) or 1.1.0 (update)
            result = await session.execute(
                text("SELECT version FROM ruleset_versions WHERE ruleset_id = :rsid ORDER BY version DESC LIMIT 1"),
                {"rsid": ruleset_id},
            )
            row = result.fetchone()
            next_version = "1.1.0" if row else "1.0.0"

            # Close any open version so the new one takes effect
            await session.execute(
                text("""
                    UPDATE ruleset_versions
                    SET effective_to = :eff
                    WHERE ruleset_id = :rsid AND (effective_to IS NULL OR effective_to > :eff)
                """),
                {"eff": eff_from, "rsid": ruleset_id},
            )
            await session.execute(
                text("""
                    INSERT INTO ruleset_versions
                    (version_id, ruleset_id, version, effective_from, effective_to, bundle_hash, bundle_json, published_at, change_summary)
                    VALUES (:vid, :rsid, :version, :eff_from, NULL, :bh, CAST(:bundle AS jsonb), :now, :summary)
                """),
                {
                    "vid": version_id,
                    "rsid": ruleset_id,
                    "version": next_version,
                    "eff_from": eff_from,
                    "bh": bh,
                    "bundle": json.dumps({"rules": rules}),
                    "now": now,
                    "summary": "Initial seed" if next_version == "1.0.0" else "Expanded ruleset",
                },
            )
            await session.commit()

    print("Seed complete!")
    print(f"API Key: {API_KEY}")
    print(f"Use: Authorization: Bearer {API_KEY}")
    print("Example: curl -X POST http://localhost:8000/v1/evaluations \\")
    print('  -H "Authorization: Bearer ' + API_KEY + '" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"effective_at":"2026-02-20T00:00:00Z","transaction":{"jurisdiction":"US-CA","tax_type":"SALES","amount":100,"product":{"category":"SAAS"},"buyer":{"type":"CONSUMER"}}}\'')


if __name__ == "__main__":
    asyncio.run(seed())
