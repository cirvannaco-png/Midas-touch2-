"""Append-only evaluation evidence for registered configurations.

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuration_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "config_hash",
            sa.String(64),
            sa.ForeignKey("configuration_registry.config_hash"),
            nullable=False,
        ),
        sa.Column("evidence_version", sa.Integer(), nullable=False),
        sa.Column("objective_score", sa.JSON(), nullable=False),
        sa.Column("performance_metrics", sa.JSON(), nullable=False),
        sa.Column("risk_metrics", sa.JSON(), nullable=False),
        sa.Column("validation_evidence", sa.JSON(), nullable=False),
        sa.Column("statistical_evidence", sa.JSON(), nullable=False),
        sa.Column("regime_conditions", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_configuration_evaluations_config_hash",
        "configuration_evaluations",
        ["config_hash"],
    )
    op.create_index(
        "ix_configuration_evaluations_status",
        "configuration_evaluations",
        ["decision"],
    )
    op.create_unique_constraint(
        "uq_configuration_evaluations_hash_version",
        "configuration_evaluations",
        ["config_hash", "evidence_version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_configuration_evaluations_hash_version",
        "configuration_evaluations",
        type_="unique",
    )
    op.drop_index(
        "ix_configuration_evaluations_status",
        table_name="configuration_evaluations",
    )
    op.drop_index(
        "ix_configuration_evaluations_config_hash",
        table_name="configuration_evaluations",
    )
    op.drop_table("configuration_evaluations")
