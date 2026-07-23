"""Helpers for editing a previous on-duty-chat check message."""

from __future__ import annotations

from datetime import datetime

import requests

from core.keyboard import edit_on_duty_message, type_text
from core.settings import read_config


def edit_check_enabled() -> bool:
    return read_config().get("edit_check_message", "true").lower() in ("1", "true", "yes")


def smart_strike_previous(prev: str) -> str:
    lines = []
    for line in (prev or "").splitlines():
        s = line.strip()
        if s.startswith("~~") and s.endswith("~~") and len(s) >= 4:
            lines.append(line)
        elif s:
            lines.append(f"~~{line}~~")
        else:
            lines.append(line)
    return "\n".join(lines)


def build_edited_content(previous: str, new_line: str) -> str:
    struck = smart_strike_previous(previous)
    new_line = (new_line or "").strip("\n")
    if struck:
        return f"{struck}\n{new_line}"
    return new_line


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


def fetch_editable_check(self, user_id: str) -> dict:
    """POST /staffcheck/editable_check_message. Returns editable/offset/content/created_at."""
    empty = {
        "editable": False,
        "offset": None,
        "content": None,
        "created_at": None,
    }
    if not edit_check_enabled():
        return empty
    try:
        config = read_config()
        response = requests.post(
            f"{config['api_url']}/staffcheck/editable_check_message",
            json={"userID": str(user_id)},
            timeout=20,
            headers=getattr(self, "headers", None) or {},
        )
        if response.status_code != 200:
            return empty
        data = response.json()
        if not isinstance(data, dict):
            return empty
        return {
            "editable": bool(data.get("editable")),
            "offset": data.get("offset"),
            "content": data.get("content"),
            "created_at": data.get("created_at"),
        }
    except Exception:
        return empty


def post_or_edit_check_message(self, new_line: str, editable_info: dict | None = None) -> None:
    """Post a new check message, or edit the previous one when eligible."""
    info = editable_info if editable_info is not None else fetch_editable_check(
        self, self.user_id.get()
    )
    if (
        info.get("editable")
        and info.get("offset")
        and info.get("content") is not None
    ):
        body = build_edited_content(str(info.get("content") or ""), new_line)
        edit_on_duty_message(
            self,
            int(info["offset"]),
            body,
            extra_ups=extra_ups_for_date_dividers(info.get("created_at")),
        )
    else:
        type_text(self, new_line)
