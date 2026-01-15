"""HTTP-сервер для проверки состояния."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Type

from shared.constants import HEALTH_PATH


class HealthServer:
    """Легкий HTTP-сервер для проверки состояния."""

    def __init__(self, host: str, port: int, status_provider: Callable[[], Dict[str, object]]) -> None:
        self._host = host
        self._port = port
        self._status_provider = status_provider
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Запустить сервер проверки состояния в фоновом потоке."""

        handler = self._make_handler(self._status_provider)
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Остановить сервер проверки состояния."""

        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    @staticmethod
    def _make_handler(
        status_provider: Callable[[], Dict[str, object]]
    ) -> Type[BaseHTTPRequestHandler]:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - требуется BaseHTTPRequestHandler
                if self.path != HEALTH_PATH:
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = status_provider()
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - stdlib
                return

        return Handler
