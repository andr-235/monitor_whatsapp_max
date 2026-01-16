"""Фоновый опрос БД и уведомления пользователей."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, TypeVar

import psycopg2
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError

from bot.formatting import has_displayable_content
from bot.message_sender import send_message_with_media
from shared.constants import NOTIFY_LIMIT
from shared.db import Database
from shared.repositories import keywords as keyword_repo
from shared.repositories import messages as message_repo
from shared.repositories import user_state as state_repo

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def _run_db(action: Callable[..., T], *args: object) -> T:
    return await asyncio.to_thread(action, *args)


async def run_notifier(
    bot: Bot,
    db: Database,
    poll_interval: int,
    stop_event: asyncio.Event,
) -> None:
    """Запустить цикл опроса БД и отправки уведомлений."""

    while not stop_event.is_set():
        await poll_and_notify(bot, db)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            continue


async def poll_and_notify(bot: Bot, db: Database) -> None:
    """Проверить новые сообщения и отправить уведомления пользователям."""

    try:
        max_id = await _run_db(message_repo.get_max_message_id, db)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при получении max id: %s", exc)
        return

    if max_id <= 0:
        return

    try:
        users = await _run_db(state_repo.list_users_with_keywords, db)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при получении пользователей: %s", exc)
        return

    for user_id in users:
        try:
            last_seen = await _run_db(state_repo.get_last_seen_message_id, db, user_id)
            if last_seen >= max_id:
                continue
            if last_seen == 0:
                await _run_db(state_repo.upsert_last_seen_message_id, db, user_id, max_id)
                continue

            keywords = await _run_db(keyword_repo.list_keywords, db, user_id)
            if not keywords:
                await _run_db(state_repo.upsert_last_seen_message_id, db, user_id, max_id)
                continue

            await _notify_user(bot, db, user_id, keywords, last_seen, max_id)
            await _run_db(state_repo.upsert_last_seen_message_id, db, user_id, max_id)
        except psycopg2.Error as exc:
            logger.error("Ошибка БД при обработке пользователя %s: %s", user_id, exc)
        except TelegramAPIError as exc:
            logger.warning("Ошибка Telegram при отправке пользователю %s: %s", user_id, exc)
            await _run_db(state_repo.upsert_last_seen_message_id, db, user_id, max_id)


async def _notify_user(
    bot: Bot,
    db: Database,
    user_id: int,
    keywords: List[str],
    last_seen: int,
    max_id: int,
) -> None:
    current = last_seen
    while current < max_id:
        messages = await _run_db(
            message_repo.get_messages_by_keywords_between_ids,
            db,
            keywords,
            current,
            max_id,
            NOTIFY_LIMIT,
        )
        if not messages:
            break

        for message in messages:
            if not has_displayable_content(message):
                continue
            try:
                await send_message_with_media(bot, user_id, message)
            except TelegramForbiddenError:
                logger.info("Пользователь %s заблокировал бота", user_id)
                return
            except TelegramBadRequest as exc:
                logger.warning("Некорректный запрос Telegram для %s: %s", user_id, exc)
                return
        current = messages[-1].db_id
