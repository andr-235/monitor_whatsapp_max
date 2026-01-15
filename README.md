# Monitor WhatsApp Max

## Обзор
Проект содержит два независимых сервиса:
- `worker`: опрашивает WhatsApp API (gate.whapi.cloud) и сохраняет сообщения в PostgreSQL.
- `bot`: Telegram-бот, который ищет и пагинирует сообщения из PostgreSQL.

Общие утилиты находятся в `shared`, миграции БД — в `database`.

## Архитектура
```
/worker   - сервис опроса WhatsApp API
/bot      - Telegram-бот (долгий опрос)
/database - миграции Alembic
/shared   - общая конфигурация, утилиты БД, модели
```

## Требования
- Python 3.10+
- PostgreSQL 13+
- Poetry
- Docker (опционально)

## Конфигурация
Скопируйте `.env.example` в `.env` и заполните значения:
- `WHAPI_API_URL`, `WHAPI_API_TOKEN`, `WHAPI_POLL_INTERVAL`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `LOG_LEVEL`
- `BOT_POLL_INTERVAL` — интервал опроса БД ботом (по умолчанию 60 секунд)

Опционально:
- `WHAPI_REQUEST_TIMEOUT`, `WHAPI_PAGE_SIZE`, `WHAPI_INCLUDE_SYSTEM_MESSAGES`
- `WORKER_HEALTH_PORT`, `BOT_HEALTH_PORT`

## Миграции БД
Через Poetry:
```
poetry run alembic -c database/alembic.ini upgrade head
```

## Запуск локально
```
poetry install
poetry run worker
poetry run bot
```

## Запуск через Docker Compose
```
docker-compose up --build
```

## Команды Telegram-бота
- `/start` — справка и описание
- `/add_keyword <слово>` — добавить ключевое слово
- `/remove_keyword <слово>` — удалить ключевое слово
- `/list_keywords` — список активных ключевых слов
- `/search` — поиск по всем ключевым словам (OR, ILIKE)
- `/recent [N]` — показать последние N сообщений (по умолчанию 10), по 10 на страницу

## Схема БД
`messages`:
- `id` SERIAL PRIMARY KEY
- `message_id` VARCHAR UNIQUE NOT NULL
- `chat_id` VARCHAR NOT NULL
- `sender` VARCHAR NOT NULL
- `text` TEXT
- `timestamp` TIMESTAMP NOT NULL
- `metadata` JSONB
- `created_at` TIMESTAMP DEFAULT NOW()

Индексы:
- уникальный индекс на `message_id`
- индекс на `timestamp`
- GIN индекс на `text` (триграммы, pg_trgm)

`keywords`:
- `id` SERIAL PRIMARY KEY
- `user_id` BIGINT NOT NULL
- `keyword` VARCHAR NOT NULL
- `created_at` TIMESTAMP DEFAULT NOW()
- уникальность на (`user_id`, `keyword`)

`user_state`:
- `user_id` BIGINT PRIMARY KEY
- `last_seen_message_id` INTEGER NOT NULL
- `updated_at` TIMESTAMP DEFAULT NOW()

## Мониторинг и проверка состояния
Каждый сервис отдает `/health`:
- Сервис `worker`: включает время последнего успешного опроса и размер буфера.
- Сервис `bot`: включает время запуска и доступность БД.

## Интервал опроса
Интервал по умолчанию — 10 минут (`WHAPI_POLL_INTERVAL=600`).

## Авто-уведомления
Бот опрашивает БД и автоматически отправляет новые сообщения, которые совпадают с ключевыми словами пользователя. Интервал опроса настраивается через `BOT_POLL_INTERVAL`.
