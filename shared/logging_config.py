"""Помощники конфигурации логирования."""

import logging


def configure_logging(log_level: str) -> None:
    """Настроить корневой логгер со стандартным форматом."""

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
