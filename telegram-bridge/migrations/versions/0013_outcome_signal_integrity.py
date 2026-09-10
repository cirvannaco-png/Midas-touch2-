"""Enforce signal/outcome identity integrity.

Revision ID: 0013
Revises: 0012

An outcome is research data and must belong to the exact signal that created
it. The API payload cannot be allowed to change symbol or direction for an
existing signal_id.
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION validate_signal_outcome_identity()
RETURNS trigger AS $$
DECLARE
    s_symbol text;
    s_direction text;
BEGIN
    SELECT symbol, direction INTO s_symbol, s_direction
      FROM signals WHERE signal_id = NEW.signal_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'signal_id % does not exist', NEW.signal_id;
    END IF;

    IF s_symbol <> NEW.symbol OR s_direction <> NEW.direction THEN
        RAISE EXCEPTION 'outcome identity mismatch for signal_id %: stored %, %; received %, %',
            NEW.signal_id, s_symbol, s_direction, NEW.symbol, NEW.direction;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(TRIGGER_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER trg_validate_signal_outcome_identity
        BEFORE INSERT OR UPDATE ON signal_outcomes
        FOR EACH ROW EXECUTE FUNCTION validate_signal_outcome_identity();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_validate_signal_outcome_identity ON signal_outcomes;")
    op.execute("DROP FUNCTION IF EXISTS validate_signal_outcome_identity();")
