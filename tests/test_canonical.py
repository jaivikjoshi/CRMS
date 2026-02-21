"""Unit tests for canonical JSON and hashing."""

from crms.utils.canonical import canonical_json, request_hash, bundle_hash


def test_canonical_json_sorts_keys():
    """Canonical JSON sorts keys."""
    obj = {"b": 1, "a": 2}
    assert canonical_json(obj) == '{"a":2,"b":1}'


def test_request_hash_deterministic():
    """Request hash is deterministic."""
    obj = {"transaction": {"amount": 100, "jurisdiction": "US-CA"}}
    h1 = request_hash(obj)
    h2 = request_hash(obj)
    assert h1 == h2


def test_bundle_hash():
    """Bundle hash produces consistent hash for rules."""
    rules = [
        {"rule_id": "R1", "priority": 10, "when": {"eq": ["x", "y"]}},
        {"rule_id": "R2", "priority": 5, "when": {"eq": ["a", "b"]}},
    ]
    h1 = bundle_hash(rules)
    h2 = bundle_hash(rules)
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex
