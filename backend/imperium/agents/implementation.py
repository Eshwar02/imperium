"""Implementation Agent(s) (TDD §8, §9). Executes approved changes per category in
ISOLATED branches, commits traceable to the originating to-do item (PRD Step 8).

Branch-per-category strategy:
  1. Read approved categories from the Decision log (Gate A verdict = "approve").
  2. For each approved category, create a git branch imperiumm/<category>/<repo_id[:8]>.
  3. Use LLM (Codestral) to generate edits per file in the changeset.
  4. Apply the edits to the working tree, commit, and link the commit SHA → Decision.

Safety (PRD §14): never touches main/master; all writes are in isolated branches.
"""
from __future__ import annotations

import logging
import os
import re

from imperium.agents.base import AgentContext, BaseAgent

log = logging.getLogger("imperium.agents.implementation")

_EDIT_SYSTEM = (
    "You are a world-class code migration engineer using Mistral Codestral. "
    "Given the original file contents and a transformation category (e.g. modernization, "
    "security), apply ONLY the minimum changes needed for that category. "
    "Preserve ALL business logic, function signatures, and behaviour. "
    "Output ONLY the complete new file content — no explanation, no markdown fences."
)

_BRANCH_PREFIX = "imperium"


def _safe_branch_name(category: str, repo_id: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]", "-", category.lower())
    return f"{_BRANCH_PREFIX}/{slug}/{repo_id[:8]}"


class ImplementationAgent(BaseAgent):
    name = "implementation"
    role = "implementation"  # → Mistral Codestral

    def run(self, ctx: AgentContext) -> dict:
        """Apply approved transformations in isolated git branches."""
        repository_id = ctx.repository_id
        repo_path = ctx.repo_path

        if not repo_path or not os.path.isdir(repo_path):
            log.warning("ImplementationAgent: no repo_path for %s", repository_id)
            return {"branches": [], "commits": [], "skipped": []}

        # 1. Fetch approved categories from Decision log
        approved_categories = self._approved_categories(repository_id)
        if not approved_categories:
            log.info("ImplementationAgent: no approved categories for %s", repository_id)
            return {"branches": [], "commits": [], "skipped": []}

        # 2. Load changeset (files to transform per cluster)
        file_paths = self._changeset_files(repository_id)
        if not file_paths:
            log.info("ImplementationAgent: no changeset files for %s", repository_id)
            return {"branches": [], "commits": [], "skipped": []}

        branches: list[str] = []
        commits: list[dict] = []
        skipped: list[str] = []

        for category in approved_categories:
            branch = _safe_branch_name(category, repository_id)
            try:
                commit_info = self._apply_category(
                    repository_id=repository_id,
                    repo_path=repo_path,
                    category=category,
                    branch=branch,
                    file_paths=file_paths,
                )
                branches.append(branch)
                commits.extend(commit_info)
            except Exception as exc:  # noqa: BLE001
                log.warning("Implementation failed for category %s: %s", category, exc)
                skipped.append(category)

        return {"branches": branches, "commits": commits, "skipped": skipped}

    def _approved_categories(self, repository_id: str) -> list[str]:
        try:
            from imperium.rkb.store import get_decisions, get_session

            session = get_session()
            try:
                decisions = get_decisions(session, repository_id)
            finally:
                session.close()

            return list({
                d.category for d in decisions
                if d.gate in ("gate-a", "gate_a", "A") and d.verdict == "approve"
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch approved categories: %s", exc)
            return []

    def _changeset_files(self, repository_id: str) -> list[str]:
        try:
            from imperium.rkb.store import get_changesets, get_session

            session = get_session()
            try:
                manifests = get_changesets(session, repository_id)
            finally:
                session.close()

            if not manifests:
                return []

            # Use the most recent manifest
            latest = manifests[-1]
            return [cf.file_path for cf in latest.files]
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch changeset files: %s", exc)
            return []

    def _apply_category(
        self,
        repository_id: str,
        repo_path: str,
        category: str,
        branch: str,
        file_paths: list[str],
    ) -> list[dict]:
        """Checkout a new branch, transform each file, commit, link Decision."""
        try:
            from git import InvalidGitRepositoryError, Repo
        except ImportError:
            log.warning("gitpython not installed — cannot create branches")
            return []

        try:
            repo = Repo(repo_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Cannot open git repo at %s: %s", repo_path, exc)
            return []

        # Create branch off current HEAD (never touch main)
        try:
            new_branch = repo.create_head(branch, force=True)
            new_branch.checkout()
        except Exception as exc:  # noqa: BLE001
            log.warning("Branch creation failed for %s: %s", branch, exc)
            return []

        commits: list[dict] = []

        for rel_path in file_paths:
            abs_path = os.path.join(repo_path, rel_path) if not os.path.isabs(rel_path) else rel_path
            if not os.path.isfile(abs_path):
                continue

            try:
                with open(abs_path, encoding="utf-8", errors="ignore") as fh:
                    old_code = fh.read()

                new_code = self._generate_edit(old_code, category, rel_path)

                if new_code.strip() == old_code.strip():
                    continue  # No change — skip

                with open(abs_path, "w", encoding="utf-8") as fh:
                    fh.write(new_code)

                repo.index.add([abs_path])

            except Exception as exc:  # noqa: BLE001
                log.warning("Edit failed for %s: %s", rel_path, exc)
                continue

        # Commit if anything was staged
        diff = repo.index.diff("HEAD")
        if diff or repo.untracked_files:
            try:
                commit = repo.index.commit(
                    f"imperium({category}): automated transformation\n\n"
                    f"repository_id={repository_id}\ncategory={category}"
                )
                commit_sha = commit.hexsha
                commits.append({"category": category, "branch": branch, "sha": commit_sha})
                self._link_commit_to_decision(repository_id, category, commit_sha, branch)
            except Exception as exc:  # noqa: BLE001
                log.warning("Commit failed for %s: %s", branch, exc)
        else:
            log.info("No changes to commit for category %s", category)

        return commits

    def _generate_edit(self, old_code: str, category: str, file_path: str) -> str:
        """Use Codestral to generate a category-specific transformation."""
        from imperium.llm.client import complete

        prompt = (
            f"File: {file_path}\n"
            f"Transformation category: {category}\n\n"
            f"Original file:\n{old_code[:6000]}\n\n"
            "Apply the transformation and return the complete new file:"
        )
        return complete(self.role, prompt, system=_EDIT_SYSTEM, temperature=0.1)

    def _link_commit_to_decision(
        self, repository_id: str, category: str, commit_sha: str, branch: str
    ) -> None:
        """Append a Decision record linking this commit to the implementation action."""
        try:
            from imperium.rkb.store import append_decision, get_session

            session = get_session()
            try:
                append_decision(
                    session=session,
                    repository_id=repository_id,
                    category=category,
                    change_summary=f"Automated implementation commit {commit_sha[:8]} on branch {branch}",
                    gate="implementation",
                    origin="agent",
                    verdict="committed",
                    prompt_asked=f"Transform files in category={category}",
                    prompt_answer=f"commit_sha={commit_sha}",
                )
            finally:
                session.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not link commit to decision: %s", exc)
