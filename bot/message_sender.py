"""Send messages to Telegram chats with media when available."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from bot.formatting import extract_media, format_message, format_message_caption
from shared.models import MessageView

logger = logging.getLogger(__name__)


async def send_message_with_media(bot: Bot, chat_id: int, message: MessageView) -> None:
    """Send a message with media when possible, otherwise fallback to text."""

    media = extract_media(message.metadata)
    if media is None:
        await bot.send_message(
            chat_id=chat_id,
            text=format_message(message),
            parse_mode=ParseMode.HTML,
        )
        return

    caption = format_message_caption(message, media.caption)
    try:
        if media.media_type == "image":
            await bot.send_photo(
                chat_id=chat_id,
                photo=media.url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        if media.media_type in {"video", "short"}:
            await bot.send_video(
                chat_id=chat_id,
                video=media.url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        if media.media_type == "gif":
            await bot.send_animation(
                chat_id=chat_id,
                animation=media.url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        if media.media_type == "document":
            await bot.send_document(
                chat_id=chat_id,
                document=media.url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        if media.media_type == "audio":
            await bot.send_audio(
                chat_id=chat_id,
                audio=media.url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        if media.media_type == "voice":
            await bot.send_voice(
                chat_id=chat_id,
                voice=media.url,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        if media.media_type == "sticker":
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode=ParseMode.HTML,
            )
            await bot.send_sticker(chat_id=chat_id, sticker=media.url)
            return
    except TelegramBadRequest as exc:
        logger.warning("Failed to send media to chat %s: %s", chat_id, exc)

    has_text = bool((message.text or "").strip())
    has_caption = bool((media.caption or "").strip())
    force_links = not (has_text or has_caption)
    await bot.send_message(
        chat_id=chat_id,
        text=format_message(message, force_links=force_links),
        parse_mode=ParseMode.HTML,
    )
