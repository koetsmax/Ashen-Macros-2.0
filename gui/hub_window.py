import logging
import threading

from PySide6.QtCore import QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QVBoxLayout, QWidget
from shiboken6 import isValid

from core import auth, updates
from core.window_positions import load_window_geometry, save_window_geometry, track_window_geometry
from gui.apps.registry import APP_REGISTRY, open_app, restore_session_apps
from gui.components.toast import ToastStack
from gui.components.version_badge import VersionBadge
from gui.settings_dialog import SettingsDialog
from gui.views.staffcheck_view import StaffcheckView
from staffcheck import verification

logger = logging.getLogger(__name__)


class PollWorker(QThread):
    finished = Signal(bool, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        connected = auth.check_connection()
        verified, username = auth.check_login()
        self.finished.emit(connected, verified, username or "")


class UpdateWorker(QThread):
    finished = Signal(dict)

    def __init__(self, silent: bool = True, parent=None):
        super().__init__(parent)
        self.silent = silent

    def run(self):
        self.finished.emit(updates.check_for_updates(silent=self.silent))


class StaffcheckHub(QMainWindow):
    def __init__(self, local_version: str, username: str | None, verified: bool):
        super().__init__()
        self.local_version = local_version
        self.username = username
        self.verified = verified
        self.connected = False
        self._open_apps: dict[str, QMainWindow] = {}
        self._online_version = None
        self._update_worker = None
        self._poll_worker = None
        self._update_request_id = 0

        self.setWindowTitle("Ashen Macros")
        self.setMinimumSize(960, 640)
        load_window_geometry(self)
        track_window_geometry(self)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        status_bar = QFrame()
        status_bar.setObjectName("hubStatusBar")
        bar_layout = QHBoxLayout(status_bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(12)

        self.status_label = QLabel("Checking...")
        self.status_label.setObjectName("hubApiStatus")
        bar_layout.addWidget(self.status_label)

        self.welcome_label = QLabel()
        self.welcome_label.setObjectName("hubWelcome")
        self._set_welcome_text(username)
        bar_layout.addWidget(self.welcome_label)
        bar_layout.addStretch()
        outer.addWidget(status_bar)

        self.staffcheck = StaffcheckView(self)
        outer.addWidget(self.staffcheck)

        footer = QHBoxLayout()
        footer.addStretch()
        self.version_badge = VersionBadge(local_version)
        footer.addWidget(self.version_badge)
        outer.addLayout(footer)

        self.toast_stack = ToastStack(central)
        self.toast_stack.setParent(central)
        self.toast_stack.raise_()

        self._build_menu()
        self.staffcheck.build_customize_menu(self.customize_menu)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_status)
        self._poll_timer.start(10000)

        self._poll_status()
        self._check_updates()
        self._session_restored = False
        logger.info(
            "Hub initialized (version=%s, verified=%s, username=%s)",
            local_version,
            verified,
            username or "none",
        )

    def _build_menu(self):
        bar = self.menuBar()
        apps_menu = bar.addMenu("Apps")
        for entry in APP_REGISTRY:
            action = apps_menu.addAction(entry.label)
            action.triggered.connect(lambda checked=False, e=entry: open_app(self, e))

        bar.addAction("Settings", self._open_settings)
        bar.addAction("Check for updates", lambda: self._check_updates(silent=False))
        if not self.verified:
            bar.addAction("Verify account", self._run_verify)

        self.customize_menu = bar.addMenu("Customize")

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._position_toast_stack()
        if not self._session_restored:
            self._session_restored = True
            restore_session_apps(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast_stack()

    def _position_toast_stack(self):
        if hasattr(self, "toast_stack"):
            self.toast_stack.setGeometry(
                self.width() - 300, 36, 280, max(120, self.height() - 80)
            )
            self.toast_stack.raise_()

    def _set_welcome_text(self, username: str | None):
        if username and username != "N/A":
            self.welcome_label.setText(f"Signed in as {username}")
            self.welcome_label.setVisible(True)
        else:
            self.welcome_label.clear()
            self.welcome_label.setVisible(False)

    def _open_settings(self):
        SettingsDialog(self).exec()

    def _run_verify(self):
        threading.Thread(
            target=verification.start_verification,
            args=(self.staffcheck,),
            kwargs={"on_refresh": self._schedule_refresh_auth},
            daemon=True,
        ).start()

    def _schedule_refresh_auth(self):
        QTimer.singleShot(0, self._refresh_auth)

    def _refresh_auth(self):
        self.verified, self.username = auth.check_login()
        self._apply_gating()

    def _worker_running(self, worker: QThread | None) -> bool:
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

    def _release_poll_worker(self, worker: PollWorker):
        if self._poll_worker is worker:
            self._poll_worker = None
        worker.deleteLater()

    def _poll_status(self):
        if self._worker_running(self._poll_worker):
            logger.debug("Skipping status poll; previous worker still running")
            return
        worker = PollWorker(self)
        worker.finished.connect(self._on_poll_result)
        worker.finished.connect(lambda *_args, w=worker: self._release_poll_worker(w))
        worker.start()
        self._poll_worker = worker

    @Slot(bool, bool, str)
    def _on_poll_result(self, connected: bool, verified: bool, username: str):
        logger.debug(
            "Status poll result: connected=%s verified=%s username=%s",
            connected,
            verified,
            username or "none",
        )
        self.connected = connected
        self.verified = verified
        if username:
            self.username = username
        self._set_welcome_text(self.username)
        self._apply_gating()

    def _apply_gating(self):
        ready = self.connected and self.verified
        self.staffcheck.set_ready(ready)

        if self.connected:
            self.status_label.setText("Connected")
            self.status_label.setObjectName("statusConnected")
        else:
            self.status_label.setText("Not connected")
            self.status_label.setObjectName("statusDisconnected")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if not self.verified:
            self.toast_stack.show_toast(
                "verify",
                "Verify now to use the program",
                on_click=self._run_verify,
                dismiss_ms=0,
            )
        else:
            self.toast_stack.dismiss("verify")

    def _check_updates(self, silent: bool = True):
        if self._worker_running(self._update_worker):
            if not silent:
                logger.debug("Skipping update check; previous worker still running")
            return

        self._update_request_id += 1
        request_id = self._update_request_id

        if not silent:
            self.toast_stack.show_toast("update_check", "Checking for updates...", dismiss_ms=0)

        worker = UpdateWorker(silent=silent, parent=self)
        worker.finished.connect(
            lambda result, rid=request_id, sil=silent, w=worker: self._on_update_worker_finished(w, result, sil, rid)
        )
        worker.start()
        self._update_worker = worker

    def _on_update_worker_finished(self, worker: UpdateWorker, result: dict, silent: bool, request_id: int):
        if self._update_worker is worker:
            self._update_worker = None
        worker.deleteLater()
        self._on_update_result(result, silent, request_id)

    def _on_update_result(self, result: dict, silent: bool, request_id: int):
        if request_id != self._update_request_id:
            return

        kind = result.get("kind")
        self.toast_stack.dismiss("update_check")
        logger.info("Update check result: kind=%s silent=%s", kind, silent)

        if kind == "outdated":
            self._online_version = result["online_version"]
            self.version_badge.set_outdated(True)
            self.toast_stack.show_toast(
                "update",
                f"Update available (v{self._online_version})",
                on_click=self._download_update,
                dismiss_ms=0,
            )
        elif kind == "elevate":
            from pyuac import runAsAdmin
            self.close()
            runAsAdmin()
        elif not silent:
            if kind == "current":
                self.version_badge.set_outdated(False)
                self.toast_stack.dismiss("update")
                self.toast_stack.show_toast(
                    "update_status",
                    "You're on the latest version.",
                    dismiss_ms=6000,
                )
            elif kind == "dev":
                self.toast_stack.show_toast(
                    "update_status",
                    "You're on a dev version — ahead of the latest release.",
                    dismiss_ms=6000,
                )
            else:
                self.toast_stack.show_toast(
                    "update_status",
                    "Couldn't check for updates right now.",
                    dismiss_ms=6000,
                )

    def _download_update(self):
        if self._online_version:
            updates.download_update(self._online_version)
            self.close()

    def closeEvent(self, event: QCloseEvent):
        from core.settings import set_custom_value

        open_keys = [key for key, win in self._open_apps.items() if isValid(win)]
        set_custom_value("SESSION", "open_apps", ",".join(open_keys))
        logger.info("Closing hub with %s open app(s): %s", len(open_keys), open_keys or "none")

        for win in list(self._open_apps.values()):
            if isValid(win):
                save_window_geometry(win)
                win.close()
        self._open_apps.clear()

        save_window_geometry(self)
        super().closeEvent(event)
