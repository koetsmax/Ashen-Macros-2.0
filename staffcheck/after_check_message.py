import logging
import time

import requests

from core.discord_bridge import on_duty_channel_id, resolve_channel_id
from core.keyboard import (
    clear_typing_bar,
    execute_slash_command,
    opt_bool,
    opt_str,
    opt_sub,
    opt_user,
    switch_channel,
)
from core.settings import read_config
from staffcheck import abort, pipeline
from staffcheck.qt_ui import btn_config, btn_enable, label_set, on_main_thread, report_bridge_error
from staffcheck.tasks import run_background

logger = logging.getLogger(__name__)


def after_check_message(self):
    self.reason_entry.setEnabled(False)
    btn_config(
        self.function_button,
        "Neither of these apply",
        lambda: pipeline.continue_to_next(self),
    )
    btn_enable(self.function_button, True)
    btn_config(self.kill_button, "Unprivate Xbox (modmail)", lambda: unprivate_xbox(self))
    btn_config(self.start_button, "Join AWR", lambda: join_awr(self))
    btn_config(self.function_button_2, "Verify account", lambda: verify_account(self))
    btn_enable(self.kill_button, True)
    btn_enable(self.start_button, True)
    btn_enable(self.function_button_2, True)


def _set_after_check_buttons_enabled(self, enabled: bool) -> None:
    btn_enable(self.kill_button, enabled)
    btn_enable(self.start_button, enabled)
    btn_enable(self.function_button, enabled)
    btn_enable(self.function_button_2, enabled)


def unprivate_xbox(self):
    """Wait for modmail, run /create, then recall Unprivate Xbox."""
    from core.discord_bridge import DiscordBridgeError

    _set_after_check_buttons_enabled(self, False)
    label_set(self.status_label, "Opening modmail…", "orange")
    # Register the bot waiter before /create so the channel-create event is not missed.
    run_background(unprivate_api_request, self)
    try:
        from core.discord_bridge import prefer_bridge

        # Tiny pause so the API waiter thread starts before /create hits Discord.
        if not prefer_bridge():
            abort.interruptible_sleep(self, 0.4)
        switch_channel(self, "#on-duty-chat")
        clear_typing_bar()
        execute_slash_command(
            self,
            "create",
            [opt_str("user", self.user_id.get(), autocomplete=True)],
            channel_id=on_duty_channel_id(),
        )
    except abort.AbortError:
        _set_after_check_buttons_enabled(self, True)
        return
    except DiscordBridgeError as exc:
        report_bridge_error(self, exc)
        _set_after_check_buttons_enabled(self, True)
        return


def unprivate_api_request(self):
    """Ask the bot for modmail channel id/name, then recall via macro/bridge."""
    from core.discord_bridge import DiscordBridgeError

    if abort.is_abort_requested(self):
        on_main_thread(lambda: _set_after_check_buttons_enabled(self, True))
        return

    request_error = False
    try:
        payload = {"userID": self.user_id.get()}
        config = read_config()
        response = requests.post(
            f"{config['api_url']}/staffcheck/unprivate",
            json=payload,
            timeout=180,
            headers=self.headers,
        )
        while not response.json():
            time.sleep(0.1)
        if abort.is_abort_requested(self):
            on_main_thread(lambda: _set_after_check_buttons_enabled(self, True))
            return
        if response.status_code != 200:
            request_error = True
        elif response.json().get("error") != "none":
            request_error = True
            err = response.json().get("error") or "Failed to get modmail channel"
            label_set(self.status_label, err, "red")
        else:
            r = response.json()
            channel_name = str(r.get("modmail_channel") or "").strip()
            # Prefer id from the bot — dynamic *-modmail is not in bridge meta.
            channel_id = str(r.get("modmail_channel_id") or "").strip() or (
                resolve_channel_id(f"#{channel_name}") if channel_name else None
            )
            try:
                switch_channel(
                    self,
                    channel_id or f"#{channel_name}",
                )
                clear_typing_bar()
                execute_slash_command(
                    self,
                    "message-store",
                    [
                        opt_sub(
                            "recall",
                            [
                                opt_str("name", "Unprivate Xbox", autocomplete=True),
                                opt_bool("copyable", True),
                            ],
                        )
                    ],
                    channel_id=channel_id or None,
                )
            except abort.AbortError:
                on_main_thread(lambda: _set_after_check_buttons_enabled(self, True))
                return
            except DiscordBridgeError as exc:
                report_bridge_error(self, exc)
                on_main_thread(lambda: _set_after_check_buttons_enabled(self, True))
                return

            on_main_thread(lambda: pipeline.continue_to_next(self))
            return

    except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
        request_error = True
    if request_error:
        if abort.is_abort_requested(self):
            on_main_thread(lambda: _set_after_check_buttons_enabled(self, True))
            return

        def _fail():
            label_set(self.status_label, "Failed to get modmail channel", "red")
            _set_after_check_buttons_enabled(self, True)
            pipeline.continue_to_next(self)

        on_main_thread(_fail)
        return

    on_main_thread(lambda: _set_after_check_buttons_enabled(self, True))


def join_awr(self):
    from core.discord_bridge import DiscordBridgeError

    try:
        clear_typing_bar()
        switch_channel(self, "#on-duty-chat")
        execute_slash_command(
            self,
            "joinawr",
            [opt_user("member", self.user_id.get())],
            channel_id=on_duty_channel_id(),
        )
    except abort.AbortError:
        return
    except DiscordBridgeError as exc:
        report_bridge_error(self, exc)
        return
    pipeline.continue_to_next(self)


def verify_account(self):
    from core.discord_bridge import DiscordBridgeError

    try:
        clear_typing_bar()
        switch_channel(self, "#on-duty-chat")
        execute_slash_command(
            self,
            "verify",
            [
                opt_user("member", self.user_id.get()),
                opt_str("verify_type", "verify"),
            ],
            channel_id=on_duty_channel_id(),
        )
    except abort.AbortError:
        return
    except DiscordBridgeError as exc:
        report_bridge_error(self, exc)
        return
    pipeline.continue_to_next(self)
