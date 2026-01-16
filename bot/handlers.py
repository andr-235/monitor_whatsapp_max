"""Обработчики команд Telegram-бота."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, TypeVar

import psycopg2
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError

from bot.constants import (
    ADD_KEYWORD_PROMPT,
    DB_ERROR_MESSAGE,
    KEYWORD_EMPTY_MESSAGE,
    KEYWORD_ADDED_MESSAGE,
    KEYWORD_EXISTS_MESSAGE,
    KEYWORD_NOT_FOUND_MESSAGE,
    KEYWORD_REMOVED_MESSAGE,
    MENU_MESSAGE,
    NO_KEYWORDS_MESSAGE,
    NO_RESULTS_MESSAGE,
    RECENT_USAGE,
    RECENT_RESULTS_HEADER,
    REMOVE_KEYWORD_PROMPT,
    SEARCH_RESULTS_ERROR_SUFFIX,
    SEARCH_RESULTS_HEADER,
    START_MESSAGE,
)
from bot.formatting import format_keywords_list, has_displayable_content
from bot.menu import build_main_menu
from bot.message_sender import send_message_with_media
from bot.keyword_service import KeywordService
from bot.states import KeywordDialog
from shared.constants import (
    DEFAULT_RECENT_LIMIT,
    PAGE_SIZE,
    SEARCH_LIMIT,
)
from shared.db import Database
from shared.models import MessageView
from shared.repositories import user_state as state_repo
from shared.repositories.messages import (
    get_max_message_id,
    get_max_message_id_max,
    get_recent_messages_combined,
    search_messages_by_keywords_combined,
)

logger = logging.getLogger(__name__)

router = Router()

T = TypeVar("T")


def _get_user_id(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id


async def _run_db(action: Callable[..., T], *args: object) -> T:
    return await asyncio.to_thread(action, *args)


@router.message(Command("start"))
async def start(message: Message, state: FSMContext) -> None:
    """Обработать команду /start."""

    await state.clear()
    await message.reply(START_MESSAGE, reply_markup=build_main_menu())


@router.message(Command("menu"))
@router.message(Command("help"))
async def show_menu(message: Message, state: FSMContext) -> None:
    """Показать меню команд."""

    await state.clear()
    await message.reply(MENU_MESSAGE, reply_markup=build_main_menu())


@router.message(Command("recent"))
async def recent(
    message: Message, command: CommandObject, db: Database, state: FSMContext
) -> None:
    """Обработать команду /recent."""

    await state.clear()
    limit = DEFAULT_RECENT_LIMIT
    if command.args:
        candidate = command.args.split(maxsplit=1)[0]
        try:
            limit = int(candidate)
        except ValueError:
            await message.reply(RECENT_USAGE)
            return

    if limit <= 0:
        await message.reply(RECENT_USAGE)
        return

    try:
        messages = await _run_db(get_recent_messages_combined, db, limit, 0)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /recent: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    messages = [item for item in messages if has_displayable_content(item)]
    if not messages:
        await message.reply(NO_RESULTS_MESSAGE)
        return

    await message.reply(RECENT_RESULTS_HEADER.format(count=len(messages)))
    await _send_paginated(message, messages)


@router.message(Command("add_keyword"))
async def add_keyword(
    message: Message,
    command: CommandObject,
    keyword_service: KeywordService,
    db: Database,
    state: FSMContext,
) -> None:
    """Обработать команду /add_keyword."""

    await state.clear()
    keyword = (command.args or "").strip()
    if not keyword:
        await state.set_state(KeywordDialog.waiting_for_add)
        await message.reply(ADD_KEYWORD_PROMPT, reply_markup=build_main_menu())
        return

    await _handle_add_keyword(message, keyword_service, db, keyword)


@router.message(KeywordDialog.waiting_for_add, F.text, ~F.text.startswith("/"))
async def add_keyword_from_text(
    message: Message, keyword_service: KeywordService, db: Database, state: FSMContext
) -> None:
    """Добавить ключевое слово из следующего сообщения."""

    keyword = (message.text or "").strip()
    if not keyword:
        await message.reply(KEYWORD_EMPTY_MESSAGE)
        return

    await _handle_add_keyword(message, keyword_service, db, keyword)
    await state.clear()


@router.message(KeywordDialog.waiting_for_add, ~F.text)
async def add_keyword_non_text(message: Message) -> None:
    """Сообщить о некорректном вводе ключевого слова."""

    await message.reply(KEYWORD_EMPTY_MESSAGE)


@router.message(Command("remove_keyword"))
async def remove_keyword(
    message: Message,
    command: CommandObject,
    keyword_service: KeywordService,
    state: FSMContext,
) -> None:
    """Обработать команду /remove_keyword."""

    await state.clear()
    keyword = (command.args or "").strip()
    if not keyword:
        await state.set_state(KeywordDialog.waiting_for_remove)
        await message.reply(REMOVE_KEYWORD_PROMPT, reply_markup=build_main_menu())
        return

    await _handle_remove_keyword(message, keyword_service, keyword)


@router.message(KeywordDialog.waiting_for_remove, F.text, ~F.text.startswith("/"))
async def remove_keyword_from_text(
    message: Message, keyword_service: KeywordService, state: FSMContext
) -> None:
    """Удалить ключевое слово из следующего сообщения."""

    keyword = (message.text or "").strip()
    if not keyword:
        await message.reply(KEYWORD_EMPTY_MESSAGE)
        return

    await _handle_remove_keyword(message, keyword_service, keyword)
    await state.clear()


@router.message(KeywordDialog.waiting_for_remove, ~F.text)
async def remove_keyword_non_text(message: Message) -> None:
    """Сообщить о некорректном вводе ключевого слова."""

    await message.reply(KEYWORD_EMPTY_MESSAGE)


@router.message(Command("list_keywords"))
async def list_keywords(
    message: Message, keyword_service: KeywordService, state: FSMContext
) -> None:
    """Обработать команду /list_keywords."""

    await state.clear()
    user_id = _get_user_id(message)
    if user_id is None:
        return

    try:
        keywords = await _run_db(keyword_service.list_keywords, user_id)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /list_keywords: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    if not keywords:
        await message.reply(NO_KEYWORDS_MESSAGE)
        return

    formatted = format_keywords_list(keywords)
    await message.reply(formatted)


@router.message(Command("search"))
async def search(
    message: Message, db: Database, keyword_service: KeywordService, state: FSMContext
) -> None:
    """Обработать команду /search."""

    await state.clear()
    user_id = _get_user_id(message)
    if user_id is None:
        return

    try:
        keywords = await _run_db(keyword_service.list_keywords, user_id)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /search (ключевые слова): %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    if not keywords:
        await message.reply(NO_KEYWORDS_MESSAGE)
        return

    try:
        messages = await _run_db(
            search_messages_by_keywords_combined, db, keywords, SEARCH_LIMIT, 0
        )
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /search: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    messages = [item for item in messages if has_displayable_content(item)]
    if not messages:
        await message.reply(NO_RESULTS_MESSAGE)
        return

    sent_count, failed_count = await _send_paginated(message, messages, keywords=keywords)
    summary = SEARCH_RESULTS_HEADER.format(found=len(messages), sent=sent_count)
    if failed_count:
        summary += SEARCH_RESULTS_ERROR_SUFFIX.format(failed=failed_count)
    await message.reply(summary)


async def _handle_add_keyword(
    message: Message, keyword_service: KeywordService, db: Database, keyword: str
) -> None:
    user_id = _get_user_id(message)
    if user_id is None:
        return

    try:
        added = await _run_db(keyword_service.add_keyword, user_id, keyword)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /add_keyword: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    keyword_display = keyword.strip()
    reply_text = (
        KEYWORD_ADDED_MESSAGE.format(keyword=keyword_display)
        if added
        else KEYWORD_EXISTS_MESSAGE.format(keyword=keyword_display)
    )
    await message.reply(reply_text)

    if added:
        await _initialize_user_state(db, user_id)


async def _handle_remove_keyword(
    message: Message, keyword_service: KeywordService, keyword: str
) -> None:
    user_id = _get_user_id(message)
    if user_id is None:
        return

    try:
        removed = await _run_db(keyword_service.remove_keyword, user_id, keyword)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /remove_keyword: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    keyword_display = keyword.strip()
    reply_text = (
        KEYWORD_REMOVED_MESSAGE.format(keyword=keyword_display)
        if removed
        else KEYWORD_NOT_FOUND_MESSAGE.format(keyword=keyword_display)
    )
    await message.reply(reply_text)


async def _send_paginated(
    message: Message,
    messages: List[MessageView],
    keywords: List[str] | None = None,
) -> tuple[int, int]:
    sent_count = 0
    failed_count = 0
    for offset in range(0, len(messages), PAGE_SIZE):
        page = messages[offset : offset + PAGE_SIZE]
        for item in page:
            try:
                await send_message_with_media(
                    message.bot,
                    message.chat.id,
                    item,
                    keywords=keywords,
                )
                sent_count += 1
            except TelegramAPIError as exc:
                failed_count += 1
                logger.warning(
                    "Ошибка Telegram при отправке сообщения %s пользователю %s: %s",
                    item.db_id,
                    message.chat.id,
                    exc,
                )
    return sent_count, failed_count


async def _initialize_user_state(db: Database, user_id: int) -> None:
    try:
        last_seen = await _run_db(state_repo.get_last_seen_message_id, db, user_id)
        last_seen_max = await _run_db(state_repo.get_last_seen_message_max_id, db, user_id)
        max_id = await _run_db(get_max_message_id, db)
        max_id_max = await _run_db(get_max_message_id_max, db)
        if last_seen == 0:
            await _run_db(state_repo.upsert_last_seen_message_id, db, user_id, max_id)
        if last_seen_max == 0:
            await _run_db(
                state_repo.upsert_last_seen_message_max_id, db, user_id, max_id_max
            )
    except psycopg2.Error as exc:
        logger.warning("Не удалось инициализировать состояние пользователя %s: %s", user_id, exc)
