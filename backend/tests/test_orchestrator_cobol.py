"""Legacy-language graph build: COBOL paragraphs → Neo4j nodes, PERFORM → edges."""
from __future__ import annotations

import imperium.core.orchestrator as orchestrator

COBOL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM SUB-PARA.
       SUB-PARA.
           DISPLAY 'DONE'.
"""


def test_build_legacy_graph_cobol(tmp_path, monkeypatch):
    cbl = tmp_path / "payroll.cbl"
    cbl.write_text(COBOL)

    captured: dict = {}

    def fake_write(repository_id, nodes, edges):
        captured["repository_id"] = repository_id
        captured["nodes"] = nodes
        captured["edges"] = edges

    monkeypatch.setattr(orchestrator, "write_call_graph", fake_write)

    result = orchestrator._build_legacy_graph("repo1", [str(cbl)], str(tmp_path))

    assert result["legacy_files"] == 1
    assert result["legacy_nodes"] >= 2
    assert result["legacy_edges"] >= 1

    nodes = captured["nodes"]
    edges = captured["edges"]
    assert len(nodes) >= 2
    for n in nodes:
        assert "id" in n
        assert "kind" in n
        assert "name" in n
        assert n["repository_id"] == "repo1"

    assert any(e["type"] in ("PERFORMS", "CALLS") for e in edges)
    # The PERFORM edge should resolve to the sibling SUB-PARA paragraph node.
    node_ids = {n["id"] for n in nodes}
    for e in edges:
        assert e["source"] in node_ids
        assert e["target"] in node_ids
