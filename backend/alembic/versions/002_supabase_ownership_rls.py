"""supabase_ownership_rls

Revision ID: 002
Revises: 001
Create Date: 2026-08-05 00:00:00.000000

Per-user multi-tenancy on the RKB relational store (Supabase).

  * repositories.owner_id  → auth.users.id  (JWT `sub`) — the single ownership anchor.
  * Row Level Security enabled on all 11 app tables.
  * `authenticated` role: may touch only rows it owns (directly, or via the parent
    repository / changeset manifest). `anon` gets NO policy → default-deny.
  * `service_role` (the backend) bypasses RLS automatically → full access.

Supabase-only migration: relies on the `auth` schema + Supabase roles, so it is a
no-op path in local dev/test (which bootstrap via Base.metadata.create_all).
"""
from __future__ import annotations

from alembic import op

# revision identifiers
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

# Tables scoped through a direct repository_id column.
_REPO_CHILDREN = [
    "modules",
    "business_rules",
    "decisions",
    "test_results",
    "transformation_priority",
    "changeset_manifests",
    "simulation_results",
    "timeline_events",
]

_ALL_TABLES = ["repositories", *_REPO_CHILDREN, "changeset_files"]


def _owns_repo(repo_id_col: str) -> str:
    """SQL predicate: the current user owns the repository referenced by repo_id_col."""
    return (
        f"EXISTS (SELECT 1 FROM public.repositories r "
        f"WHERE r.id = {repo_id_col} AND r.owner_id = auth.uid())"
    )


def upgrade() -> None:
    # ── ownership anchor ──────────────────────────────────────────────────────
    op.execute(
        "ALTER TABLE public.repositories "
        "ADD COLUMN IF NOT EXISTS owner_id uuid "
        "REFERENCES auth.users(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE public.repositories "
        "ALTER COLUMN owner_id SET DEFAULT auth.uid()"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_repositories_owner_id "
        "ON public.repositories (owner_id)"
    )

    # ── enable RLS everywhere (default-deny until a policy grants access) ──────
    # NOTE: intentionally NOT FORCE — the backend connects as the table-owner role
    # (`postgres`) and must keep bypassing RLS. FORCE would subject it to the
    # authenticated-only policies and lock the backend out. RLS here guards the
    # anon/authenticated PostgREST path; the backend guards itself via owner_id filters.
    for tbl in _ALL_TABLES:
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY")

    # ── repositories: own rows only ───────────────────────────────────────────
    op.execute("DROP POLICY IF EXISTS repositories_owner ON public.repositories")
    op.execute(
        "CREATE POLICY repositories_owner ON public.repositories "
        "FOR ALL TO authenticated "
        "USING (owner_id = auth.uid()) "
        "WITH CHECK (owner_id = auth.uid())"
    )

    # ── direct children: scope through parent repository ──────────────────────
    for tbl in _REPO_CHILDREN:
        pred = _owns_repo(f"public.{tbl}.repository_id")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_owner ON public.{tbl}")
        op.execute(
            f"CREATE POLICY {tbl}_owner ON public.{tbl} "
            f"FOR ALL TO authenticated "
            f"USING ({pred}) WITH CHECK ({pred})"
        )

    # ── changeset_files: scope through changeset_manifests → repositories ──────
    cf_pred = (
        "EXISTS (SELECT 1 FROM public.changeset_manifests m "
        "JOIN public.repositories r ON r.id = m.repository_id "
        "WHERE m.id = public.changeset_files.manifest_id AND r.owner_id = auth.uid())"
    )
    op.execute("DROP POLICY IF EXISTS changeset_files_owner ON public.changeset_files")
    op.execute(
        "CREATE POLICY changeset_files_owner ON public.changeset_files "
        "FOR ALL TO authenticated "
        f"USING ({cf_pred}) WITH CHECK ({cf_pred})"
    )


def downgrade() -> None:
    for tbl in _ALL_TABLES:
        policy = "repositories_owner" if tbl == "repositories" else f"{tbl}_owner"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON public.{tbl}")
        op.execute(f"ALTER TABLE public.{tbl} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS public.ix_repositories_owner_id")
    op.execute("ALTER TABLE public.repositories DROP COLUMN IF EXISTS owner_id")
