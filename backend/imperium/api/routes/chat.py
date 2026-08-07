"""RKB Chat / Copilot (frontend §8) — conversational query over org memory.

Retrieves grounding context from semantic memory (Qdrant) filtered to the repository,
then streams an answer over SSE. The first event carries the cited sources (clickable
into the graph/editor in the UI); subsequent events stream answer tokens.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from imperium.api.ownership import require_owner

log = logging.getLogger("imperium.api.chat")

router = APIRouter(tags=["chat"])

_CHAT_SYSTEM = (
    "You are Imperium's codebase copilot for a single repository. "
    "Be concise and conversational. If the user just greets you or makes small talk, "
    "greet them back in one short sentence and invite a question about the repo — do "
    "NOT lecture about missing context. "
    "When retrieved context is provided, ground your answer in it and cite sources by "
    "their [n] index. If a real question needs context that isn't present, say so in one "
    "sentence rather than guessing or padding."
)

# Words that indicate the user is just saying hi, not asking about the repo. Kept
# tiny on purpose — a greeting shouldn't require any repository context to answer.
_GREETINGS = {
    "hi", "hey", "hello", "yo", "hiya", "howdy", "sup", "hey!", "hi!", "hello!",
    "good morning", "good afternoon", "good evening", "thanks", "thank you", "ok",
    "okay", "cool", "nice", "test", "ping",
}


def _is_smalltalk(query: str) -> bool:
    return query.strip().lower().strip("?.! ") in _GREETINGS


class ChatRequest(BaseModel):
    query: str
    top_k: int = 8


def _retrieve(repository_id: str, query: str, top_k: int) -> list[dict]:
    """Semantic search over the repository's slice of memory; empty on any failure.

    Drops hits below `chat_min_score`: Qdrant always returns the top_k nearest vectors
    even when they're irrelevant, so an off-topic query still yields weak matches that
    would otherwise be fed to the LLM as if they were real context.
    """
    try:
        from imperium.config import get_settings
        from imperium.rkb.embeddings import search

        min_score = get_settings().chat_min_score
        hits = search(query, top_k=top_k, filters={"repository_id": repository_id})
        return [h for h in hits if (h.get("score") or 0.0) >= min_score]
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
def chat(repository_id: str, req: ChatRequest, request: Request) -> StreamingResponse:
    """Stream a grounded answer as SSE: a `sources` event, then `token`s, then `done`."""
    require_owner(repository_id, request)

    from imperium.rkb.embeddings import count_by_repository

    smalltalk = _is_smalltalk(req.query)
    indexed = count_by_repository(repository_id)
    # Only hit the vector store when there's something indexed and a real question.
    sources = [] if (smalltalk or indexed == 0) else _retrieve(repository_id, req.query, req.top_k)

    def _say(msg: str):
        """Stream a canned message as tokens then close — no LLM call needed."""
        yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'text': msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # Repo has no embeddings yet — tell the user plainly instead of letting the LLM
    # emit a confusing "no context" wall of text. This is the common case right after
    # ingest while the background knowledge-base build is still running.
    if not smalltalk and indexed == 0:
        return StreamingResponse(
            _say(
                "This repository isn't indexed yet, so I have nothing to answer from. "
                "Indexing runs in the background after ingest and can take a few minutes "
                "for a large repo — try again shortly. If it stays empty, re-ingest the repo."
            ),
            media_type="text/event-stream",
        )

    # Repo is indexed but nothing cleared the relevance bar — the question is about
    # something this repo doesn't cover. Say so in one line instead of grounding the LLM
    # in noise, which produced rambling "I couldn't find X" answers over bogus sources.
    if not smalltalk and not sources:
        return StreamingResponse(
            _say(
                "I couldn't find anything relevant to that in this repository's indexed "
                "knowledge. Try rephrasing, or ask about code, commits, or rules that "
                "exist in this repo."
            ),
            media_type="text/event-stream",
        )

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
