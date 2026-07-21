"""FastAPI app entrypoint. Wires the pipeline surface (TDD §3, §7, §9)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from imperium import __version__
from imperium.api.routes import analysis, gates, health, ingest

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
)

app.include_router(health.router)
app.include_router(ingest.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(gates.router, prefix="/api")


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "Imperium", "version": __version__, "docs": "/docs"}
