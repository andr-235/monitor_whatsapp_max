"""Точка входа сервиса worker."""

from __future__ import annotations

import logging
import signal
from threading import Event
from types import FrameType
from typing import Dict, Optional

from shared.config import load_environment, load_worker_config
from shared.db import Database
from shared.health import HealthServer
from shared.logging_config import configure_logging
from worker.buffer import MessageBuffer
from worker.poller import Poller
from worker.whapi_client import WhapiClient


def main() -> None:
    """Запустить worker для опроса WhatsApp."""

    load_environment()
    config = load_worker_config()
    configure_logging(config.log_level)
    logger = logging.getLogger("worker.main")

    db = Database(config.database)
    try:
        db.connect()
    except Exception as exc:  # noqa: BLE001 - логируем и продолжаем с буфером
        logger.warning("Не удалось подключиться к БД при старте: %s", exc)

    whapi = WhapiClient(config.whapi)
    buffer = MessageBuffer()
    poller = Poller(whapi, db, config.whapi.poll_interval, buffer)
    stop_event = Event()

    def handle_signal(signum: int, _frame: Optional[FrameType]) -> None:
        logger.info("Получен сигнал %s, завершение работы", signum)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    def health_status() -> Dict[str, object]:
        status = poller.health_status()
        status["бд_доступна"] = db.ping()
        return status

    health_server = HealthServer("0.0.0.0", config.health_port, health_status)
    health_server.start()

    try:
        poller.run(stop_event)
    finally:
        health_server.stop()
        whapi.close()
        db.close()


if __name__ == "__main__":
    main()
