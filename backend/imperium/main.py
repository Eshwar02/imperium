"""FastAPI app entrypoint. Wires the pipeline surface (TDD §3, §7, §9)."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from imperium import __version__
from imperium.api.auth import verify_jwt
from imperium.api.routes import (
    analysis,
    chat,
    code,
    comprehension,
    gates,
    health,
    ingest,
    insights,
    runs,
)

app = FastAPI(
    title="Imperium API",
    version=__version__,
    summary="Enterprise Knowledge Operating System — Phase 1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# /health is public; all /api/* routes require a valid Supabase JWT.
app.include_router(health.router)
_auth = [Depends(verify_jwt)]
app.include_router(ingest.router, prefix="/api", dependencies=_auth)
app.include_router(analysis.router, prefix="/api", dependencies=_auth)
app.include_router(gates.router, prefix="/api", dependencies=_auth)
app.include_router(runs.router, prefix="/api", dependencies=_auth)
app.include_router(insights.router, prefix="/api", dependencies=_auth)
app.include_router(code.router, prefix="/api", dependencies=_auth)
app.include_router(comprehension.router, prefix="/api", dependencies=_auth)
app.include_router(chat.router, prefix="/api", dependencies=_auth)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "Imperium", "version": __version__, "docs": "/docs"}
