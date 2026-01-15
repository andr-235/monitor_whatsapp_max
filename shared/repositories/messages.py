"""Репозиторий сообщений для доступа к БД."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from psycopg2.extras import Json, execute_values

from shared.db import Database
from shared.models import MessageRecord, MessageView


def insert_messages(db: Database, messages: Iterable[MessageRecord]) -> int:
    """Вставить сообщения в БД, пропуская дубликаты."""

    rows = [
        (
            message.message_id,
            message.chat_id,
            message.sender,
            message.text,
            message.timestamp,
            Json(message.metadata),
        )
        for message in messages
    ]
    if not rows:
        return 0

    query = (
        "INSERT INTO messages (message_id, chat_id, sender, text, timestamp, metadata) "
        "VALUES %s ON CONFLICT (message_id) DO NOTHING"
    )
    with db.connection() as conn, conn.cursor() as cursor:
        execute_values(cursor, query, rows, page_size=100)
        return max(cursor.rowcount, 0)


def get_recent_messages(db: Database, limit: int, offset: int) -> List[MessageView]:
    """Получить последние сообщения для отображения."""

    rows = db.fetch_all(
        "SELECT sender, timestamp, text FROM messages ORDER BY timestamp DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )
    return [
        MessageView(sender=row["sender"], timestamp=row["timestamp"], text=row["text"])
        for row in rows
    ]


def search_messages_by_keywords(
    db: Database, keywords: Sequence[str], limit: int, offset: int
) -> List[MessageView]:
    """Искать сообщения по ключевым словам через ILIKE."""

    patterns = [f"%{keyword}%" for keyword in keywords]
    rows = db.fetch_all(
        ""
        "SELECT sender, timestamp, text "
        "FROM messages "
        "WHERE COALESCE(text, '') ILIKE ANY(%s) "
        "ORDER BY timestamp DESC "
        "LIMIT %s OFFSET %s",
        (patterns, limit, offset),
    )
    return [
        MessageView(sender=row["sender"], timestamp=row["timestamp"], text=row["text"])
        for row in rows
    ]


def get_latest_message_timestamp(db: Database) -> Optional[int]:
    """Получить время последнего сообщения в секундах epoch."""

    value = db.fetch_value("SELECT EXTRACT(EPOCH FROM MAX(timestamp)) FROM messages")
    if value is None:
        return None
    return int(value)
