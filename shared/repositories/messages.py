"""Репозиторий сообщений для доступа к БД."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from psycopg2.extras import Json, execute_values

from shared.constants import MESSAGES_MAX_TABLE, MESSAGES_TABLE
from shared.db import Database
from shared.models import MessageRecord, MessageView


def insert_messages(db: Database, messages: Iterable[MessageRecord]) -> int:
    """Вставить сообщения WhatsApp в БД, пропуская дубликаты."""

    return _insert_messages(db, messages, MESSAGES_TABLE)


def insert_messages_max(db: Database, messages: Iterable[MessageRecord]) -> int:
    """Вставить сообщения Max в БД, пропуская дубликаты."""

    return _insert_messages(db, messages, MESSAGES_MAX_TABLE)


def get_recent_messages(db: Database, limit: int, offset: int) -> List[MessageView]:
    """Получить последние сообщения WhatsApp для отображения."""

    return _get_recent_messages(db, limit, offset, MESSAGES_TABLE)


def get_recent_messages_max(db: Database, limit: int, offset: int) -> List[MessageView]:
    """Получить последние сообщения Max для отображения."""

    return _get_recent_messages(db, limit, offset, MESSAGES_MAX_TABLE)


def search_messages_by_keywords(
    db: Database, keywords: Sequence[str], limit: int, offset: int
) -> List[MessageView]:
    """Искать сообщения WhatsApp по ключевым словам через ILIKE."""

    return _search_messages_by_keywords(db, keywords, limit, offset, MESSAGES_TABLE)


def search_messages_by_keywords_max(
    db: Database, keywords: Sequence[str], limit: int, offset: int
) -> List[MessageView]:
    """Искать сообщения Max по ключевым словам через ILIKE."""

    return _search_messages_by_keywords(db, keywords, limit, offset, MESSAGES_MAX_TABLE)


def get_messages_by_keywords_between_ids(
    db: Database, keywords: Sequence[str], start_id: int, end_id: int, limit: int
) -> List[MessageView]:
    """Получить сообщения WhatsApp по ключевым словам в диапазоне id."""

    return _get_messages_by_keywords_between_ids(
        db, keywords, start_id, end_id, limit, MESSAGES_TABLE
    )


def get_messages_by_keywords_between_ids_max(
    db: Database, keywords: Sequence[str], start_id: int, end_id: int, limit: int
) -> List[MessageView]:
    """Получить сообщения Max по ключевым словам в диапазоне id."""

    return _get_messages_by_keywords_between_ids(
        db, keywords, start_id, end_id, limit, MESSAGES_MAX_TABLE
    )


def get_max_message_id(db: Database) -> int:
    """Получить максимальный id сообщения WhatsApp."""

    return _get_max_message_id(db, MESSAGES_TABLE)


def get_max_message_id_max(db: Database) -> int:
    """Получить максимальный id сообщения Max."""

    return _get_max_message_id(db, MESSAGES_MAX_TABLE)


def get_latest_message_timestamp(db: Database) -> Optional[int]:
    """Получить время последнего сообщения WhatsApp в секундах epoch."""

    return _get_latest_message_timestamp(db, MESSAGES_TABLE)


def get_latest_message_timestamp_max(db: Database) -> Optional[int]:
    """Получить время последнего сообщения Max в секундах epoch."""

    return _get_latest_message_timestamp(db, MESSAGES_MAX_TABLE)


def get_recent_messages_combined(db: Database, limit: int, offset: int) -> List[MessageView]:
    """Получить последние сообщения из WhatsApp и Max."""

    return _merge_by_timestamp(
        _get_recent_messages(db, limit + offset, 0, MESSAGES_TABLE),
        _get_recent_messages(db, limit + offset, 0, MESSAGES_MAX_TABLE),
        limit,
        offset,
    )


def search_messages_by_keywords_combined(
    db: Database, keywords: Sequence[str], limit: int, offset: int
) -> List[MessageView]:
    """Искать сообщения из WhatsApp и Max по ключевым словам через ILIKE."""

    return _merge_by_timestamp(
        _search_messages_by_keywords(db, keywords, limit + offset, 0, MESSAGES_TABLE),
        _search_messages_by_keywords(db, keywords, limit + offset, 0, MESSAGES_MAX_TABLE),
        limit,
        offset,
    )


def _insert_messages(
    db: Database, messages: Iterable[MessageRecord], table_name: str
) -> int:
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

    table = _resolve_table_name(table_name)
    query = (
        f"INSERT INTO {table} (message_id, chat_id, sender, text, timestamp, metadata) "
        "VALUES %s "
        "ON CONFLICT (message_id) DO UPDATE SET "
        "sender = CASE "
        f"WHEN EXCLUDED.sender = 'неизвестно' THEN {table}.sender "
        f"WHEN EXCLUDED.sender LIKE '%%@lid' AND {table}.sender NOT LIKE '%%@lid' THEN {table}.sender "
        f"WHEN EXCLUDED.sender LIKE '%%@lid' THEN {table}.sender "
        "ELSE EXCLUDED.sender END, "
        "metadata = EXCLUDED.metadata"
    )
    with db.connection() as conn, conn.cursor() as cursor:
        execute_values(cursor, query, rows, page_size=100)
        return max(cursor.rowcount, 0)


def _get_recent_messages(
    db: Database, limit: int, offset: int, table_name: str
) -> List[MessageView]:
    table = _resolve_table_name(table_name)
    rows = db.fetch_all(
        f"SELECT id, sender, timestamp, text, metadata "
        f"FROM {table} ORDER BY timestamp DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )
    return _rows_to_view(rows)


def _search_messages_by_keywords(
    db: Database, keywords: Sequence[str], limit: int, offset: int, table_name: str
) -> List[MessageView]:
    patterns = [f"%{keyword}%" for keyword in keywords]
    table = _resolve_table_name(table_name)
    rows = db.fetch_all(
        ""
        f"SELECT id, sender, timestamp, text, metadata "
        f"FROM {table} "
        "WHERE COALESCE(text, '') ILIKE ANY(%s) "
        "ORDER BY timestamp DESC "
        "LIMIT %s OFFSET %s",
        (patterns, limit, offset),
    )
    return _rows_to_view(rows)


def _get_messages_by_keywords_between_ids(
    db: Database,
    keywords: Sequence[str],
    start_id: int,
    end_id: int,
    limit: int,
    table_name: str,
) -> List[MessageView]:
    patterns = [f"%{keyword}%" for keyword in keywords]
    table = _resolve_table_name(table_name)
    rows = db.fetch_all(
        ""
        f"SELECT id, sender, timestamp, text, metadata "
        f"FROM {table} "
        "WHERE id > %s AND id <= %s AND COALESCE(text, '') ILIKE ANY(%s) "
        "ORDER BY id ASC "
        "LIMIT %s",
        (start_id, end_id, patterns, limit),
    )
    return _rows_to_view(rows)


def _get_max_message_id(db: Database, table_name: str) -> int:
    table = _resolve_table_name(table_name)
    value = db.fetch_value(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
    if value is None:
        return 0
    return int(value)


def _get_latest_message_timestamp(db: Database, table_name: str) -> Optional[int]:
    table = _resolve_table_name(table_name)
    value = db.fetch_value(f"SELECT EXTRACT(EPOCH FROM MAX(timestamp)) FROM {table}")
    if value is None:
        return None
    return int(value)


def _merge_by_timestamp(
    left: List[MessageView],
    right: List[MessageView],
    limit: int,
    offset: int,
) -> List[MessageView]:
    combined = left + right
    if not combined:
        return []
    combined.sort(key=lambda item: (item.timestamp, item.db_id), reverse=True)
    return combined[offset : offset + limit]


def _rows_to_view(rows: List[dict]) -> List[MessageView]:
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


def _resolve_table_name(table_name: str) -> str:
    if table_name not in {MESSAGES_TABLE, MESSAGES_MAX_TABLE}:
        raise ValueError(f"Недопустимое имя таблицы: {table_name}")
    return table_name
