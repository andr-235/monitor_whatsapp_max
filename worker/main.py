"""Точка входа сервиса worker."""

from __future__ import annotations

import logging
import signal
from threading import Event, Thread
from types import FrameType
from typing import Dict, Optional

from shared.config import load_environment, load_worker_config
from shared.constants import PROVIDER_MAX, PROVIDER_WAPPI, WAPPI_SKIPPED_CHAT_IDS
from shared.db import Database
from shared.health import HealthServer
from shared.logging_config import configure_logging
from shared.repositories import messages as message_repo
from worker.buffer import MessageBuffer
from worker.poller import Poller
from worker.max_client import MaxClient
from worker.wappi_client import WappiClient


def main() -> None:
    """Запустить worker для опроса WhatsApp и Max."""

    load_environment()
    config = load_worker_config()
    configure_logging(config.log_level)
    logger = logging.getLogger("worker.main")

    db = Database(config.database)
    try:
        db.connect()
    except Exception as exc:  # noqa: BLE001 - логируем и продолжаем с буфером
        logger.warning("Не удалось подключиться к БД при старте: %s", exc)

    wappi = WappiClient(config.wappi)
    max_client = MaxClient(config.max_api)
    wappi_buffer = MessageBuffer()
    max_buffer = MessageBuffer()
    wappi_poller = Poller(
        wappi,
        db,
        config.wappi.poll_interval,
        wappi_buffer,
        insert_messages_fn=message_repo.insert_messages,
        get_latest_timestamp_fn=message_repo.get_latest_message_timestamp,
        full_sync_on_start=config.wappi.full_sync_on_start,
        skipped_chat_ids=WAPPI_SKIPPED_CHAT_IDS,
        provider=PROVIDER_WAPPI,
    )
    max_poller = Poller(
        max_client,
        db,
        config.max_api.poll_interval,
        max_buffer,
        insert_messages_fn=message_repo.insert_messages_max,
        get_latest_timestamp_fn=message_repo.get_latest_message_timestamp_max,
        full_sync_on_start=config.max_api.full_sync_on_start,
        skipped_chat_ids=set(),
        provider=PROVIDER_MAX,
    )
    stop_event = Event()

    def handle_signal(signum: int, _frame: Optional[FrameType]) -> None:
        logger.info("Получен сигнал %s, завершение работы", signum)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    def health_status() -> Dict[str, object]:
        return {
            "статус": "ок",
            "whatsapp": wappi_poller.health_status(),
            "max": max_poller.health_status(),
            "бд_доступна": db.ping(),
        }

    health_server = HealthServer("0.0.0.0", config.health_port, health_status)
    health_server.start()

    try:
        threads = [
            Thread(target=wappi_poller.run, args=(stop_event,), name="wappi-poller"),
            Thread(target=max_poller.run, args=(stop_event,), name="max-poller"),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        health_server.stop()
        wappi.close()
        max_client.close()
        db.close()


if __name__ == "__main__":
    main()
