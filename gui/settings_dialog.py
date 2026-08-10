import keyboard
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.settings import config_bool, read_config, set_custom_value
from core.window_positions import reset_app_window_positions
from gui import theme


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._key_test_hotkey = None
        self._key_test_label = None

        config = read_config()
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)
        self._tabs = tabs

        general = QWidget()
        general_layout = QVBoxLayout(general)
        tabs.addTab(general, "General")

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.flavor_combo = QComboBox()
        for flavor in theme.PALETTE_FLAVORS:
            self.flavor_combo.addItem(flavor.name, flavor.identifier)
        current = theme.get_flavor_identifier()
        for i in range(self.flavor_combo.count()):
            if self.flavor_combo.itemData(i) == current:
                self.flavor_combo.setCurrentIndex(i)
                break
        self.flavor_combo.currentIndexChanged.connect(self._on_flavor_changed)
        theme_row.addWidget(self.flavor_combo, stretch=1)
        general_layout.addLayout(theme_row)

        self.compact_panels_check = QCheckBox("Compact panels")
        self.compact_panels_check.setChecked(config_bool("compact_panels", "true"))
        self.compact_panels_check.setToolTip(
            "When enabled, result panels show a compact summary. "
            "When disabled, a classic 2×2 grid shows every field with color-coded values."
        )
        general_layout.addWidget(self.compact_panels_check)

        self.edit_check_message_check = QCheckBox("Edit previous check message")
        self.edit_check_message_check.setChecked(config_bool("edit_check_message", "true"))
        self.edit_check_message_check.setToolTip(
            "When enabled, if you posted a good/not-good check for this user in "
            "#on-duty-chat within the last 30 minutes, edit that message instead of posting a new one."
        )
        general_layout.addWidget(self.edit_check_message_check)

        nav_row = QHBoxLayout()
        nav_row.addWidget(QLabel("Test navigate messages up:"))
        self.edit_nav_offset_entry = QLineEdit(
            config.get("edit_check_nav_test_offset", "4")
        )
        self.edit_nav_offset_entry.setMaximumWidth(60)
        nav_row.addWidget(self.edit_nav_offset_entry)
        self.edit_nav_test_btn = QPushButton("Test navigate in on-duty-chat")
        self.edit_nav_test_btn.setAutoDefault(False)
        self.edit_nav_test_btn.setDefault(False)
        self.edit_nav_test_btn.setToolTip(
            "Switch to #on-duty-chat and move focus up N messages. Does not open edit. "
            "Disabled while the Vencord Discord bridge is enabled (keyboard-only debug tool)."
        )
        self.edit_nav_test_btn.clicked.connect(self._test_edit_navigate)
        nav_row.addWidget(self.edit_nav_test_btn)
        nav_row.addStretch(1)
        general_layout.addLayout(nav_row)

        general_layout.addWidget(QLabel(
            "Delay Initial Command: wait after the slash command.\n"
            "Delay follow up: wait after each variable.\n"
            "Abort key: stops an in-progress staffcheck.\n"
            "API URL: leave default unless you know what you're doing.\n"
            "All delays are in seconds."
        ))

        grid = QGridLayout()
        self.entries = {}
        fields = [
            ("Delay initial command:", "initial_command", "COMMANDS", config.get("initial_command", "2")),
            ("Delay follow up:", "follow_up", "COMMANDS", config.get("follow_up", "0.4")),
            ("Abort key:", "abort_key", "COMMANDS", config.get("abort_key", "escape")),
            ("API URL:", "api_url", "API", config.get("api_url", "https://ashen.api.famkoets.nl")),
        ]
        for i, (label, key, section, default) in enumerate(fields):
            grid.addWidget(QLabel(label), i, 0)
            entry = QLineEdit(default)
            self.entries[key] = (entry, section)
            grid.addWidget(entry, i, 1)
            if key == "abort_key":
                test_btn = QPushButton("Test key")
                test_btn.setAutoDefault(False)
                test_btn.setDefault(False)
                test_btn.clicked.connect(self._test_key)
                grid.addWidget(test_btn, i, 2)
                self._key_test_label = QLabel("")
                grid.addWidget(self._key_test_label, i, 3)
        general_layout.addLayout(grid)

        reset_apps_btn = QPushButton("Reset app window positions to 0, 0")
        reset_apps_btn.setAutoDefault(False)
        reset_apps_btn.setDefault(False)
        reset_apps_btn.clicked.connect(self._reset_app_positions)
        general_layout.addWidget(reset_apps_btn)

        open_log_btn = QPushButton("Open log")
        open_log_btn.setAutoDefault(False)
        open_log_btn.setDefault(False)
        open_log_btn.setToolTip("Open the folder that contains ashen-macros.log")
        open_log_btn.clicked.connect(self._open_log_location)
        general_layout.addWidget(open_log_btn)
        general_layout.addStretch(1)

        experimental_page = QWidget()
        experimental_layout = QVBoxLayout(experimental_page)
        tabs.addTab(experimental_page, "Experimental")

        experimental = QGroupBox("Vencord Discord bridge")
        bridge_layout = QVBoxLayout(experimental)
        self.vencord_bridge_check = QCheckBox("Enable Vencord Discord bridge")
        self.vencord_bridge_check.setChecked(config_bool("vencord_bridge", "false"))
        self.vencord_bridge_check.setToolTip(
            "When enabled, Discord actions go through the localhost Vencord plugin. "
            "There is no keyboard fallback — if the bridge errors, the action fails "
            "and the status line shows the error. Default off."
        )
        self.vencord_bridge_check.toggled.connect(self._on_vencord_bridge_toggled)
        bridge_layout.addWidget(self.vencord_bridge_check)

        self._bridge_fields = QGridLayout()
        self._bridge_fields.addWidget(QLabel("Bridge port:"), 0, 0)
        self.vencord_port_entry = QLineEdit(
            config.get("vencord_bridge_port", "47832")
        )
        self.vencord_port_entry.setMaximumWidth(100)
        self._bridge_fields.addWidget(self.vencord_port_entry, 0, 1)
        self._bridge_fields.addWidget(QLabel("Shared token:"), 1, 0)
        self.vencord_token_entry = QLineEdit(config.get("vencord_bridge_token", "change-me"))
        self.vencord_token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.vencord_token_entry.setPlaceholderText("change-me")
        self._bridge_fields.addWidget(self.vencord_token_entry, 1, 1)
        show_token = QPushButton("Show")
        show_token.setAutoDefault(False)
        show_token.setDefault(False)
        show_token.setCheckable(True)
        show_token.toggled.connect(self._toggle_token_visibility)
        self._bridge_fields.addWidget(show_token, 1, 2)
        bridge_layout.addLayout(self._bridge_fields)
        self._on_vencord_bridge_toggled(self.vencord_bridge_check.isChecked())
        experimental_layout.addWidget(experimental)

        shadow_box = QGroupBox("Staffcheck model")
        shadow_layout = QVBoxLayout(shadow_box)
        self.staffcheck_shadow_check = QCheckBox(
            "Show model shadow suggestions in live staffcheck"
        )
        self.staffcheck_shadow_check.setChecked(
            config_bool("staffcheck_model_shadow", "false")
        )
        self.staffcheck_shadow_check.setToolTip(
            "When enabled, live staffcheck shows the model suggestion + cited reasons "
            "before Good / Not Good. Training and silent prediction logs "
            "always run. Off by default. Never auto-applies."
        )
        shadow_layout.addWidget(self.staffcheck_shadow_check)
        experimental_layout.addWidget(shadow_box)

        leave_box = QGroupBox("Leave message marks")
        leave_layout = QVBoxLayout(leave_box)
        self.leave_animated_emojis_check = QCheckBox(
            "Use animated tick / cross emojis"
        )
        self.leave_animated_emojis_check.setChecked(
            config_bool("leave_animated_emojis", "false")
        )
        self.leave_animated_emojis_check.setToolTip(
            "When enabled, Tick / Cross & Warn use the animated BetterTick / bettercross "
            "emojis instead of the static ones. Requires the Vencord bridge."
        )
        leave_layout.addWidget(self.leave_animated_emojis_check)
        experimental_layout.addWidget(leave_box)
        experimental_layout.addStretch(1)

        btn_row = QHBoxLayout()
        save = QPushButton("Save Changes")
        save.setAutoDefault(True)
        save.setDefault(True)
        save.clicked.connect(self._save)
        reset = QPushButton("Reset To Default")
        reset.setAutoDefault(False)
        reset.setDefault(False)
        reset.setToolTip("Reset only the currently selected tab to defaults")
        reset.clicked.connect(self._reset)
        btn_row.addWidget(save)
        btn_row.addWidget(reset)
        layout.addLayout(btn_row)

    def _on_vencord_bridge_toggled(self, checked: bool) -> None:
        self.vencord_port_entry.setVisible(checked)
        self.vencord_token_entry.setVisible(checked)
        for i in range(self._bridge_fields.count()):
            item = self._bridge_fields.itemAt(i)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setVisible(checked)
        # Keyboard-only debug navigate — unavailable with bridge enabled.
        self.edit_nav_offset_entry.setEnabled(not checked)
        self.edit_nav_test_btn.setEnabled(not checked)

    def _toggle_token_visibility(self, show: bool) -> None:
        mode = (
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        )
        self.vencord_token_entry.setEchoMode(mode)

    def _on_flavor_changed(self, index: int):
        identifier = self.flavor_combo.itemData(index)
        if not identifier:
            return
        theme.set_flavor(identifier)
        from PySide6.QtWidgets import QApplication
        theme.apply_theme(QApplication.instance())

    def _test_key(self):
        if self._key_test_hotkey:
            try:
                keyboard.remove_hotkey(self._key_test_hotkey)
            except (KeyError, ValueError):
                pass
        key = self.entries["abort_key"][0].text().strip()
        if not key:
            self._key_test_label.setText("Enter a key first")
            self._key_test_label.setStyleSheet(f"color: {theme.RED};")
            return
        try:
            self._key_test_hotkey = keyboard.add_hotkey(key, self._on_key_detected, suppress=True)
            self._key_test_label.setText("Press the key now...")
            self._key_test_label.setStyleSheet(f"color: {theme.PEACH};")
        except ValueError:
            self._key_test_label.setText("Invalid key name")
            self._key_test_label.setStyleSheet(f"color: {theme.RED};")

    def _on_key_detected(self):
        # keyboard.add_hotkey runs this on its hook thread — marshal UI to Qt.
        from staffcheck.qt_ui import on_main_thread

        def _apply():
            self._key_test_label.setText("Key recognized!")
            self._key_test_label.setStyleSheet(f"color: {theme.GREEN};")
            if self._key_test_hotkey:
                try:
                    keyboard.remove_hotkey(self._key_test_hotkey)
                except (KeyError, ValueError):
                    pass
                self._key_test_hotkey = None

        on_main_thread(_apply)

    def keyPressEvent(self, event: QKeyEvent):
        if self._key_test_hotkey is not None and event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def _reset_app_positions(self):
        reset_app_window_positions(self.parent())

    def _open_log_location(self) -> None:
        import logging
        import os
        import subprocess
        import sys

        from core.logging import log_file_path
        from core.settings import DATA_DIR

        os.makedirs(DATA_DIR, exist_ok=True)
        path = log_file_path()
        folder = DATA_DIR
        try:
            if sys.platform == "win32":
                if os.path.isfile(path):
                    subprocess.Popen(
                        ["explorer", "/select,", os.path.normpath(path)]
                    )
                else:
                    os.startfile(folder)  # noqa: S606
            elif sys.platform == "darwin":
                if os.path.isfile(path):
                    subprocess.Popen(["open", "-R", path])
                else:
                    subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to open log location %s", folder
            )

    def _test_edit_navigate(self):
        if self.vencord_bridge_check.isChecked():
            return
        raw = self.edit_nav_offset_entry.text().strip() or "4"
        try:
            n = max(1, int(raw))
        except ValueError:
            n = 4
        self.edit_nav_offset_entry.setText(str(n))
        set_custom_value("STAFFCHECK", "edit_check_nav_test_offset", str(n))
        self.edit_nav_test_btn.setEnabled(False)
        from staffcheck.tasks import run_background

        run_background(self._run_edit_nav_test, n)

    def _run_edit_nav_test(self, n: int):
        import threading
        from types import SimpleNamespace

        from core.keyboard import navigate_to_on_duty_message, switch_channel
        from staffcheck.abort import (
            AbortError,
            end_abort_session,
            start_abort_session,
        )
        from staffcheck.qt_ui import on_main_thread

        ctx = SimpleNamespace(
            keyboard_lock=threading.Lock(),
            abort_requested=False,
            _abort_session_active=False,
            _abort_hotkey=None,
        )
        try:
            start_abort_session(ctx)
            switch_channel(ctx, "#on-duty-chat")
            navigate_to_on_duty_message(ctx, n)
        except AbortError:
            pass
        finally:
            end_abort_session(ctx)
            on_main_thread(lambda: self.edit_nav_test_btn.setEnabled(True))

    def _save(self):
        for key, (entry, section) in self.entries.items():
            set_custom_value(section, key, entry.text())
        set_custom_value(
            "UI",
            "compact_panels",
            "true" if self.compact_panels_check.isChecked() else "false",
        )
        set_custom_value(
            "STAFFCHECK",
            "edit_check_message",
            "true" if self.edit_check_message_check.isChecked() else "false",
        )
        raw = self.edit_nav_offset_entry.text().strip() or "4"
        try:
            n = max(1, int(raw))
        except ValueError:
            n = 4
        set_custom_value("STAFFCHECK", "edit_check_nav_test_offset", str(n))

        set_custom_value(
            "EXPERIMENTAL",
            "vencord_bridge",
            "true" if self.vencord_bridge_check.isChecked() else "false",
        )
        port_raw = self.vencord_port_entry.text().strip() or "47832"
        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                port = 47832
        except ValueError:
            port = 47832
        set_custom_value("EXPERIMENTAL", "vencord_bridge_port", str(port))
        set_custom_value(
            "EXPERIMENTAL",
            "vencord_bridge_token",
            self.vencord_token_entry.text().strip(),
        )
        set_custom_value(
            "EXPERIMENTAL",
            "staffcheck_model_shadow",
            "true" if self.staffcheck_shadow_check.isChecked() else "false",
        )
        set_custom_value(
            "EXPERIMENTAL",
            "leave_animated_emojis",
            "true" if self.leave_animated_emojis_check.isChecked() else "false",
        )

        from core.discord_bridge import sync_bridge_lifecycle

        sync_bridge_lifecycle()
        parent = self.parent()
        if parent is not None and hasattr(parent, "_update_menu_gating"):
            parent._update_menu_gating()
        if parent is not None and hasattr(parent, "_update_bridge_status"):
            parent._update_bridge_status()
        self.accept()

    def _reset(self):
        tab = self._tabs.tabText(self._tabs.currentIndex())
        if tab == "Experimental":
            self._reset_experimental_tab()
        else:
            self._reset_general_tab()

    def _reset_general_tab(self):
        defaults = {
            "initial_command": "2",
            "follow_up": "0.4",
            "abort_key": "escape",
            "api_url": "https://ashen.api.famkoets.nl",
        }
        for key, (entry, section) in self.entries.items():
            entry.setText(defaults[key])
            set_custom_value(section, key, defaults[key])
        self.compact_panels_check.setChecked(True)
        set_custom_value("UI", "compact_panels", "true")
        self.edit_check_message_check.setChecked(True)
        set_custom_value("STAFFCHECK", "edit_check_message", "true")
        self.edit_nav_offset_entry.setText("4")
        set_custom_value("STAFFCHECK", "edit_check_nav_test_offset", "4")
        theme.set_flavor(theme.DEFAULT_FLAVOR)
        for i in range(self.flavor_combo.count()):
            if self.flavor_combo.itemData(i) == theme.DEFAULT_FLAVOR:
                self.flavor_combo.setCurrentIndex(i)
                break
        from PySide6.QtWidgets import QApplication

        theme.apply_theme(QApplication.instance())

    def _reset_experimental_tab(self):
        self.vencord_bridge_check.setChecked(False)
        set_custom_value("EXPERIMENTAL", "vencord_bridge", "false")
        self.vencord_port_entry.setText("47832")
        set_custom_value("EXPERIMENTAL", "vencord_bridge_port", "47832")
        self.vencord_token_entry.setText("change-me")
        set_custom_value("EXPERIMENTAL", "vencord_bridge_token", "change-me")
        self.staffcheck_shadow_check.setChecked(False)
        set_custom_value("EXPERIMENTAL", "staffcheck_model_shadow", "false")
        self.leave_animated_emojis_check.setChecked(False)
        set_custom_value("EXPERIMENTAL", "leave_animated_emojis", "false")
        self._on_vencord_bridge_toggled(False)
        from core.discord_bridge import sync_bridge_lifecycle

        sync_bridge_lifecycle()
        parent = self.parent()
        if parent is not None and hasattr(parent, "_update_menu_gating"):
            parent._update_menu_gating()
        if parent is not None and hasattr(parent, "_update_bridge_status"):
            parent._update_bridge_status()

    def closeEvent(self, event):
        if self._key_test_hotkey:
            try:
                keyboard.remove_hotkey(self._key_test_hotkey)
            except (KeyError, ValueError):
                pass
        super().closeEvent(event)
