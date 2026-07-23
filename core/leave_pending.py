"""Helpers for reacting :pending: on #queue leave messages before prep/process."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from core.keyboard import react_to_channel_message

if TYPE_CHECKING:
    from core.queue_ws import QueueWsClient

logger = logging.getLogger(__name__)


def extra_ups_for_date_dividers(created_at: str | None) -> int:
    """How many Discord date-divider rows sit between now and the message (local time)."""
    if not created_at:
        return 0
    try:
        when = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.astimezone()
        msg_day = when.astimezone().date()
        now_day = datetime.now().astimezone().date()
        return max(0, (now_day - msg_day).days)
    except Exception:
        return 0


def fetch_leave_message(client: "QueueWsClient | None", message_id: str) -> dict:
    """Ask the queue hub (over the existing WS) for leave offset + reaction state."""
    empty = {
        "found": False,
        "offset": None,
        "message_id": None,
        "created_at": None,
        "has_pending_reaction": False,
        "self_reacted": False,
        "reason": "request_failed",
    }
    mid = str(message_id or "").strip()
    if not mid:
        return {**empty, "reason": "missing_message_id"}
    if client is None:
        return {**empty, "reason": "not_connected"}
    try:
        data = client.request({"type": "leave_message", "message_id": mid}, timeout=20.0)
        if not isinstance(data, dict):
            return empty
        return {
            "found": bool(data.get("found")),
            "offset": data.get("offset"),
            "message_id": data.get("message_id") or mid,
            "created_at": data.get("created_at"),
            "has_pending_reaction": bool(data.get("has_pending_reaction")),
            "self_reacted": bool(data.get("self_reacted")),
            "reason": str(data.get("reason") or ""),
        }
    except Exception:
        logger.exception("fetch_leave_message failed for %s", mid)
        return empty


def react_pending_on_leave(
    self,
    message_id: str,
    *,
    info: dict | None = None,
    client: "QueueWsClient | None" = None,
) -> str:
    """React :pending: to a leave message. Returns status: reacted|skipped|already|failed."""
    data = (
        info
        if info is not None
        else fetch_leave_message(client, message_id)
    )
    if not data.get("found") or not data.get("offset"):
        return "failed"
    if data.get("has_pending_reaction") and not data.get("self_reacted"):
        return "skipped"
    if data.get("self_reacted"):
        return "already"
    try:
        react_to_channel_message(
            self,
            int(data["offset"]),
            "pending",
            extra_ups=extra_ups_for_date_dividers(data.get("created_at")),
        )
        return "reacted"
    except Exception:
        logger.exception("react_pending_on_leave failed for %s", message_id)
        return "failed"
