"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-07-23 00:00:00.000000

Creates all tables for the Repo Intelligence Engine:
  - repositories
  - modules
  - business_rules (with registry fields: statement_hash, version, is_current)
  - decisions (with HITL fields: origin, approver, verdict, prompt_asked/answer)
  - test_results
  - transformation_priority (§1.1)
  - changeset_manifests + changeset_files (§1.2)
  - simulation_results (§1.5)
  - timeline_events (§1.6)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── repositories ──────────────────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("ref", sa.String(), nullable=False, server_default="HEAD"),
        sa.Column("languages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── modules ───────────────────────────────────────────────────────────────
    op.create_table(
        "modules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ai_authorship_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("comprehension_score", sa.Float(), nullable=True),
        sa.Column("flagged_for_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── business_rules ────────────────────────────────────────────────────────
    op.create_table(
        "business_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("statement_hash", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("locations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("developer_answer", sa.Text(), nullable=True),
        sa.Column("linked_node_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("linked_decision_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("hitl_question", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_rules_statement_hash", "business_rules", ["statement_hash"])
    op.create_index("ix_business_rules_repo_hash", "business_rules", ["repository_id", "statement_hash"])

    # ── decisions ─────────────────────────────────────────────────────────────
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("rule_preserved", sa.Text(), nullable=True),
        sa.Column("alternative_rejected", sa.Text(), nullable=True),
        sa.Column("gate", sa.String(), nullable=True),
        sa.Column("origin", sa.String(), nullable=False, server_default="agent"),
        sa.Column("approver", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=True),
        sa.Column("prompt_asked", sa.Text(), nullable=True),
        sa.Column("prompt_answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── test_results ──────────────────────────────────────────────────────────
    op.create_table(
        "test_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("dimension", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── transformation_priority (§1.1) ────────────────────────────────────────
    op.create_table(
        "transformation_priority",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("module_id", sa.String(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("blast_radius_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_rule_density", sa.Float(), nullable=False, server_default="0"),
        sa.Column("business_rule_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ai_authorship_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("churn_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("age_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("security_debt_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("factor_breakdown", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("computed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── changeset_manifests (§1.2) ────────────────────────────────────────────
    op.create_table(
        "changeset_manifests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "changeset_files",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("manifest_id", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("cluster_label", sa.String(), nullable=True),
        sa.Column("call_graph_proximity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("shared_rule_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["manifest_id"], ["changeset_manifests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── simulation_results (§1.5) ─────────────────────────────────────────────
    op.create_table(
        "simulation_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("old_code_hash", sa.String(64), nullable=False),
        sa.Column("new_code", sa.Text(), nullable=False),
        sa.Column("diff", sa.Text(), nullable=False),
        sa.Column("expected_old_behavior", sa.Text(), nullable=True),
        sa.Column("predicted_new_behavior", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("safety_passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("evidence_vector_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── timeline_events (§1.6) ────────────────────────────────────────────────
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("committed_at", sa.DateTime(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("files_changed", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("modules_affected", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("churn_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "commit_sha", name="uq_timeline_repo_sha"),
    )
    op.create_index("ix_timeline_repo_sha", "timeline_events", ["repository_id", "commit_sha"])


def downgrade() -> None:
    op.drop_table("timeline_events")
    op.drop_table("simulation_results")
    op.drop_table("changeset_files")
    op.drop_table("changeset_manifests")
    op.drop_table("transformation_priority")
    op.drop_table("test_results")
    op.drop_table("decisions")
    op.drop_table("business_rules")
    op.drop_table("modules")
    op.drop_table("repositories")
