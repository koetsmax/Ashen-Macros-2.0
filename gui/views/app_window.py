from __future__ import annotations

import threading

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget


class AppWindow(QMainWindow):
    """Shared shell for secondary tool windows."""

    def __init__(self, title: str, *, keyboard_lock: bool = False):
        super().__init__()
        self.setWindowTitle(title)
        if keyboard_lock:
            self.keyboard_lock = threading.Lock()

        central = QWidget()
        self.setCentralWidget(central)
        self.root_layout = QVBoxLayout(central)
        self.root_layout.setContentsMargins(12, 12, 12, 12)
        self.root_layout.setSpacing(8)
        self._build_ui()

    def _build_ui(self) -> None:
        raise NotImplementedError

    def add_grid(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        self.root_layout.addLayout(layout)
        return layout

    def add_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.root_layout.addLayout(layout)
        return layout
