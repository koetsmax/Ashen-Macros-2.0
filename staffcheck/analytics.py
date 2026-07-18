"""Staffcheck analytics helpers (check_id + outcome reporting)."""

from __future__ import annotations

import logging
import threading

import requests

from core.settings import read_config

logger = logging.getLogger(__name__)


def attach_check_id(self, payload: dict) -> dict:
    """Copy payload and add check_id when the session has one."""
    out = dict(payload)
    check_id = getattr(self, "check_id", None)
    if check_id:
        out["check_id"] = check_id
    return out


def store_check_id_from_response(self, data: dict | None) -> None:
    if not isinstance(data, dict):
        return
    cid = data.get("check_id")
    if cid:
        self.check_id = str(cid)


def report_outcome(
    self,
    *,
    outcome: str,
    reason: str | None = None,
) -> None:
    """Fire-and-forget POST /staffcheck/complete."""
    check_id = getattr(self, "check_id", None)
    if not check_id:
        return

    payload = {
        "check_id": check_id,
        "outcome": outcome,
        "reason": reason,
        "userID": self.user_id.get() if hasattr(self, "user_id") else None,
        "xboxGT": str(self.xbox_gt) if getattr(self, "xbox_gt", None) not in (None, [], "") else "",
    }
    headers = getattr(self, "headers", None) or {}

    def _post():
        try:
            config = read_config()
            requests.post(
                f"{config['api_url']}/staffcheck/complete",
                json=payload,
                timeout=15,
                headers=headers,
            )
        except Exception:
            logger.exception("Failed to report staffcheck outcome %s", outcome)

    threading.Thread(target=_post, daemon=True).start()
