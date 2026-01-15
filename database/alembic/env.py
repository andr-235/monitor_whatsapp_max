"""Конфигурация окружения Alembic."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Объект конфигурации Alembic.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None else default


def get_url() -> str:
    """Сформировать URL БД из переменных окружения."""

    host = _get_env("POSTGRES_HOST", "localhost")
    port = _get_env("POSTGRES_PORT", "5432")
    name = _get_env("POSTGRES_DB", "postgres")
    user = _get_env("POSTGRES_USER", "postgres")
    password = _get_env("POSTGRES_PASSWORD", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def run_migrations_offline() -> None:
    """Запустить миграции в офлайн режиме."""

    url = get_url()
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запустить миграции в онлайн режиме."""

    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
