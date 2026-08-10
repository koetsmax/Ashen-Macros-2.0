"""Tick / Cross & Warn actions for #leave-channel leave notices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.discord_bridge import (
    DiscordBridgeError,
    get_bridge,
    is_enabled,
    leave_channel_id,
    leave_mark_emoji,
    leave_warning_rule,
    prefer_bridge,
    resolve_channel_id,
)
from core.keyboard import (
    clear_typing_bar,
    execute_slash_command,
    extra_ups_for_date_dividers,
    opt_str,
    opt_user,
    react_to_channel_message,
    switch_channel,
)
from staffcheck.abort import AbortError, check_abort, interruptible_sleep

if TYPE_CHECKING:
    from core.queue_ws import QueueWsClient

logger = logging.getLogger(__name__)


def fetch_leave_channel_notice(
    client: "QueueWsClient | None", message_id: str
) -> dict:
    """Ask the queue hub for #leave-channel notice offset (keyboard react)."""
    empty = {
        "found": False,
        "offset": None,
        "message_id": None,
        "channel_id": None,
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
            {"type": "leave_channel_notice", "message_id": mid},
            timeout=20.0,
        )
        if not isinstance(data, dict):
            return empty
        return {
            "found": bool(data.get("found")),
            "offset": data.get("offset"),
            "message_id": data.get("message_id") or mid,
            "channel_id": data.get("channel_id") or data.get("channelId"),
            "created_at": data.get("created_at"),
            "reason": str(data.get("reason") or ""),
        }
    except Exception:
        logger.exception("fetch_leave_channel_notice failed for %s", mid)
        return empty


def react_leave_notice_mark(
    self,
    *,
    message_id: str,
    mark: str,
    client: "QueueWsClient | None" = None,
) -> None:
    """Switch to #leave-channel and react tick/cross (bridge or keyboard)."""
    mid = str(message_id or "").strip()
    if not mid:
        raise RuntimeError("Missing leave message id")

    emoji = leave_mark_emoji(mark)
    emoji_name = str(emoji.get("name") or mark).strip() or mark

    # Prefer bridge when available.
    if is_enabled() and prefer_bridge():
        channel_id = leave_channel_id() or resolve_channel_id("#leave-channel") or ""
        if not channel_id:
            raise DiscordBridgeError("No leave-channel id from bridge config")
        switch_channel(self, "#leave-channel")
        check_abort(self)
        get_bridge().react(channel_id, mid, emoji, abort_ctx=self)
        return

    # Keyboard failover: resolve offset via queue hub, then react by name.
    info = fetch_leave_channel_notice(client, mid)
    if not info.get("found") or not info.get("offset"):
        reason = info.get("reason") or "not_found"
        raise RuntimeError(
            f"Cannot locate leave notice for keyboard react ({reason})"
        )
    switch_channel(self, "#leave-channel")
    check_abort(self)
    react_to_channel_message(
        self,
        int(info["offset"]),
        emoji_name,
        extra_ups=extra_ups_for_date_dividers(info.get("created_at")),
    )


def warn_leave_rule_and_report(
    self,
    *,
    user_id: str,
    rule_number: int = 3,
) -> None:
    """In #on-duty-commands: /warn with scraped rule text, then /user_report."""
    uid = str(user_id or "").strip()
    if not uid:
        raise RuntimeError("Missing member id for leave warning")
    reason = leave_warning_rule(rule_number)
    if not reason:
        raise RuntimeError(f"Leave warning Rule #{rule_number} unavailable")

    channel_id = resolve_channel_id("#on-duty-commands") or ""
    if is_enabled() and prefer_bridge() and not channel_id:
        raise DiscordBridgeError("No on-duty-commands id from bridge config")

    switch_channel(self, "#on-duty-commands")
    check_abort(self)
    clear_typing_bar()
    check_abort(self)
    execute_slash_command(
        self,
        "warn",
        [opt_user("member", uid), opt_str("reason", reason)],
        channel_id=channel_id or None,
    )
    check_abort(self)
    # Full gap even with bridge — Discord still needs settle between slash posts.
    interruptible_sleep(self, 1.5, bridge_fast=False)
    check_abort(self)
    clear_typing_bar()
    check_abort(self)
    execute_slash_command(
        self,
        "user_report",
        [opt_user("member", uid)],
        channel_id=channel_id or None,
    )


def tick_leave_notice(
    self,
    *,
    message_id: str,
    client: "QueueWsClient | None" = None,
) -> None:
    react_leave_notice_mark(
        self, message_id=message_id, mark="tick", client=client
    )


def cross_and_warn_leave_notice(
    self,
    *,
    message_id: str,
    user_id: str,
    client: "QueueWsClient | None" = None,
) -> None:
    react_leave_notice_mark(
        self, message_id=message_id, mark="cross", client=client
    )
    check_abort(self)
    warn_leave_rule_and_report(self, user_id=user_id, rule_number=3)
