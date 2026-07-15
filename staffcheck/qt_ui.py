from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from gui.theme import resolve_color, TEXT


class _MainThreadInvoker(QObject):
    """Marshal callables onto the Qt main thread via a queued signal."""

    _invoke = Signal(object)

    def __init__(self):
        super().__init__()
        self._invoke.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run(self, fn) -> None:
        fn()

    def submit(self, fn) -> None:
        self._invoke.emit(fn)


_invoker: _MainThreadInvoker | None = None


def init_main_thread_bridge() -> None:
    """Create the main-thread invoker. Call once from the Qt GUI thread."""
    global _invoker
    if _invoker is None:
        _invoker = _MainThreadInvoker()


def on_main_thread(fn) -> None:
    app = QApplication.instance()
    if app is None or QThread.currentThread() == app.thread():
        fn()
        return
    if _invoker is None:
        # Safety net if init was skipped: still try a queued timer on the app object.
        QTimer.singleShot(0, app, fn)
        return
    _invoker.submit(fn)


def label_set(label, text: str, color: str = ""):
    def apply():
        label.setText(text)
        if color:
            label.setStyleSheet(f"color: {resolve_color(color)}; background: transparent;")
        else:
            label.setStyleSheet(f"color: {TEXT}; background: transparent;")

    on_main_thread(apply)


def btn_enable(btn, on: bool = True):
    on_main_thread(lambda: btn.setEnabled(on))


def btn_config(btn, text: str | None = None, on_click=None):
    def apply():
        if text is not None:
            btn.setText(text)
        if on_click is not None:
            try:
                btn.clicked.disconnect()
            except RuntimeError:
                pass
            btn.clicked.connect(on_click)

    on_main_thread(apply)


class Var:
    def __init__(self, getter, setter):
        self._get = getter
        self._set = setter

    def get(self):
        return self._get()

    def set(self, value):
        self._set(value)
