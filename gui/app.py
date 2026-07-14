import os
import sys

from PySide6.QtWidgets import QApplication

from core import auth, updates
from gui import theme
from gui.hub_window import StaffcheckHub


class App:
    def __init__(self):
        self.local_version = updates.read_local_version()
        self.verified, self.username = auth.check_login()
        print(f"Valid login: {self.verified}")

    def run(self):
        os.makedirs(os.path.expanduser("~/Documents/Ashen Macros"), exist_ok=True)

        app = QApplication(sys.argv)
        theme.apply_theme(app)

        hub = StaffcheckHub(self.local_version, self.username, self.verified)
        hub.show()

        sys.exit(app.exec())
