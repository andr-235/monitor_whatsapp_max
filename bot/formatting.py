"""Помощники форматирования ответов бота."""

from __future__ import annotations

import json
import os
from typing import Any, Iterable, List, Optional
from urllib.parse import quote

from shared.constants import DATETIME_FORMAT
from shared.models import MessageView


def format_message(message: MessageView) -> str:
    """Отформатировать одно сообщение для отображения."""

    timestamp = message.timestamp.strftime(DATETIME_FORMAT)
    text = (message.text or "").strip()
    links = _extract_media_links(message.metadata)
    media_type = _extract_media_type(message.metadata)

    lines: List[str] = [
        f"Отправитель: {message.sender}",
        f"Время: {timestamp}",
    ]

    if media_type and media_type != "текст":
        lines.append(f"Тип: {media_type}")

    if text:
        lines.append(f"Текст: {text}")

    if links:
        if len(links) == 1:
            lines.append(f"Ссылка: {links[0]}")
        else:
            lines.append("Ссылки:\n" + "\n".join(links))

    if not text and not links:
        lines.append("Текст: <нет текста>")

    return "\n".join(lines)


def format_message_page(messages: Iterable[MessageView]) -> str:
    """Отформатировать список сообщений как одну страницу."""

    items: List[str] = [format_message(message) for message in messages]
    return "\n\n".join(items)


def _extract_media_links(metadata: Any) -> List[str]:
    if metadata is None:
        return []
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return []
    if not isinstance(metadata, dict):
        return []

    links: List[str] = []
    media_ids: List[str] = []
    link_keys = {"link", "url", "media_url", "preview_url", "canonical"}

    def add_link(value: Any) -> None:
        if isinstance(value, str):
            link = value.strip()
            if link:
                links.append(link)

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(value, dict):
            if _looks_like_media(value):
                media_id = value.get("id")
                if isinstance(media_id, str) and media_id.strip():
                    media_ids.append(media_id.strip())
            for key, item in value.items():
                if key in link_keys:
                    add_link(item)
                else:
                    walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)

    walk(metadata)

    base_url = _get_whapi_base_url()
    token = _get_whapi_token()
    if base_url:
        for media_id in media_ids:
            links.append(_build_media_url(base_url, token, media_id))

    unique_links: List[str] = []
    seen = set()
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    return unique_links


def _looks_like_media(value: dict) -> bool:
    if "id" not in value:
        return False
    for key in ("mime_type", "file_name", "filename", "file_size", "sha256", "seconds", "width", "height"):
        if key in value:
            return True
    return False


def _get_whapi_base_url() -> Optional[str]:
    base_url = os.getenv("WHAPI_API_URL")
    if not base_url:
        return None
    return base_url.rstrip("/")


def _get_whapi_token() -> Optional[str]:
    token = os.getenv("WHAPI_API_TOKEN")
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _build_media_url(base_url: str, token: Optional[str], media_id: str) -> str:
    encoded_id = quote(media_id, safe="")
    url = f"{base_url}/media/{encoded_id}"
    if token:
        return f"{url}?token={quote(token, safe='')}"
    return url


def _extract_media_type(metadata: Any) -> Optional[str]:
    if metadata is None:
        return None
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return None
    if not isinstance(metadata, dict):
        return None

    raw_type = metadata.get("type")
    if isinstance(raw_type, str):
        return _translate_type(raw_type)

    for key in (
        "text",
        "image",
        "video",
        "document",
        "gif",
        "sticker",
        "audio",
        "voice",
        "short",
        "link_preview",
        "location",
        "live_location",
        "poll",
        "contact",
        "contact_list",
        "interactive",
        "buttons",
        "list",
        "order",
        "group_invite",
        "newsletter_invite",
        "admin_invite",
        "product",
        "catalog",
        "product_items",
        "hsm",
        "system",
        "action",
    ):
        if key in metadata:
            return _translate_type(key)
    return None


def _translate_type(raw_type: str) -> str:
    normalized = raw_type.strip().lower()
    mapping = {
        "text": "текст",
        "image": "изображение",
        "video": "видео",
        "document": "документ",
        "gif": "гиф",
        "sticker": "стикер",
        "audio": "аудио",
        "voice": "голосовое сообщение",
        "short": "короткое видео",
        "link_preview": "ссылка",
        "location": "локация",
        "live_location": "живое местоположение",
        "poll": "опрос",
        "contact": "контакт",
        "contact_list": "список контактов",
        "interactive": "интерактивное сообщение",
        "buttons": "кнопки",
        "list": "список",
        "order": "заказ",
        "group_invite": "приглашение в группу",
        "newsletter_invite": "приглашение в рассылку",
        "admin_invite": "приглашение администратора",
        "product": "продукт",
        "catalog": "каталог",
        "product_items": "список продуктов",
        "hsm": "шаблонное сообщение",
        "system": "системное сообщение",
        "action": "событие",
    }
    return mapping.get(normalized, normalized)
