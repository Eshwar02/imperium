"""Tests for the Claude-Code-style navigation + editing tools and the CodeAgent."""
from __future__ import annotations

from imperium.agents.base import AgentContext


def _ctx(path) -> AgentContext:
    return AgentContext(repository_id="r1", repo_path=str(path))


def _tool(ctx, name):
    from imperium.agents.code_tools import build_code_tools

    return next(t for t in build_code_tools(ctx) if t.name == name)


def test_grep_and_find_definition(tmp_path):
    (tmp_path / "m.py").write_text("def login(user):\n    return check(user)\n")
    ctx = _ctx(tmp_path)
    grep = _tool(ctx, "grep_code")
    assert "m.py:1" in grep.invoke({"pattern": "def login"})
    finddef = _tool(ctx, "find_definition")
    assert "m.py:1" in finddef.invoke({"name": "login"})
    assert "No definition" in finddef.invoke({"name": "nonexistent"})


def test_read_file_range(tmp_path):
    (tmp_path / "f.py").write_text("a\nb\nc\nd\n")
    read = _tool(_ctx(tmp_path), "read_file")
    out = read.invoke({"relative_path": "f.py", "start_line": 2, "end_line": 3})
    assert "2\tb" in out and "3\tc" in out and "1\ta" not in out


def test_edit_file_exact_unique(tmp_path):
    (tmp_path / "f.py").write_text("x = 1\ny = 2\n")
    edit = _tool(_ctx(tmp_path), "edit_file")
    msg = edit.invoke({"relative_path": "f.py", "old_string": "x = 1", "new_string": "x = 42"})
    assert "1 replacement" in msg
    assert (tmp_path / "f.py").read_text() == "x = 42\ny = 2\n"


def test_edit_file_rejects_missing_and_ambiguous(tmp_path):
    (tmp_path / "f.py").write_text("v = 1\nv = 1\n")
    edit = _tool(_ctx(tmp_path), "edit_file")
    assert "not found" in edit.invoke({"relative_path": "f.py", "old_string": "zzz", "new_string": "q"})
    assert "matches 2" in edit.invoke({"relative_path": "f.py", "old_string": "v = 1", "new_string": "v = 2"})


def test_write_file_and_traversal_guard(tmp_path):
    ctx = _ctx(tmp_path)
    write = _tool(ctx, "write_file")
    assert "Wrote" in write.invoke({"relative_path": "new/x.py", "content": "print(1)\n"})
    assert (tmp_path / "new" / "x.py").read_text() == "print(1)\n"
    assert "escapes" in write.invoke({"relative_path": "../evil.py", "content": "bad"})


def test_read_file_traversal_guard(tmp_path):
    read = _tool(_ctx(tmp_path), "read_file")
    assert "No such file" in read.invoke({"relative_path": "../../etc/passwd"})


# ── CodeAgent ─────────────────────────────────────────────────────────────────

def _git_repo(tmp_path):
    from git import Repo

    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "T").release()
    repo.config_writer().set_value("user", "email", "t@e.com").release()
    (tmp_path / "app.py").write_text("VERSION = '1.0'\n")
    repo.index.add(["app.py"])
    repo.index.commit("init")
    return repo


def test_code_agent_edits_on_isolated_branch(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    default = repo.active_branch.name

    # stub the agent build/run: simulate the LLM editing app.py via the real edit tool
    from imperium.agents import code_agent as ca

    def fake_build_agent(role, system, tools, temperature=0.2):
        return ("AGENT", tools)

    def fake_run_agent(agent, instruction):
        _, tools = agent
        edit = next(t for t in tools if t.name == "edit_file")
        edit.invoke({"relative_path": "app.py", "old_string": "1.0", "new_string": "2.0"})
        return "Bumped VERSION to 2.0"

    monkeypatch.setattr("imperium.agents.agent_factory.build_agent", fake_build_agent)
    monkeypatch.setattr("imperium.agents.agent_factory.run_agent", fake_run_agent)
    # avoid importing heavy graph tools
    monkeypatch.setattr("imperium.agents.tools.build_tools", lambda ctx: [])

    out = ca.CodeAgent().run_task(_ctx(tmp_path), "bump version to 2.0")

    assert out["applied"] is True
    assert out["files_changed"] == ["app.py"]
    assert out["branch"].startswith("imperium/code-")
    assert "2.0" in out["diff"]
    # default branch untouched
    assert repo.git.show(f"{default}:app.py").strip() == "VERSION = '1.0'"
