"""Памятный буфер сообщений на случай недоступности БД."""

from __future__ import annotations

from collections import deque
from typing import Deque, Iterable, List

from shared.constants import MAX_BUFFER_SIZE
from shared.models import MessageRecord


class MessageBuffer:
    """Ограниченный буфер записей сообщений."""

    def __init__(self, max_size: int = MAX_BUFFER_SIZE) -> None:
        self._max_size = max_size
        self._buffer: Deque[MessageRecord] = deque()

    def add(self, messages: Iterable[MessageRecord]) -> int:
        """Добавить сообщения в буфер, удаляя самые старые при переполнении."""

        dropped = 0
        for message in messages:
            if len(self._buffer) >= self._max_size:
                self._buffer.popleft()
                dropped += 1
            self._buffer.append(message)
        return dropped

    def drain(self) -> List[MessageRecord]:
        """Вернуть сообщения из буфера и очистить буфер."""

        items = list(self._buffer)
        self._buffer.clear()
        return items

    def items(self) -> List[MessageRecord]:
        """Вернуть сообщения из буфера без очистки."""

        return list(self._buffer)

    def size(self) -> int:
        """Вернуть текущий размер буфера."""

        return len(self._buffer)

    def is_empty(self) -> bool:
        """Проверить, пуст ли буфер."""

        return not self._buffer
