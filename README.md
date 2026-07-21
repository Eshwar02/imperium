# Imperium

Enterprise Knowledge Operating System (EKOS) — Phase 1 prototype foundation.

Repository intelligence + human-verified knowledge base + governed incremental
modernization. This repo is the **foundation scaffold**: the full Phase 1 skeleton
per the Technical Design Document, with a runnable spine and stubbed internals for
the team to fill in.

> Status: foundation code. Boots, connects, exposes the pipeline surface. Agent /
> intelligence internals are stubs marked `# TODO(team)`.

## Layout

```
imperium/
├── docker-compose.yml     # postgres, qdrant, neo4j, redis
├── .env.example           # copy → .env
├── backend/               # Python — FastAPI, agents, intelligence engine, RKB
└── frontend/              # TypeScript/React — structure map, Gate A/B UIs
```

## Architecture map (TDD → code)

| TDD section | Code location |
|---|---|
| 4. Repository Intelligence Engine | `backend/imperium/intelligence/` |
| 5. Repository Knowledge Base (RKB) | `backend/imperium/rkb/` |
| 6. Memory Architecture (RAG) | `backend/imperium/rkb/store.py`, `embeddings.py` |
| 7. Human-in-the-Loop | `backend/imperium/api/routes/gates.py` |
| 8. Multi-Agent Architecture | `backend/imperium/agents/`, `core/orchestrator.py` |
| 9. Incremental Transformation | `backend/imperium/agents/implementation.py`, `sandbox/` |
| 10. Integrations | `docker-compose.yml`, `rkb/*`, `llm/client.py` |
| Structure map / Mermaid | `frontend/src/pages/StructureMap.tsx` |

## Quick start

```bash
# 1. backing services
cp .env.example .env
docker compose up -d

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn imperium.main:app --reload
# → http://localhost:8000/health   http://localhost:8000/docs

# 3. frontend
cd ../frontend
npm install
npm run dev
# → http://localhost:5173
```

## Pipeline (TDD §3) — current stub status

Repository → Intelligence Engine → Parsing → Classification → Knowledge
Extraction → RKB → Human Verification → Documentation → Mermaid → Transformation
Planning → Risk → Blast Radius → Sandbox → Regression → Merge

Endpoints exist for each stage under `/api`; handlers are stubs.

## Team build order

See `backend/imperium/` module docstrings — each carries a `# TODO(team)` with the
concrete first task. Suggested slice order: intelligence.parser → rkb.models →
agents.structure → api.analysis → frontend.StructureMap → gates → sandbox.
