"""Persist deterministic decision lineage and complete temporal provenance.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    signal_cols = [
        ("decision_schema_version", sa.String(64)),
        ("strategy_version", sa.String(64)),
        ("model_version", sa.String(64)),
        ("calibration_version", sa.String(64)),
        ("feature_schema_version", sa.String(64)),
        ("environment_schema_version", sa.String(64)),
        ("decision_fingerprint", sa.String(64)),
        ("canonical_decision", sa.Text()),
        ("parity_status", sa.String(32)),
        ("policy_action", sa.String(32)),
        ("reduce_risk", sa.Boolean()),
        ("spread_points", sa.Float()),
        ("environment_key", sa.String(512)),
        ("signal_time", sa.DateTime(timezone=True)),
        ("decision_time", sa.DateTime(timezone=True)),
        ("data_received_time", sa.DateTime(timezone=True)),
    ]
    outcome_cols = [
        ("decision_schema_version", sa.String(64)),
        ("decision_time", sa.DateTime(timezone=True)),
        ("execution_time", sa.DateTime(timezone=True)),
        ("outcome_time", sa.DateTime(timezone=True)),
        ("data_received_time", sa.DateTime(timezone=True)),
        ("strategy_version", sa.String(64)),
        ("model_version", sa.String(64)),
        ("calibration_version", sa.String(64)),
        ("feature_schema_version", sa.String(64)),
        ("environment_schema_version", sa.String(64)),
        ("decision_fingerprint", sa.String(64)),
        ("original_decision_fingerprint", sa.String(64)),
        ("canonical_decision", sa.Text()),
        ("parity_status", sa.String(32)),
    ]
    for name, typ in signal_cols:
        op.add_column("signals", sa.Column(name, typ, nullable=True))
    for name, typ in outcome_cols:
        op.add_column("signal_outcomes", sa.Column(name, typ, nullable=True))
    op.create_index("ix_signals_decision_fingerprint", "signals", ["decision_fingerprint"])
    op.create_index("ix_signal_outcomes_decision_fingerprint", "signal_outcomes", ["decision_fingerprint"])
    op.create_index("ix_signal_outcomes_decision_time", "signal_outcomes", ["decision_time"])
    op.create_index("ix_signal_outcomes_execution_time", "signal_outcomes", ["execution_time"])
    op.create_index("ix_signal_outcomes_outcome_time", "signal_outcomes", ["outcome_time"])
    op.create_index("ix_signal_outcomes_data_received_time", "signal_outcomes", ["data_received_time"])


def downgrade() -> None:
    for idx, table in [
        ("ix_signal_outcomes_data_received_time", "signal_outcomes"),
        ("ix_signal_outcomes_outcome_time", "signal_outcomes"),
        ("ix_signal_outcomes_execution_time", "signal_outcomes"),
        ("ix_signal_outcomes_decision_time", "signal_outcomes"),
        ("ix_signal_outcomes_decision_fingerprint", "signal_outcomes"),
        ("ix_signals_decision_fingerprint", "signals"),
    ]:
        op.drop_index(idx, table_name=table)
    for name in [
        "parity_status","canonical_decision","original_decision_fingerprint","decision_schema_version",
        "decision_fingerprint","environment_schema_version","feature_schema_version",
        "calibration_version","model_version","strategy_version",
        "data_received_time","outcome_time","execution_time","decision_time",
    ]:
        op.drop_column("signal_outcomes", name)
    for name in [
        "data_received_time","decision_time","signal_time","environment_key","decision_schema_version",
        "spread_points","reduce_risk","policy_action","parity_status",
        "canonical_decision","decision_fingerprint","environment_schema_version",
        "feature_schema_version","calibration_version","model_version","strategy_version",
    ]:
        op.drop_column("signals", name)
