"""Обработчики команд Telegram-бота."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, TypeVar

import psycopg2
from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message

from bot.constants import (
    ADD_KEYWORD_USAGE,
    DB_ERROR_MESSAGE,
    KEYWORD_ADDED_MESSAGE,
    KEYWORD_EXISTS_MESSAGE,
    KEYWORD_NOT_FOUND_MESSAGE,
    KEYWORD_REMOVED_MESSAGE,
    KEYWORDS_LIST_HEADER,
    NO_KEYWORDS_MESSAGE,
    NO_RESULTS_MESSAGE,
    RECENT_USAGE,
    REMOVE_KEYWORD_USAGE,
    START_MESSAGE,
)
from bot.formatting import format_message_page
from bot.keyword_service import KeywordService
from shared.constants import DEFAULT_RECENT_LIMIT, PAGE_SIZE, SEARCH_LIMIT
from shared.db import Database
from shared.models import MessageView
from shared.repositories.messages import get_recent_messages, search_messages_by_keywords

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
async def start(message: Message) -> None:
    """Обработать команду /start."""

    await message.reply(START_MESSAGE)


@router.message(Command("recent"))
async def recent(message: Message, command: CommandObject, db: Database) -> None:
    """Обработать команду /recent."""

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
        messages = await _run_db(get_recent_messages, db, limit, 0)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /recent: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    if not messages:
        await message.reply(NO_RESULTS_MESSAGE)
        return

    await _send_paginated(message, messages)


@router.message(Command("add_keyword"))
async def add_keyword(
    message: Message, command: CommandObject, keyword_service: KeywordService
) -> None:
    """Обработать команду /add_keyword."""

    keyword = (command.args or "").strip()
    if not keyword:
        await message.reply(ADD_KEYWORD_USAGE)
        return

    user_id = _get_user_id(message)
    if user_id is None:
        return

    try:
        added = await _run_db(keyword_service.add_keyword, user_id, keyword)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /add_keyword: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    await message.reply(KEYWORD_ADDED_MESSAGE if added else KEYWORD_EXISTS_MESSAGE)


@router.message(Command("remove_keyword"))
async def remove_keyword(
    message: Message, command: CommandObject, keyword_service: KeywordService
) -> None:
    """Обработать команду /remove_keyword."""

    keyword = (command.args or "").strip()
    if not keyword:
        await message.reply(REMOVE_KEYWORD_USAGE)
        return

    user_id = _get_user_id(message)
    if user_id is None:
        return

    try:
        removed = await _run_db(keyword_service.remove_keyword, user_id, keyword)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /remove_keyword: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    await message.reply(KEYWORD_REMOVED_MESSAGE if removed else KEYWORD_NOT_FOUND_MESSAGE)


@router.message(Command("list_keywords"))
async def list_keywords(message: Message, keyword_service: KeywordService) -> None:
    """Обработать команду /list_keywords."""

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

    formatted = "\n".join([KEYWORDS_LIST_HEADER, *keywords])
    await message.reply(formatted)


@router.message(Command("search"))
async def search(message: Message, db: Database, keyword_service: KeywordService) -> None:
    """Обработать команду /search."""

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
        messages = await _run_db(search_messages_by_keywords, db, keywords, SEARCH_LIMIT, 0)
    except psycopg2.Error as exc:
        logger.error("Ошибка БД при /search: %s", exc)
        await message.reply(DB_ERROR_MESSAGE)
        return

    if not messages:
        await message.reply(NO_RESULTS_MESSAGE)
        return

    await _send_paginated(message, messages)


async def _send_paginated(message: Message, messages: List[MessageView]) -> None:
    for offset in range(0, len(messages), PAGE_SIZE):
        page = messages[offset : offset + PAGE_SIZE]
        await message.reply(format_message_page(page))
