"""API Mapper (TDD §4). Catalogues exposed + consumed API contracts (PRD Step 2).

TODO(team): detect routes (Flask/FastAPI decorators, OpenAPI), REST/GraphQL calls,
SDK usage; record method, path, request/response shape, call sites.
"""
from __future__ import annotations


def map_apis(repo_path: str) -> list[dict]:
    """Return [{kind: exposed|consumed, method, path, call_sites, contract}]. TODO(team)."""
    raise NotImplementedError("API mapping — team task")
