"""Pytest fixtures."""

import pytest

# Unit tests (evaluator, canonical) don't need DB.
# Integration/API tests require Postgres - run with: docker-compose up -d postgres && pytest
