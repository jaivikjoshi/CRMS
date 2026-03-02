# Sample Data

This folder contains sample requests and pre-generated responses for the CRMS evaluation API.

## Files

| File | Description |
|------|-------------|
| `sample_requests.json` | 40 example evaluation requests covering all rulesets and rule paths |
| `sample_responses.json` | Corresponding evaluation results (taxable, rate, obligations, risk_flags, etc.) |

## Regenerating Responses

To regenerate `sample_responses.json` from `sample_requests.json` (e.g. after changing rules):

```bash
python scripts/generate_sample_responses.py
```

No database or API server required—the script runs the rule evaluator in-memory against all compliance rulesets.

## Rule Coverage

The samples exercise every rule path across all rulesets:

### US-CA / SALES (18 requests)
| Idempotency | Rule | Scenario |
|-------------|------|----------|
| ca_001 | US-CA-SALES-211 | Consumer SaaS (simplified, no evidence) |
| ca_002 | US-CA-SALES-999 | B2B SaaS fallback exempt |
| ca_003–004 | US-CA-SALES-005 | REFUND, CHARGEBACK |
| ca_005 | US-CA-SALES-010 | Marketplace facilitated |
| ca_006 | US-CA-SALES-020 | Low evidence confidence + risk flag |
| ca_007 | US-CA-SALES-030 | Conflicting evidence (billing≠IP) |
| ca_008 | US-CA-SALES-100 | B2B physical + valid resale cert → exempt |
| ca_009–010 | US-CA-SALES-110 | B2B physical, no/invalid cert → taxable + rate_components |
| ca_011 | US-CA-SALES-200 | Consumer physical shipped to CA |
| ca_012 | US-CA-SALES-210 | Digital with evidence (US/CA) |
| ca_013–014 | US-CA-SALES-211 | Digital goods, services (consumer) |
| ca_015–016 | US-CA-SALES-250 | District tax (LA_CITY, SF_CITY) |
| ca_017 | US-CA-SALES-300 | Nexus threshold reached |
| ca_018 | US-CA-SALES-999 | B2B other fallback |

### EU / VAT (9 requests)
| Idempotency | Rule | Scenario |
|-------------|------|----------|
| eu_001 | EU-VAT-010 | Refund |
| eu_002 | EU-VAT-100 | B2B valid VAT ID → reverse charge (0%) |
| eu_003 | EU-VAT-120 | B2B missing VAT ID → B2C rate + risk flag |
| eu_004 | EU-VAT-120 | B2B low VAT confidence |
| eu_005–006 | EU-VAT-200 | B2C digital (SAAS, DIGITAL_GOODS) |
| eu_007 | EU-VAT-210 | Conflicting evidence |
| eu_008 | EU-VAT-300 | OSS threshold |
| eu_009 | EU-VAT-999 | Fallback |

### CA-ON / HST (6 requests)
| Idempotency | Rule | Scenario |
|-------------|------|----------|
| on_001–002 | CA-ON-HST-010 | Digital with evidence (ON) |
| on_003 | CA-ON-HST-011 | Services consumer (simplified) |
| on_004 | CA-ON-HST-050 | Conflicting evidence |
| on_005 | CA-ON-HST-200 | Registration monitor |
| on_006 | CA-ON-HST-999 | Fallback |

### US-TX / SALES (4 requests)
| Idempotency | Rule | Scenario |
|-------------|------|----------|
| tx_001–002 | US-TX-SALES-001 | SaaS, digital consumer → 6.25% |
| tx_003 | US-TX-SALES-002 | B2B SaaS exempt |
| tx_004 | US-TX-SALES-DEFAULT | Tangible fallback |

### US-NY / SALES (3 requests)
| Idempotency | Rule | Scenario |
|-------------|------|----------|
| ny_001 | US-NY-SALES-001 | SaaS consumer → 4% |
| ny_002 | US-NY-SALES-DEFAULT | B2B fallback |
| ny_003 | US-NY-SALES-DEFAULT | Digital goods fallback |
