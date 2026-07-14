import threading

import requests
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from core.auth import get_token


class QueueWindow(QMainWindow):
    _queue_data = Signal(dict)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Queue Monitor")
        self.headers = {"Authorization": get_token()}

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self.queue_box = QGroupBox("Queue Info")
        self.queue_layout = QVBoxLayout(self.queue_box)
        self.queue_labels = {}
        layout.addWidget(self.queue_box)

        self.ship_box = QGroupBox("Ship Info")
        self.ship_layout = QVBoxLayout(self.ship_box)
        self.ship_labels = {"active": QLabel("Ships: Initializing")}
        self.ship_layout.addWidget(self.ship_labels["active"])
        layout.addWidget(self.ship_box)

        for key in (
            "active", "total", "any", "fotd", "we", "gh", "mrcnt", "oos",
            "rpr", "atn", "hc", "sk", "sf", "tt", "ss", "unk",
        ):
            lbl = QLabel(f"{key}: ...")
            self.queue_labels[key] = lbl
            self.queue_layout.addWidget(lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)
        self._queue_data.connect(self._apply_queue)
        self._refresh()

    def _refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            resp = requests.get("http://localhost:5000/queue/members", headers=self.headers, timeout=3)
            if resp.status_code != 200:
                return
            self._queue_data.emit(resp.json())
        except Exception:
            pass

    def _apply_queue(self, data):
        active = "Active" if data.get("active") else "Stopped"
        counts = {k: 0 for k in self.queue_labels}
        counts["active"] = active
        counts["total"] = len(data.get("queue", []))

        for entry in data.get("queue", []):
            act = entry.get("activity", "").lower()
            if "anything" in act:
                counts["any"] += 1
            if "fort of the damned" in act:
                counts["fotd"] += 1
            if "world events" in act:
                counts["we"] += 1
            if "athena" in act:
                counts["atn"] += 1
            if "gold hoarders" in act:
                counts["gh"] += 1
            if "order of souls" in act:
                counts["oos"] += 1
            if "merchant" in act:
                counts["mrcnt"] += 1
            if "sea fort" in act:
                counts["sf"] += 1
            if "sunken kingdom" in act:
                counts["sk"] += 1
            if "fishing" in act:
                counts["hc"] += 1
            if "tall tale" in act:
                counts["tt"] += 1
            if "siren song" in act:
                counts["ss"] += 1
            if "reaper" in act:
                counts["rpr"] += 1
            if not entry.get("is_known") and not entry.get("manual_override"):
                counts["unk"] += 1

        for key, lbl in self.queue_labels.items():
            if key == "active":
                lbl.setText(f"Queue: {counts['active']}")
            elif key == "total":
                lbl.setText(f"Total: {counts['total']}")
            else:
                lbl.setText(f"{key}: {counts.get(key, 0)}")
