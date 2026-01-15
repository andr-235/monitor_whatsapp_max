"""Бизнес-логика управления ключевыми словами."""

from __future__ import annotations

from shared.db import Database
from shared.repositories import keywords as keyword_repo


class KeywordService:
    """CRUD операции по ключевым словам с валидацией."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add_keyword(self, user_id: int, keyword: str) -> bool:
        """Добавить ключевое слово пользователю."""

        normalized = self._normalize(keyword)
        return keyword_repo.add_keyword(self._db, user_id, normalized)

    def remove_keyword(self, user_id: int, keyword: str) -> int:
        """Удалить ключевое слово у пользователя."""

        normalized = self._normalize(keyword)
        return keyword_repo.remove_keyword(self._db, user_id, normalized)

    def list_keywords(self, user_id: int) -> list[str]:
        """Получить список ключевых слов пользователя."""

        return keyword_repo.list_keywords(self._db, user_id)

    @staticmethod
    def _normalize(keyword: str) -> str:
        """Нормализовать ключевое слово для единообразного хранения."""

        return keyword.strip().lower()
