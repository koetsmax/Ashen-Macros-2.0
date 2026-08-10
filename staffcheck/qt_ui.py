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


_COMMAND_INDEX_MISS_MARKERS = (
    "Application command not found in index",
    "Open the Apps / slash menu once",
)
_last_command_index_warn_at = 0.0


def is_command_index_miss(exc: BaseException | str) -> bool:
    text = str(exc)
    return any(marker in text for marker in _COMMAND_INDEX_MISS_MARKERS)


def warn_command_index_miss(exc: BaseException | str | None = None) -> None:
    """Visible warning when Discord's slash/Apps command index is cold.

    Opening `/` or the Apps menu in that channel is still Discord's reliable
    warm path; allowFetch is best-effort only.
    """
    import time

    from PySide6.QtWidgets import QMessageBox, QWidget

    global _last_command_index_warn_at
    if exc is not None and not is_command_index_miss(exc):
        return
    now = time.monotonic()
    if now - _last_command_index_warn_at < 8.0:
        return
    _last_command_index_warn_at = now

    message = (
        "Discord has not loaded slash commands for this channel yet.\n\n"
        "In Discord, open that channel, type / (or open the Apps menu) once, "
        "then retry the macro."
    )

    def _show() -> None:
        app = QApplication.instance()
        if app is None:
            return
        for widget in app.topLevelWidgets():
            stack = getattr(widget, "toast_stack", None)
            if stack is not None and hasattr(stack, "show_toast"):
                stack.show_toast(
                    "slash_command_index",
                    "Slash commands not loaded — type / once in that Discord "
                    "channel, then retry.",
                    dismiss_ms=14000,
                )
                if hasattr(widget, "_position_toast_stack"):
                    widget._position_toast_stack()
                return
        parent: QWidget | None = None
        for widget in app.topLevelWidgets():
            if isinstance(widget, QWidget) and widget.isVisible():
                parent = widget
                break
        QMessageBox.warning(parent, "Slash commands not loaded", message)

    on_main_thread(_show)


def report_bridge_error(ctx, exc: BaseException) -> None:
    """Show a bridge failure on the nearest status UI for this context."""
    if is_command_index_miss(exc):
        warn_command_index_miss(exc)
    msg = f"Bridge error: {exc}"
    status = getattr(ctx, "status_label", None)
    if status is not None:
        label_set(status, msg, "red")
        return
    emit = getattr(ctx, "_command_status", None)
    if emit is not None:
        try:
            emit.emit(msg)
            return
        except Exception:
            pass
    setter = getattr(ctx, "_set_status", None)
    if callable(setter):
        on_main_thread(lambda: setter(msg))


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
