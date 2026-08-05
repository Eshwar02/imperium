# Imperium — Project Overview

**One line:** Imperium is an **Enterprise Knowledge Operating System** — a multi-agent
system that reads an organization's codebase, remembers *why* it is the way it is, and
modernizes it safely under human approval.

## The problem

Large codebases outlive the people who understand them. Business rules get buried in
code, AI-generated changes ship faster than humans can comprehend them, and
"modernize this" becomes risky because nobody knows what behavior must be preserved.
Imperium's bet: the missing layer is **durable org memory + gated automation** — a
system that understands the whole repo, records every decision, and never changes
behavior without a human in the loop.

## How it works (the spine)

Ingest a repo → build memory → let specialized agents analyze it → **human approves
(Gate A)** → simulate the change → **human approves the behavioral diff (Gate B)** →
apply, document, and check that humans still understand it.

```
ingest → build knowledge base → analyze (parallel agents) → Gate A
      → simulate → changeset → Gate B → documentation + comprehension
```

## Two pillars

### 1. The Repo Intelligence Engine (org memory)
Turns a repository into queryable, hierarchical memory across **three stores by design**:

- **Postgres** — relational metadata: modules, business rules, decisions, timeline,
  priority scores, simulations.
- **Qdrant** — embeddings / semantic memory, organized by a memory hierarchy
  (`Repository → Domain → Module → File → Function → Paragraph → Statement`) so agents
  retrieve at the right altitude.
- **Neo4j** — the call graph + dependency/architecture graph (blast-radius queries).

Its distinctive capabilities:
- **Transformation Priority Score** — what to modernize first (blast radius, business-rule
  density, AI-authorship %, churn/age).
- **Business Rule Registry** — extracted, deduped, versioned rules linked to code,
  decisions, and priority; low-confidence rules trigger human questions.
- **Repository Timeline** — *why* the code evolved (from git history), giving agents narrative context.
- **Transformation Simulation** — dry-run a change: expected old behavior → predicted
  new behavior → diff → confidence score; below threshold blocks and escalates.
- **Decision & Approval Memory** — append-only audit trail of every agent decision and
  human approval/rejection. This is both the audit log and the training signal for future runs.

### 2. The Multi-Agent System
Specialized agents, each routed to the model best suited to its job (per-agent LLM
routing across NVIDIA Nemotron / Groq / Gemini / Cerebras / Mistral — no OpenAI):

| Agent | Job |
|-------|-----|
| Research | External synthesis + timeline/rule context (long-context) |
| Structure / Repo Analysis | Parse, graph, and map the system |
| Business Logic | Extract and preserve business rules |
| Security / Compatibility | Safety and integration checks |
| Transformation / Implementation | Prioritize + generate the modernization changeset |
| Testing | Edge-case reasoning + test codegen |
| Documentation | Summaries, rules, decisions, timeline into docs |
| Comprehension | Post-merge checks that humans still understand AI-shipped code |

Orchestration lives in `core/orchestrator.py`; routing in `llm/routing.py`.

## The idea that ties it together: two-dimensional drift

Imperium tracks not just **code drift** (stored model vs. real behavior) but
**comprehension drift** (human understanding vs. what the AI actually shipped).
High-AI-authorship / low-comprehension modules get flagged back for human review — the
system actively defends the org against losing understanding of its own code.

## Architecture at a glance

- **Backend** — Python / FastAPI. `imperium/` = `agents/`, `core/` (orchestrator),
  `intelligence/` (parse, graph, priority, changeset, simulation, timeline),
  `rkb/` (the three-store memory), `llm/` (per-agent routing → LangChain).
- **Frontend** — React + Vite + TypeScript; the **human-in-the-loop surface**: ingest →
  analysis dashboard → structure map (React Flow) → Gate A / clarifications → Gate B →
  decision log. (See `docs/frontend-build-guide.md`.)
- **LLM layer** — moving onto LangChain in three phases (LLM layer → tool-using agents →
  LangGraph orchestration). (See `docs/superpowers/specs/2026-07-30-langchain-agent-layer-design.md`.)

## Status (2026-07)

Foundation scaffold is in place: the three-store RKB, intelligence modules (priority,
changeset, simulation, timeline), the agent set, the gated orchestrator, Alembic
migrations, and the API + frontend skeleton. The LangChain LLM layer (Phase 1) is
implemented. The active build focus is the Research / Transformation / Repo Analysis /
Documentation agents on top of the intelligence engine.

## In one sentence

**Imperium reads your whole codebase, remembers why it exists, and modernizes it
without ever letting a machine change behavior a human hasn't approved — while making
sure your team never loses understanding of its own system.**
