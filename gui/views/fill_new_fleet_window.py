from core.keyboard import clear_typing_bar, execute_command, switch_channel
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QWidget


class MemberInQueue:
    def __init__(self, queuepos, fleetnum, shipnum):
        self.queuepos = queuepos
        self.fleetnum = fleetnum
        self.shipnum = shipnum


class FillNewFleetWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fill New Fleet")
        self.keyboard_lock = __import__("threading").Lock()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QGridLayout(central)

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
        start.clicked.connect(self._start)
        layout.addWidget(start, 7, 0, 1, 2)

    def _start(self):
        fleet = self.fleet_combo.currentText()
        ships = [e.text() for e in self.ship_entries]
        members_in_queue = []
        count = 0

        def add_member(shipnum, ship_text):
            for queuepos in ship_text.split(","):
                members_in_queue.append(MemberInQueue(queuepos.strip(), fleet, shipnum))

        for ship in ships:
            if ship == "":
                count += 1
            else:
                add_member(count + 1, ship)

        for member in members_in_queue:
            member.queuepos = int(member.queuepos)

        members_in_queue.sort(key=lambda x: x.queuepos)

        current_change = 0
        for to_process in members_in_queue:
            actual_queuepos = str(to_process.queuepos + current_change)
            process = ["/process", actual_queuepos, f"{to_process.fleetnum} {to_process.shipnum}"]
            clear_typing_bar()
            execute_command(self, process[0], process[1:])
            current_change -= 1
