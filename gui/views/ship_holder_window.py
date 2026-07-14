from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class ShipHolderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ship Holder")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Ship Holder — coming soon"))
