"""Точка входа сервиса Telegram-бота."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from datetime import datetime
from typing import Dict

from aiogram import Bot, Dispatcher

from bot.handlers import router as bot_router
from bot.keyword_service import KeywordService
from bot.menu import setup_bot_commands
from bot.notifier import run_notifier
from shared.config import load_bot_config, load_environment
from shared.constants import DATETIME_FORMAT
from shared.db import Database
from shared.health import HealthServer
from shared.logging_config import configure_logging


async def _run_bot() -> None:
    """Запустить Telegram-бота с долгим опросом."""

    load_environment()
    config = load_bot_config()
    configure_logging(config.log_level)
    logger = logging.getLogger("bot.main")

    db = Database(config.database)
    try:
        db.connect()
    except Exception as exc:  # noqa: BLE001 - логируем и продолжаем
        logger.warning("Не удалось подключиться к БД при старте: %s", exc)

    keyword_service = KeywordService(db)
    bot = Bot(token=config.telegram.bot_token)
    try:
        await setup_bot_commands(bot)
    except Exception as exc:  # noqa: BLE001 - логируем и продолжаем
        logger.warning("Не удалось обновить меню команд: %s", exc)
    dispatcher = Dispatcher()
    dispatcher.include_router(bot_router)

    started_at = datetime.utcnow()

    def health_status() -> Dict[str, object]:
        return {
            "статус": "ок",
            "время_запуска": started_at.strftime(DATETIME_FORMAT),
            "бд_доступна": db.ping(),
        }

    health_server = HealthServer("0.0.0.0", config.health_port, health_status)
    health_server.start()

    stop_event = asyncio.Event()
    notifier_task = asyncio.create_task(run_notifier(bot, db, config.poll_interval, stop_event))

    try:
        await dispatcher.start_polling(bot, db=db, keyword_service=keyword_service)
    finally:
        stop_event.set()
        notifier_task.cancel()
        with suppress(asyncio.CancelledError):
            await notifier_task
        health_server.stop()
        await bot.session.close()
        db.close()


def main() -> None:
    """Запустить приложение."""

    asyncio.run(_run_bot())


if __name__ == "__main__":
    main()
