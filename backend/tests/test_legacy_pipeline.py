"""Fixture-driven legacy graph build — COBOL + JCL through the frontend → graph path.

Offline: mocks the Neo4j write and asserts the nodes/edges the frontends produce for a
realistic mini mainframe repo (program + copybook + JCL).
"""
from __future__ import annotations

import os

import pytest

import imperium.core.orchestrator as orch

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "legacy")


@pytest.fixture
def captured(monkeypatch):
    box: dict = {"nodes": [], "edges": []}
    monkeypatch.setattr(
        orch, "write_call_graph",
        lambda rid, nodes, edges: box.update(nodes=nodes, edges=edges),
    )
    return box


def test_cobol_program_graph(captured):
    res = orch._build_legacy_graph("repo-legacy", [os.path.join(FIX, "orders.cbl")], FIX)
    assert res["legacy_nodes"] >= 3
    names = {n["name"] for n in captured["nodes"]}
    assert {"ORDERS", "MAIN-PARA", "VALIDATE-ORDER"} <= names
    etypes = {e["type"] for e in captured["edges"]}
    # PERFORM/CALL become call edges; COPY + EXEC SQL become relation edges.
    assert "PERFORMS" in etypes or "CALLS" in etypes
    assert "COPIES" in etypes
    assert "READS" in etypes and "WRITES" in etypes


def test_jcl_graph(captured):
    res = orch._build_legacy_graph("repo-legacy", [os.path.join(FIX, "pay.jcl")], FIX)
    assert res["legacy_nodes"] >= 2
    etypes = {e["type"] for e in captured["edges"]}
    assert "RUNS" in etypes and "USES_DATASET" in etypes
