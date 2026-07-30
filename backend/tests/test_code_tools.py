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

    out = ca.CodeAgent().run_task(_ctx(tmp_path), "bump version to 2.0", plan=False)

    assert out["applied"] is True
    assert out["files_changed"] == ["app.py"]
    assert out["branch"].startswith("imperium/code-")
    assert "2.0" in out["diff"]
    # default branch untouched
    assert repo.git.show(f"{default}:app.py").strip() == "VERSION = '1.0'"


# ── run_tests tool + test loop ──────────────────────────────────────────────────

def test_run_test_command_parses_pass_fail(tmp_path):
    from imperium.agents.code_tools import run_test_command

    (tmp_path / "ok.sh").write_text("echo '3 passed'\n")
    res = run_test_command(str(tmp_path), "echo '3 passed'")
    assert res["ok"] is True and res["passed"] == 3 and res["failed"] == 0

    res = run_test_command(str(tmp_path), "echo '1 failed'; exit 1")
    assert res["ok"] is False and res["failed"] == 1


def test_run_tests_tool(tmp_path):
    tool = _tool(_ctx(tmp_path), "run_tests")
    assert "PASSED" in tool.invoke({"command": "echo '2 passed'"})
    assert "FAILED" in tool.invoke({"command": "echo '1 failed'; exit 1"})


def test_test_loop_iterates_until_pass(tmp_path, monkeypatch):
    from imperium.agents import code_agent as ca
    from imperium.agents import code_tools

    # test fails once, then passes after one fix attempt
    outcomes = iter([
        {"ok": False, "exit_code": 1, "passed": 0, "failed": 1, "output": "boom"},
        {"ok": True, "exit_code": 0, "passed": 1, "failed": 0, "output": "1 passed"},
    ])
    monkeypatch.setattr(code_tools, "run_test_command", lambda p, c: next(outcomes))
    calls = []
    monkeypatch.setattr("imperium.agents.agent_factory.run_agent", lambda a, m: calls.append(m))

    result = ca.CodeAgent()._test_loop(_ctx(tmp_path), "AGENT", "pytest -q", max_iters=2)
    assert result["passed"] is True
    assert result["iterations"] == 1
    assert len(result["attempts"]) == 2
    assert len(calls) == 1  # one fix attempt


# ── multi-file plan parsing ─────────────────────────────────────────────────────

def test_parse_steps_extracts_json():
    from imperium.agents.code_agent import CodeAgent

    raw = 'Here is the plan:\n[{"file": "a.py", "action": "rename", "rationale": "x"}, {"nope": 1}]'
    steps = CodeAgent()._parse_steps(raw)
    assert steps == [{"file": "a.py", "action": "rename", "rationale": "x"}]
    assert CodeAgent()._parse_steps("no json here") == []


def test_parse_steps_handles_double_encoded():
    from imperium.agents.code_agent import CodeAgent

    # some models return an array of JSON *strings* rather than objects
    raw = '["{\\"file\\": \\"app.py\\", \\"action\\": \\"doc\\", \\"rationale\\": \\"y\\"}"]'
    steps = CodeAgent()._parse_steps(raw)
    assert steps == [{"file": "app.py", "action": "doc", "rationale": "y"}]


def test_with_plan_renders_steps():
    from imperium.agents.code_agent import CodeAgent

    steps = [{"file": "a.py", "action": "do X", "rationale": "why"}]
    out = CodeAgent._with_plan("refactor", steps)
    assert "refactor" in out and "1. [a.py] do X — why" in out
    assert CodeAgent._with_plan("refactor", []) == "refactor"


# ── live streaming events ───────────────────────────────────────────────────────

def test_run_agent_stream_yields_events():
    from imperium.agents.agent_factory import run_agent_stream
    from langchain_core.messages import AIMessage, ToolMessage

    class FakeAgent:
        def stream(self, _inp, stream_mode=None):
            yield {"model": {"messages": [AIMessage(content="", tool_calls=[
                {"name": "grep_code", "args": {"pattern": "x"}, "id": "1"}])]}}
            yield {"tools": {"messages": [ToolMessage(content="a.py:1", name="grep_code", tool_call_id="1")]}}
            yield {"model": {"messages": [AIMessage(content="Done editing.")]}}

    events = list(run_agent_stream(FakeAgent(), "go"))
    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "message", "final"]
    assert events[0]["name"] == "grep_code" and events[0]["args"] == {"pattern": "x"}
    assert events[-1]["text"] == "Done editing."
