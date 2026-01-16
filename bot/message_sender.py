"""Send messages to Telegram chats with media when available."""

from __future__ import annotations

import logging
import re
from typing import Sequence

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from bot.constants import TELEGRAM_CAPTION_LIMIT, TELEGRAM_MESSAGE_LIMIT
from bot.formatting import extract_media, format_message, format_message_caption
from shared.models import MessageView

logger = logging.getLogger(__name__)


async def send_message_with_media(
    bot: Bot,
    chat_id: int,
    message: MessageView,
    keywords: Sequence[str] | None = None,
) -> None:
    """Send a message with media when possible, otherwise fallback to text."""

    media = extract_media(message.metadata)
    if media is None:
        await _send_text_chunks(
            bot,
            chat_id,
            format_message(message, keywords=keywords),
        )
        return

    caption = format_message_caption(message, media.caption, keywords=keywords)
    caption_chunks = _split_text(caption, TELEGRAM_CAPTION_LIMIT)
    caption_head = caption_chunks[0] if caption_chunks else ""
    caption_tail = caption_chunks[1:]
    try:
        if media.media_type == "image":
            await bot.send_photo(
                chat_id=chat_id,
                photo=media.url,
                caption=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
        if media.media_type in {"video", "short"}:
            await bot.send_video(
                chat_id=chat_id,
                video=media.url,
                caption=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
        if media.media_type == "gif":
            await bot.send_animation(
                chat_id=chat_id,
                animation=media.url,
                caption=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
        if media.media_type == "document":
            await bot.send_document(
                chat_id=chat_id,
                document=media.url,
                caption=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
        if media.media_type == "audio":
            await bot.send_audio(
                chat_id=chat_id,
                audio=media.url,
                caption=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
        if media.media_type == "voice":
            await bot.send_voice(
                chat_id=chat_id,
                voice=media.url,
                caption=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
        if media.media_type == "sticker":
            await bot.send_message(
                chat_id=chat_id,
                text=caption_head,
                parse_mode=ParseMode.HTML,
            )
            await bot.send_sticker(chat_id=chat_id, sticker=media.url)
            await _send_caption_tail(bot, chat_id, caption_tail)
            return
    except TelegramBadRequest as exc:
        logger.warning("Failed to send media to chat %s: %s", chat_id, exc)

    has_text = bool((message.text or "").strip())
    has_caption = bool((media.caption or "").strip())
    force_links = not (has_text or has_caption)
    await _send_text_chunks(
        bot,
        chat_id,
        format_message(message, force_links=force_links, keywords=keywords),
    )


HTML_TAG_PATTERN = re.compile(r"</?[^>]+>")
WHITESPACE_PATTERN = re.compile(r"(\s+)")


async def _send_text_chunks(bot: Bot, chat_id: int, text: str) -> None:
    chunks = _split_text(text, TELEGRAM_MESSAGE_LIMIT)
    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
            )
        except TelegramBadRequest as exc:
            logger.warning("Failed to send HTML chunk to chat %s: %s", chat_id, exc)
            plain = _strip_html(chunk)
            await bot.send_message(chat_id=chat_id, text=plain)


async def _send_caption_tail(
    bot: Bot,
    chat_id: int,
    chunks: list[str],
) -> None:
    for chunk in chunks:
        await _send_text_chunks(bot, chat_id, chunk)


def _strip_html(text: str) -> str:
    return HTML_TAG_PATTERN.sub("", text)


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    tokens = WHITESPACE_PATTERN.split(text)
    chunks: list[str] = []
    current = ""
    for token in tokens:
        if not token:
            continue
        if len(current) + len(token) <= limit:
            current += token
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(token) <= limit:
            current = token
            continue
        start = 0
        while start < len(token):
            part = token[start : start + limit]
            if len(part) >= limit:
                chunks.append(part)
                current = ""
            else:
                current = part
            start += limit
    if current:
        chunks.append(current)
    return chunks
