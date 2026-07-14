from PySide6.QtWidgets import QLabel


class VersionBadge(QLabel):
    def __init__(self, version: str, parent=None):
        super().__init__(f"v{version}", parent)
        self.setObjectName("versionBadge")
        self._outdated = False

    def set_outdated(self, outdated: bool):
        self._outdated = outdated
        self.setProperty("outdated", "true" if outdated else "false")
        self.style().unpolish(self)
        self.style().polish(self)
