#!/usr/bin/env python3
"""
Seed script: creates tenant, API key, ruleset US-CA/SALES, rules, and publishes v1.0.0.
Run after migrations: python scripts/seed.py
"""

import asyncio
import os
import sys
from datetime import datetime
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from crms.config import settings
from crms.auth.middleware import hash_api_key
from crms.utils.canonical import bundle_hash


API_KEY = "sk_demo_crms_12345"  # Demo API key - print this for user


async def seed():
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        tenant_id = str(uuid4())
        api_key_hash = hash_api_key(API_KEY)
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

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

        # Get or create ruleset
        result = await session.execute(
            text("""
                SELECT ruleset_id FROM rulesets
                WHERE tenant_id = :tid AND jurisdiction = 'US-CA' AND tax_type = 'SALES'
            """),
            {"tid": tenant_id},
        )
        row = result.fetchone()
        if row:
            ruleset_id = str(row[0])
            print("Ruleset already exists, re-seeding rules.")
        else:
            ruleset_id = str(uuid4())
            await session.execute(
                text("""
                    INSERT INTO rulesets (ruleset_id, tenant_id, jurisdiction, tax_type, name, created_at)
                    VALUES (:rid, :tid, 'US-CA', 'SALES', 'CA Sales Tax', :now)
                """),
                {"rid": ruleset_id, "tid": tenant_id, "now": now},
            )
            await session.commit()

        # Delete existing draft rules and re-insert
        await session.execute(
            text("DELETE FROM rules WHERE ruleset_id = :rsid"),
            {"rsid": ruleset_id},
        )
        await session.commit()

        # Create rules (draft)
        rules_data = [
            {
                "rule_id": "US-CA-SALES-001",
                "name": "CA SaaS consumer taxable",
                "priority": 10,
                "rule_json": {
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
            },
            {
                "rule_id": "US-CA-SALES-002",
                "name": "CA B2B SaaS exempt",
                "priority": 5,
                "rule_json": {
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
            },
            {
                "rule_id": "US-CA-SALES-DEFAULT",
                "name": "Default fallback",
                "priority": 0,
                "rule_json": {
                    "rule_id": "US-CA-SALES-DEFAULT",
                    "name": "Default fallback",
                    "priority": 0,
                    "when": {"eq": ["transaction.jurisdiction", "US-CA"]},
                    "then": {"set": {"taxable": False, "rate": 0}, "emit_obligations": []},
                    "because": "Default: not taxable.",
                },
            },
        ]

        for r in rules_data:
            await session.execute(
                text("""
                    INSERT INTO rules (rule_pk, ruleset_id, rule_id, name, priority, rule_json, state, updated_at)
                    VALUES (:pk, :rsid, :rid, :name, :prio, :json::jsonb, 'draft', :now)
                """),
                {
                    "pk": str(uuid4()),
                    "rsid": ruleset_id,
                    "rid": r["rule_id"],
                    "name": r["name"],
                    "prio": r["priority"],
                    "json": __import__("json").dumps(r["rule_json"]),
                    "now": now,
                },
            )
        await session.commit()

        # Load draft rules and publish
        result = await session.execute(
            text("""
                SELECT rule_json FROM rules
                WHERE ruleset_id = :rsid AND state = 'draft'
                ORDER BY priority DESC
            """),
            {"rsid": ruleset_id},
        )
        rows = result.fetchall()
        rules = [row[0] for row in rows]
        if not rules:
            print("No draft rules found.")
            return

        # Check if version 1.0.0 already exists
        result = await session.execute(
            text("""
                SELECT version_id FROM ruleset_versions
                WHERE ruleset_id = :rsid AND version = '1.0.0'
            """),
            {"rsid": ruleset_id},
        )
        if result.fetchone():
            print("Version 1.0.0 already published.")
        else:
                bh = bundle_hash(rules)
            version_id = str(uuid4())
            eff_from = "2026-02-01T00:00:00Z"

            # Close previous version if any
            await session.execute(
                text("""
                    UPDATE ruleset_versions
                    SET effective_to = :eff::timestamptz
                    WHERE ruleset_id = :rsid AND (effective_to IS NULL OR effective_to > :eff::timestamptz)
                """),
                {"eff": eff_from, "rsid": ruleset_id},
            )

            await session.execute(
                text("""
                    INSERT INTO ruleset_versions
                    (version_id, ruleset_id, version, effective_from, effective_to, bundle_hash, bundle_json, published_at, change_summary)
                    VALUES (:vid, :rsid, '1.0.0', :eff_from::timestamptz, NULL, :bh, :bundle::jsonb, :now::timestamptz, 'Initial seed')
                """),
                {
                    "vid": version_id,
                    "rsid": ruleset_id,
                    "eff_from": eff_from,
                    "bh": bh,
                    "bundle": __import__("json").dumps(bundle),
                    "now": now,
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
