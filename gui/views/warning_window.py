import threading

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from gui.views.app_window import AppWindow
from staffcheck.abort import (
    AbortError,
    check_abort,
    end_abort_session,
    start_abort_session,
)
from staffcheck.qt_ui import on_main_thread


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
        self.abort_requested = False
        self._busy = False

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

        self.stop_button = QPushButton("Stop / Abort")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button, 6, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label, 7, 0, 1, 2)

    def _reason_text(self) -> str:
        custom = self.custom_reason_entry.text().strip()
        if custom:
            return custom
        return PRESET_REASONS[self.reason_combo.currentText()]

    def _set_status(self, text: str) -> None:
        on_main_thread(lambda: self.status_label.setText(text))

    def _set_busy(self, busy: bool) -> None:
        def _apply():
            self._busy = busy
            self.start_button.setEnabled(not busy)
            self.stop_button.setEnabled(busy)

        on_main_thread(_apply)

    def _stop(self):
        self.abort_requested = True
        if not self._busy:
            self._reset_start_button()

    def _reset_start_button(self) -> None:
        def _apply():
            self.start_button.setText("Start")
            try:
                self.start_button.clicked.disconnect()
            except RuntimeError:
                pass
            self.start_button.clicked.connect(self._start)
            self.stop_button.setEnabled(False)
            self.start_button.setEnabled(True)

        on_main_thread(_apply)

    def _start(self):
        if self._busy:
            return
        if self.loghistory_check.isChecked():
            threading.Thread(target=self._run_loghistory_step, daemon=True).start()
        else:
            threading.Thread(target=self._run_warn, daemon=True).start()

    def _run_loghistory_step(self) -> None:
        self._set_busy(True)
        self._set_status("Opening channel / loghistory…")
        start_abort_session(self)
        try:
            switch_channel(self, self.channel_combo.currentText())
            check_abort(self)
            clear_typing_bar()
            check_abort(self)
            execute_command(self, f"/user_report member:{self.user_id_entry.text()}")
            self._set_status("Review loghistory, then Add warning (abort key works)")

            def _arm_add():
                self.start_button.setText("Add warning")
                try:
                    self.start_button.clicked.disconnect()
                except RuntimeError:
                    pass
                self.start_button.clicked.connect(self._queue_add_warning)
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self._busy = False

            on_main_thread(_arm_add)
        except AbortError:
            self._set_status("Aborted")
            self._reset_start_button()
            self._busy = False
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
            self._reset_start_button()
            self._busy = False
        finally:
            end_abort_session(self)

    def _queue_add_warning(self) -> None:
        if self._busy:
            return
        threading.Thread(target=self._run_warn, daemon=True).start()

    def _run_warn(self) -> None:
        self._set_busy(True)
        self._set_status("Adding warning…")
        start_abort_session(self)
        try:
            switch_channel(self, self.channel_combo.currentText())
            check_abort(self)
            clear_typing_bar()
            check_abort(self)
            reason = self._reason_text()
            if self.nodm_check.isChecked():
                execute_command(
                    self,
                    f"/warn member:{self.user_id_entry.text()} reason:{reason} no_dm: True",
                )
            else:
                execute_command(
                    self,
                    f"/warn member:{self.user_id_entry.text()} reason:{reason}",
                )
            self._set_status("Done")
        except AbortError:
            self._set_status("Aborted")
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
        finally:
            end_abort_session(self)
            self._reset_start_button()
            self._busy = False
