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
        *,
        path: str = "/ws/queue",
    ):
        self._path = path
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
        # Fresh event per run: a previous thread that has not exited yet keeps
        # its own (already set) event and cannot be revived by this start().
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(self._stop,),
            name=f"ws{self._path.replace('/', '-')}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        # Called from the GUI thread (window close / app exit): never block it.
        # ws.close() defaults to waiting up to 3s for the server's close frame,
        # which the reader thread usually swallows first, so close with
        # timeout=0 and only give the daemon thread a brief moment to exit.
        self._stop.set()
        ws = self._ws
        if ws is not None:
            try:
                # Wake the reader blocked in select() first; closing the fd
                # alone leaves it parked until its 10s ping timeout.
                sock = getattr(ws, "sock", None)
                if sock is not None:
                    sock.abort()
                ws.close(timeout=0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)
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

    def _run(self, stop: threading.Event) -> None:
        try:
            import websocket
        except ImportError:
            self._on_status("websocket-client not installed")
            logger.error("websocket-client package is required for Queue Monitor")
            return

        ws = None
        while not stop.is_set():
            api_url = read_config().get("api_url", "https://ashen.api.famkoets.nl")
            ws_url = api_url_to_ws_url(api_url, self._path)
            token = get_token() or ""
            self._on_status(f"Connecting to {ws_url}...")
            try:
                ws = websocket.WebSocketApp(
                    ws_url,
                    header=[f"Authorization: {token}"],
                    on_open=self._on_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws = ws
                if stop.is_set():
                    break
                ws.run_forever(ping_interval=25, ping_timeout=10)
            except Exception as e:
                logger.warning("Queue WS run error: %s", e)
                self._on_status(f"Disconnected: {e}")
            if self._ws is ws:
                self._ws = None
            if stop.wait(5):
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
