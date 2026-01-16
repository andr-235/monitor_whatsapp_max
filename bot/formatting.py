"""Помощники форматирования ответов бота."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone, tzinfo
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence
from urllib.parse import quote
from zoneinfo import ZoneInfo

from bot.constants import (
    BOT_TIMEZONE_ENV,
    HEADER_CHAT_LABEL,
    HEADER_LINKS_LABEL,
    HEADER_MATCH_LABEL,
    HEADER_SENDER_LABEL,
    HEADER_TIME_LABEL,
    HEADER_TIME_LABEL_TZ_TEMPLATE,
    HEADER_TIMESTAMP_LABEL,
    HEADER_TYPE_LABEL,
    KEYWORD_HIGHLIGHT_TEMPLATE,
    KEYWORDS_LIST_HEADER,
    KEYWORDS_LIST_ITEM_TEMPLATE,
    LONG_MESSAGE_SPOILER_THRESHOLD,
    MESSAGE_SEPARATOR,
    TELEGRAM_CAPTION_LIMIT,
    TELEGRAM_MESSAGE_LIMIT,
    TIMEZONE_LABEL_TEMPLATE,
    UTC_LABEL,
)
from shared.constants import (
    DATETIME_FORMAT,
    PROVIDER_MAX,
    PROVIDER_WAPPI,
    SOURCE_LABEL_HEADER,
    SOURCE_LABEL_MAX,
    SOURCE_LABEL_WAPPI,
)
from shared.models import MessageView


@dataclass(frozen=True)
class MediaContent:
    """Медиа-контент для отправки через Telegram."""

    media_type: str
    url: str
    caption: Optional[str]


def format_message(
    message: MessageView,
    force_links: bool = False,
    keywords: Optional[Sequence[str]] = None,
) -> str:
    """Отформатировать одно сообщение для отображения."""

    text = (message.text or "").strip()
    links = _extract_media_links(message.metadata)
    media = extract_media(message.metadata)
    caption = (media.caption or "").strip() if media else ""

    message_type = _extract_media_type(message.metadata)
    if media and not message_type:
        message_type = _translate_type(media.media_type)
    if message_type == "текст" and text:
        message_type = None

    highlighted, matched_keywords = _highlight_text(text or caption, keywords)
    content = text or caption

    def build_message(use_spoiler: bool) -> str:
        lines = _format_header(message, message_type, matched_keywords)
        body: List[str] = []
        if content:
            display = _wrap_spoiler(highlighted) if use_spoiler else highlighted
            body.append(display)
        if links and (force_links or (not content and media is None)):
            body.append(_format_links(links))
        if body:
            lines.append(MESSAGE_SEPARATOR)
            lines.extend(body)
        return "\n".join(lines)

    use_spoiler = bool(content) and _should_wrap_spoiler(content)
    rendered = build_message(use_spoiler)
    if use_spoiler and len(rendered) > TELEGRAM_MESSAGE_LIMIT:
        rendered = build_message(False)
    return rendered


def format_message_caption(
    message: MessageView,
    fallback_caption: Optional[str],
    keywords: Optional[Sequence[str]] = None,
) -> str:
    """Сформировать подпись для медиа-сообщения."""

    text = (message.text or "").strip()
    caption = text or (fallback_caption or "").strip()
    message_type = _extract_media_type(message.metadata)

    highlighted, matched_keywords = _highlight_text(caption, keywords)
    use_spoiler = bool(caption) and _should_wrap_spoiler(caption)
    lines = _format_header(message, message_type, matched_keywords)
    if caption:
        lines.append(MESSAGE_SEPARATOR)
        display = _wrap_spoiler(highlighted) if use_spoiler else highlighted
        lines.append(display)
    rendered = "\n".join(lines)
    if use_spoiler and len(rendered) > TELEGRAM_CAPTION_LIMIT:
        lines = _format_header(message, message_type, matched_keywords)
        lines.append(MESSAGE_SEPARATOR)
        lines.append(highlighted)
        rendered = "\n".join(lines)
    return rendered


def format_message_page(messages: Iterable[MessageView]) -> str:
    """Отформатировать список сообщений как одну страницу."""

    items: List[str] = [format_message(message) for message in messages]
    return "\n\n".join(items)


def format_keywords_list(keywords: Iterable[str]) -> str:
    """Отформатировать список ключевых слов."""

    cleaned = [_normalize_keyword(keyword) for keyword in keywords]
    items = [keyword for keyword in cleaned if keyword]
    lines = [KEYWORDS_LIST_HEADER.format(count=len(items))]
    lines.extend(
        KEYWORDS_LIST_ITEM_TEMPLATE.format(index=index, keyword=keyword)
        for index, keyword in enumerate(items, start=1)
    )
    return "\n".join(lines)


def _format_header(
    message: MessageView, message_type: Optional[str], matched_keywords: List[str]
) -> List[str]:
    timestamp, tz_label = _format_timestamp_display(message.timestamp)
    chat_title = _extract_chat_title(message.metadata)
    if not chat_title:
        chat_title = _extract_chat_id(message.metadata)
    sender = (message.sender or "").strip() or "неизвестно"
    lines: List[str] = []
    source_label = _format_source_label(message.metadata)
    if source_label:
        lines.append(_format_label(SOURCE_LABEL_HEADER, source_label))
    if chat_title:
        lines.append(_format_label(HEADER_CHAT_LABEL, chat_title))
    lines.append(_format_label(HEADER_SENDER_LABEL, sender))
    time_label = (
        HEADER_TIME_LABEL_TZ_TEMPLATE.format(tz=tz_label) if tz_label else HEADER_TIME_LABEL
    )
    lines.append(_format_label(time_label, timestamp))
    epoch_timestamp = _extract_epoch_timestamp(message.metadata)
    if epoch_timestamp is not None:
        lines.append(_format_label(HEADER_TIMESTAMP_LABEL, str(epoch_timestamp)))
    if message_type:
        lines.append(_format_label(HEADER_TYPE_LABEL, message_type))
    if matched_keywords:
        lines.append(_format_label(HEADER_MATCH_LABEL, ", ".join(matched_keywords)))
    return lines


def _should_wrap_spoiler(content: str) -> bool:
    return len(content) >= LONG_MESSAGE_SPOILER_THRESHOLD


def _wrap_spoiler(content: str) -> str:
    return f"<tg-spoiler>{content}</tg-spoiler>"


def _format_label(label: str, value: str) -> str:
    return f"<b>{_escape(label)}:</b> {_escape(value)}"


def _format_links(links: List[str]) -> str:
    escaped_links = [_escape(link) for link in links]
    lines = [f"<b>{_escape(HEADER_LINKS_LABEL)}:</b>"]
    lines.extend(f"- {link}" for link in escaped_links)
    return "\n".join(lines)


def _escape(value: str) -> str:
    return html.escape(value, quote=False)


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.strip().split())


def _highlight_text(
    content: str,
    keywords: Optional[Sequence[str]],
) -> tuple[str, List[str]]:
    if not content:
        return "", []
    prepared = _prepare_keywords(keywords)
    if not prepared:
        return _escape(content), []

    pattern, group_map = _build_keyword_pattern(prepared)
    matched_keywords: List[str] = []
    parts: List[str] = []
    last_index = 0
    for match in pattern.finditer(content):
        parts.append(_escape(content[last_index : match.start()]))
        parts.append(KEYWORD_HIGHLIGHT_TEMPLATE.format(text=_escape(match.group(0))))
        last_index = match.end()
        group_name = match.lastgroup
        if group_name:
            keyword = group_map.get(group_name)
            if keyword and keyword not in matched_keywords:
                matched_keywords.append(keyword)
    parts.append(_escape(content[last_index:]))
    return "".join(parts), matched_keywords


def _prepare_keywords(keywords: Optional[Sequence[str]]) -> List[str]:
    if not keywords:
        return []
    prepared: List[str] = []
    seen = set()
    for keyword in keywords:
        normalized = _normalize_keyword(keyword)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        prepared.append(normalized)
    return prepared


def _build_keyword_pattern(
    keywords: Sequence[str],
) -> tuple[re.Pattern[str], dict[str, str]]:
    sorted_keywords = sorted(keywords, key=len, reverse=True)
    group_map: dict[str, str] = {}
    parts: List[str] = []
    for index, keyword in enumerate(sorted_keywords):
        group_name = f"kw{index}"
        group_map[group_name] = keyword
        parts.append(f"(?P<{group_name}>{re.escape(keyword)})")
    pattern = re.compile("|".join(parts), re.IGNORECASE)
    return pattern, group_map


def _extract_chat_title(metadata: Any) -> Optional[str]:
    normalized = _normalize_metadata(metadata)
    if not isinstance(normalized, dict):
        return None
    title = _extract_chat_title_from_dict(normalized)
    if title:
        return title
    raw = normalized.get("raw")
    if isinstance(raw, dict):
        return _extract_chat_title_from_dict(raw)
    return None


def _format_timestamp_display(timestamp: datetime) -> tuple[str, str]:
    aware = timestamp
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=timezone.utc)
    timezone_value, timezone_name = _resolve_timezone()
    local_time = aware.astimezone(timezone_value)
    tz_label = _format_timezone_label(local_time, timezone_name)
    return local_time.strftime(DATETIME_FORMAT), tz_label


def _resolve_timezone() -> tuple[tzinfo, Optional[str]]:
    tz_name = os.getenv(BOT_TIMEZONE_ENV)
    if not tz_name:
        return timezone.utc, None
    try:
        return ZoneInfo(tz_name), tz_name
    except Exception:
        return timezone.utc, None


def _format_timezone_label(local_time: datetime, tz_name: Optional[str]) -> str:
    offset = local_time.utcoffset()
    if offset is None:
        offset_label = UTC_LABEL
    else:
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        total_seconds = abs(total_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        offset_label = f"{UTC_LABEL}{sign}{hours:02d}:{minutes:02d}"
    if tz_name:
        return TIMEZONE_LABEL_TEMPLATE.format(name=tz_name, offset=offset_label)
    return offset_label


def _extract_epoch_timestamp(metadata: Any) -> Optional[int]:
    normalized = _normalize_metadata(metadata)
    if not isinstance(normalized, dict):
        return None
    value = normalized.get("timestamp")
    if value is None:
        raw = normalized.get("raw")
        if isinstance(raw, dict):
            value = raw.get("timestamp") or raw.get("time")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_chat_title_from_dict(payload: dict) -> Optional[str]:
    for key in ("chat_name", "chatName", "chat_title", "chatTitle"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("group_name", "groupName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    group = payload.get("group")
    if isinstance(group, dict):
        for key in ("Name", "name", "Subject", "subject", "Title", "title"):
            value = group.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    chat = payload.get("chat")
    if isinstance(chat, dict):
        for key in ("name", "title", "subject"):
            value = chat.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_chat_id(metadata: Any) -> Optional[str]:
    normalized = _normalize_metadata(metadata)
    if not isinstance(normalized, dict):
        return None
    for key in ("chat_id", "chatId"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _format_source_label(metadata: Any) -> Optional[str]:
    provider = _extract_provider(metadata)
    if not provider:
        return None
    normalized = provider.strip().lower()
    mapping = {
        PROVIDER_WAPPI: SOURCE_LABEL_WAPPI,
        PROVIDER_MAX: SOURCE_LABEL_MAX,
    }
    return mapping.get(normalized)


def _extract_provider(metadata: Any) -> Optional[str]:
    normalized = _normalize_metadata(metadata)
    if not isinstance(normalized, dict):
        return None
    provider = normalized.get("provider")
    if isinstance(provider, str) and provider.strip():
        return provider.strip()
    raw = normalized.get("raw")
    if isinstance(raw, dict):
        provider = raw.get("provider")
        if isinstance(provider, str) and provider.strip():
            return provider.strip()
    return None


def _extract_media_links(metadata: Any) -> List[str]:
    payload = _extract_payload(metadata)
    if not isinstance(payload, dict):
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

    walk(payload)

    base_url = _get_wappi_base_url()
    token = _get_wappi_token()
    if base_url and media_ids and not links:
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


def _get_wappi_base_url() -> Optional[str]:
    base_url = os.getenv("WAPPI_API_URL")
    if not base_url:
        return None
    return base_url.rstrip("/")


def _get_wappi_token() -> Optional[str]:
    token = os.getenv("WAPPI_API_TOKEN")
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
    metadata = _normalize_metadata(metadata)
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
        "unknown": "неизвестно",
    }
    return mapping.get(normalized, normalized)


def extract_media(metadata: Any) -> Optional[MediaContent]:
    """Извлечь медиа-контент из metadata, если он доступен."""

    normalized = _extract_payload(metadata)
    if not isinstance(normalized, dict):
        return None

    for key in (
        "image",
        "video",
        "document",
        "gif",
        "audio",
        "voice",
        "sticker",
        "short",
    ):
        value = normalized.get(key)
        if not isinstance(value, dict):
            continue
        url = _select_media_url(value)
        if not url:
            media_id = value.get("id")
            if isinstance(media_id, str) and media_id.strip():
                base_url = _get_wappi_base_url()
                token = _get_wappi_token()
                if base_url:
                    url = _build_media_url(base_url, token, media_id.strip())
        if not url:
            continue
        caption = value.get("caption")
        if not isinstance(caption, str):
            caption = None
        return MediaContent(media_type=key, url=url, caption=caption)

    return None


def has_displayable_content(message: MessageView) -> bool:
    """Проверить, есть ли что показывать пользователю."""

    text = (message.text or "").strip()
    if text:
        return True
    if extract_media(message.metadata):
        return True
    return bool(_extract_media_links(message.metadata))


def _normalize_metadata(metadata: Any) -> Any:
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except json.JSONDecodeError:
            return None
    return metadata


def _extract_payload(metadata: Any) -> Any:
    normalized = _normalize_metadata(metadata)
    if not isinstance(normalized, dict):
        return normalized
    raw = normalized.get("raw")
    if raw is None:
        return normalized
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return normalized
    return raw


def _select_media_url(value: dict) -> Optional[str]:
    for key in ("link", "url", "media_url"):
        link = value.get(key)
        if isinstance(link, str) and link.strip():
            return link.strip()
    return None
