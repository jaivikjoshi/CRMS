# CRMS System Design

## Overview

CRMS (Compliance Rules Microservice) evaluates compliance/tax rules for transactions using versioned rulesets. It returns taxability, rate, obligations, and an explanation of which rules fired.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│  Postgres   │
│             │     │  CRMS API   │     │             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   Engine    │
                   │  Evaluator  │
                   └─────────────┘
```

## Components

### API Layer
- **Auth**: API key via `Authorization: Bearer <key>`, tenant derived from key
- **Evaluations**: POST /v1/evaluations, GET /v1/evaluations/{id}
- **Admin**: Rulesets, rules, publish

### Engine
- **Version resolver**: Selects ruleset version by `effective_at` (effective_from <= effective_at < effective_to)
- **Rule evaluator**: First-match-wins, priority DESC, supports eq/neq/gt/gte/lt/lte/in/exists, all/any

### Storage
- **tenants**: API key hash, tenant_id
- **rulesets**: jurisdiction + tax_type per tenant
- **rules**: Draft rules (rule_json)
- **ruleset_versions**: Published bundles with effective windows
- **evaluations**: Append-only audit log

## Data Flow

1. **Evaluation**: Client sends transaction + effective_at
2. Resolve ruleset by jurisdiction/tax_type
3. Resolve version by effective_at
4. Check idempotency (tenant + idempotency_key)
5. Evaluate rules (first match wins)
6. Persist evaluation, return result + explanation

## Determinism

- Same inputs + same version → same output
- Canonical JSON hashing for request_hash and bundle_hash
- Rules evaluated in fixed priority order
