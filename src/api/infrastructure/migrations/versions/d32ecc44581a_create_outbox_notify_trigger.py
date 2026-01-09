"""create_outbox_notify_trigger

Create a PostgreSQL trigger that sends NOTIFY when rows are inserted into
the outbox table. This enables real-time processing of outbox entries by
the worker, rather than relying solely on polling.

Revision ID: d32ecc44581a
Revises: 6d11eae0e76d
Create Date: 2026-01-08 14:11:29.683215

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d32ecc44581a"
down_revision: Union[str, Sequence[str], None] = "6d11eae0e76d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the trigger function that sends NOTIFY on insert
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_outbox_insert()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('outbox_events', NEW.id::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create the trigger that fires after INSERT on the outbox table
    op.execute("""
        CREATE TRIGGER outbox_after_insert
            AFTER INSERT ON outbox
            FOR EACH ROW
            EXECUTE FUNCTION notify_outbox_insert();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the trigger first
    op.execute("DROP TRIGGER IF EXISTS outbox_after_insert ON outbox;")

    # Drop the trigger function
    op.execute("DROP FUNCTION IF EXISTS notify_outbox_insert();")
