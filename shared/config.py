"""Загрузчики конфигурации для сервисов worker и bot."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from shared.constants import (
    DEFAULT_BOT_POLL_INTERVAL,
    DEFAULT_BOT_HEALTH_PORT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PAGE_SIZE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_WORKER_HEALTH_PORT,
)

ENV_WHAPI_API_URL = "WHAPI_API_URL"
ENV_WHAPI_API_TOKEN = "WHAPI_API_TOKEN"
ENV_WHAPI_POLL_INTERVAL = "WHAPI_POLL_INTERVAL"
ENV_WHAPI_REQUEST_TIMEOUT = "WHAPI_REQUEST_TIMEOUT"
ENV_WHAPI_PAGE_SIZE = "WHAPI_PAGE_SIZE"
ENV_WHAPI_INCLUDE_SYSTEM = "WHAPI_INCLUDE_SYSTEM_MESSAGES"

ENV_POSTGRES_HOST = "POSTGRES_HOST"
ENV_POSTGRES_PORT = "POSTGRES_PORT"
ENV_POSTGRES_DB = "POSTGRES_DB"
ENV_POSTGRES_USER = "POSTGRES_USER"
ENV_POSTGRES_PASSWORD = "POSTGRES_PASSWORD"

ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"

ENV_LOG_LEVEL = "LOG_LEVEL"
ENV_WORKER_HEALTH_PORT = "WORKER_HEALTH_PORT"
ENV_BOT_HEALTH_PORT = "BOT_HEALTH_PORT"
ENV_BOT_POLL_INTERVAL = "BOT_POLL_INTERVAL"


@dataclass(frozen=True)
class DatabaseConfig:
    """Параметры подключения к базе данных."""

    host: str
    port: int
    name: str
    user: str
    password: str
    connect_timeout: int = 5
    max_connections: int = 5

    @property
    def dsn(self) -> str:
        """Сформировать строку DSN PostgreSQL."""

        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password} connect_timeout={self.connect_timeout}"
        )


@dataclass(frozen=True)
class WhapiConfig:
    """Конфигурация WhatsApp API."""

    api_url: str
    api_token: str
    poll_interval: int
    request_timeout: int
    page_size: int
    include_system_messages: bool


@dataclass(frozen=True)
class TelegramConfig:
    """Конфигурация Telegram-бота."""

    bot_token: str


@dataclass(frozen=True)
class WorkerConfig:
    """Конфигурация сервиса worker."""

    database: DatabaseConfig
    whapi: WhapiConfig
    log_level: str
    health_port: int


@dataclass(frozen=True)
class BotConfig:
    """Конфигурация сервиса bot."""

    database: DatabaseConfig
    telegram: TelegramConfig
    log_level: str
    health_port: int
    poll_interval: int


def load_environment() -> None:
    """Загрузить переменные окружения из .env при наличии."""

    load_dotenv()


def _get_env_int(name: str, default: int) -> int:
    """Считать целое число из окружения."""

    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_bool(name: str, default: bool) -> bool:
    """Считать булево значение из окружения."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _required_env(name: str) -> str:
    """Считать обязательную переменную окружения."""

    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Отсутствует обязательная переменная окружения: {name}")
    return value


def load_database_config() -> DatabaseConfig:
    """Загрузить параметры БД из переменных окружения."""

    return DatabaseConfig(
        host=_required_env(ENV_POSTGRES_HOST),
        port=_get_env_int(ENV_POSTGRES_PORT, 5432),
        name=_required_env(ENV_POSTGRES_DB),
        user=_required_env(ENV_POSTGRES_USER),
        password=_required_env(ENV_POSTGRES_PASSWORD),
    )


def load_whapi_config() -> WhapiConfig:
    """Загрузить конфигурацию WhatsApp API из переменных окружения."""

    return WhapiConfig(
        api_url=_required_env(ENV_WHAPI_API_URL).rstrip("/"),
        api_token=_required_env(ENV_WHAPI_API_TOKEN),
        poll_interval=_get_env_int(ENV_WHAPI_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        request_timeout=_get_env_int(ENV_WHAPI_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
        page_size=_get_env_int(ENV_WHAPI_PAGE_SIZE, DEFAULT_PAGE_SIZE),
        include_system_messages=_get_env_bool(ENV_WHAPI_INCLUDE_SYSTEM, True),
    )


def load_worker_config() -> WorkerConfig:
    """Загрузить конфигурацию worker из переменных окружения."""

    return WorkerConfig(
        database=load_database_config(),
        whapi=load_whapi_config(),
        log_level=os.getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        health_port=_get_env_int(ENV_WORKER_HEALTH_PORT, DEFAULT_WORKER_HEALTH_PORT),
    )


def load_bot_config() -> BotConfig:
    """Загрузить конфигурацию bot из переменных окружения."""

    telegram = TelegramConfig(bot_token=_required_env(ENV_TELEGRAM_BOT_TOKEN))
    return BotConfig(
        database=load_database_config(),
        telegram=telegram,
        log_level=os.getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        health_port=_get_env_int(ENV_BOT_HEALTH_PORT, DEFAULT_BOT_HEALTH_PORT),
        poll_interval=_get_env_int(ENV_BOT_POLL_INTERVAL, DEFAULT_BOT_POLL_INTERVAL),
    )
