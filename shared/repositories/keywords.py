"""Репозиторий ключевых слов для доступа к БД."""

from __future__ import annotations

from typing import List

from shared.db import Database


def add_keyword(db: Database, user_id: int, keyword: str) -> bool:
    """Добавить ключевое слово пользователю."""

    query = (
        "INSERT INTO keywords (user_id, keyword) VALUES (%s, %s) "
        "ON CONFLICT (user_id, keyword) DO NOTHING"
    )
    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute(query, (user_id, keyword))
        return cursor.rowcount > 0


def remove_keyword(db: Database, user_id: int, keyword: str) -> int:
    """Удалить ключевое слово у пользователя."""

    with db.connection() as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM keywords WHERE user_id = %s AND keyword = %s", (user_id, keyword))
        return cursor.rowcount


def list_keywords(db: Database, user_id: int) -> List[str]:
    """Получить список ключевых слов пользователя."""

    rows = db.fetch_all("SELECT keyword FROM keywords WHERE user_id = %s ORDER BY keyword", (user_id,))
    return [row["keyword"] for row in rows]
