# Repo Intelligence Engine — Spec (IMPORTANT for Backend / Agent role)

> **Status:** authoritative requirements for the Repo Intelligence Engine + org memory.
> **Scope right now:** only the **Research, Transformation, Repo Analysis, and Documentation**
> features — and within those, the **agents** part. Everything else (Implementation execution,
> Testing runners, Security/Compatibility gates) is out of scope for this pass unless an agent
> above needs it as a read-only input.
>
> **Storage contract (fixed):**
> - **Postgres** → metadata (relational store, `imperium/rkb/store.py`, models in `rkb/models.py`)
> - **Qdrant** → embeddings / semantic memory (`imperium/rkb/embeddings.py`)
> - **Neo4j** → call graph + architecture/dependency graph (`imperium/rkb/graph.py`)

---

## 1. Required capabilities of the engine

### 1.1 Transformation Priority Score
A rankable score per file/module/rule that tells the Transformation agent **what to modernize first**.
- Inputs to fold in: blast radius (Neo4j dependents), business-rule density & confidence, AI-authorship %
  (`Module.ai_authorship_pct`), churn/age from repository timeline (§1.6), security/tech-debt signals.
- Output: a numeric score + the factor breakdown, persisted as metadata in Postgres.
- **Home:** new `intelligence/priority.py`; scores stored on a `transformation_priority` table (Postgres).

### 1.2 Organize the files changed
Group and structure the set of files a transformation touches — not a flat list.
- Cluster by module/domain, by call-graph proximity, and by shared business rules.
- Produce a changeset manifest the Transformation + Documentation agents consume.
- **Home:** `intelligence/changeset.py`; changeset manifest as metadata (Postgres) with graph lookups (Neo4j).

### 1.3 Decision & approval memory
Remember **every** decision an agent made and every human approval/rejection.
- Already modeled: `rkb/models.py::Decision` (category, change_summary, rule_preserved, alternative_rejected, gate).
- Extend for HITL: who approved, timestamp, agent vs human origin, the prompt/question, the verdict.
- This is the audit trail + the training signal for future runs. Never overwrite — append-only.
- **Home:** Postgres `decisions` (extend), surfaced via `api/routes/gates.py`.

### 1.4 Business Rule Registry
A first-class registry of extracted business rules so modernization is repeatable.
- Already modeled: `rkb/models.py::BusinessRule` (statement, locations, confidence, verified, developer_answer)
  and extractor at `intelligence/business_rule_extractor.py`.
- Make it a *registry*: dedup, version, link rule → code locations (Neo4j), rule → decisions (§1.3),
  rule → priority (§1.1). Low-confidence rules trigger HITL questions.
- **Home:** Postgres `business_rules` (registry semantics + versioning), embeddings of rule text in Qdrant.

### 1.5 Transformation Simulation
Dry-run a transformation before it is real:
`old code (expected) → new code (expected output) → diff → confidence score (safety check)`.
- Capture expected old behavior, predicted new behavior, the behavioral/structural diff, and a
  confidence/safety score. Below threshold ⇒ block + escalate to human.
- Reuses `rkb/models.py::TestResult` (baseline vs post_change, per dimension) for the diff evidence.
- **Home:** new `intelligence/simulation.py`; results as metadata (Postgres), evidence vectors optional in Qdrant.

### 1.6 Repository Timeline
Understand **why** the org codebase evolved over time — not just what changed.
- Derive from git history: churn, authorship, refactors, dependency shifts, incident-driven changes.
- Feeds priority (§1.1) and gives agents narrative context ("this module was rewritten twice for X").
- **Home:** new `intelligence/timeline.py`; timeline events as metadata (Postgres), summaries in Qdrant.

---

## 2. Org-wide memory pipeline (how the engine "remembers the whole org")

Ordered pipeline — this is the ingestion → memory build path:

1. **Parse the repo** — `ingestion/loader.py` + `intelligence/parser.py` / `ast_builder.py` /
   `language_detection.py`.
2. **Build a graph** — call graph + dependency + architecture graph into **Neo4j**
   (`intelligence/call_graph.py`, `dependency_mapper.py`, `api_mapper.py`, `db_mapper.py` →
   `rkb/graph.py::write_call_graph`).
3. **Store embeddings** — chunk + embed into **Qdrant** (`rkb/embeddings.py::upsert`) with the
   memory-hierarchy payload (see §3).
4. **Store metadata separately** — relational facts (modules, rules, decisions, timeline, priority,
   simulations) into **Postgres** (`rkb/store.py`, `rkb/models.py`). Metadata and embeddings are kept
   in separate stores by design.
5. **Build summaries** — per-node summaries (`Module.summary`, doc extraction via
   `intelligence/doc_extractor.py`); summaries are embedded for retrieval.
6. **Hierarchical memory** — organize all of the above into the hierarchy in §3 so agents can retrieve
   at the right altitude (org → function).

## 3. Memory hierarchy (Qdrant payload + Postgres FKs)

```
Repository → Domain → Module → File → Function → Paragraph → Statement
```
Encoded as payload filters on Qdrant vectors (already noted in `rkb/embeddings.py`) and as foreign-key
relationships in Postgres. Retrieval picks the coarsest level that answers the query, then drills down.

---

## 4. Agent responsibilities (current scope: Research, Transformation, Repo Analysis, Documentation)

| Agent | File | Uses from engine |
|-------|------|------------------|
| Research | `agents/research.py` | timeline (§1.6), business rule registry (§1.4), semantic memory (Qdrant) |
| Transformation | (implementation/structure agents) | priority (§1.1), changeset (§1.2), simulation (§1.5), decisions (§1.3) |
| Repo Analysis | `agents/comprehension.py`, `structure.py` | full parse+graph+metadata (§2), memory hierarchy (§3) |
| Documentation | `agents/documentation.py` | summaries (§2.5), business rules, decisions, timeline |

Orchestration lives in `core/orchestrator.py`. Per-agent LLM routing in `llm/routing.py`.

---

## 5. Build status / gaps (as of 2026-07-23)

**Exists (scaffold):** `rkb/{store,graph,embeddings,models}.py`, business-rule extractor, `Decision`,
`BusinessRule`, `TestResult` models, ingestion + intelligence parsers. Most write methods are
`NotImplementedError` `TODO(team)`.

**To build (this spec):**
- [ ] `intelligence/priority.py` — Transformation Priority Score (§1.1)
- [ ] `intelligence/changeset.py` — organize files changed (§1.2)
- [ ] extend `Decision` model + `gates` route for full HITL approval memory (§1.3)
- [ ] registry semantics (dedup/version/links) over `BusinessRule` (§1.4)
- [ ] `intelligence/simulation.py` — transformation simulation + confidence (§1.5)
- [ ] `intelligence/timeline.py` — repository timeline from git history (§1.6)
- [ ] implement the `TODO(team)` writes in `rkb/graph.py` and `rkb/embeddings.py` (§2 steps 2–3)
- [ ] Alembic migrations (models note this is still `create_all`)
