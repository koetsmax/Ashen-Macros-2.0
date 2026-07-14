from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton

from gui.views.app_window import AppWindow


class RenameFleetWindow(AppWindow):
    def __init__(self):
        super().__init__("Rename Fleet")

    def _build_ui(self) -> None:
        layout = self.add_grid()

        layout.addWidget(QLabel("Fleet:"), 0, 0)
        self.fleet_combo = QComboBox()
        self.fleet_combo.addItems([str(i) for i in range(1, 11)])
        layout.addWidget(self.fleet_combo, 0, 1)

        self.ship_entries = []
        for i in range(5):
            layout.addWidget(QLabel(f"Ship {i + 1}:"), i + 1, 0)
            entry = QLineEdit()
            self.ship_entries.append(entry)
            layout.addWidget(entry, i + 1, 1)

        layout.addWidget(
            QLabel("Make sure everyone is staffchecked before pressing start or you will have a bad time"),
            6, 0, 1, 2,
        )

        start = QPushButton("Start")
        start.clicked.connect(lambda: None)
        layout.addWidget(start, 7, 0, 1, 2)
