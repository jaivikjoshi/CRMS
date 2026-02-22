# Sample Data

This folder contains sample requests and pre-generated responses for the CRMS evaluation API.

## Files

| File | Description |
|------|-------------|
| `sample_requests.json` | 100 example evaluation requests (transactions) |
| `sample_responses.json` | Corresponding evaluation results |

## Regenerating Responses

To regenerate `sample_responses.json` from `sample_requests.json` (e.g. after changing rules):

```bash
python scripts/generate_sample_responses.py
```

No database or API server required—the script runs the rule evaluator in-memory.

## Rule Coverage

The samples exercise all three seed rules:

- **US-CA-SALES-001** — CA SaaS + CONSUMER → taxable 7.25%, NEXUS_MONITOR obligation
- **US-CA-SALES-002** — CA SaaS + BUSINESS → exempt
- **US-CA-SALES-DEFAULT** — CA other → exempt (default fallback)
