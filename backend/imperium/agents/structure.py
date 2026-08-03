"""Structure & Integration Agent (TDD §8). Produces the dependency/call graph for the
interactive map (PRD Step 3) as React-Flow-ready ``{nodes, edges}``.

<<<<<<< HEAD
Drives intelligence.call_graph + api_mapper + db_mapper, writes to rkb.graph, and
returns a React-Flow-ready {nodes, edges} structure map.
=======
Prefers the graph already written to Neo4j by the ingestion pipeline
(``core.orchestrator.build_knowledge_base``); if that store is empty but source is on
disk, it builds the call graph on the fly from the parsed AST.
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
"""
from __future__ import annotations

import logging

from imperium.agents.base import AgentContext, BaseAgent
from imperium.api.schemas import Category, Finding

log = logging.getLogger("imperium.agents.structure")

log = logging.getLogger("imperium.agents.structure")


class StructureAgent(BaseAgent):
    name = "structure"
    role = "structure"  # → Cerebras (llm/routing.py)

    def run(self, ctx: AgentContext) -> dict:
<<<<<<< HEAD
        """Build call graph, map APIs and DB, persist to Neo4j, return structure map."""
        repository_id = ctx.repository_id
        repo_path = ctx.repo_path
        findings: list[Finding] = []
        structure_map: dict = {"nodes": [], "edges": []}

        if not repo_path:
            log.warning("StructureAgent: no repo_path for %s", repository_id)
            return {"structure_map": structure_map, "findings": []}

        # 1. Parse repo files and build call graph → Neo4j
=======
        """Return the repository's structure map ({nodes, edges}) for the graph viewer."""
        graph = self._fetch_graph(ctx.repository_id)
        if not graph.get("nodes") and ctx.repo_path:
            graph = self._build_graph(ctx.repository_id, ctx.repo_path)
        return {"structure_map": graph, "findings": []}

    def _fetch_graph(self, repository_id: str) -> dict:
        try:
            from imperium.rkb.graph import repo_graph

            return repo_graph(repository_id) or {"nodes": [], "edges": []}
        except Exception as exc:  # noqa: BLE001
            log.debug("graph fetch failed: %s", exc)
            return {"nodes": [], "edges": []}

    def _build_graph(self, repository_id: str, repo_path: str) -> dict:
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
        try:
            from imperium.intelligence.call_graph import build_call_graph
            from imperium.intelligence.parser import parse_directory

            parsed = parse_directory(repo_path)
<<<<<<< HEAD
            graph = build_call_graph(parsed_files=parsed, repository_id=repository_id)
            structure_map["nodes"] = graph.get("nodes", [])
            structure_map["edges"] = graph.get("edges", [])
            log.info(
                "StructureAgent: %d nodes, %d edges for %s",
                len(structure_map["nodes"]), len(structure_map["edges"]), repository_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Call graph build failed: %s", exc)

        # 2. Map API endpoints (graceful — may raise NotImplementedError)
        api_catalogue: list[dict] = []
        try:
            from imperium.intelligence.api_mapper import map_apis

            api_catalogue = map_apis(repo_path)
            for ep in api_catalogue[:50]:
                findings.append(Finding(
                    category=Category.integration,
                    title=f"API endpoint: {ep.get('method', '')} {ep.get('path', '')}",
                    detail=str(ep.get("contract", "")),
                    confidence=0.9,
                    locations=ep.get("call_sites", []),
                ))
        except NotImplementedError:
            log.debug("api_mapper not yet implemented — skipping")
        except Exception as exc:  # noqa: BLE001
            log.warning("API mapping failed: %s", exc)

        # 3. Map database schema (graceful — may raise NotImplementedError)
        try:
            from imperium.intelligence.db_mapper import map_database

            db_info = map_database(repo_path)
            for tbl in db_info.get("tables", [])[:20]:
                findings.append(Finding(
                    category=Category.integration,
                    title=f"DB table: {tbl.get('name', tbl)}",
                    detail=f"Table detected in repository schema: {tbl}",
                    confidence=0.85,
                    locations=[],
                ))
        except NotImplementedError:
            log.debug("db_mapper not yet implemented — skipping")
        except Exception as exc:  # noqa: BLE001
            log.warning("DB mapping failed: %s", exc)

        # 4. Enrich structure_map nodes with API + DB info
        if api_catalogue:
            structure_map["api_endpoints"] = api_catalogue

        # 5. Upsert Module rows for each top-level directory (domain)
        self._upsert_modules(repository_id, repo_path, structure_map["nodes"])

        return {
            "structure_map": structure_map,
            "findings": [f.model_dump() for f in findings],
        }

    def _upsert_modules(self, repository_id: str, repo_path: str, nodes: list[dict]) -> None:
        """Create Module rows in Postgres for each unique file found in the graph."""
        try:
            import os

            from imperium.rkb.store import get_session, upsert_module

            session = get_session()
            try:
                seen: set[str] = set()
                for node in nodes:
                    fp = node.get("file", "")
                    if not fp or fp in seen:
                        continue
                    seen.add(fp)
                    rel = os.path.relpath(fp, repo_path) if repo_path else fp
                    name = os.path.splitext(os.path.basename(rel))[0]
                    upsert_module(
                        session=session,
                        repository_id=repository_id,
                        name=name,
                        path=rel,
                    )
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Module upsert failed: %s", exc)
=======
            return build_call_graph(parsed_files=parsed, repository_id=repository_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("call graph build failed: %s", exc)
            return {"nodes": [], "edges": []}
>>>>>>> a623fc793a781919e487d947e94daaefb57acf11
