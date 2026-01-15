"""Клиент для взаимодействия с API gate.whapi.cloud."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from shared.config import WhapiConfig
from shared.constants import WHAPI_CHATS_ENDPOINT, WHAPI_MESSAGES_ENDPOINT
from shared.retry import backoff_delays


class RetryableWhapiError(RuntimeError):
    """Исключение для ретраимых ошибок API."""


class WhapiClient:
    """HTTP-клиент для WhatsApp API."""

    def __init__(self, config: WhapiConfig) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._base_url = config.api_url
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

        return self._paginate(WHAPI_CHATS_ENDPOINT, "chats")

    def list_messages(
        self, chat_id: str, time_from: Optional[int] = None, time_to: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получить все сообщения чата с пагинацией."""

        endpoint = WHAPI_MESSAGES_ENDPOINT.format(chat_id=chat_id)
        params: Dict[str, Any] = {}
        if time_from is not None:
            params["time_from"] = time_from
        if time_to is not None:
            params["time_to"] = time_to
        params["sort"] = "asc"
        params["normal_types"] = not self._include_system_messages
        return self._paginate(endpoint, "messages", extra_params=params)

    def _paginate(
        self, endpoint: str, items_key: str, extra_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        offset = 0
        while True:
            params = {
                "count": self._page_size,
                "offset": offset,
            }
            if extra_params:
                params.update(extra_params)
            data = self._request_json(endpoint, params)
            page = self._extract_items(data, items_key)
            if not page:
                break
            items.extend(page)
            offset += len(page)
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

    def _request_json(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        for delay in backoff_delays():
            try:
                response = self._client.get(endpoint, params=params)
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    raise RetryableWhapiError(
                        f"Код ответа для ретрая: {response.status_code}"
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError, RetryableWhapiError) as exc:
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
        if not header_value.lower().startswith("bearer "):
            header_value = f"Bearer {header_value}"
        return {
            "Authorization": header_value,
            "Accept": "application/json",
        }
