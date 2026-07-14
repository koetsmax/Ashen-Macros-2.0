from PySide6.QtWidgets import QLabel

from gui.views.app_window import AppWindow


class ShipHolderWindow(AppWindow):
    def __init__(self):
        super().__init__("Ship Holder")

    def _build_ui(self) -> None:
        self.root_layout.addWidget(QLabel("Ship Holder — coming soon"))
