import ast
import threading

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from gui.views.app_window import AppWindow
from staffcheck.abort import (
    AbortError,
    check_abort,
    end_abort_session,
    interruptible_sleep,
    start_abort_session,
)
from staffcheck.qt_ui import on_main_thread


class CommandExecutorWindow(AppWindow):
    def __init__(self):
        super().__init__("Command Executor", keyboard_lock=True)
        self.abort_requested = False

    def _build_ui(self) -> None:
        layout = self.add_grid()

        layout.addWidget(QLabel("Command:"), 0, 0)
        self.command_entry = QLineEdit()
        layout.addWidget(self.command_entry, 0, 1)

        layout.addWidget(QLabel("Parameters, max 1:"), 1, 0)
        self.params_entry = QLineEdit()
        layout.addWidget(self.params_entry, 1, 1)

        layout.addWidget(QLabel("Members:"), 2, 0)
        self.members_entry = QLineEdit()
        layout.addWidget(self.members_entry, 2, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label, 3, 0, 1, 2)

        start = QPushButton("Start!")
        start.clicked.connect(self._start)
        layout.addWidget(start, 4, 1)

    def _set_status(self, text: str) -> None:
        on_main_thread(lambda: self.status_label.setText(text))

    def _start(self):
        try:
            members = ast.literal_eval(self.members_entry.text())
        except (SyntaxError, ValueError):
            self.status_label.setText("Invalid members list")
            return
        if not isinstance(members, (list, tuple)):
            self.status_label.setText("Members must be a list")
            return

        command = self.command_entry.text().strip()
        if not command:
            self.status_label.setText("Enter a command")
            return

        self._set_status("Starting in 5s… (abort key cancels)")
        threading.Thread(
            target=self._run,
            args=(command, list(members)),
            daemon=True,
        ).start()

    def _run(self, command: str, members: list) -> None:
        start_abort_session(self)
        try:
            interruptible_sleep(self, 5)
            switch_channel(self, "#lieutenant-commands")
            check_abort(self)
            clear_typing_bar()
            check_abort(self)
            for member in members:
                check_abort(self)
                execute_command(self, f"/{command}{member}")
            self._set_status("Done")
        except AbortError:
            self._set_status("Aborted")
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
        finally:
            end_abort_session(self)
