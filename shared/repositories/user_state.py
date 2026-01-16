"""Репозиторий состояния пользователя для авто-уведомлений."""

from __future__ import annotations

from typing import List

from shared.db import Database


def list_users_with_keywords(db: Database) -> List[int]:
    """Получить список пользователей, у которых есть ключевые слова."""

    rows = db.fetch_all("SELECT DISTINCT user_id FROM keywords")
    return [int(row["user_id"]) for row in rows]


def get_last_seen_message_id(db: Database, user_id: int) -> int:
    """Получить последний обработанный id сообщения для пользователя."""

    value = db.fetch_value(
        "SELECT last_seen_message_id FROM user_state WHERE user_id = %s",
        (user_id,),
    )
    if value is None:
        return 0
    return int(value)


def get_last_seen_message_max_id(db: Database, user_id: int) -> int:
    """Получить последний обработанный id сообщения Max для пользователя."""

    value = db.fetch_value(
        "SELECT last_seen_message_max_id FROM user_state WHERE user_id = %s",
        (user_id,),
    )
    if value is None:
        return 0
    return int(value)


def upsert_last_seen_message_id(db: Database, user_id: int, last_seen_message_id: int) -> None:
    """Обновить последний обработанный id сообщения для пользователя."""

    db.execute(
        ""
        "INSERT INTO user_state (user_id, last_seen_message_id) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "last_seen_message_id = EXCLUDED.last_seen_message_id, "
        "updated_at = now()",
        (user_id, last_seen_message_id),
    )


def upsert_last_seen_message_max_id(
    db: Database, user_id: int, last_seen_message_id: int
) -> None:
    """Обновить последний обработанный id сообщения Max для пользователя."""

    db.execute(
        ""
        "INSERT INTO user_state (user_id, last_seen_message_max_id) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "last_seen_message_max_id = EXCLUDED.last_seen_message_max_id, "
        "updated_at = now()",
        (user_id, last_seen_message_id),
    )
