from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Toast(QFrame):
    def __init__(
        self,
        message: str,
        parent: QWidget,
        on_click=None,
        on_removed=None,
        dismiss_ms: int = 8000,
        action_label: str = "Open",
    ):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._on_removed = on_removed
        self._dismissing = False
        self._removed = False
        self._timer = None
        self._action_btn = None
        self._fade_anim = None
        self._dismiss_anim = None

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10)
        self._layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        header.addWidget(self.label, stretch=1)

        dismiss_btn = QPushButton("\u00d7")
        dismiss_btn.setObjectName("toastDismiss")
        dismiss_btn.setFlat(True)
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.setToolTip("Dismiss")
        dismiss_btn.setFixedSize(22, 22)
        dismiss_btn.clicked.connect(self.request_dismiss)
        header.addWidget(dismiss_btn, alignment=Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(header)

        self._set_action_button(on_click, action_label)
        self._set_auto_dismiss(dismiss_ms)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self._fade_in()
        QTimer.singleShot(0, self._sync_label_width)

    def _content_width(self) -> int:
        return ToastStack.TOAST_WIDTH - 28 - 22 - 8

    def _sync_label_width(self):
        width = ToastStack.TOAST_WIDTH
        self.setFixedWidth(width)
        self.label.setFixedWidth(self._content_width())
        self.label.updateGeometry()
        self.updateGeometry()

    def update_content(
        self,
        message: str,
        on_click=None,
        dismiss_ms: int = 8000,
        action_label: str = "Open",
    ):
        if self._dismissing:
            return
        self.label.setText(message)
        self._set_action_button(on_click, action_label)
        self._set_auto_dismiss(dismiss_ms)
        self._opacity.setOpacity(1.0)
        self._sync_label_width()

    def _set_action_button(self, on_click, action_label: str = "Open"):
        if on_click:
            if self._action_btn is None:
                self._action_btn = QPushButton(action_label)
                self._action_btn.setObjectName("toastAction")
                self._action_btn.setFlat(True)
                self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self._action_btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                self._layout.addWidget(self._action_btn)
            else:
                self._action_btn.setText(action_label)
            try:
                self._action_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self._action_btn.clicked.connect(on_click)
            self._action_btn.setVisible(True)
        elif self._action_btn is not None:
            self._action_btn.setVisible(False)

    def _set_auto_dismiss(self, dismiss_ms: int):
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if dismiss_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.request_dismiss)
            self._timer.start(dismiss_ms)

    def request_dismiss(self):
        if self._dismissing:
            return
        self._dismissing = True
        if self._timer is not None:
            self._timer.stop()
        self._dismiss()

    def _stop_animation(self, anim: QPropertyAnimation | None):
        if anim is None:
            return
        try:
            anim.finished.disconnect()
        except RuntimeError:
            pass
        anim.stop()

    def _fade_in(self):
        self._stop_animation(self._fade_anim)
        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_in_finished)
        self._fade_anim.start()

    def _on_fade_in_finished(self):
        if not self._removed:
            self._opacity.setOpacity(1.0)

    def _dismiss(self):
        self._stop_animation(self._fade_anim)
        self._fade_anim = None
        self._stop_animation(self._dismiss_anim)
        self._dismiss_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._dismiss_anim.setDuration(200)
        self._dismiss_anim.setStartValue(self._opacity.opacity())
        self._dismiss_anim.setEndValue(0.0)
        self._dismiss_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._dismiss_anim.finished.connect(self._finish_dismiss)
        self._dismiss_anim.start()

    def _finish_dismiss(self):
        if self._removed:
            return
        self._removed = True
        self._stop_animation(self._fade_anim)
        self._stop_animation(self._dismiss_anim)
        self._fade_anim = None
        self._dismiss_anim = None
        if self._on_removed:
            self._on_removed()
        self.deleteLater()


class ToastStack(QWidget):
    TOAST_WIDTH = 360

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self._layout = layout
        self._active: dict[str, Toast] = {}

    def show_toast(
        self,
        key: str,
        message: str,
        on_click=None,
        dismiss_ms: int = 8000,
        action_label: str = "Open",
    ):
        existing = self._active.get(key)
        if existing is not None:
            if not existing._dismissing:
                existing.update_content(message, on_click, dismiss_ms, action_label)
                return
            existing._on_removed = None
            self._layout.removeWidget(existing)
            existing.deleteLater()
            self._active.pop(key, None)

        toast = Toast(
            message,
            self,
            on_click=on_click,
            dismiss_ms=dismiss_ms,
            action_label=action_label,
        )

        def _removed(t=toast):
            if self._active.get(key) is t:
                self._active.pop(key, None)

        toast._on_removed = _removed
        self._layout.insertWidget(0, toast)
        self._active[key] = toast
        toast._sync_label_width()

    def sync_toast_widths(self):
        for toast in self._active.values():
            toast._sync_label_width()

    def dismiss(self, key: str):
        toast = self._active.get(key)
        if toast:
            toast.request_dismiss()
