import re
import time
import webbrowser

import keyboard
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QWidget

from core.settings import read_config


class BanListWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add To Ban List")
        self.delay = float(read_config().get("delay", "15"))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QGridLayout(central)

        layout.addWidget(QLabel("Entire Ban Entry as in AoA:"), 0, 0)
        self.requiem_entry = QLineEdit()
        layout.addWidget(self.requiem_entry, 0, 1, 1, 2)

        layout.addWidget(
            QLabel("Allows multiple bans. The macro automatically separates it into multiple entries."),
            1, 0, 1, 3,
        )

        fields = [
            ("Discord ID:", "discord_id"),
            ("Discord Name:", "discord_name"),
            ("Xbox Gamertag:", "xbox_gt"),
            ("Xbox ID:", "xbox_id"),
        ]
        self.entries = {}
        row = 2
        for label, key in fields:
            layout.addWidget(QLabel(label), row, 0)
            entry = QLineEdit()
            self.entries[key] = entry
            layout.addWidget(entry, row, 1, 1, 2)
            row += 1

        layout.addWidget(QLabel("Server:"), row, 0)
        self.server_combo = QComboBox()
        self.server_combo.addItems(["Athena's Vanguard", "Obsidian", "Sea of Grogs"])
        layout.addWidget(self.server_combo, row, 1, 1, 2)
        row += 1

        layout.addWidget(QLabel("Reason:"), row, 0)
        self.reason_entry = QLineEdit()
        layout.addWidget(self.reason_entry, row, 1, 1, 2)
        row += 1

        requiem_btn = QPushButton("Add Requiem ban")
        requiem_btn.clicked.connect(lambda: self._start_requiem(self.requiem_entry.text()))
        layout.addWidget(requiem_btn, row, 1)

        other_btn = QPushButton("Add Other ban")
        other_btn.clicked.connect(self._add_other)
        layout.addWidget(other_btn, row, 2)

    def _open_sheet(self):
        url = "https://docs.google.com/spreadsheets/d/1V5Z61CKmJoNZn7L3PWziJdbHRVzYuxaZU4qTOIRHfWg/edit#gid=125271616"
        webbrowser.open(url, new=2)
        time.sleep(self.delay)
        keyboard.press_and_release("ctrl + down")
        time.sleep(2)

    def _add_other(self):
        self._open_sheet()
        fields = [
            self.entries["discord_name"],
            self.entries["discord_id"],
            self.entries["xbox_gt"],
            self.entries["xbox_id"],
            self.server_combo,
            self.reason_entry,
        ]
        for field in fields:
            text = field.currentText() if isinstance(field, QComboBox) else field.text()
            for value in text.split(","):
                if value == "Athena's Vanguard":
                    value = "AV"
                elif value == "Sea of Grogs":
                    value = "SoG"
                if value in ("AV", "SoG", "Obsidian"):
                    for _ in self.entries["discord_name"].text().split(","):
                        keyboard.press_and_release("down")
                        time.sleep(0.5)
                        keyboard.write(value.strip())
                else:
                    keyboard.press_and_release("down")
                    time.sleep(0.5)
                    keyboard.write(value.strip())
            time.sleep(0.5)
            keyboard.press_and_release("right")
            time.sleep(0.5)
            keyboard.press_and_release("ctrl + up")
            time.sleep(0.5)

        keyboard.press_and_release("right")
        time.sleep(0.5)
        for entry in self.entries.values():
            entry.clear()
        self.reason_entry.clear()

    def _start_requiem(self, string: str):
        self._open_sheet()
        keyboard.press_and_release("down")

        for ban in string.split(")"):
            if not ban:
                continue
            parts = ban.split("-")
            gamertag = (
                parts[0].split(":")[1].strip()
                if len(parts[0].split(":")) > 1 and parts[0].split(":")[1].strip().count("?") < 3
                else "N/A"
            )
            discord_tag = "N/A"
            xuid = "N/A"
            for i, part in enumerate(parts):
                if i == 2:
                    discord_tag = part.strip() if part.strip().count("?") < 3 else "N/A"
                elif "DC:" in part:
                    xuid = part.replace("DC:", "").strip()
                    if xuid.count("?") >= 3:
                        xuid = "N/A"

            user_id_matches = re.findall(r"\d{17,19}", ban)
            user_id = user_id_matches[-1] if user_id_matches else "N/A"
            reason = parts[-1].strip()

            for val in (discord_tag, user_id, gamertag, xuid, "Requiem", reason):
                keyboard.write(val)
                time.sleep(0.5)
                keyboard.press_and_release("right")

            keyboard.press_and_release("down")
            time.sleep(0.5)
            keyboard.press_and_release("ctrl + left")
            time.sleep(0.5)

        self.requiem_entry.clear()
