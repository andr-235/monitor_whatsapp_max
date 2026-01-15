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
        "SELECT id, sender, timestamp, text, metadata "
        "FROM messages ORDER BY timestamp DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )
    return [
        MessageView(
            db_id=row["id"],
            sender=row["sender"],
            timestamp=row["timestamp"],
            text=row["text"],
            metadata=row["metadata"],
        )
        for row in rows
    ]


def search_messages_by_keywords(
    db: Database, keywords: Sequence[str], limit: int, offset: int
) -> List[MessageView]:
    """Искать сообщения по ключевым словам через ILIKE."""

    patterns = [f"%{keyword}%" for keyword in keywords]
    rows = db.fetch_all(
        ""
        "SELECT id, sender, timestamp, text, metadata "
        "FROM messages "
        "WHERE COALESCE(text, '') ILIKE ANY(%s) "
        "ORDER BY timestamp DESC "
        "LIMIT %s OFFSET %s",
        (patterns, limit, offset),
    )
    return [
        MessageView(
            db_id=row["id"],
            sender=row["sender"],
            timestamp=row["timestamp"],
            text=row["text"],
            metadata=row["metadata"],
        )
        for row in rows
    ]


def get_messages_by_keywords_between_ids(
    db: Database, keywords: Sequence[str], start_id: int, end_id: int, limit: int
) -> List[MessageView]:
    """Получить сообщения по ключевым словам в диапазоне id."""

    patterns = [f"%{keyword}%" for keyword in keywords]
    rows = db.fetch_all(
        ""
        "SELECT id, sender, timestamp, text, metadata "
        "FROM messages "
        "WHERE id > %s AND id <= %s AND COALESCE(text, '') ILIKE ANY(%s) "
        "ORDER BY id ASC "
        "LIMIT %s",
        (start_id, end_id, patterns, limit),
    )
    return [
        MessageView(
            db_id=row["id"],
            sender=row["sender"],
            timestamp=row["timestamp"],
            text=row["text"],
            metadata=row["metadata"],
        )
        for row in rows
    ]


def get_max_message_id(db: Database) -> int:
    """Получить максимальный id сообщения."""

    value = db.fetch_value("SELECT COALESCE(MAX(id), 0) FROM messages")
    if value is None:
        return 0
    return int(value)


def get_latest_message_timestamp(db: Database) -> Optional[int]:
    """Получить время последнего сообщения в секундах epoch."""

    value = db.fetch_value("SELECT EXTRACT(EPOCH FROM MAX(timestamp)) FROM messages")
    if value is None:
        return None
    return int(value)
