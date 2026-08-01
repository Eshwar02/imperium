"""Qdrant embeddings store — semantic RAG memory (TDD §5, §6).

Memory hierarchy (Repository → Domain → Module → File → Function → Paragraph →
Statement) is encoded as payload filters on vectors.

Embedding model: sentence-transformers via a lightweight local call or
provider API. Collection is auto-created on first upsert.
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any

from imperium.config import get_settings

log = logging.getLogger("imperium.rkb.embeddings")

_VECTOR_SIZE = 1536  # text-embedding-3-small / compatible


@lru_cache
def _client():
    from qdrant_client import QdrantClient

    # check_compatibility=False silences the client/server version-skew UserWarning;
    # the REST API we use is stable across these versions.
    return QdrantClient(url=get_settings().qdrant_url, check_compatibility=False)


def _ensure_collection() -> None:
    """Create the Qdrant collection if it does not exist yet."""
    from qdrant_client.http.models import Distance, VectorParams

    client = _client()
    settings = get_settings()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        log.info("Created Qdrant collection %s", settings.qdrant_collection)


def _embed(text: str) -> list[float]:
    """Embed text using the configured LLM provider (Mistral / fallback).

    Falls back to a zero-vector if no embedding provider is available so the
    pipeline degrades gracefully during dev without API keys.
    """
    settings = get_settings()
    try:
        import httpx

        # Use Mistral embedding endpoint (codestral-embed / mistral-embed)
        if settings.mistral_api_key and settings.mistral_api_key != "changeme":
            resp = httpx.post(
                "https://api.mistral.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
                json={"model": "mistral-embed", "input": text},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception as exc:  # noqa: BLE001
        log.warning("Embedding failed, using zero vector: %s", exc)

    # Deterministic pseudo-vector for offline / test runs
    digest = hashlib.sha256(text.encode()).digest()
    vec = [(b / 255.0) * 2 - 1 for b in digest]
    # Pad or truncate to _VECTOR_SIZE
    while len(vec) < _VECTOR_SIZE:
        vec.extend(vec)
    return vec[:_VECTOR_SIZE]


def _payload_to_filter(filters: dict) -> Any:
    """Convert a flat {key: value} dict to a Qdrant Filter object."""
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue

    conditions = [
        FieldCondition(key=k, match=MatchValue(value=v))
        for k, v in filters.items()
    ]
    return Filter(must=conditions) if conditions else None


def upsert(texts: list[str], payloads: list[dict]) -> None:
    """Embed texts and upsert into Qdrant with hierarchy payload.

    payloads[i] must include the memory-hierarchy keys that apply:
        repository_id, domain, module, file, function, paragraph, statement
    plus any extra metadata (e.g. rule_id, decision_id).
    """
    if len(texts) != len(payloads):
        raise ValueError("texts and payloads must have the same length")

    _ensure_collection()
    from qdrant_client.http.models import PointStruct

    client = _client()
    settings = get_settings()

    points = []
    for i, (text, payload) in enumerate(zip(texts, payloads)):
        vector = _embed(text)
        # Deterministic point ID from content hash so re-upserts are idempotent
        point_id = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**63)
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    client.upsert(collection_name=settings.qdrant_collection, points=points)
    log.debug("Upserted %d vectors into %s", len(points), settings.qdrant_collection)


def search(
    query: str,
    top_k: int = 8,
    filters: dict | None = None,
) -> list[dict]:
    """RAG retrieval — returns top_k most relevant payloads.

    filters: hierarchy/metadata constraints, e.g. {"repository_id": "abc", "module": "auth"}.
    Returns list of {score, payload} dicts.
    """
    _ensure_collection()
    client = _client()
    settings = get_settings()

    query_vector = _embed(query)
    qdrant_filter = _payload_to_filter(filters) if filters else None

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
        with_payload=True,
    )
    return [{"score": hit.score, "payload": hit.payload} for hit in results]


def delete_by_repository(repository_id: str) -> None:
    """Remove all vectors for a repository (e.g. on re-ingest)."""
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue

    client = _client()
    settings = get_settings()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="repository_id", match=MatchValue(value=repository_id))]
        ),
    )


def ping() -> dict[str, str]:
    try:
        _client().get_collections()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "error": str(exc)[:200]}
