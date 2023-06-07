import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QGridLayout, QWidget


def on_button_click():
    print("Button clicked!")


app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("PyQt6 Grid Example")

# Create a central widget and set it as the main window's central widget
central_widget = QWidget()
window.setCentralWidget(central_widget)

# Create a grid layout and set it as the layout for the central widget
grid_layout = QGridLayout(central_widget)

# Create and add widgets to the grid layout
label1 = QLabel("Label 1")
grid_layout.addWidget(label1, 0, 0)  # Add label1 to row 0, column 0

label2 = QLabel("Label 2")
grid_layout.addWidget(label2, 1, 0)  # Add label2 to row 1, column 0

button = QPushButton("Click me!")
button.clicked.connect(on_button_click)
grid_layout.addWidget(button, 2, 0, 1, 2)  # Add button to row 2, column 0, spanning 1 row and 2 columns

window.show()

sys.exit(app.exec())
