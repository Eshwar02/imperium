"""Tests for the multi-graph intelligence: API mapper, DB mapper, and the builder
that assembles the API/data/dependency layers. No Neo4j (build with write=False).
"""
from __future__ import annotations


def test_api_mapper_detects_exposed_and_consumed(tmp_path):
    from imperium.intelligence.api_mapper import map_apis

    (tmp_path / "routes.py").write_text(
        '@router.post("/api/orders")\n'
        "def create_order():\n"
        "    resp = requests.get('https://ext/api/rate')\n"
    )
    recs = map_apis(str(tmp_path))
    exposed = {(r["method"], r["path"]) for r in recs if r["kind"] == "exposed"}
    consumed = {(r["method"], r["path"]) for r in recs if r["kind"] == "consumed"}
    assert ("POST", "/api/orders") in exposed
    assert ("GET", "https://ext/api/rate") in consumed


def test_api_mapper_flask_route_methods(tmp_path):
    from imperium.intelligence.api_mapper import map_apis

    (tmp_path / "app.py").write_text('@app.route("/login", methods=["GET", "POST"])\ndef login(): ...\n')
    exposed = {(r["method"], r["path"]) for r in map_apis(str(tmp_path)) if r["kind"] == "exposed"}
    assert ("GET", "/login") in exposed
    assert ("POST", "/login") in exposed


def test_db_mapper_detects_tables_and_access(tmp_path):
    from imperium.intelligence.db_mapper import map_database

    (tmp_path / "models.py").write_text('class User(Base):\n    __tablename__ = "users"\n')
    (tmp_path / "repo.py").write_text(
        'db.execute("SELECT * FROM users WHERE id = 1")\n'
        'db.execute("UPDATE accounts SET balance = 0")\n'
    )
    out = map_database(str(tmp_path))
    assert {t["name"] for t in out["tables"]} == {"users"}
    ops = {(a["table"], a["op"]) for a in out["access"]}
    assert ("users", "read") in ops
    assert ("accounts", "write") in ops


def test_build_multigraph_assembles_layers_without_neo4j(tmp_path):
    from imperium.intelligence.multigraph import build_multigraph

    (tmp_path / "routes.py").write_text('@app.get("/health")\ndef health(): ...\n')
    (tmp_path / "models.py").write_text('class Order(Base):\n    __tablename__ = "orders"\n')
    (tmp_path / "q.py").write_text('db.execute("INSERT INTO orders VALUES (1)")\n')

    mg = build_multigraph("repo-1", str(tmp_path), write=False)
    kinds = {n["kind"] for n in mg["nodes"]}
    rels = {e["type"] for e in mg["edges"]}
    assert "Endpoint" in kinds and "Table" in kinds
    assert "EXPOSES" in rels and "WRITES" in rels
    assert mg["counts"]["endpoints"] >= 1
