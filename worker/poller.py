"""Логика опроса WhatsApp API."""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Event
from typing import Any, Dict, Iterable, List, Optional

import psycopg2

from shared.constants import DATETIME_FORMAT, WAPPI_SKIPPED_CHAT_IDS
from shared.db import Database
from shared.models import MessageRecord
from shared.repositories.messages import get_latest_message_timestamp, insert_messages
from worker.buffer import MessageBuffer
from worker.wappi_client import WappiClient


class Poller:
    """Координирует опрос и сохранение сообщений WhatsApp."""

    def __init__(
        self,
        wappi_client: WappiClient,
        db: Database,
        poll_interval: int,
        buffer: MessageBuffer,
        full_sync_on_start: bool = False,
    ) -> None:
        self._wappi = wappi_client
        self._db = db
        self._poll_interval = poll_interval
        self._buffer = buffer
        self._logger = logging.getLogger(self.__class__.__name__)
        self._last_poll_started_at: Optional[datetime] = None
        self._last_poll_success_at: Optional[datetime] = None
        self._last_message_ts: Optional[int] = None
        self._force_full_sync = full_sync_on_start

    def run(self, stop_event: Event) -> None:
        """Запустить цикл опроса до установки stop_event."""

        while not stop_event.is_set():
            self._last_poll_started_at = datetime.utcnow()
            cycle_started = self._last_poll_started_at
            self._logger.info(
                "Цикл опроса стартовал в %s",
                cycle_started.strftime(DATETIME_FORMAT),
            )
            success = self._poll_once()
            if success:
                self._last_poll_success_at = datetime.utcnow()
            self._logger.info(
                "Цикл опроса завершен статус=%s буфер=%s",
                "успех" if success else "ошибка",
                self._buffer.size(),
            )
            stop_event.wait(self._poll_interval)

    def health_status(self) -> Dict[str, object]:
        """Вернуть данные состояния worker."""

        return {
            "статус": "ок",
            "последний_старт_опроса": self._format_dt(self._last_poll_started_at),
            "последний_успешный_опрос": self._format_dt(self._last_poll_success_at),
            "размер_буфера": self._buffer.size(),
        }

    def _poll_once(self) -> bool:
        success = True
        if not self._flush_buffer():
            success = False

        if self._force_full_sync:
            self._last_message_ts = None
            self._logger.info("Полная синхронизация включена, игнорируем последний timestamp")
        elif self._last_message_ts is None:
            try:
                self._last_message_ts = get_latest_message_timestamp(self._db)
            except psycopg2.Error as exc:
                self._logger.warning("Не удалось загрузить время последнего сообщения: %s", exc)

        try:
            chats = self._wappi.list_chats()
        except Exception as exc:  # noqa: BLE001 - широкая ошибка, чтобы цикл не падал
            self._logger.error("Не удалось получить список чатов: %s", exc)
            return False

        for chat in chats:
            chat_id = chat.get("id")
            if not chat_id:
                continue
            chat_id = str(chat_id)
            if chat_id in WAPPI_SKIPPED_CHAT_IDS:
                continue
            try:
                chat_name = self._extract_chat_name(chat)
                participants_map = self._extract_group_participants(chat)
                time_from = self._calculate_time_from()
                messages = self._wappi.list_messages(chat_id, time_from=time_from)
                self._process_messages(chat_id, chat_name, participants_map, messages)
            except Exception as exc:  # noqa: BLE001 - продолжаем опрос других чатов
                self._logger.error("Не удалось обработать чат %s: %s", chat_id, exc)
                success = False
        if self._force_full_sync:
            self._force_full_sync = False
        return success

    def _process_messages(
        self,
        chat_id: str,
        chat_name: Optional[str],
        participants_map: Dict[str, str],
        messages: Iterable[Dict[str, Any]],
    ) -> None:
        batch: List[MessageRecord] = []
        inserted_total = 0

        for payload in messages:
            record = self._build_message_record(payload, chat_id, chat_name, participants_map)
            if record is None:
                continue
            batch.append(record)
            if len(batch) >= 200:
                inserted_total += self._store_messages(batch)
                batch = []

        if batch:
            inserted_total += self._store_messages(batch)

        if inserted_total:
            self._logger.info("Сохранено %s сообщений для чата %s", inserted_total, chat_id)

    def _store_messages(self, messages: List[MessageRecord]) -> int:
        try:
            inserted = insert_messages(self._db, messages)
            return inserted
        except psycopg2.Error as exc:
            dropped = self._buffer.add(messages)
            if dropped:
                self._logger.warning("Буфер переполнен, отброшено %s сообщений", dropped)
            self._logger.error("Ошибка БД, буферизация %s сообщений: %s", len(messages), exc)
            return 0

    def _flush_buffer(self) -> bool:
        if self._buffer.is_empty():
            return True
        buffered = self._buffer.items()
        try:
            inserted = insert_messages(self._db, buffered)
            self._buffer.drain()
            self._logger.info("Сброшено в БД %s сообщений из буфера", inserted)
            return True
        except psycopg2.Error as exc:
            self._logger.warning("Не удалось сбросить буфер: %s", exc)
            return False

    def _calculate_time_from(self) -> Optional[int]:
        if self._force_full_sync:
            return None
        if self._last_message_ts is None:
            return None
        return max(self._last_message_ts - 1, 0)

    def _build_message_record(
        self,
        payload: Dict[str, Any],
        fallback_chat_id: str,
        chat_name: Optional[str],
        participants_map: Dict[str, str],
    ) -> Optional[MessageRecord]:
        message_id = payload.get("id")
        chat_id = payload.get("chat_id") or payload.get("chatId") or fallback_chat_id
        sender = (
            payload.get("senderName")
            or payload.get("from_name")
            or payload.get("from")
            or payload.get("author")
        )
        timestamp = payload.get("time")
        if timestamp is None:
            timestamp = payload.get("timestamp")

        if not message_id or not chat_id or timestamp is None:
            self._logger.warning("Пропуск сообщения с отсутствующими полями: %s", payload)
            return None

        sender = self._normalize_sender(sender, participants_map)
        if sender is None:
            sender = "неизвестно"

        text = self._extract_text(payload)
        message_time = datetime.utcfromtimestamp(int(timestamp))
        self._last_message_ts = max(self._last_message_ts or 0, int(timestamp))
        chat_id_value = str(chat_id)

        metadata = self._build_metadata(
            payload=payload,
            message_id=str(message_id),
            chat_id=chat_id_value,
            chat_name=chat_name,
            sender=str(sender),
            timestamp=int(timestamp),
        )

        return MessageRecord(
            message_id=str(message_id),
            chat_id=chat_id_value,
            sender=str(sender),
            text=text,
            timestamp=message_time,
            metadata=metadata,
        )

    def _extract_text(self, payload: Dict[str, Any]) -> Optional[str]:
        for path in (
            ("body",),
            ("text", "body"),
            ("image", "caption"),
            ("video", "caption"),
            ("document", "caption"),
            ("gif", "caption"),
            ("short", "caption"),
            ("link_preview", "body"),
            ("interactive", "body", "text"),
            ("interactive", "header", "text"),
            ("buttons", "text"),
            ("list", "body"),
            ("system", "body"),
            ("hsm", "body"),
            ("poll", "title"),
            ("order", "title"),
            ("order", "text"),
            ("group_invite", "body"),
            ("newsletter_invite", "body"),
            ("admin_invite", "body"),
            ("catalog", "title"),
            ("catalog", "description"),
            ("location", "address"),
            ("location", "name"),
            ("action", "comment"),
        ):
            value = self._get_nested(payload, path)
            if value:
                return value
        return None

    @staticmethod
    def _get_nested(payload: Dict[str, Any], path: Iterable[str]) -> Optional[str]:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        if isinstance(current, str) and current.strip():
            return current.strip()
        return None

    @staticmethod
    def _normalize_sender(
        sender: Optional[object],
        participants_map: Dict[str, str],
    ) -> Optional[str]:
        if sender is None:
            return None
        if not isinstance(sender, str):
            sender = str(sender)
        sender = sender.strip()
        if not sender:
            return None
        if sender.endswith("@c.us") or sender.endswith("@s.whatsapp.net"):
            sender = sender.split("@", 1)[0].strip()
            return sender or None
        if sender.endswith("@lid"):
            phone = participants_map.get(sender)
            if phone:
                return phone
            return None
        return sender

    def _build_metadata(
        self,
        payload: Dict[str, Any],
        message_id: str,
        chat_id: str,
        chat_name: Optional[str],
        sender: str,
        timestamp: int,
    ) -> Dict[str, Any]:
        raw_payload = dict(payload) if isinstance(payload, dict) else {"payload": payload}
        chat_name_value = None
        if isinstance(raw_payload, dict):
            existing = raw_payload.get("chat_name") or raw_payload.get("chatName")
            if isinstance(existing, str) and existing.strip():
                chat_name_value = existing.strip()
        if chat_name and self._should_override_chat_name(chat_name_value, chat_id):
            chat_name_value = chat_name

        metadata: Dict[str, Any] = {
            "provider": "wappi",
            "message_id": message_id,
            "chat_id": chat_id,
            "sender": sender,
            "timestamp": timestamp,
            "raw": raw_payload,
        }
        if chat_name_value:
            metadata["chat_name"] = chat_name_value
        message_type = raw_payload.get("type") if isinstance(raw_payload, dict) else None
        if isinstance(message_type, str) and message_type.strip():
            metadata["type"] = message_type.strip()
        if chat_id.endswith("@g.us"):
            metadata["is_group"] = True
        return metadata

    @staticmethod
    def _should_override_chat_name(
        existing: Optional[object], chat_id: str
    ) -> bool:
        if existing is None:
            return True
        if not isinstance(existing, str):
            return True
        existing = existing.strip()
        if not existing:
            return True
        if existing == chat_id:
            return True
        return existing.endswith("@g.us") or existing.endswith("@c.us")

    @staticmethod
    def _extract_chat_name(chat: Dict[str, Any]) -> Optional[str]:
        name = chat.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        group = chat.get("group")
        if isinstance(group, dict):
            for key in ("Name", "name", "Subject", "subject"):
                value = group.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        contact = chat.get("contact")
        if isinstance(contact, dict):
            for key in ("FullName", "PushName", "FirstName", "BusinessName"):
                value = contact.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _extract_group_participants(chat: Dict[str, Any]) -> Dict[str, str]:
        group = chat.get("group")
        if not isinstance(group, dict):
            return {}
        participants = group.get("Participants")
        if not isinstance(participants, list):
            return {}
        mapping: Dict[str, str] = {}
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            lid = (
                participant.get("JID")
                or participant.get("jid")
                or participant.get("LID")
                or participant.get("lid")
                or participant.get("id")
            )
            phone = (
                participant.get("PhoneNumber")
                or participant.get("phoneNumber")
                or participant.get("phone_number")
            )
            if not lid or not phone:
                continue
            lid_value = str(lid).strip()
            phone_value = str(phone).strip()
            if lid_value and phone_value:
                mapping[lid_value] = phone_value
        return mapping

    @staticmethod
    def _format_dt(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime(DATETIME_FORMAT)
