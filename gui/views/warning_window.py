from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from gui.views.app_window import AppWindow


PRESET_REASONS = {
    "leave warning (rule 3)": (
        "Rule #3: You must give a warning before leaving a ship by using !leave 10 minutes "
        "before you plan to leave the ship. Leaving significantly before or after the 10 minutes "
        "is not acceptable, however, you are allowed to leave earlier if a replacement is already on your ship."
    ),
    "Alt+F4 warning": (
        "Rule #4: When leaving the game, ensure to exit gracefully by using the LEAVE GAME option. "
        "It is strictly prohibited to use ALT+F4 or force kill your game. Failure to comply will "
        "result in new crew members being locked out of the ship for 10 minutes."
    ),
}


class WarningWindow(AppWindow):
    def __init__(self):
        super().__init__("Add Warning", keyboard_lock=True)

    def _build_ui(self) -> None:
        layout = self.add_grid()

        layout.addWidget(QLabel("Channel:"), 0, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems([
            "#staff-commands", "#on-duty-commands", "#captain-commands", "#admin-commands"
        ])
        self.channel_combo.setCurrentText("#on-duty-commands")
        layout.addWidget(self.channel_combo, 0, 1)

        layout.addWidget(QLabel("Preset warning:"), 1, 0)
        self.reason_combo = QComboBox()
        self.reason_combo.addItems(list(PRESET_REASONS.keys()))
        layout.addWidget(self.reason_combo, 1, 1)

        layout.addWidget(QLabel("Discord ID:"), 2, 0)
        self.user_id_entry = QLineEdit()
        layout.addWidget(self.user_id_entry, 2, 1)

        layout.addWidget(QLabel("Custom Reason:"), 3, 0)
        self.custom_reason_entry = QLineEdit()
        layout.addWidget(self.custom_reason_entry, 3, 1)

        self.loghistory_check = QCheckBox("Check loghistory before adding warning")
        layout.addWidget(self.loghistory_check, 4, 0, 1, 2)

        self.nodm_check = QCheckBox("Add warning as nodm")
        layout.addWidget(self.nodm_check, 5, 0, 1, 2)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start)
        layout.addWidget(self.start_button, 6, 0)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button, 6, 1)

    def _reason_text(self) -> str:
        custom = self.custom_reason_entry.text().strip()
        if custom:
            return custom
        return PRESET_REASONS[self.reason_combo.currentText()]

    def _add_warning(self):
        clear_typing_bar()
        reason = self._reason_text()
        if self.nodm_check.isChecked():
            execute_command(self, f"/warn member:{self.user_id_entry.text()} reason:{reason} no_dm: True")
        else:
            execute_command(self, f"/warn member:{self.user_id_entry.text()} reason:{reason}")

    def _stop(self):
        self.start_button.setText("Start")
        try:
            self.start_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.start_button.clicked.connect(self._start)
        self.stop_button.setEnabled(False)

    def _start(self):
        if self.loghistory_check.isChecked():
            switch_channel(self, self.channel_combo.currentText())
            clear_typing_bar()
            execute_command(self, f"/user_report member:{self.user_id_entry.text()}")
            self.start_button.setText("Add warning")
            try:
                self.start_button.clicked.disconnect()
            except RuntimeError:
                pass
            self.start_button.clicked.connect(self._add_warning)
            self.stop_button.setEnabled(True)
        else:
            switch_channel(self, self.channel_combo.currentText())
            clear_typing_bar()
            self._add_warning()
