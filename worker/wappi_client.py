"""Клиент для взаимодействия с API Wappi."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from shared.config import WappiConfig
from shared.constants import (
    WAPPI_CHATS_ENDPOINT,
    WAPPI_MESSAGES_ENDPOINT,
    WAPPI_MESSAGE_DATE_FORMAT,
)
from shared.retry import backoff_delays


class RetryableWappiError(RuntimeError):
    """Исключение для ретраимых ошибок API."""


class WappiClient:
    """HTTP-клиент для Wappi API."""

    def __init__(self, config: WappiConfig) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._profile_id = config.profile_id
        self._page_size = config.page_size
        self._include_system_messages = config.include_system_messages
        self._client = httpx.Client(
            base_url=config.api_url,
            timeout=config.request_timeout,
            headers=self._build_headers(config.api_token),
        )

    def close(self) -> None:
        """Закрыть внутренний HTTP-клиент."""

        self._client.close()

    def list_chats(self) -> List[Dict[str, Any]]:
        """Получить все чаты из API с пагинацией."""

        params = {
            "profile_id": self._profile_id,
            "show_all": str(False).lower(),
        }
        return self._paginate(
            WAPPI_CHATS_ENDPOINT,
            "dialogs",
            params=params,
            method="POST",
        )

    def list_messages(
        self, chat_id: str, time_from: Optional[int] = None, time_to: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получить все сообщения чата с пагинацией."""

        chat_id = self._normalize_chat_id(chat_id)
        params: Dict[str, Any] = {
            "profile_id": self._profile_id,
            "chat_id": chat_id,
            "order": "asc",
        }
        if time_from is not None:
            params["date"] = self._format_message_date(time_from)
        messages = self._paginate(
            WAPPI_MESSAGES_ENDPOINT,
            "messages",
            params=params,
        )
        if not self._include_system_messages:
            messages = [
                message for message in messages if message.get("type") != "system"
            ]
        return messages

    def _paginate(
        self,
        endpoint: str,
        items_key: str,
        params: Dict[str, Any],
        method: str = "GET",
        total_key: str = "total_count",
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        offset = 0
        while True:
            page_params = {
                **params,
                "limit": self._page_size,
                "offset": offset,
            }
            data = self._request_json(method, endpoint, page_params)
            page = self._extract_items(data, items_key)
            if not page:
                break
            items.extend(page)
            offset += len(page)
            total = data.get(total_key)
            if total is None:
                total = data.get("total")
            if total is not None and offset >= total:
                break
            if len(page) < self._page_size:
                break
        return items

    def _extract_items(self, data: Dict[str, Any], items_key: str) -> List[Dict[str, Any]]:
        if items_key in data and isinstance(data[items_key], list):
            return data[items_key]
        if items_key == "messages":
            for fallback in ("list", "items", "data"):
                if fallback in data and isinstance(data[fallback], list):
                    return data[fallback]
        return []

    def _request_json(
        self, method: str, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        for delay in backoff_delays():
            try:
                request_kwargs: Dict[str, Any] = {"params": params}
                if method.upper() == "POST":
                    request_kwargs["json"] = {}
                response = self._client.request(method, endpoint, **request_kwargs)
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    raise RetryableWappiError(
                        f"Код ответа для ретрая: {response.status_code}"
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError, RetryableWappiError) as exc:
                self._logger.warning(
                    "Запрос к API не удался (%s). Повтор через %sс", exc, delay
                )
                time.sleep(delay)
            except httpx.HTTPStatusError as exc:
                self._logger.error("Неретраимая ошибка API: %s", exc)
                raise
            except ValueError as exc:
                self._logger.error("Не удалось разобрать ответ API: %s", exc)
                raise
        raise RuntimeError("Цикл ретраев завершился неожиданно")

    @staticmethod
    def _build_headers(token: str) -> Dict[str, str]:
        header_value = token.strip()
        if header_value.lower().startswith("bearer "):
            header_value = header_value[7:].strip()
        return {
            "Authorization": header_value,
            "Accept": "application/json",
        }

    @staticmethod
    def _format_message_date(timestamp: int) -> str:
        return datetime.utcfromtimestamp(timestamp).strftime(WAPPI_MESSAGE_DATE_FORMAT)

    @staticmethod
    def _normalize_chat_id(chat_id: str) -> str:
        if chat_id.endswith("@g.us"):
            return chat_id.split("@", 1)[0]
        return chat_id
