"""Модели данных, используемые сервисами."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MessageRecord:
    """Представление сообщения WhatsApp, сохраняемого в БД."""

    message_id: str
    chat_id: str
    sender: str
    text: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class MessageView:
    """Легкая проекция для отображения сообщений в боте."""

    db_id: int
    sender: str
    timestamp: datetime
    text: Optional[str]
    metadata: Optional[Dict[str, Any]]
