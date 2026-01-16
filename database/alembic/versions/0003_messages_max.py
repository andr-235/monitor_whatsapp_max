"""Max messages table and user state update."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_messages_max"
down_revision = "0002_user_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create messages_max table and add Max state column."""

    op.create_table(
        "messages_max",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_id", sa.String, nullable=False),
        sa.Column("chat_id", sa.String, nullable=False),
        sa.Column("sender", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_index(
        "ix_messages_max_message_id", "messages_max", ["message_id"], unique=True
    )
    op.create_index("ix_messages_max_timestamp", "messages_max", ["timestamp"])
    op.create_index(
        "ix_messages_max_text_gin",
        "messages_max",
        ["text"],
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )

    op.add_column(
        "user_state",
        sa.Column("last_seen_message_max_id", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Drop messages_max table and Max state column."""

    op.drop_column("user_state", "last_seen_message_max_id")
    op.drop_index("ix_messages_max_text_gin", table_name="messages_max")
    op.drop_index("ix_messages_max_timestamp", table_name="messages_max")
    op.drop_index("ix_messages_max_message_id", table_name="messages_max")
    op.drop_table("messages_max")
