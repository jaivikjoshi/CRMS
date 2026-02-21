"""Initial schema - tenants, rulesets, rules, ruleset_versions, evaluations.

Revision ID: 001
Revises:
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("api_key_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "rulesets",
        sa.Column("ruleset_id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("tax_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_rulesets_tenant_jurisdiction_tax",
        "rulesets",
        ["tenant_id", "jurisdiction", "tax_type"],
    )

    op.create_table(
        "rules",
        sa.Column("rule_pk", sa.UUID(), primary_key=True),
        sa.Column("ruleset_id", sa.UUID(), sa.ForeignKey("rulesets.ruleset_id"), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("rule_json", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "ruleset_versions",
        sa.Column("version_id", sa.UUID(), primary_key=True),
        sa.Column("ruleset_id", sa.UUID(), sa.ForeignKey("rulesets.ruleset_id"), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("effective_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("bundle_hash", sa.Text(), nullable=False),
        sa.Column("bundle_json", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "evaluations",
        sa.Column("evaluation_id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("ruleset_id", sa.UUID(), sa.ForeignKey("rulesets.ruleset_id"), nullable=False),
        sa.Column("version_id", sa.UUID(), sa.ForeignKey("ruleset_versions.version_id"), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("request_hash", sa.Text(), nullable=True),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    # Partial unique: only when idempotency_key is provided
    op.create_index(
        "uq_evaluations_tenant_idempotency",
        "evaluations",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_evaluations_tenant_idempotency", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("ruleset_versions")
    op.drop_table("rules")
    op.drop_table("rulesets")
    op.drop_table("tenants")
