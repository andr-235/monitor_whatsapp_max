"""Таблица состояния пользователя для уведомлений."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_user_state"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать таблицу user_state."""

    op.create_table(
        "user_state",
        sa.Column("user_id", sa.BigInteger, primary_key=True),
        sa.Column("last_seen_message_id", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    """Удалить таблицу user_state."""

    op.drop_table("user_state")
