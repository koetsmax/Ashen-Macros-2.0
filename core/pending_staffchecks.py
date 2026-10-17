"""Pending staffchecks: alerts the bot read from #bot-notices, with prefetched data.

The self-bot watches #bot-notices for "has entered the queue but is not Staff
Checked..." alerts, prefetches the check data (essential_data with the prefetch
flag) and pushes the list over ``/ws/staffcheck``. Alerts that already have any
reaction are left out by the bot, and so are members it released from its cache
(left the queue, older than 10 minutes, or marked good to check).

Protocol (JSON over ``/ws/staffcheck``):

* bot -> app ``{"type": "pending_staffchecks", "checks": [check, ...]}`` on
  connect and whenever the list changes. ``check`` is
  ``{"user_id", "username", "xbox": [str] | None, "message_id", "channel_id",
  "alerted_at", "prefetch": dict | None}``. ``prefetch`` has the same shape as
  the ``/staffcheck/essential_data`` response, or None while it is loading.
* app -> bot ``{"type": "claim_staffcheck", "user_id", "message_id",
  "bot_react": bool, "request_id"}`` -> ``{"ok": bool, "reason":
  "claimed" | "already_reacted" | "not_found"}``. The bot drops the check for
  every client; with ``bot_react`` it also adds the pending reaction itself
  (used when the Vencord plugin is off).
* app -> bot ``{"type": "staffcheck_log", "user_id", "text"}`` -> the bot posts
  ``text`` to #macro-logs.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from core.queue_ws import QueueWsClient

logger = logging.getLogger(__name__)

WS_PATH = "/ws/staffcheck"

# essential_data keys that do not depend on who runs the check.
_COMPARE_KEYS: tuple[tuple[str, str], ...] = (
    ("linked_xbox", "Linked Xbox"),
    ("mutual_guilds", "Mutual servers"),
    ("discord_name", "Discord name"),
    ("last_check_status", "Last check result"),
    ("last_check_at", "Last check time"),
)


def _as_list(value) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def diff_prefetch(prefetch: dict, fresh: dict) -> list[str]:
    """Human-readable lines for every compared field that changed."""
    lines: list[str] = []
    for key, label in _COMPARE_KEYS:
        if key not in prefetch and key not in fresh:
            continue
        old, new = prefetch.get(key), fresh.get(key)
        if key in ("linked_xbox", "mutual_guilds"):
            old_set, new_set = set(_as_list(old)), set(_as_list(new))
            if old_set == new_set:
                continue
            added = sorted(new_set - old_set)
            removed = sorted(old_set - new_set)
            parts = []
            if added:
                parts.append("added " + ", ".join(added))
            if removed:
                parts.append("removed " + ", ".join(removed))
            lines.append(f"{label}: {'; '.join(parts)}")
        elif (old or None) != (new or None):
            lines.append(f"{label}: {old or 'none'} -> {new or 'none'}")
    return lines


def changed_kinds(lines: list[str]) -> list[str]:
    """Short names for the toast, e.g. ['Linked Xbox', 'Mutual servers']."""
    return [line.split(":", 1)[0] for line in lines]


class PendingStaffchecks:
    """Keeps the bot's pending-check list; callbacks run on the network thread."""

    def __init__(self, on_change: Callable[[list[dict]], None]):
        self._on_change = on_change
        self._lock = threading.Lock()
        self._checks: list[dict] = []
        self._client = QueueWsClient(self._on_message, self._on_status, path=WS_PATH)
        self._connected = False

    def start(self) -> None:
        self._client.start()

    def stop(self) -> None:
        self._client.stop()
        self._connected = False
        self._set_checks([])

    @property
    def connected(self) -> bool:
        return self._connected

    def checks(self) -> list[dict]:
        with self._lock:
            return [dict(c) for c in self._checks]

    def get(self, user_id: str) -> dict | None:
        uid = str(user_id or "").strip()
        with self._lock:
            for check in self._checks:
                if str(check.get("user_id")) == uid:
                    return dict(check)
        return None

    def drop_local(self, user_id: str) -> None:
        """Hide a check right away; the bot's next push confirms it."""
        uid = str(user_id or "").strip()
        with self._lock:
            checks = [c for c in self._checks if str(c.get("user_id")) != uid]
        self._set_checks(checks)

    def claim(self, user_id: str, message_id: str, *, bot_react: bool) -> dict:
        """Blocking: tell the bot this check was started. Call off the GUI thread."""
        data = self._client.request(
            {
                "type": "claim_staffcheck",
                "user_id": str(user_id),
                "message_id": str(message_id or ""),
                "bot_react": bool(bot_react),
            },
            timeout=15.0,
        )
        if not isinstance(data, dict):
            return {"ok": False, "reason": "no_response"}
        return {"ok": bool(data.get("ok")), "reason": str(data.get("reason") or "")}

    def log(self, user_id: str, text: str) -> None:
        """Ask the bot to post a line in #macro-logs (fire and forget)."""
        logger.info("Staffcheck macro-log for %s: %s", user_id, text)
        self._client.send(
            {"type": "staffcheck_log", "user_id": str(user_id), "text": text}
        )

    def _set_checks(self, checks: list[dict]) -> None:
        with self._lock:
            self._checks = list(checks)
            snapshot = [dict(c) for c in self._checks]
        try:
            self._on_change(snapshot)
        except Exception:
            logger.exception("Pending staffcheck callback failed")

    def _on_message(self, data: dict) -> None:
        if data.get("type") != "pending_staffchecks":
            return
        raw = data.get("checks") or []
        checks = [
            c for c in raw if isinstance(c, dict) and str(c.get("user_id") or "").strip()
        ]
        self._set_checks(checks)

    def _on_status(self, status: str) -> None:
        connected = status == "Connected"
        if self._connected and not connected:
            # Stale entries would be misleading while the bot is unreachable.
            self._set_checks([])
        self._connected = connected
        logger.debug("Pending staffcheck WS: %s", status)
