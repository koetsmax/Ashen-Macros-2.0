import ast
import threading
import time

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from core.keyboard import clear_typing_bar, execute_command, switch_channel
from gui.views.app_window import AppWindow


class CommandExecutorWindow(AppWindow):
    def __init__(self):
        super().__init__("Command Executor", keyboard_lock=True)

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

        start = QPushButton("Start!")
        start.clicked.connect(self._start)
        layout.addWidget(start, 3, 1)

    def _start(self):
        time.sleep(5)
        members = ast.literal_eval(self.members_entry.text())
        switch_channel(self, "#lieutenant-commands")
        clear_typing_bar()
        for member in members:
            execute_command(self, f"/{self.command_entry.text()}{member}")
