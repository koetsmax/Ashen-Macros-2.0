"""Apps → Bridge tests — manual Vencord Discord bridge harness."""

from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.discord_bridge import (
    DiscordBridgeError,
    get_bridge,
    is_connected,
    is_enabled,
    parse_discord_channel_link,
    pending_emoji,
    prefer_bridge,
)
from gui.views.app_window import AppWindow
from staffcheck.abort import (
    AbortError,
    end_abort_session,
    request_abort,
    start_abort_session,
)
from staffcheck.qt_ui import on_main_thread

logger = logging.getLogger(__name__)


class BridgeTestsWindow(AppWindow):
    """Manual tests for the localhost Vencord Discord bridge."""

    DEFAULT_SIZE = (640, 720)

    _status = Signal(str)

    def __init__(self):
        self.abort_requested = False
        self._busy = False
        self._option_rows: list[tuple[QLineEdit, QSpinBox, QLineEdit, QCheckBox]] = []
        super().__init__("Bridge tests", keyboard_lock=True)
        self._status.connect(self.status_label.setText)

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(10)

        header = QLabel(
            "Requires Settings → Experimental → Vencord Discord bridge. "
            "Escape / Stop aborts in-flight bridge waits."
        )
        header.setWordWrap(True)
        body_layout.addWidget(header)

        link_box = QGroupBox("Parse Discord link")
        link_form = QFormLayout(link_box)
        self.link_entry = QLineEdit()
        self.link_entry.setPlaceholderText(
            "https://discord.com/channels/guild/channel[/message]"
        )
        link_form.addRow("Link:", self.link_entry)
        parse_btn = QPushButton("Parse → fill IDs")
        parse_btn.clicked.connect(self._parse_link)
        link_form.addRow("", parse_btn)
        body_layout.addWidget(link_box)

        # --- Switch channel ---
        switch_box = QGroupBox("Switch channel")
        switch_form = QFormLayout(switch_box)
        self.switch_channel_entry = QLineEdit()
        self.switch_channel_entry.setPlaceholderText("Channel ID")
        switch_form.addRow("Channel ID:", self.switch_channel_entry)
        switch_btn = QPushButton("Run")
        switch_btn.clicked.connect(self._test_switch_channel)
        switch_form.addRow("", switch_btn)
        body_layout.addWidget(switch_box)

        # --- React ---
        react_box = QGroupBox("React")
        react_form = QFormLayout(react_box)
        self.react_guild_entry = QLineEdit()
        self.react_guild_entry.setPlaceholderText("Optional for unicode emoji")
        react_form.addRow("Guild ID:", self.react_guild_entry)
        self.react_channel_entry = QLineEdit()
        react_form.addRow("Channel ID:", self.react_channel_entry)
        self.react_message_entry = QLineEdit()
        react_form.addRow("Message ID:", self.react_message_entry)
        self.react_emoji_name = QLineEdit(pending_emoji().get("name", "pending"))
        react_form.addRow("Emoji name:", self.react_emoji_name)
        self.react_emoji_id = QLineEdit(pending_emoji().get("id", ""))
        self.react_emoji_id.setPlaceholderText("Optional custom emoji id")
        react_form.addRow("Emoji ID:", self.react_emoji_id)
        react_btn = QPushButton("Run")
        react_btn.clicked.connect(self._test_react)
        react_form.addRow("", react_btn)
        body_layout.addWidget(react_box)

        # --- Edit ---
        edit_box = QGroupBox("Edit message")
        edit_form = QFormLayout(edit_box)
        self.edit_channel_entry = QLineEdit()
        edit_form.addRow("Channel ID:", self.edit_channel_entry)
        self.edit_message_entry = QLineEdit()
        edit_form.addRow("Message ID:", self.edit_message_entry)
        self.edit_content_entry = QTextEdit()
        self.edit_content_entry.setPlaceholderText("New message content")
        self.edit_content_entry.setMaximumHeight(80)
        edit_form.addRow("Content:", self.edit_content_entry)
        edit_btn = QPushButton("Run")
        edit_btn.clicked.connect(self._test_edit)
        edit_form.addRow("", edit_btn)
        body_layout.addWidget(edit_box)

        # --- Send ---
        send_box = QGroupBox("Send message")
        send_form = QFormLayout(send_box)
        self.send_channel_entry = QLineEdit()
        send_form.addRow("Channel ID:", self.send_channel_entry)
        self.send_content_entry = QLineEdit()
        send_form.addRow("Content:", self.send_content_entry)
        send_btn = QPushButton("Run")
        send_btn.clicked.connect(self._test_send)
        send_form.addRow("", send_btn)
        body_layout.addWidget(send_box)

        # --- MESSAGE command ---
        msg_cmd_box = QGroupBox("MESSAGE command")
        msg_cmd_form = QFormLayout(msg_cmd_box)
        self.msg_cmd_name = QLineEdit("Update Bonus")
        msg_cmd_form.addRow("Name:", self.msg_cmd_name)
        self.msg_cmd_channel = QLineEdit()
        msg_cmd_form.addRow("Channel ID:", self.msg_cmd_channel)
        self.msg_cmd_message = QLineEdit()
        msg_cmd_form.addRow("Message ID:", self.msg_cmd_message)
        self.msg_cmd_guild = QLineEdit()
        self.msg_cmd_guild.setPlaceholderText("Optional")
        msg_cmd_form.addRow("Guild ID:", self.msg_cmd_guild)
        msg_cmd_btn = QPushButton("Run")
        msg_cmd_btn.clicked.connect(self._test_message_command)
        msg_cmd_form.addRow("", msg_cmd_btn)
        body_layout.addWidget(msg_cmd_box)

        # --- Slash command ---
        slash_box = QGroupBox("Command test (slash)")
        slash_layout = QVBoxLayout(slash_box)
        slash_form = QFormLayout()
        self.slash_name = QLineEdit("process")
        self.slash_name.setPlaceholderText("prep / process")
        slash_form.addRow("Name:", self.slash_name)
        self.slash_channel = QLineEdit()
        slash_form.addRow("Channel ID:", self.slash_channel)
        self.slash_guild = QLineEdit()
        self.slash_guild.setPlaceholderText("Optional")
        slash_form.addRow("Guild ID:", self.slash_guild)
        slash_layout.addLayout(slash_form)

        opts_header = QHBoxLayout()
        opts_header.addWidget(QLabel("Options (name / type / value / autocomplete)"))
        add_opt = QPushButton("Add option")
        add_opt.clicked.connect(lambda: self._add_option_row())
        opts_header.addWidget(add_opt)
        opts_header.addStretch(1)
        slash_layout.addLayout(opts_header)

        self._options_host = QVBoxLayout()
        slash_layout.addLayout(self._options_host)
        # /process member+ship and /prep target are STRING options with bot autocomplete
        self._add_option_row("member", 3, "", autocomplete=True)
        self._add_option_row("ship", 3, "", autocomplete=True)

        self.slash_wait_response = QCheckBox("Wait for response messageId (ephemeral)")
        self.slash_wait_response.setChecked(True)
        self.slash_wait_response.setToolTip(
            "Required before clickButton tests: Discord does not allow copying "
            "Message IDs on ephemeral replies. The plugin remembers the reply."
        )
        slash_layout.addWidget(self.slash_wait_response)

        slash_btn = QPushButton("Run slash")
        slash_btn.clicked.connect(self._test_slash_command)
        slash_layout.addWidget(slash_btn)
        body_layout.addWidget(slash_box)

        # --- Autocomplete ---
        auto_box = QGroupBox("Autocomplete (/prep target · /process member)")
        auto_form = QFormLayout(auto_box)
        self.auto_name = QLineEdit("prep")
        auto_form.addRow("Command:", self.auto_name)
        self.auto_option = QLineEdit("target")
        auto_form.addRow("Option:", self.auto_option)
        self.auto_query = QLineEdit()
        self.auto_query.setPlaceholderText("Discord user id (what you type before Tab)")
        auto_form.addRow("Query:", self.auto_query)
        self.auto_channel = QLineEdit()
        auto_form.addRow("Channel ID:", self.auto_channel)
        self.auto_guild = QLineEdit()
        self.auto_guild.setPlaceholderText("Optional")
        auto_form.addRow("Guild ID:", self.auto_guild)
        auto_btn = QPushButton("Fetch choices")
        auto_btn.clicked.connect(self._test_autocomplete)
        auto_form.addRow("", auto_btn)
        body_layout.addWidget(auto_box)

        # --- clickButton ---
        click_box = QGroupBox("clickButton (message component by label)")
        click_form = QFormLayout(click_box)
        self.click_channel = QLineEdit()
        click_form.addRow("Channel ID:", self.click_channel)
        self.click_message = QLineEdit()
        self.click_message.setPlaceholderText(
            "Optional — leave blank to use last slash ephemeral"
        )
        self.click_message.setToolTip(
            "Ephemeral replies have no Copy Message ID. Run slash with "
            "“Wait for response” checked, then click here with Message ID blank."
        )
        click_form.addRow("Message ID:", self.click_message)
        self.click_label = QLineEdit("Confirm")
        self.click_label.setPlaceholderText("Exact button label")
        click_form.addRow("Label:", self.click_label)
        self.click_buttons_hint = QLabel("")
        self.click_buttons_hint.setWordWrap(True)
        self.click_buttons_hint.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        click_form.addRow("Last buttons:", self.click_buttons_hint)
        self.click_guild = QLineEdit()
        self.click_guild.setPlaceholderText("Optional")
        click_form.addRow("Guild ID:", self.click_guild)
        click_btn = QPushButton("Click button")
        click_btn.clicked.connect(self._test_click_button)
        click_form.addRow("", click_btn)
        body_layout.addWidget(click_box)

        # --- Ping / cancel ---
        misc_box = QGroupBox("Bridge ping / cancel")
        misc_row = QHBoxLayout(misc_box)
        ping_btn = QPushButton("Ping / status")
        ping_btn.clicked.connect(self._test_ping)
        misc_row.addWidget(ping_btn)
        slow_btn = QPushButton("Slow ping then…")
        slow_btn.setToolTip(
            "Starts a 45s delayed ping; press Escape / Cancel / Stop to abort"
        )
        slow_btn.clicked.connect(self._test_slow_then_cancel)
        misc_row.addWidget(slow_btn)
        cancel_btn = QPushButton("Cancel in-flight")
        cancel_btn.clicked.connect(self._cancel_in_flight)
        misc_row.addWidget(cancel_btn)
        body_layout.addWidget(misc_box)

        controls = QHBoxLayout()
        self.stop_button = QPushButton("Stop / Abort")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        body_layout.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        body_layout.addWidget(self.status_label)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        self.root_layout.addWidget(scroll)

        if not is_enabled():
            self.status_label.setText(
                "Experimental bridge is off — enable it in Settings to run tests."
            )

    def _add_option_row(
        self,
        name: str = "",
        type_code: int = 3,
        value: str = "",
        *,
        autocomplete: bool = False,
    ) -> None:
        row = QHBoxLayout()
        name_entry = QLineEdit(name)
        name_entry.setPlaceholderText("name")
        type_spin = QSpinBox()
        type_spin.setRange(1, 11)
        type_spin.setValue(type_code)
        type_spin.setToolTip("Discord option type (3=STRING, 6=USER, …)")
        value_entry = QLineEdit(value)
        value_entry.setPlaceholderText("query / value (user id before Tab)")
        auto_check = QCheckBox("AC")
        auto_check.setChecked(autocomplete)
        auto_check.setToolTip(
            "Resolve via Discord autocomplete (query → UUID). "
            "Also auto-runs when the command schema marks the option autocomplete."
        )
        remove = QPushButton("Remove")
        row.addWidget(name_entry, stretch=2)
        row.addWidget(type_spin)
        row.addWidget(value_entry, stretch=3)
        row.addWidget(auto_check)
        row.addWidget(remove)
        self._options_host.addLayout(row)
        entries = (name_entry, type_spin, value_entry, auto_check)
        self._option_rows.append(entries)

        def _remove() -> None:
            if entries in self._option_rows:
                self._option_rows.remove(entries)
            while row.count():
                item = row.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            self._options_host.removeItem(row)

        remove.clicked.connect(_remove)

    def _option_payloads(self) -> list[dict]:
        options: list[dict] = []
        for name_entry, type_spin, value_entry, auto_check in self._option_rows:
            name = name_entry.text().strip()
            if not name:
                continue
            opt: dict = {
                "name": name,
                "type": int(type_spin.value()),
                "value": value_entry.text().strip(),
            }
            if auto_check.isChecked():
                opt["autocomplete"] = True
            options.append(opt)
        return options

    def _parse_link(self) -> None:
        parsed = parse_discord_channel_link(self.link_entry.text())
        guild = parsed.get("guild_id") or ""
        channel = parsed.get("channel_id") or ""
        message = parsed.get("message_id") or ""
        if not channel:
            self.status_label.setText("Could not parse a Discord channel link")
            return
        for entry in (
            self.switch_channel_entry,
            self.react_channel_entry,
            self.edit_channel_entry,
            self.send_channel_entry,
            self.msg_cmd_channel,
            self.slash_channel,
            self.auto_channel,
            self.click_channel,
        ):
            entry.setText(channel)
        if guild:
            self.react_guild_entry.setText(guild)
            self.msg_cmd_guild.setText(guild)
            self.slash_guild.setText(guild)
            self.auto_guild.setText(guild)
            self.click_guild.setText(guild)
        if message:
            self.react_message_entry.setText(message)
            self.edit_message_entry.setText(message)
            self.msg_cmd_message.setText(message)
            self.click_message.setText(message)
        self.status_label.setText(
            f"Parsed guild={guild or '—'} channel={channel} message={message or '—'}"
        )

    def _set_busy(self, busy: bool) -> None:
        def _apply() -> None:
            self._busy = busy
            self.stop_button.setEnabled(busy)

        on_main_thread(_apply)

    def _set_status(self, text: str) -> None:
        self._status.emit(text)

    def _stop(self) -> None:
        self.abort_requested = True
        try:
            request_abort(self)
        except Exception:
            pass
        try:
            get_bridge().cancel()
        except Exception:
            pass
        self._set_status("Abort requested…")

    def _cancel_in_flight(self) -> None:
        get_bridge().cancel()
        self.abort_requested = True
        self._set_status("Cancel sent for in-flight bridge ops")

    def _guard_enabled(self) -> bool:
        if not is_enabled():
            self._set_status(
                "Enable Settings → Experimental → Vencord Discord bridge first"
            )
            return False
        return True

    def _run_test(self, label: str, fn) -> None:
        if self._busy:
            self._set_status("Already running a test")
            return
        if not self._guard_enabled():
            return

        def worker() -> None:
            self._set_busy(True)
            self.abort_requested = False
            start_abort_session(self)
            try:
                get_bridge().ensure_started()
                self._set_status(f"{label}…")
                result = fn()
                self._set_status(f"{label} OK: {result!r}")
            except AbortError:
                self._set_status(f"{label} aborted")
            except DiscordBridgeError as exc:
                self._set_status(f"{label} failed: {exc}")
            except Exception as exc:
                logger.exception("Bridge test %s failed", label)
                self._set_status(f"{label} error: {exc}")
            finally:
                end_abort_session(self)
                self._set_busy(False)

        threading.Thread(target=worker, name=f"bridge-test-{label}", daemon=True).start()

    def _test_switch_channel(self) -> None:
        channel_id = self.switch_channel_entry.text().strip()

        def run():
            if not channel_id:
                raise DiscordBridgeError("Channel ID required")
            return get_bridge().switch_channel(channel_id, abort_ctx=self)

        self._run_test("switchChannel", run)

    def _test_react(self) -> None:
        channel_id = self.react_channel_entry.text().strip()
        message_id = self.react_message_entry.text().strip()
        guild_id = self.react_guild_entry.text().strip() or None
        name = self.react_emoji_name.text().strip() or pending_emoji().get(
            "name", "pending"
        )
        emoji_id = self.react_emoji_id.text().strip() or pending_emoji().get("id", "")
        emoji: dict = {"name": name}
        if emoji_id:
            emoji["id"] = emoji_id

        def run():
            if not channel_id or not message_id:
                raise DiscordBridgeError("Channel and message IDs required")
            return get_bridge().react(
                channel_id,
                message_id,
                emoji,
                guild_id=guild_id,
                abort_ctx=self,
            )

        self._run_test("react", run)

    def _test_edit(self) -> None:
        channel_id = self.edit_channel_entry.text().strip()
        message_id = self.edit_message_entry.text().strip()
        content = self.edit_content_entry.toPlainText()

        def run():
            if not channel_id or not message_id:
                raise DiscordBridgeError("Channel and message IDs required")
            return get_bridge().edit(
                channel_id, message_id, content, abort_ctx=self
            )

        self._run_test("edit", run)

    def _test_send(self) -> None:
        channel_id = self.send_channel_entry.text().strip()
        content = self.send_content_entry.text()

        def run():
            if not channel_id or not content:
                raise DiscordBridgeError("Channel ID and content required")
            return get_bridge().send(channel_id, content, abort_ctx=self)

        self._run_test("send", run)

    def _test_message_command(self) -> None:
        name = self.msg_cmd_name.text().strip() or "Update Bonus"
        channel_id = self.msg_cmd_channel.text().strip()
        message_id = self.msg_cmd_message.text().strip()
        guild_id = self.msg_cmd_guild.text().strip() or None

        def run():
            if not channel_id or not message_id:
                raise DiscordBridgeError("Channel and message IDs required")
            return get_bridge().message_command(
                name,
                channel_id,
                message_id,
                guild_id=guild_id,
                abort_ctx=self,
            )

        self._run_test("messageCommand", run)

    def _test_slash_command(self) -> None:
        name = self.slash_name.text().strip()
        channel_id = self.slash_channel.text().strip()
        guild_id = self.slash_guild.text().strip() or None
        options = self._option_payloads()
        # Read widgets on the UI thread — worker-thread isChecked() is unreliable.
        wait_for_response = self.slash_wait_response.isChecked()

        def run():
            if not name or not channel_id:
                raise DiscordBridgeError("Command name and channel ID required")
            result = get_bridge().slash_command(
                name,
                channel_id,
                options,
                guild_id=guild_id,
                abort_ctx=self,
                wait_for_response=wait_for_response,
            )
            mid = str(result.get("messageId") or "").strip()
            if mid:
                on_main_thread(lambda m=mid: self.click_message.setText(m))
                if channel_id:
                    on_main_thread(
                        lambda c=channel_id: self.click_channel.setText(c)
                    )
            buttons = result.get("buttons") or []
            if isinstance(buttons, list) and buttons:
                labels = ", ".join(
                    str(b.get("label") or "")
                    for b in buttons
                    if isinstance(b, dict) and b.get("label")
                )
                on_main_thread(
                    lambda t=labels: self.click_buttons_hint.setText(t or "(none)")
                )
            return result

        self._run_test("slashCommand", run)

    def _test_autocomplete(self) -> None:
        name = self.auto_name.text().strip()
        option_name = self.auto_option.text().strip()
        query = self.auto_query.text().strip()
        channel_id = self.auto_channel.text().strip()
        guild_id = self.auto_guild.text().strip() or None

        def run():
            if not name or not option_name or not channel_id:
                raise DiscordBridgeError("Command, option, and channel ID required")
            return get_bridge().autocomplete(
                name,
                channel_id,
                option_name,
                query,
                guild_id=guild_id,
                abort_ctx=self,
            )

        self._run_test("autocomplete", run)

    def _test_click_button(self) -> None:
        channel_id = self.click_channel.text().strip()
        message_id = self.click_message.text().strip() or None
        label = self.click_label.text().strip()
        guild_id = self.click_guild.text().strip() or None

        def run():
            if not channel_id or not label:
                raise DiscordBridgeError(
                    "Channel ID and label required "
                    "(Message ID optional — uses last slash ephemeral)"
                )
            return get_bridge().click_button(
                channel_id,
                message_id,
                label=label,
                guild_id=guild_id,
                abort_ctx=self,
            )

        self._run_test("clickButton", run)

    def _test_ping(self) -> None:
        def run():
            bridge = get_bridge()
            bridge.ensure_started()
            # Brief settle for connect/auth when just enabled.
            deadline = time.time() + 5
            while time.time() < deadline and not prefer_bridge():
                time.sleep(0.1)
            connected = is_connected()
            status = {
                "enabled": is_enabled(),
                "connected": connected,
                "last_error": bridge.last_error() or None,
            }
            if connected:
                status["ping"] = bridge.ping(abort_ctx=self, timeout=8.0)
            return status

        self._run_test("ping/status", run)

    def _test_slow_then_cancel(self) -> None:
        """Start a delayed ping; user should Cancel / Escape."""

        def run():
            # delay_ms makes the plugin actually wait so Escape can abort mid-flight.
            return get_bridge().ping(
                abort_ctx=self, timeout=60.0, delay_ms=45_000
            )

        self._run_test("slow ping (cancel/Escape)", run)
