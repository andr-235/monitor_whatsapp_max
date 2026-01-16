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
from shared.constants import NOTIFY_LIMIT, SOURCE_LABEL_MAX, SOURCE_LABEL_WAPPI
from shared.db import Database
from shared.models import MessageView
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
        users = await _run_db(state_repo.list_users_with_keywords, db)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при получении пользователей: %s", exc)
        return

    if not users:
        return

    await _poll_provider(
        bot=bot,
        db=db,
        users=users,
        provider_label=SOURCE_LABEL_WAPPI,
        get_max_id=message_repo.get_max_message_id,
        get_last_seen=state_repo.get_last_seen_message_id,
        upsert_last_seen=state_repo.upsert_last_seen_message_id,
        get_messages=message_repo.get_messages_by_keywords_between_ids,
    )
    await _poll_provider(
        bot=bot,
        db=db,
        users=users,
        provider_label=SOURCE_LABEL_MAX,
        get_max_id=message_repo.get_max_message_id_max,
        get_last_seen=state_repo.get_last_seen_message_max_id,
        upsert_last_seen=state_repo.upsert_last_seen_message_max_id,
        get_messages=message_repo.get_messages_by_keywords_between_ids_max,
    )


async def _poll_provider(
    bot: Bot,
    db: Database,
    users: List[int],
    provider_label: str,
    get_max_id: Callable[[Database], int],
    get_last_seen: Callable[[Database, int], int],
    upsert_last_seen: Callable[[Database, int, int], None],
    get_messages: Callable[[Database, List[str], int, int, int], List[MessageView]],
) -> None:
    try:
        max_id = await _run_db(get_max_id, db)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при получении max id (%s): %s", provider_label, exc)
        return

    if max_id <= 0:
        return

    for user_id in users:
        try:
            last_seen = await _run_db(get_last_seen, db, user_id)
            if last_seen >= max_id:
                continue
            if last_seen == 0:
                await _run_db(upsert_last_seen, db, user_id, max_id)
                continue

            keywords = await _run_db(keyword_repo.list_keywords, db, user_id)
            if not keywords:
                await _run_db(upsert_last_seen, db, user_id, max_id)
                continue

            await _notify_user(
                bot,
                db,
                user_id,
                keywords,
                last_seen,
                max_id,
                get_messages,
            )
            await _run_db(upsert_last_seen, db, user_id, max_id)
        except psycopg2.Error as exc:
            logger.error(
                "Ошибка БД при обработке пользователя %s (%s): %s",
                user_id,
                provider_label,
                exc,
            )
        except TelegramAPIError as exc:
            logger.warning(
                "Ошибка Telegram при отправке пользователю %s (%s): %s",
                user_id,
                provider_label,
                exc,
            )
            await _run_db(upsert_last_seen, db, user_id, max_id)


async def _notify_user(
    bot: Bot,
    db: Database,
    user_id: int,
    keywords: List[str],
    last_seen: int,
    max_id: int,
    get_messages: Callable[[Database, List[str], int, int, int], List[MessageView]],
) -> None:
    current = last_seen
    while current < max_id:
        messages = await _run_db(
            get_messages,
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
