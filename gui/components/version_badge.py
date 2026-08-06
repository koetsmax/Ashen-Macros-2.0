from PySide6.QtWidgets import QLabel

from core import updates


class VersionBadge(QLabel):
    def __init__(self, version: str, parent=None):
        display = updates.display_version(version)
        super().__init__(f"v{display}", parent)
        self.setObjectName("versionBadge")
        self._outdated = False

    def set_outdated(self, outdated: bool):
        self._outdated = outdated
        self.setProperty("outdated", "true" if outdated else "false")
        self.style().unpolish(self)
        self.style().polish(self)
