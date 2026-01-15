"""Помощники форматирования ответов бота."""

from __future__ import annotations

from typing import Iterable, List

from shared.constants import DATETIME_FORMAT
from shared.models import MessageView


def format_message(message: MessageView) -> str:
    """Отформатировать одно сообщение для отображения."""

    timestamp = message.timestamp.strftime(DATETIME_FORMAT)
    text = message.text or "<нет текста>"
    return f"Отправитель: {message.sender}\nВремя: {timestamp}\nТекст: {text}"


def format_message_page(messages: Iterable[MessageView]) -> str:
    """Отформатировать список сообщений как одну страницу."""

    items: List[str] = [format_message(message) for message in messages]
    return "\n\n".join(items)
