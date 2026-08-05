"""Orchestrator Agent (TDD §8, PRD §8). Sequences sub-agents end-to-end and enforces
approval-gate checkpoints. This is the spine the API routes call.

Full pipeline implementation:
  1. Parse repo → build graph → embed → priority → timeline
  2. Run structure + business-logic + security + research agents (parallel via threads)
  3. Merge findings, persist to RKB
  4. Gate A: human approval per category
  5. Simulation → changeset → implementation
  6. Gate B: behavioral diff review
  7. Documentation + comprehension checks
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from imperium.agents.base import AgentContext
from imperium.agents.business_logic import BusinessLogicAgent
from imperium.agents.comprehension import ComprehensionAgent
from imperium.agents.compatibility import CompatibilityAgent
from imperium.agents.documentation import DocumentationAgent
from imperium.agents.implementation import ImplementationAgent
from imperium.agents.research import ResearchAgent
from imperium.agents.security import SecurityAgent
from imperium.agents.structure import StructureAgent
from imperium.agents.testing import TestingAgent
from imperium.api.schemas import AnalysisResponse, Category, Finding, GateDecision, GateRequest
from imperium.rkb.graph import write_call_graph

log = logging.getLogger("imperium.core.orchestrator")

# Frontend edge ``type`` → target node ``kind`` for the bare names those edges point at.
_EDGE_TARGET_KIND = {
    "COPIES": "Copybook",
    "READS": "Db2Table",
    "WRITES": "Db2Table",
    "EXPOSES": "CicsTransaction",
    "RUNS": "Program",
    "USES_DATASET": "Dataset",
    "CALLS": "Program",
    "PERFORMS": "Paragraph",
    "GOES_TO": "Paragraph",
}

# Latest completed analysis per repository, so GET /analysis can return the real
# result without re-running the pipeline. Process-local by design: analyses are
# also durably reflected in the RKB (business rules) as a fallback across restarts.
_ANALYSIS_SNAPSHOTS: dict[str, AnalysisResponse] = {}
# Repositories whose analysis is currently running in a background task.
_ANALYSIS_RUNNING: set[str] = set()


class Orchestrator:
    """Coordinates the multi-agent pipeline (PRD §7 Steps 1-16)."""

    def __init__(self) -> None:
        self.structure = StructureAgent()
        self.business_logic = BusinessLogicAgent()
        self.security = SecurityAgent()
        self.research = ResearchAgent()
        self.implementation = ImplementationAgent()
        self.compatibility = CompatibilityAgent()
        self.testing = TestingAgent()
        self.documentation = DocumentationAgent()
        self.comprehension = ComprehensionAgent()

    def _context(self, repository_id: str) -> AgentContext:
        """Build an AgentContext, resolving repo_path from Postgres."""
        repo_path = ""
        try:
            from imperium.rkb.store import get_repository, get_session

            session = get_session()
            try:
                repo = get_repository(session, repository_id)
                if repo and repo.url:
                    import os
                    from imperium.config import get_settings

                    settings = get_settings()
                    repo_path = os.path.join(settings.workspace_dir, repository_id)
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not resolve repo_path for %s: %s", repository_id, exc)

        return AgentContext(repository_id=repository_id, repo_path=repo_path)

    # ── Steps 1-2: Ingestion pipeline ─────────────────────────────────────────

    def build_knowledge_base(self, repository_id: str, repo_path: str) -> dict:
        """Parse repo → call graph → embeddings → priority → timeline.

        This is the prerequisite before analysis agents run.
        """
        results: dict = {"repository_id": repository_id}

        # 1. Parse files
        try:
            from imperium.intelligence.parser import parse_directory

            parsed = parse_directory(repo_path)
            results["parsed_files"] = len(parsed)
        except Exception as exc:  # noqa: BLE001
            log.warning("Parse failed: %s", exc)
            parsed = []

        # 2. Build call graph → Neo4j
        try:
            from imperium.intelligence.call_graph import build_call_graph

            graph = build_call_graph(parsed_files=parsed, repository_id=repository_id)
            results["graph_nodes"] = len(graph.get("nodes", []))
            results["graph_edges"] = len(graph.get("edges", []))
        except Exception as exc:  # noqa: BLE001
            log.warning("Call graph build failed: %s", exc)
            graph = {"nodes": [], "edges": []}

        # 2b. Build API + data + dependency graph layers → Neo4j
        try:
            from imperium.intelligence.multigraph import build_multigraph

            mg = build_multigraph(repository_id, repo_path, write=True)
            results["multigraph"] = mg["counts"]
        except Exception as exc:  # noqa: BLE001
            log.warning("Multigraph build failed: %s", exc)

        # 2c. Build legacy-language (COBOL/JCL) call graph → Neo4j
        try:
            from imperium.intelligence.language_detection import detect_detailed

            legacy_langs = {"cobol", "jcl"}
            legacy_paths: list[str] = []
            try:
                import os

                _detected = {d["language"] for d in detect_detailed(repo_path)}
                if legacy_langs & _detected:
                    from imperium.intelligence.language_detection import _EXT_LANG, _SKIP_DIRS

                    for root, dirs, files in os.walk(repo_path):
                        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                        for name in files:
                            lang = _EXT_LANG.get(os.path.splitext(name)[1].lower())
                            if lang in legacy_langs:
                                legacy_paths.append(os.path.join(root, name))
            except Exception as exc:  # noqa: BLE001
                log.warning("Legacy file discovery failed: %s", exc)

            if legacy_paths:
                legacy = _build_legacy_graph(repository_id, legacy_paths, repo_path)
                results.update(legacy)
        except Exception as exc:  # noqa: BLE001
            log.warning("Legacy graph build failed: %s", exc)

        # 3. Build timeline → Postgres + Qdrant
        try:
            from imperium.intelligence.timeline import build_timeline

            build_timeline(repository_id, repo_path, embed=True)
            results["timeline"] = "built"
        except Exception as exc:  # noqa: BLE001
            log.warning("Timeline build failed: %s", exc)

        # 4. Embed module summaries
        try:
            from imperium.intelligence.doc_extractor import extract
            from imperium.rkb.embeddings import upsert

            doc_data = extract(repo_path)
            summaries = doc_data.get("module_summaries", {})
            if summaries:
                texts = list(summaries.values())[:50]
                payloads = [
                    {"repository_id": repository_id, "level": "module", "module": k}
                    for k in list(summaries.keys())[:50]
                ]
                upsert(texts, payloads)
                results["summaries_embedded"] = len(texts)
        except Exception as exc:  # noqa: BLE001
            log.warning("Module embedding failed: %s", exc)
            summaries = {}

        # 4b. Persist module rows → Postgres (so priority/comprehension can join on
        # modules, and per-module comprehension scores have a home). Idempotent upsert.
        try:
            from imperium.rkb.store import get_session, upsert_module

            if summaries:
                sess = get_session()
                try:
                    for path, summary in list(summaries.items())[:200]:
                        name = path.rsplit("/", 1)[-1] or path
                        upsert_module(sess, repository_id, name=name, path=path, summary=summary)
                finally:
                    sess.close()
                results["modules_persisted"] = min(len(summaries), 200)
        except Exception as exc:  # noqa: BLE001
            log.warning("Module persist failed: %s", exc)

        # 5. Compute priority scores
        try:
            from imperium.intelligence.priority import run_for_repository

            scores = run_for_repository(repository_id)
            results["priority_scores"] = len(scores)
        except Exception as exc:  # noqa: BLE001
            log.warning("Priority scoring failed: %s", exc)

        return results

    # ── Steps 3-6: Analysis (parallel sub-agents) ─────────────────────────────

    def analyze(self, repository_id: str) -> AnalysisResponse:
        """Run structure + business-logic + security + research; merge findings.

        Sub-agents run concurrently via ThreadPoolExecutor.
        Results are persisted to RKB.
        """
        ctx = self._context(repository_id)

        # Run analysis agents in parallel
        agents = [
            ("structure", self.structure),
            ("business_logic", self.business_logic),
            ("security", self.security),
            ("research", self.research),
        ]

        all_findings: list[dict] = []
        structure_map: dict | None = None

        from imperium.core.run_events import emit, run_context

        def _run_named(name, agent):
            # Emit live start/done inside the worker so the copied context's emitter
            # (bound to the active run) reaches the run's event log.
            emit({"event": "agent_start", "agent": name})
            result = self._run_agent_safe(agent, ctx)
            emit(
                {
                    "event": "agent_done",
                    "agent": name,
                    "findings": len(result.get("findings", [])),
                }
            )
            return result

        with ThreadPoolExecutor(max_workers=4) as pool:
            # copy_context() per submit so the run emitter (a contextvar) is visible
            # in the pool threads — contextvars do not cross threads on their own.
            futures = {
                pool.submit(run_context().run, _run_named, name, agent): name
                for name, agent in agents
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    if name == "structure" and "structure_map" in result:
                        structure_map = result["structure_map"]
                    all_findings.extend(result.get("findings", []))
                except Exception as exc:  # noqa: BLE001
                    emit({"event": "agent_error", "agent": name, "error": str(exc)[:200]})
                    log.warning("Agent %s failed: %s", name, exc)

        # Persist findings to RKB
        self._persist_findings(repository_id, all_findings)

        # Build Finding objects
        findings = [
            Finding(
                category=Category(f.get("category", "modernization")),
                title=f.get("title", ""),
                detail=f.get("detail", ""),
                confidence=float(f.get("confidence", 0.0)),
                locations=f.get("locations", []),
            )
            for f in all_findings
            if f.get("title")
        ]

        response = AnalysisResponse(
            repository_id=repository_id,
            status="complete",
            structure_map=structure_map,
            findings=findings,
        )
        # Cache the full snapshot so GET /analysis returns it without re-running.
        _ANALYSIS_SNAPSHOTS[repository_id] = response
        _ANALYSIS_RUNNING.discard(repository_id)
        return response

    def analyze_in_background(self, repository_id: str) -> None:
        """Run analyze() as a background task, tracking running state and errors."""
        _ANALYSIS_RUNNING.add(repository_id)
        try:
            self.analyze(repository_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("Background analysis failed for %s: %s", repository_id, exc)
        finally:
            _ANALYSIS_RUNNING.discard(repository_id)

    def get_analysis(self, repository_id: str) -> AnalysisResponse:
        """Return the latest analysis: cached snapshot first, then RKB fallback."""
        snapshot = _ANALYSIS_SNAPSHOTS.get(repository_id)
        if snapshot is not None:
            return snapshot

        if repository_id in _ANALYSIS_RUNNING:
            return AnalysisResponse(repository_id=repository_id, status="running")

        try:
            from imperium.rkb.store import get_business_rules, get_session

            session = get_session()
            try:
                rules = get_business_rules(session, repository_id)
            finally:
                session.close()

            if not rules:
                return AnalysisResponse(repository_id=repository_id, status="queued")

            findings = [
                Finding(
                    category=Category.modernization,
                    title=f"Business rule: {r.statement[:80]}",
                    detail=r.statement,
                    confidence=r.confidence,
                    locations=[str(loc) for loc in r.locations],
                )
                for r in rules[:50]
            ]
            return AnalysisResponse(
                repository_id=repository_id,
                status="complete",
                findings=findings,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("get_analysis failed: %s", exc)
            return AnalysisResponse(repository_id=repository_id, status="queued")

    def _run_agent_safe(self, agent, ctx: AgentContext) -> dict:
        """Run an agent under the self-healing boundary (diagnose → remediate → retry)."""
        from imperium.core.healing import heal_call

        return heal_call(f"agent.{agent.name}", agent.run, ctx, default={}, retries=1)

    def _persist_findings(self, repository_id: str, findings: list[dict]) -> None:
        """Persist findings that represent business rules to RKB."""
        try:
            from imperium.rkb.store import get_session, upsert_business_rule

            session = get_session()
            try:
                for f in findings:
                    if f.get("category") == "modernization":
                        upsert_business_rule(
                            session=session,
                            repository_id=repository_id,
                            statement=f.get("detail", f.get("title", "")),
                            locations=f.get("locations", []),
                            confidence=float(f.get("confidence", 0.5)),
                        )
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Findings persist failed: %s", exc)

    # ── Step 7 & 13: Approval gates ───────────────────────────────────────────

    def apply_gate_a(self, req: GateRequest) -> dict:
        """Gate A — persist votes as Decision rows; only approved categories advance."""
        recorded = 0
        try:
            from imperium.rkb.store import append_decision, get_session

            session = get_session()
            try:
                for vote in req.votes:
                    append_decision(
                        session=session,
                        repository_id=req.repository_id,
                        category=vote.category.value,
                        change_summary=vote.note or f"Gate A vote: {vote.decision.value}",
                        gate="gate-a",
                        origin="human",
                        verdict=vote.decision.value,
                        prompt_asked="Gate A approval",
                        prompt_answer=vote.note,
                    )
                    recorded += 1
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Gate A persist failed: %s", exc)

        approved = [v.category.value for v in req.votes if v.decision == GateDecision.approve]
        return {
            "repository_id": req.repository_id,
            "recorded": recorded,
            "gate": "A",
            "approved_categories": approved,
        }

    def apply_gate_b(self, req: GateRequest) -> dict:
        """Gate B — persist votes; approved categories merge to integration."""
        recorded = 0
        try:
            from imperium.rkb.store import append_decision, get_session

            session = get_session()
            try:
                for vote in req.votes:
                    append_decision(
                        session=session,
                        repository_id=req.repository_id,
                        category=vote.category.value,
                        change_summary=vote.note or f"Gate B vote: {vote.decision.value}",
                        gate="gate-b",
                        origin="human",
                        verdict=vote.decision.value,
                        prompt_asked="Gate B approval (behavioral diff review)",
                        prompt_answer=vote.note,
                    )
                    recorded += 1
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Gate B persist failed: %s", exc)

        approved = [v.category.value for v in req.votes if v.decision == GateDecision.approve]
        return {
            "repository_id": req.repository_id,
            "recorded": recorded,
            "gate": "B",
            "approved_categories": approved,
        }

    # ── Step 7: HITL clarifications ───────────────────────────────────────────

    def pending_clarifications(self, repository_id: str) -> list[dict]:
        """Return unverified low-confidence BusinessRule rows as HITL questions."""
        try:
            from imperium.rkb.store import get_session, get_unverified_rules

            session = get_session()
            try:
                rules = get_unverified_rules(session, repository_id, threshold=0.70)
            finally:
                session.close()

            return [
                {
                    "rule_id": r.id,
                    "statement": r.statement,
                    "confidence": r.confidence,
                    "locations": r.locations,
                    "question": r.hitl_question or (
                        f"Can you confirm the business rule: \"{r.statement[:100]}\"? "
                        "Please describe the intended behavior."
                    ),
                }
                for r in rules
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("pending_clarifications failed: %s", exc)
            return []


# ── Legacy-language graph build (COBOL/JCL → Neo4j) ───────────────────────────

def _build_legacy_graph(
    repository_id: str, file_paths: list[str], repo_path: str
) -> dict:
    """Feed legacy-language files (COBOL/JCL) into the Neo4j call graph.

    Modules/paragraphs/steps become nodes; PERFORM/CALL/GO TO plus frontend
    relations (COPIES/READS/WRITES/EXPOSES/RUNS/USES_DATASET) become edges.
    Returns ``{legacy_files, legacy_nodes, legacy_edges}``.
    """
    import os

    from imperium.intelligence.frontends import get_frontend, has_frontend
    from imperium.intelligence.language_detection import _EXT_LANG

    def nid(key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()[:16]

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    n_files = 0

    def add_node(node_id: str, kind: str, name: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "kind": kind,
                "name": name,
                "repository_id": repository_id,
            }

    def bare_target(etype: str, name: str) -> str:
        kind = _EDGE_TARGET_KIND.get(etype, "Program")
        tid = nid(f"{etype}:{name}")
        add_node(tid, kind, name)
        return tid

    for path in file_paths:
        language = _EXT_LANG.get(os.path.splitext(path)[1].lower())
        if not language or not has_frontend(language):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                src = fh.read()
            fe = get_frontend(language)
            root = fe.structure(path, src)

            # Module/program root node.
            root_kind = "Program" if language == "cobol" else "JclJob"
            root_id = nid(f"{path}:{root.name}:{root.kind}")
            add_node(root_id, root_kind, root.name)

            # Paragraph / step nodes, indexed by name for sibling resolution.
            para_ids: dict[str, str] = {}
            para_kind = "Paragraph" if language == "cobol" else "JclStep"
            for child in root.children:
                if child.kind != "function":
                    continue
                cid = nid(f"{path}:{child.name}:{child.kind}")
                add_node(cid, para_kind, child.name)
                para_ids[child.name] = cid

            # Call children (PERFORM / CALL / GO TO) → edges.
            for child in root.children:
                if child.kind != "function":
                    continue
                src_id = para_ids[child.name]
                for call in child.children:
                    if call.kind != "call":
                        continue
                    ck = call.metadata.get("cobol_kind")
                    if ck == "perform":
                        etype = "PERFORMS"
                    elif ck == "goto":
                        etype = "GOES_TO"
                    else:
                        etype = "CALLS"
                    # Resolve PERFORM/GO TO to a sibling paragraph; else bare node.
                    if etype in ("PERFORMS", "GOES_TO") and call.name in para_ids:
                        tgt_id = para_ids[call.name]
                    else:
                        tgt_id = bare_target(etype, call.name)
                    edges.append({"source": src_id, "target": tgt_id, "type": etype})

            # Frontend non-call edges (COPIES/READS/WRITES/EXPOSES/RUNS/…).
            for e in fe.edges(path, root, src):
                etype = e.get("type", "CALLS")
                s_name = e.get("source", "")
                t_name = e.get("target", "")
                # Source is either a paragraph/step in this file or the program.
                if s_name in para_ids:
                    s_id = para_ids[s_name]
                elif s_name == root.name:
                    s_id = root_id
                else:
                    s_id = bare_target("CALLS", s_name)
                t_id = bare_target(etype, t_name)
                edges.append({"source": s_id, "target": t_id, "type": etype})

            n_files += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Legacy frontend failed for %s: %s", path, exc)

    node_list = list(nodes.values())
    write_call_graph(repository_id, node_list, edges)
    return {
        "legacy_files": n_files,
        "legacy_nodes": len(node_list),
        "legacy_edges": len(edges),
    }
