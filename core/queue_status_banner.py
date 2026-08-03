"""Queue status banner helpers (WS offset + wait for new banner after recall)."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from core.queue_ws import QueueWsClient

logger = logging.getLogger(__name__)

BANNER_RECALL_NAMES = {
    "ships_full": "Ships full",
    "ships_requiring_crew": "Ships requiring crew queue message",
}

BANNER_BUTTON_LABELS = {
    "ships_full": "Ships full",
    "ships_requiring_crew": "Ships requiring crew",
}


def fetch_status_banner_offset(client: "QueueWsClient | None", message_id: str) -> dict:
    empty = {
        "found": False,
        "offset": None,
        "message_id": None,
        "created_at": None,
        "reason": "request_failed",
    }
    mid = str(message_id or "").strip()
    if not mid:
        return {**empty, "reason": "missing_message_id"}
    if client is None:
        return {**empty, "reason": "not_connected"}
    try:
        data = client.request(
            {"type": "queue_status_banner_offset", "message_id": mid},
            timeout=20.0,
        )
        if not isinstance(data, dict):
            return empty
        return {
            "found": bool(data.get("found")),
            "offset": data.get("offset"),
            "message_id": data.get("message_id") or mid,
            "created_at": data.get("created_at"),
            "reason": str(data.get("reason") or ""),
        }
    except Exception:
        logger.exception("fetch_status_banner_offset failed for %s", mid)
        return empty


def wait_for_status_banner(
    get_snapshot: Callable[[], dict | None],
    *,
    expected_type: str,
    previous_message_id: str | None,
    timeout_s: float = 20.0,
    poll_s: float = 0.4,
    abort_check: Callable[[], bool] | None = None,
) -> dict | None:
    """Poll latest snapshot until banner message_id changes to expected_type."""
    deadline = time.monotonic() + max(1.0, timeout_s)
    prev = str(previous_message_id or "")
    while time.monotonic() < deadline:
        if abort_check and abort_check():
            return None
        snap = get_snapshot() or {}
        banner = snap.get("queue_status_banner") or {}
        mid = str(banner.get("message_id") or "")
        typ = str(banner.get("type") or "")
        if mid and typ == expected_type and mid != prev:
            return dict(banner)
        time.sleep(poll_s)
    return None
