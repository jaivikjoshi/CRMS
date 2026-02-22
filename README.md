# CRMS — Compliance Rules Microservice

A production-style microservice that evaluates compliance and tax rules for transactions. Send a transaction, get back taxability, rate, obligations, and a clear explanation of which rules applied—with full audit trails and versioned rulesets.

---

## What It Does

CRMS is a **rules engine** for tax and compliance. You define rules (e.g., "CA SaaS sold to consumers is taxable at 7.25%"), and the service evaluates transactions against them.

**Example:** A $100 SaaS sale in California to a consumer → **taxable: true**, **rate: 7.25%**, **tax_amount: $7.25**, plus an explanation of which rule fired.

### Key Features

- **Versioned rulesets** — Rules have effective dates; evaluations use the correct version for the given time
- **Explainability** — Every response includes which rules fired and why
- **Audit trail** — Every evaluation is stored and retrievable
- **Idempotency** — Safe retries with the same result when using an idempotency key
- **Multi-tenant** — API key auth with tenant isolation

---

## Architecture

```
┌─────────────┐     POST /v1/evaluations      ┌─────────────────┐
│   Client    │ ─────────────────────────────▶│  FastAPI (CRMS)  │
│             │                               │  • Auth          │
└─────────────┘                               │  • Version lookup │
                                              │  • Rule engine   │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │    Postgres      │
                                              │  (Supabase OK)   │
                                              └─────────────────┘
```

**Flow:** Request → API key auth → Find ruleset → Resolve version by `effective_at` → Evaluate rules (first match wins) → Persist audit record → Return result + explanation.

---

## Prerequisites

- **Python 3.11+**
- **PostgreSQL** — Either:
  - Docker (recommended), or
  - Local Postgres, or
  - [Supabase](https://supabase.com) (free tier)

---

## Setup & Run (After Cloning)

### Option A: Docker (Postgres + API)

If you have Docker installed:

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd CRMS

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start Postgres
docker compose up -d postgres

# 4. Run migrations
alembic upgrade head

# 5. Seed demo data (creates tenant, ruleset, rules, version 1.0.0)
python scripts/seed.py
# Save the API key printed at the end (e.g. sk_demo_crms_12345)

# 6. Start the API
uvicorn crms.main:app --reload --port 8000
```

### Option B: Supabase (No Docker)

If you don't have Docker, use a free [Supabase](https://supabase.com) database:

1. **Create a Supabase project** at [supabase.com](https://supabase.com) and note your database password.

2. **Get the connection string**  
   Project Settings → Database → Connection string (URI) → Use the **direct** connection (port 5432).

3. **Create `.env`** in the project root:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:

   ```
   DATABASE_URL=postgresql+asyncpg://postgres.[project-ref]:[YOUR_PASSWORD]@db.[project-ref].supabase.co:5432/postgres?sslmode=require
   ```

   Replace `[YOUR_PASSWORD]` and `[project-ref]` with your values.

4. **Install, migrate, seed, and run:**

   ```bash
   pip install -r requirements.txt
   alembic upgrade head
   python scripts/seed.py
   uvicorn crms.main:app --reload --port 8000
   ```

---

## Verify It Works

**1. Health check**

```bash
curl http://localhost:8000/health
```

**2. Evaluate a transaction**

```bash
curl -X POST http://localhost:8000/v1/evaluations \
  -H "Authorization: Bearer sk_demo_crms_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "effective_at": "2026-02-20T00:00:00Z",
    "transaction": {
      "jurisdiction": "US-CA",
      "tax_type": "SALES",
      "amount": 100,
      "product": {"category": "SAAS"},
      "buyer": {"type": "CONSUMER"}
    }
  }'
```

Expected: `taxable: true`, `rate: 0.0725`, `tax_amount: 7.25`, and a fired rule in the explanation.

**3. Interactive API docs**

- Swagger UI: http://localhost:8000/docs  
- ReDoc: http://localhost:8000/redoc  

---

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/evaluations` | POST | Evaluate a transaction |
| `/v1/evaluations/{id}` | GET | Fetch an audit record |
| `/v1/admin/rulesets` | POST | Create a ruleset |
| `/v1/admin/rulesets/{id}/rules` | POST | Add or update a rule |
| `/v1/admin/rulesets/{id}/publish` | POST | Publish a new version |
| `/health` | GET | Health check |
| `/metrics` | GET | Basic metrics |

All endpoints except `/health` and `/metrics` require:

```
Authorization: Bearer <your-api-key>
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://crms:crms_secret@localhost:5432/crms` | Postgres connection string |
| `API_KEY_HASH_SALT` | `default_salt_change_in_prod` | Salt for API key hashing (change in production) |
| `LOG_LEVEL` | `INFO` | Logging level |

For Supabase, append `?sslmode=require` to `DATABASE_URL`.

---

## Project Structure

```
CRMS/
├── crms/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings from .env
│   ├── database.py          # DB engine, sessions, Supabase SSL
│   ├── api/
│   │   ├── evaluations.py   # Evaluate + get audit
│   │   ├── admin.py         # Rulesets, rules, publish
│   │   └── health.py        # Health + metrics
│   ├── auth/middleware.py   # API key → tenant
│   ├── engine/evaluator.py  # Rule evaluation (first match wins)
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic request/response
│   ├── storage/repositories.py
│   └── utils/canonical.py   # JSON hashing
├── alembic/                 # Migrations
├── scripts/seed.py          # Demo tenant, ruleset, rules
├── tests/                   # pytest
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Rule Format

Rules are JSON with `when` (conditions), `then` (actions), and `because` (explanation):

```json
{
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
  "then": {
    "set": {"taxable": true, "rate": 0.0725},
    "emit_obligations": [{"type": "NEXUS_MONITOR", "threshold": 500000}]
  },
  "because": "CA SaaS sold to consumers taxable."
}
```

**Operators:** `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `exists`  
**Combinators:** `all`, `any`  
**Semantics:** Rules sorted by priority (desc); first match wins.

---

## Testing

```bash
pytest
```

Unit tests cover the rule evaluator and canonical hashing. Integration tests assume a running Postgres.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: psycopg2` | Use `postgresql+asyncpg://` in `DATABASE_URL` (async driver) |
| `ssl.SSLCertVerificationError` (Supabase) | The project uses a permissive SSL context for Supabase on macOS |
| `column created_at is of type timestamp` | Ensure migrations are up to date: `alembic upgrade head` |
| No rules firing | Ensure transaction is wrapped as `{"transaction": {...}}` in the evaluator context |

---

## Sample Data (No Setup Required)

To see example inputs and outputs without running the API:

- **`examples/sample_requests.json`** — 100 sample evaluation requests
- **`examples/sample_responses.json`** — Corresponding results (taxable, rate, fired rules)

To regenerate responses after changing rules:

```bash
python scripts/generate_sample_responses.py
```

See [examples/README.md](examples/README.md) for details.

---

## Deploy to Render

See [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) for step-by-step instructions. Two options:

- **Blueprint** — Uses Render Postgres (one-click)
- **Manual** — Use your existing Supabase database

---

## Documentation

- **System design:** [docs/system_design.md](docs/system_design.md)
- **OpenAPI:** http://localhost:8000/docs (when server is running)

---

## License

See repository license file.
