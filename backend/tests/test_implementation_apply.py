"""Test Implementation.apply_changes on a real temp git repo — proves edits land on an
isolated branch and the default branch is never touched.
"""
from __future__ import annotations

import pytest

from imperium.agents.base import AgentContext
from imperium.agents.implementation import ImplementationAgent


def _git_repo(tmp_path):
    from git import Repo

    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()
    (tmp_path / "app.py").write_text("x = 1\n")
    repo.index.add(["app.py"])
    repo.index.commit("initial")
    return repo


def test_apply_changes_uses_isolated_branch(tmp_path):
    repo = _git_repo(tmp_path)
    default_branch = repo.active_branch.name

    ctx = AgentContext(repository_id="r1", repo_path=str(tmp_path))
    changes = [{"file_path": "app.py", "new_code": "x = 2  # modernized\n", "diff": "..."}]

    out = ImplementationAgent().apply_changes(ctx, changes)

    assert out["applied"] is True
    assert out["files"] == ["app.py"]
    assert out["branch"].startswith("imperium/auto-")
    assert repo.active_branch.name == out["branch"]  # on the new branch

    # default branch content is unchanged
    default_content = repo.git.show(f"{default_branch}:app.py")
    assert default_content == "x = 1"


def test_apply_changes_guards_non_git_path(tmp_path):
    ctx = AgentContext(repository_id="r1", repo_path=str(tmp_path))
    out = ImplementationAgent().apply_changes(ctx, [{"file_path": "a.py", "new_code": "y"}])
    assert out["applied"] is False


def test_apply_changes_no_changes():
    ctx = AgentContext(repository_id="r1", repo_path="")
    assert ImplementationAgent().apply_changes(ctx, [])["applied"] is False
