"""Помощники для подключения к БД."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Sequence

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from shared.config import DatabaseConfig


class Database:
    """Обертка над пулом подключений PostgreSQL."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._pool: Optional[pool.ThreadedConnectionPool] = None

    def connect(self) -> None:
        """Инициализировать пул подключений."""

        if self._pool is None:
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self._config.max_connections,
                dsn=self._config.dsn,
            )

    def close(self) -> None:
        """Закрыть пул подключений."""

        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    def ping(self) -> bool:
        """Проверить доступность БД."""

        try:
            _ = self.fetch_value("SELECT 1")
            return True
        except psycopg2.Error:
            return False

    def execute(self, query: str, params: Sequence[Any] | Dict[str, Any] | None = None) -> None:
        """Выполнить запрос без возврата строк."""

        with self.connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)

    def fetch_all(
        self, query: str, params: Sequence[Any] | Dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
        """Выполнить запрос и вернуть все строки словарями."""

        with self.connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            rows: List[Dict[str, Any]] = list(cursor.fetchall())
            return rows

    def fetch_value(
        self, query: str, params: Sequence[Any] | Dict[str, Any] | None = None
    ) -> Optional[Any]:
        """Выполнить запрос и вернуть одно значение."""

        with self.connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row is None:
                return None
            return row[0]

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Контекстный менеджер, возвращающий соединение из пула."""

        if self._pool is None:
            self.connect()
        if self._pool is None:
            raise RuntimeError("Пул подключений к БД недоступен")
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            yield conn
        finally:
            self._pool.putconn(conn)
