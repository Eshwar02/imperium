"""layer_graph / repo_graph must surface relationship properties on edges."""
from __future__ import annotations

import contextlib

import imperium.rkb.graph as graph


class _Rec(dict):
    """A stand-in for a neo4j Record: dict access + dict() both work."""


class _Session:
    def __init__(self, edge_records, node_records):
        self._edge_records = edge_records
        self._node_records = node_records

    def run(self, query, **_):
        # First RETURN with `type(r)` is the edge query; the other is nodes.
        if "type(r)" in query:
            return iter(self._edge_records)
        return iter(self._node_records)


class _Driver:
    def __init__(self, session):
        self._session = session

    @contextlib.contextmanager
    def session(self):
        yield self._session


def test_layer_graph_flattens_edge_properties(monkeypatch):
    edge = _Rec(source="fileA", target="epChat", type="CONSUMES",
                props={"method": "api.chat()", "route": "POST /api/chat/{id}"})
    node = _Rec(n={"id": "fileA", "kind": "File", "name": "chat.ts"})
    monkeypatch.setattr(graph, "_driver", lambda: _Driver(_Session([edge], [node])))

    out = graph.layer_graph("repo-1", ["CONSUMES"])
    e = out["edges"][0]
    assert e["source"] == "fileA" and e["target"] == "epChat" and e["type"] == "CONSUMES"
    assert e["method"] == "api.chat()"
    assert e["route"] == "POST /api/chat/{id}"
