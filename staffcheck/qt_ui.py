from PySide6.QtWidgets import QApplication

from gui.theme import resolve_color, TEXT


def flush():
    QApplication.processEvents()


def label_set(label, text: str, color: str = ""):
    label.setText(text)
    if color:
        label.setStyleSheet(f"color: {resolve_color(color)}; background: transparent;")
    else:
        label.setStyleSheet(f"color: {TEXT}; background: transparent;")


def btn_enable(btn, on: bool = True):
    btn.setEnabled(on)


def btn_config(btn, text: str | None = None, on_click=None):
    if text is not None:
        btn.setText(text)
    if on_click is not None:
        try:
            btn.clicked.disconnect()
        except RuntimeError:
            pass
        btn.clicked.connect(on_click)


class Var:
    def __init__(self, getter, setter):
        self._get = getter
        self._set = setter

    def get(self):
        return self._get()

    def set(self, value):
        self._set(value)
