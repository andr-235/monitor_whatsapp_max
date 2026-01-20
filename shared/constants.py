"""Константы приложения."""

DEFAULT_POLL_INTERVAL = 600
DEFAULT_BOT_POLL_INTERVAL = 60
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 100
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[component]}</cyan> | "
    "{message}"
)
DEFAULT_RECENT_LIMIT = 10
PAGE_SIZE = 10
SEARCH_LIMIT = 50
NOTIFY_LIMIT = 50
MAX_BUFFER_SIZE = 1000
MAX_RETRY_DELAY = 60
RETRY_BACKOFF_START = 1

WAPPI_CHATS_ENDPOINT = "/api/sync/chats/get"
WAPPI_MESSAGES_ENDPOINT = "/api/sync/messages/get"
WAPPI_SKIPPED_CHAT_IDS = {"status@broadcast", "0@s.whatsapp.net"}
WAPPI_MESSAGE_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

MAX_CHATS_ENDPOINT = "/maxapi/sync/chats/get"
MAX_MESSAGES_ENDPOINT = "/maxapi/sync/messages/get"
MAX_MESSAGE_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

PROVIDER_WAPPI = "wappi"
PROVIDER_MAX = "max"

SOURCE_LABEL_WAPPI = "WhatsApp"
SOURCE_LABEL_MAX = "Max"
SOURCE_LABEL_HEADER = "Источник"

MESSAGES_TABLE = "messages"
MESSAGES_MAX_TABLE = "messages_max"

HEALTH_PATH = "/health"
DEFAULT_WORKER_HEALTH_PORT = 8081
DEFAULT_BOT_HEALTH_PORT = 8082

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
