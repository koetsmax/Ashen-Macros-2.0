import keyboard
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
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
        layout.addLayout(theme_row)

        self.compact_panels_check = QCheckBox("Compact panels")
        self.compact_panels_check.setChecked(config_bool("compact_panels", "true"))
        self.compact_panels_check.setToolTip(
            "When enabled, result panels show a compact summary. "
            "When disabled, a classic 2×2 grid shows every field with color-coded values."
        )
        layout.addWidget(self.compact_panels_check)

        self.edit_check_message_check = QCheckBox("Edit previous check message")
        self.edit_check_message_check.setChecked(config_bool("edit_check_message", "true"))
        self.edit_check_message_check.setToolTip(
            "When enabled, if you posted a good/not-good check for this user in "
            "#on-duty-chat within the last 30 minutes, edit that message instead of posting a new one."
        )
        layout.addWidget(self.edit_check_message_check)

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
            "Switch to #on-duty-chat and move focus up N messages. Does not open edit."
        )
        self.edit_nav_test_btn.clicked.connect(self._test_edit_navigate)
        nav_row.addWidget(self.edit_nav_test_btn)
        nav_row.addStretch(1)
        layout.addLayout(nav_row)

        layout.addWidget(QLabel(
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
        layout.addLayout(grid)

        reset_apps_btn = QPushButton("Reset app window positions to 0, 0")
        reset_apps_btn.setAutoDefault(False)
        reset_apps_btn.setDefault(False)
        reset_apps_btn.clicked.connect(self._reset_app_positions)
        layout.addWidget(reset_apps_btn)

        btn_row = QHBoxLayout()
        save = QPushButton("Save Changes")
        save.setAutoDefault(True)
        save.setDefault(True)
        save.clicked.connect(self._save)
        reset = QPushButton("Reset To Default")
        reset.setAutoDefault(False)
        reset.setDefault(False)
        reset.clicked.connect(self._reset)
        btn_row.addWidget(save)
        btn_row.addWidget(reset)
        layout.addLayout(btn_row)

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
        self._key_test_label.setText("Key recognized!")
        self._key_test_label.setStyleSheet(f"color: {theme.GREEN};")
        if self._key_test_hotkey:
            try:
                keyboard.remove_hotkey(self._key_test_hotkey)
            except (KeyError, ValueError):
                pass
            self._key_test_hotkey = None

    def keyPressEvent(self, event: QKeyEvent):
        if self._key_test_hotkey is not None and event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def _reset_app_positions(self):
        reset_app_window_positions(self.parent())

    def _test_edit_navigate(self):
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
        self.accept()

    def _reset(self):
        defaults = {"initial_command": "2", "follow_up": "0.4", "abort_key": "escape", "api_url": "https://ashen.api.famkoets.nl"}
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

    def closeEvent(self, event):
        if self._key_test_hotkey:
            try:
                keyboard.remove_hotkey(self._key_test_hotkey)
            except (KeyError, ValueError):
                pass
        super().closeEvent(event)
