"""RKB Chat / Copilot (frontend §8) — conversational query over org memory.

Retrieves grounding context from semantic memory (Qdrant) filtered to the repository,
then streams an answer over SSE. The first event carries the cited sources (clickable
into the graph/editor in the UI); subsequent events stream answer tokens.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

log = logging.getLogger("imperium.api.chat")

router = APIRouter(tags=["chat"])

_CHAT_SYSTEM = (
    "You are Imperium's codebase copilot. Answer the user's question about this "
    "repository using ONLY the retrieved context below. Cite the sources you used by "
    "their [n] index. If the context is insufficient, say so plainly rather than "
    "guessing."
)


class ChatRequest(BaseModel):
    query: str
    top_k: int = 8


def _retrieve(repository_id: str, query: str, top_k: int) -> list[dict]:
    """Semantic search over the repository's slice of memory; empty on any failure."""
    try:
        from imperium.rkb.embeddings import search

        return search(query, top_k=top_k, filters={"repository_id": repository_id})
    except Exception as exc:  # noqa: BLE001
        log.warning("chat retrieval failed for %s: %s", repository_id, exc)
        return []


def _context_block(sources: list[dict]) -> str:
    lines = []
    for i, hit in enumerate(sources, start=1):
        payload = hit.get("payload") or {}
        text = payload.get("statement") or payload.get("text") or json.dumps(payload)
        loc = payload.get("file") or payload.get("module") or ""
        lines.append(f"[{i}] ({loc}) {text}")
    return "\n".join(lines) if lines else "(no relevant context found)"


@router.post("/chat/{repository_id}")
def chat(repository_id: str, req: ChatRequest) -> StreamingResponse:
    """Stream a grounded answer as SSE: a `sources` event, then `token`s, then `done`."""
    sources = _retrieve(repository_id, req.query, req.top_k)

    def gen():
        # 1) hand the UI the citations up front so it can render clickable sources.
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        prompt = (
            f"Context:\n{_context_block(sources)}\n\n"
            f"Question: {req.query}\n\nAnswer (cite sources as [n]):"
        )
        try:
            from imperium.llm.client import stream

            for chunk in stream(
                "research", [("system", _CHAT_SYSTEM), ("user", prompt)]
            ):
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
        except Exception as exc:  # noqa: BLE001 — never break the SSE stream
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
