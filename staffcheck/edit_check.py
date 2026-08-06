"""Helpers for editing a previous on-duty-chat check message."""

from __future__ import annotations

import requests

from core.keyboard import edit_on_duty_message, extra_ups_for_date_dividers, type_text
from core.settings import config_bool


def edit_check_enabled() -> bool:
    return config_bool("edit_check_message", "true")


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


def empty_edit_check() -> dict:
    return {
        "editable": False,
        "offset": None,
        "content": None,
        "created_at": None,
        "message_id": None,
    }


def store_edit_check_from_essential(self, data: dict | None) -> None:
    """Use pre-check last_check_* fields for Edit vs Post labels (no offset yet)."""
    data = data or {}
    editable = bool(data.get("last_check_editable")) and edit_check_enabled()
    self._edit_check = {
        "editable": editable,
        "offset": None,
        "content": None,
        "created_at": data.get("last_check_at"),
        "message_id": data.get("last_check_message_id"),
    }


def fetch_editable_check(self, user_id: str, *, message_id: str | None = None) -> dict:
    """
    POST /staffcheck/editable_check_message.

    Resolves tab offset (+ content) at click time. Pass message_id from pre-check
    so the API can skip search and only count history tabs.
    """
    empty = empty_edit_check()
    if not edit_check_enabled():
        return empty
    hint = message_id
    if not hint:
        hint = (getattr(self, "_edit_check", None) or {}).get("message_id")
    try:
        config = read_config()
        body = {"userID": str(user_id)}
        if hint:
            body["messageID"] = str(hint)
        response = requests.post(
            f"{config['api_url']}/staffcheck/editable_check_message",
            json=body,
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
            "message_id": data.get("message_id") or hint,
        }
    except Exception:
        return empty


def resolve_edit_at_click(self, user_id: str | None = None) -> dict:
    """
    At button click: only resolve offset if pre-check said the last check is ours.
    Otherwise post a new message (do not hunt for an older own check).
    """
    empty = empty_edit_check()
    if not edit_check_enabled():
        return empty
    pre = getattr(self, "_edit_check", None) or empty
    if not pre.get("editable"):
        return empty
    uid = str(user_id if user_id is not None else self.user_id.get() or "")
    return fetch_editable_check(self, uid, message_id=pre.get("message_id"))


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
