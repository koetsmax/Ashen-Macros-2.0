import time

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QWidget


class HammertimeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timestamp generator")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QGridLayout(central)

        self.values = (
            time.strftime("%m/%d/%Y", time.localtime()),
            time.strftime("%B %d, %Y", time.localtime()),
            time.strftime("%I:%M %p", time.localtime()),
            time.strftime("%I:%M:%S %p", time.localtime()),
            time.strftime("%B %d, %Y %I:%M %p", time.localtime()),
            time.strftime("%A, %B %d, %Y %I:%M %p", time.localtime()),
            "In one minute",
            time.strftime("%m/%d/%Y %I:%M:%S %p", time.localtime()),
        )
        self.formats = ("d", "D", "t", "T", "f", "F", "R", None)

        layout.addWidget(QLabel("Show:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(self.values)
        layout.addWidget(self.format_combo, 0, 1)

        layout.addWidget(QLabel("Hours from now:"), 1, 0)
        self.hours_entry = QLineEdit("0")
        layout.addWidget(self.hours_entry, 1, 1)

        layout.addWidget(QLabel("Minutes from now:"), 2, 0)
        self.minutes_entry = QLineEdit("0")
        layout.addWidget(self.minutes_entry, 2, 1)

        layout.addWidget(QLabel("Seconds from now:"), 3, 0)
        self.seconds_entry = QLineEdit("0")
        layout.addWidget(self.seconds_entry, 3, 1)

        start = QPushButton("Copy timestamp")
        start.clicked.connect(self._copy)
        layout.addWidget(start, 4, 0, 1, 2)

    def _copy(self):
        hours = int(self.hours_entry.text() or 0)
        minutes = int(self.minutes_entry.text() or 0) + hours * 60
        seconds = int(self.seconds_entry.text() or 0) + minutes * 60
        ts = round(time.time() + seconds)

        idx = self.format_combo.currentIndex()
        fmt = self.formats[idx]
        if fmt:
            timestamp = f"<t:{ts}:{fmt}>"
        else:
            timestamp = str(ts)

        QGuiApplication.clipboard().setText(timestamp)
