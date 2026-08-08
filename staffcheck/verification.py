"""Account verification: DM the bot with the local macros token."""

from __future__ import annotations

import logging
import time

import keyboard

from core.auth import check_login, get_token
from core.keyboard import clear_typing_bar, switch_channel

logger = logging.getLogger(__name__)

# Wait for the bot to bind the token before refreshing hub auth.
_POST_SEND_POLL_ATTEMPTS = 8
_POST_SEND_POLL_INTERVAL_S = 0.75


def start_verification(ctx, on_refresh=None):
    """Type !verifymeprettyplease in DMs, then refresh hub auth (always)."""
    try:
        time.sleep(3)
        token = get_token()
        if not token or len(token) != 128:
            logger.error("Verification aborted: missing or invalid local token")
            return

        switch_channel(ctx, "derry_fastulfr", kwargs=True)
        clear_typing_bar()
        keyboard.write(f"!verifymeprettyplease {token}")
        time.sleep(3)
        keyboard.press_and_release("enter")

        # Bot may take a moment to commit; poll until validate_token succeeds.
        for attempt in range(1, _POST_SEND_POLL_ATTEMPTS + 1):
            time.sleep(_POST_SEND_POLL_INTERVAL_S)
            verified, _, _ = check_login()
            if verified:
                logger.info(
                    "Verification succeeded after poll attempt %s", attempt
                )
                return
        logger.warning(
            "Verification finished but token still not valid after %s polls",
            _POST_SEND_POLL_ATTEMPTS,
        )
    except Exception:
        logger.exception("Verification automation failed")
    finally:
        if on_refresh:
            on_refresh()
