# CRMS - Compliance Rules Microservice

A production-style microservice that evaluates compliance/tax rules for transactions using versioned rulesets. Returns taxability, rate, obligations, and explanation with immutable audit logs.

## Quick Start

### 1. Start Postgres

```bash
docker-compose up -d postgres
```

### 2. Run Migrations

```bash
# Install deps
pip install -r requirements.txt

# Run migrations (uses DATABASE_URL from .env or default)
alembic upgrade head
```

### 3. Seed Data

```bash
python scripts/seed.py
```

This creates a tenant, API key, ruleset US-CA/SALES, and publishes version 1.0.0. **Save the API key** printed at the end.

### 4. Start API

```bash
uvicorn crms.main:app --reload --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker-compose up api
```

## API Examples

### Evaluate Transaction

```bash
curl -X POST http://localhost:8000/v1/evaluations \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "inv_123",
    "effective_at": "2026-02-20T00:00:00Z",
    "transaction": {
      "jurisdiction": "US-CA",
      "tax_type": "SALES",
      "currency": "USD",
      "amount": 100.00,
      "product": { "category": "SAAS" },
      "buyer": { "type": "CONSUMER" }
    }
  }'
```

### Get Audit Record

```bash
curl http://localhost:8000/v1/evaluations/{evaluation_id} \
  -H "Authorization: Bearer sk_demo_crms_12345"
```

### Admin: Create Ruleset

```bash
curl -X POST http://localhost:8000/v1/admin/rulesets \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{"jurisdiction": "US-CA", "tax_type": "SALES", "name": "CA Sales Tax"}'
```

### Admin: Add Rule

```bash
curl -X POST http://localhost:8000/v1/admin/rulesets/{ruleset_id}/rules \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "US-CA-SALES-001",
    "name": "CA SaaS consumer taxable",
    "priority": 10,
    "when": {
      "all": [
        {"eq": ["transaction.jurisdiction", "US-CA"]},
        {"eq": ["transaction.product.category", "SAAS"]},
        {"eq": ["transaction.buyer.type", "CONSUMER"]}
      ]
    },
    "then": {"set": {"taxable": true, "rate": 0.0725}, "emit_obligations": []},
    "because": "CA SaaS sold to consumers taxable."
  }'
```

### Admin: Publish Version

```bash
curl -X POST http://localhost:8000/v1/admin/rulesets/{ruleset_id}/publish \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{"effective_from": "2026-02-01T00:00:00Z", "change_summary": "Add SaaS consumer rule"}'
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql+asyncpg://crms:crms_secret@localhost:5432/crms | Postgres connection |
| API_KEY_HASH_SALT | default_salt_change_in_prod | Salt for API key hashing |
| LOG_LEVEL | INFO | Logging level |

## Testing

```bash
pytest
```

Unit tests cover the rule evaluator and canonical hashing. Integration tests require a running Postgres.

## Docs

- **OpenAPI**: http://localhost:8000/docs
- **System Design**: [docs/system_design.md](docs/system_design.md)
# CRMS
