"""Account verification: DM the bot with the local macros token."""

from __future__ import annotations

import logging
import time

from core.auth import check_login, get_token
from core.discord_bridge import (
    BRIDGE_OFF_MESSAGE,
    BridgeRequiredError,
    DiscordBridgeError,
    get_bridge,
    is_connected,
    is_enabled,
)
from core.platform import keyboard_automation_supported

logger = logging.getLogger(__name__)

VERIFY_BOT_USERNAME = "derry_fastulfr"

# Wait for the bot to bind the token before refreshing hub auth.
_POST_SEND_POLL_ATTEMPTS = 8
_POST_SEND_POLL_INTERVAL_S = 0.75


def verification_ready() -> tuple[bool, str]:
    """Whether Verify can run now, and why not (tooltip / toast text).

    Through the plugin (always on Linux, or with the toggle on), verification
    waits until the plugin is on and connected. The bot's channel config needs
    a verified token, so the socket is all that is required here.
    """
    if not is_enabled() and keyboard_automation_supported():
        return True, ""
    if not is_enabled():
        return False, "Turn on the Vencord plugin in Settings before verifying."
    if not is_connected():
        return False, (
            "Connect the Vencord plugin before verifying (Discord running with "
            "AshenMacrosBridge enabled; port and token must match Settings)."
        )
    return True, ""


def _send_via_keyboard(ctx, text: str) -> None:
    import keyboard

    from core.keyboard import clear_typing_bar, switch_channel

    switch_channel(ctx, VERIFY_BOT_USERNAME, kwargs=True)
    clear_typing_bar()
    keyboard.write(text)
    time.sleep(3)
    keyboard.press_and_release("enter")


def _send_via_bridge(text: str) -> None:
    # The bot's channel config needs a verified token, so only the plugin
    # socket is required here (not prefer_bridge()).
    if not is_enabled():
        from staffcheck.qt_ui import warn_bridge_required

        warn_bridge_required(f"Can't verify your account.\n\n{BRIDGE_OFF_MESSAGE}")
        raise BridgeRequiredError(BRIDGE_OFF_MESSAGE)
    get_bridge().send_dm(text, username=VERIFY_BOT_USERNAME)


def start_verification(ctx, on_refresh=None):
    """DM !verifymeprettyplease to the bot, then refresh hub auth (always)."""
    try:
        time.sleep(3)
        token = get_token()
        if not token or len(token) != 128:
            logger.error("Verification aborted: missing or invalid local token")
            return

        text = f"!verifymeprettyplease {token}"
        if is_enabled() or not keyboard_automation_supported():
            try:
                _send_via_bridge(text)
            except BridgeRequiredError:
                raise  # already showed its own dialog
            except DiscordBridgeError as exc:
                from staffcheck.qt_ui import warn_bridge_required

                warn_bridge_required(
                    f"Could not DM {VERIFY_BOT_USERNAME} through the Vencord plugin:\n{exc}\n\n"
                    "Update the plugin (Settings → Update plugin & Vencord), fully "
                    "restart Discord, then press Verify again.",
                    title="Verification failed",
                )
                raise
        else:
            _send_via_keyboard(ctx, text)

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
