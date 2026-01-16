#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD=${COMPOSE_CMD:-"docker compose"}
PG_SERVICE=${PG_SERVICE:-postgres}
WINDOW=${1:-"1 hour"}

$COMPOSE_CMD exec -T -e WINDOW="$WINDOW" "$PG_SERVICE" sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v window="$WINDOW" -f -' <<'SQL'
\pset pager off

\echo === Messages per minute (last :window) ===
SELECT date_trunc('minute', timestamp) AS minute, count(*) AS messages
FROM messages
WHERE timestamp >= now() - (:'window')::interval
GROUP BY 1
ORDER BY 1;

\echo === Average messages per minute (last :window) ===
SELECT round(
    count(*) / (extract(epoch from (:'window')::interval) / 60.0),
    2
) AS avg_per_min
FROM messages
WHERE timestamp >= now() - (:'window')::interval;

\echo === Active chats (last :window) ===
SELECT count(DISTINCT chat_id) AS active_chats
FROM messages
WHERE timestamp >= now() - (:'window')::interval;

\echo === Top chats (last :window) ===
SELECT chat_id, count(*) AS messages
FROM messages
WHERE timestamp >= now() - (:'window')::interval
GROUP BY chat_id
ORDER BY messages DESC
LIMIT 20;
SQL
