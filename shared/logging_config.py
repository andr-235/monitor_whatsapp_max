"""Помощники конфигурации логирования."""

from __future__ import annotations

import logging
import sys

from loguru import logger

from shared.constants import LOG_FORMAT


class InterceptHandler(logging.Handler):
    """Перенаправляет стандартные логи в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(component=record.name).opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def configure_logging(log_level: str) -> None:
    """Настроить корневой логгер через loguru."""

    logger.remove()
    logger.configure(extra={"component": "-"})
    logger.add(
        sys.stdout,
        level=log_level,
        format=LOG_FORMAT,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=log_level,
        force=True,
    )
