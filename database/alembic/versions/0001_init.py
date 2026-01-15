"""Начальная схема для сообщений и ключевых слов."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать таблицы messages и keywords."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_id", sa.String, nullable=False),
        sa.Column("chat_id", sa.String, nullable=False),
        sa.Column("sender", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_messages_message_id", "messages", ["message_id"], unique=True)
    op.create_index("ix_messages_timestamp", "messages", ["timestamp"])
    op.create_index(
        "ix_messages_text_gin",
        "messages",
        ["text"],
        postgresql_using="gin",
        postgresql_ops={"text": "gin_trgm_ops"},
    )

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("keyword", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "keyword", name="uq_keywords_user_keyword"),
    )


def downgrade() -> None:
    """Удалить таблицы messages и keywords."""
    op.drop_table("keywords")
    op.drop_index("ix_messages_text_gin", table_name="messages")
    op.drop_index("ix_messages_timestamp", table_name="messages")
    op.drop_index("ix_messages_message_id", table_name="messages")
    op.drop_table("messages")
