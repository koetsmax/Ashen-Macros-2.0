import logging
import sys

from PySide6.QtWidgets import QApplication

from core import auth, updates
from gui import theme
from gui.hub_window import StaffcheckHub

logger = logging.getLogger(__name__)


class App:
    def __init__(self):
        self.local_version = updates.read_local_version()
        self.verified, self.username = auth.check_login()
        logger.info(
            "Login check complete: verified=%s username=%s",
            self.verified,
            self.username or "none",
        )

    def run(self):
        logger.info("Starting Ashen Macros v%s", self.local_version)

        app = QApplication(sys.argv)
        theme.apply_theme(app)

        hub = StaffcheckHub(self.local_version, self.username, self.verified)
        hub.show()

        exit_code = app.exec()
        logger.info("Application exiting with code %s", exit_code)
        sys.exit(exit_code)
