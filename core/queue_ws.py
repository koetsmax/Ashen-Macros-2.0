"""WebSocket client for the bot queue hub."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Callable
from urllib.parse import urlparse, urlunparse

from core.auth import get_token
from core.settings import read_config

logger = logging.getLogger(__name__)


def api_url_to_ws_url(api_url: str, path: str = "/ws/queue") -> str:
    parsed = urlparse(api_url.strip())
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path
    return urlunparse((scheme, netloc, path, "", "", ""))


class QueueWsClient:
    """Background WebSocket client; callbacks are invoked from the network thread."""

    def __init__(
        self,
        on_message: Callable[[dict], None],
        on_status: Callable[[str], None] | None = None,
    ):
        self._on_message = on_message
        self._on_status = on_status or (lambda _s: None)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws = None
        self._pending_lock = threading.Lock()
        self._pending: dict[str, dict] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="queue-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        with self._pending_lock:
            for entry in self._pending.values():
                entry["event"].set()
            self._pending.clear()

    def send(self, payload: dict) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            ws.send(json.dumps(payload))
        except Exception:
            logger.exception("Failed to send queue WS message")

    def request(self, payload: dict, *, timeout: float = 20.0) -> dict | None:
        """Send a message with request_id and wait for a matching response."""
        request_id = str(uuid.uuid4())
        event = threading.Event()
        with self._pending_lock:
            self._pending[request_id] = {"event": event, "response": None}
        try:
            self.send({**payload, "request_id": request_id})
            if not event.wait(timeout):
                logger.warning(
                    "Queue WS request timed out (%s)", payload.get("type")
                )
                return None
            with self._pending_lock:
                entry = self._pending.get(request_id) or {}
                return entry.get("response")
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)

    def request_refresh(self) -> None:
        self.send({"type": "refresh"})

    def _fulfill_pending(self, data: dict) -> bool:
        request_id = data.get("request_id")
        if not request_id:
            return False
        with self._pending_lock:
            entry = self._pending.get(str(request_id))
            if entry is None:
                return False
            entry["response"] = data
            entry["event"].set()
            return True

    def _run(self) -> None:
        try:
            import websocket
        except ImportError:
            self._on_status("websocket-client not installed")
            logger.error("websocket-client package is required for Queue Monitor")
            return

        while not self._stop.is_set():
            api_url = read_config().get("api_url", "https://ashen.api.famkoets.nl")
            ws_url = api_url_to_ws_url(api_url)
            token = get_token() or ""
            self._on_status(f"Connecting to {ws_url}...")
            try:
                self._ws = websocket.WebSocketApp(
                    ws_url,
                    header=[f"Authorization: {token}"],
                    on_open=self._on_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=25, ping_timeout=10)
            except Exception as e:
                logger.warning("Queue WS run error: %s", e)
                self._on_status(f"Disconnected: {e}")
            self._ws = None
            if self._stop.wait(5):
                break

    def _on_open(self, _ws) -> None:
        self._on_status("Connected")
        logger.info("Queue WS connected")

    def _on_ws_message(self, _ws, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Invalid queue WS JSON")
            return
        if not isinstance(data, dict):
            return
        # Request/response pairs are consumed by waiting worker threads.
        if self._fulfill_pending(data):
            return
        self._on_message(data)

    def _on_error(self, _ws, error) -> None:
        logger.warning("Queue WS error: %s", error)
        self._on_status(f"Error: {error}")

    def _on_close(self, _ws, status_code, msg) -> None:
        logger.info("Queue WS closed: %s %s", status_code, msg)
        if not self._stop.is_set():
            self._on_status("Disconnected; reconnecting...")
