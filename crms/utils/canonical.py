"""Canonical JSON and hashing utilities."""

import json
from decimal import Decimal
from typing import Any


def _canonical_value(obj: Any) -> Any:
    """Convert value for canonical representation."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, Decimal)):
        return float(obj) if isinstance(obj, (float, Decimal)) else int(obj)
    if isinstance(obj, dict):
        return {k: _canonical_value(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_canonical_value(v) for v in obj]
    if isinstance(obj, str):
        return obj
    return str(obj)


def canonical_json(obj: Any) -> str:
    """Produce canonical JSON string (sorted keys, consistent formatting)."""
    canonical = _canonical_value(obj)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def request_hash(obj: Any) -> str:
    """Compute SHA256 hash of canonical request JSON."""
    import hashlib
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def bundle_hash(bundle: list[dict]) -> str:
    """Compute SHA256 hash of canonical bundle JSON."""
    import hashlib
    return hashlib.sha256(canonical_json(bundle).encode()).hexdigest()
