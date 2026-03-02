# Transaction Schema Assumptions

Rules in CRMS expect transactions with the following structure. Paths use dot notation (e.g. `transaction.buyer.type`).

## Supported Fields

```json
{
  "transaction": {
    "jurisdiction": "US-CA",
    "tax_type": "SALES",
    "amount": 100,
    "currency": "USD",
    "buyer": {
      "type": "CONSUMER | BUSINESS",
      "vat_id": "...",
      "vat_id_confidence": 0.0,
      "is_marketplace": false
    },
    "product": {
      "category": "SAAS | TANGIBLE | PHYSICAL_GOODS | DIGITAL_GOODS | SERVICES",
      "subtype": "...",
      "is_subscription": false,
      "is_exempt": false
    },
    "evidence": {
      "billing_country": "US",
      "billing_region": "CA",
      "ip_country": "US",
      "ip_region": "CA",
      "bank_country": "US",
      "resolved_country": "US",
      "resolved_region": "CA",
      "resolved_confidence": 0.95,
      "locality_code": "LA_CITY"
    },
    "marketplace": {
      "facilitator": "...",
      "is_facilitated": false
    },
    "fulfillment": {
      "ship_from_region": "...",
      "ship_to_region": "CA",
      "is_digital_delivery": true
    },
    "metrics": {
      "ca_revenue_t12m": 0,
      "eu_b2c_revenue_t12m": 0,
      "ca_revenue_prev_quarter": 0
    },
    "doc": {
      "has_resale_cert": false,
      "resale_cert_valid": false,
      "invoice_required": false
    },
    "event": {
      "type": "SALE | REFUND | CHARGEBACK"
    }
  }
}
```

## Operator Notes

- **not_exists**: `{ "not_exists": ["transaction.doc.resale_cert_valid"] }` — path missing or empty
- **path_eq**: `{ "path_eq": ["transaction.evidence.billing_country", "transaction.evidence.ip_country"] }` — two paths equal
- **path_neq**: `{ "path_neq": ["transaction.evidence.billing_country", "transaction.evidence.ip_country"] }` — two paths differ (conflicting evidence)

If your fields differ, adjust rule paths accordingly. For `path_eq`/`path_neq`, you can compute `evidence.resolved_country` upstream and use `eq` against a single field instead.
