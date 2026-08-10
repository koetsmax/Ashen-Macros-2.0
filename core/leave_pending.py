"""Helpers for reacting :pending: on #queue leave messages before prep/process."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.discord_bridge import (
    DiscordBridgeError,
    get_bridge,
    is_enabled,
    pending_emoji,
    prefer_bridge,
    queue_channel_id,
)
from core.keyboard import extra_ups_for_date_dividers, react_to_channel_message
from staffcheck.abort import AbortError

if TYPE_CHECKING:
    from core.queue_ws import QueueWsClient

logger = logging.getLogger(__name__)


def fetch_leave_message(client: "QueueWsClient | None", message_id: str) -> dict:
    """Ask the queue hub (over the existing WS) for leave offset + reaction state."""
    empty = {
        "found": False,
        "offset": None,
        "message_id": None,
        "channel_id": None,
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
            "channel_id": data.get("channel_id") or data.get("channelId"),
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
    mid = str(data.get("message_id") or message_id or "").strip()
    if data.get("has_pending_reaction") and not data.get("self_reacted"):
        return "skipped"
    if data.get("self_reacted"):
        return "already"

    # Bridge path: message id (+ queue channel) — no offset required.
    if is_enabled():
        if not prefer_bridge():
            raise DiscordBridgeError("Vencord bridge is not connected")
        if not mid or not data.get("found"):
            return "failed"
        channel_id = str(
            data.get("channel_id") or queue_channel_id() or ""
        ).strip()
        if not channel_id:
            raise DiscordBridgeError("No channel id for pending react")
        get_bridge().react(
            channel_id,
            mid,
            pending_emoji(),
            abort_ctx=self,
        )
        return "reacted"

    if not data.get("found") or not data.get("offset"):
        return "failed"
    try:
        react_to_channel_message(
            self,
            int(data["offset"]),
            "pending",
            extra_ups=extra_ups_for_date_dividers(data.get("created_at")),
        )
        return "reacted"
    except AbortError:
        raise
    except Exception:
        logger.exception("react_pending_on_leave failed for %s", message_id)
        return "failed"
