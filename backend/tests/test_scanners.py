"""Tests for the deterministic intelligence scanners (no LLM, no network)."""
from __future__ import annotations


def test_security_scanner_flags_common_vulns(tmp_path):
    from imperium.intelligence.security_scanner import scan

    (tmp_path / "v.py").write_text(
        "import subprocess, pickle\n"
        "def q(uid):\n"
        "    cur.execute(f'SELECT * FROM users WHERE id={uid}')\n"
        "    subprocess.run(cmd, shell=True)\n"
        "    pickle.loads(data)\n"
        "    api_key = 'sk-supersecretvalue'\n"
    )
    findings = scan(str(tmp_path))
    titles = " ".join(f.title for f in findings)
    assert "SQL injection" in titles
    assert "shell=True" in titles
    assert "deserialization" in titles
    assert "credential" in titles.lower() or "secret" in titles.lower()
    # secret VALUE is never echoed into the finding
    assert all("supersecret" not in f.detail for f in findings)
    assert all(f.category.value == "security" for f in findings)


def test_security_scanner_skips_test_dirs(tmp_path):
    from imperium.intelligence.security_scanner import scan

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("os.system('x')\n")
    assert scan(str(tmp_path)) == []


def test_test_coverage_maps_and_finds_gaps(tmp_path):
    from imperium.intelligence.test_coverage import analyze

    (tmp_path / "orders.py").write_text("def create(): ...\n")
    (tmp_path / "billing.py").write_text("def charge(): ...\n")
    (tmp_path / "test_orders.py").write_text("import pytest\ndef test_create(): ...\n")

    out = analyze(str(tmp_path))
    assert "orders" in out["covered_modules"]
    assert "pytest" in out["frameworks"]
    assert any("billing.py" in g for g in out["gaps"])
    assert not any("orders.py" in g for g in out["gaps"])


def test_language_detection_ranks_by_weight_and_manifest(tmp_path):
    from imperium.intelligence.language_detection import detect, detect_detailed

    (tmp_path / "a.py").write_text("x = 1\n" * 50)
    (tmp_path / "b.py").write_text("y = 2\n" * 50)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "s.js").write_text("const a = 1\n")

    langs = detect(str(tmp_path))
    assert langs[0] == "python"  # more LOC + manifest boost
    detailed = {d["language"]: d for d in detect_detailed(str(tmp_path))}
    assert detailed["python"]["files"] == 2
    assert detailed["python"]["loc"] >= 100
