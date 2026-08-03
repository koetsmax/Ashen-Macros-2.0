import logging
import threading

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton, QVBoxLayout, QWidget
from shiboken6 import isValid

from core import auth, updates
from core.window_positions import load_window_geometry, save_window_geometry, track_window_geometry
from gui.apps.registry import APP_BY_KEY, APP_REGISTRY, app_allowed, open_app, restore_session_apps
from gui.components.toast import ToastStack
from gui.components.version_badge import VersionBadge
from gui.settings_dialog import SettingsDialog
from gui.views.app_window import AppWindow
from gui.views.staffcheck_view import StaffcheckView
from staffcheck import verification

logger = logging.getLogger(__name__)


class PollWorker(QThread):
    finished = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        connected = auth.check_connection()
        self.finished.emit(connected)


class UpdateWorker(QThread):
    finished = Signal(dict)

    def __init__(self, silent: bool = True, parent=None):
        super().__init__(parent)
        self.silent = silent

    def run(self):
        self.finished.emit(updates.check_for_updates(silent=self.silent))


class StaffcheckHub(QMainWindow):
    _update_download_ready = Signal(str)
    _update_download_failed = Signal()

    def __init__(
        self,
        local_version: str,
        username: str | None,
        verified: bool,
        permissions: list[str] | None = None,
    ):
        super().__init__()
        self.local_version = local_version
        self.username = username
        self.verified = verified
        self.permissions = list(permissions or [])
        self.connected = False
        self._verification_in_progress = False
        self._open_apps: dict[str, AppWindow] = {}
        self._online_version = None
        self._update_worker = None
        self._poll_worker = None
        self._update_request_id = 0
        self._verify_action = None
        self._apps_menu = None
        self._settings_action = None
        self._updates_action = None

        self._update_download_ready.connect(self._start_installer_and_quit)
        self._update_download_failed.connect(self._on_update_download_failed)

        self.setWindowTitle("Ashen Macros")
        # Content is ~700–800px wide and left-aligned; a 960px floor left a
        # permanent empty strip (~toast width) on the right that could not shrink.
        self.setMinimumSize(720, 520)
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

        welcome_header = QHBoxLayout()
        welcome_header.setSpacing(10)

        self.welcome_label = QLabel()
        self.welcome_label.setObjectName("hubWelcome")
        welcome_header.addWidget(self.welcome_label)

        self.not_verified_label = QLabel("Not verified!")
        self.not_verified_label.setObjectName("hubNotVerified")
        welcome_header.addWidget(self.not_verified_label)

        self.verify_button = QPushButton("Verify now!")
        self.verify_button.setObjectName("hubHeaderButton")
        self.verify_button.clicked.connect(self._run_verify)
        welcome_header.addWidget(self.verify_button)

        self.recheck_permissions_button = QPushButton("Recheck permissions")
        self.recheck_permissions_button.setObjectName("hubHeaderButton")
        self.recheck_permissions_button.clicked.connect(self._recheck_permissions)
        welcome_header.addWidget(self.recheck_permissions_button)

        self.retry_connection_button = QPushButton("Retry connection")
        self.retry_connection_button.setObjectName("hubHeaderButton")
        self.retry_connection_button.clicked.connect(self._poll_status)
        welcome_header.addWidget(self.retry_connection_button)

        bar_layout.addLayout(welcome_header)
        self._set_welcome_text(username)
        self._update_welcome_header()
        bar_layout.addStretch()
        outer.addWidget(status_bar)

        self.staffcheck = StaffcheckView(self)
        outer.addWidget(self.staffcheck, stretch=0)
        outer.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        self.version_badge = VersionBadge(local_version)
        footer.addWidget(self.version_badge)
        outer.addLayout(footer)

        # Parent to the window (not central's layout tree) so toasts never
        # participate in size constraints — only setGeometry positioning.
        self.toast_stack = ToastStack(self)
        self.toast_stack.raise_()

        self._build_menu()
        self.staffcheck.build_customize_menu(self.customize_menu)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_status)
        self._poll_timer.start(60000)

        self._poll_status()
        self._check_updates()
        self._session_restored = False
        logger.info(
            "Hub initialized (version=%s, verified=%s, username=%s, permissions=%s)",
            local_version,
            verified,
            username or "none",
            self.permissions,
        )

    def _build_menu(self):
        bar = self.menuBar()
        self._apps_menu = bar.addMenu("Apps")
        self._app_actions = []
        for entry in APP_REGISTRY:
            action = self._apps_menu.addAction(entry.label)
            action.triggered.connect(lambda checked=False, e=entry: open_app(self, e))
            action.setProperty("app_key", entry.window_cls.__name__)
            self._app_actions.append(action)

        self._settings_action = bar.addAction("Settings", self._open_settings)
        self._updates_action = bar.addAction("Check for updates", lambda: self._check_updates(silent=False))
        if not self.verified:
            self._verify_action = bar.addAction("Verify account", self._run_verify)

        self.customize_menu = bar.addMenu("Customize")
        self._update_menu_gating()

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
        if not hasattr(self, "toast_stack"):
            return
        if not self.toast_stack.isVisible():
            return
        width = self.toast_stack.TOAST_WIDTH
        height = self.toast_stack.preferred_height()
        central = self.centralWidget()
        if central is not None:
            top_right = central.mapTo(self, central.rect().topRight())
            x = top_right.x() - width - 20
            y = top_right.y() + 8
        else:
            x = self.width() - width - 20
            y = 36
        self.toast_stack.setGeometry(x, y, width, height)
        self.toast_stack.raise_()
        # Re-measure after geometry settles (second toast often needs this).
        QTimer.singleShot(0, self._relayout_toast_stack)

    def _relayout_toast_stack(self):
        if not hasattr(self, "toast_stack") or not self.toast_stack.isVisible():
            return
        width = self.toast_stack.TOAST_WIDTH
        height = self.toast_stack.preferred_height()
        central = self.centralWidget()
        if central is not None:
            top_right = central.mapTo(self, central.rect().topRight())
            x = top_right.x() - width - 20
            y = top_right.y() + 8
        else:
            x = self.width() - width - 20
            y = 36
        self.toast_stack.setGeometry(x, y, width, height)
        self.toast_stack.raise_()

    def _set_welcome_text(self, username: str | None):
        if username and username != "N/A":
            self.welcome_label.setText(f"Signed in as {username}")
            self.welcome_label.setVisible(True)
        else:
            self.welcome_label.clear()
            self.welcome_label.setVisible(False)

    def _has_permission(self, key: str) -> bool:
        return key in (self.permissions or [])

    def _update_welcome_header(self):
        show_verify = self.connected and not self.verified
        show_no_perms = self.connected and self.verified and not self.permissions
        if show_no_perms:
            self.not_verified_label.setText("No permissions granted")
            self.not_verified_label.setVisible(True)
        elif show_verify:
            self.not_verified_label.setText("Not verified!")
            self.not_verified_label.setVisible(True)
        else:
            self.not_verified_label.setVisible(False)
        self.verify_button.setVisible(show_verify)
        # Only useful while waiting for Max to grant the first permission(s).
        self.recheck_permissions_button.setVisible(
            self.connected and self.verified and not self.permissions
        )
        self.retry_connection_button.setVisible(not self.connected)

    def _update_menu_gating(self):
        menus_enabled = self.verified
        if self._apps_menu is not None:
            self._apps_menu.menuAction().setEnabled(menus_enabled)
        for action in getattr(self, "_app_actions", []):
            entry = APP_BY_KEY.get(str(action.property("app_key") or ""))
            allowed = entry is not None and app_allowed(entry, self.permissions)
            action.setEnabled(menus_enabled and allowed)
            action.setVisible(not menus_enabled or allowed)
        if self._settings_action is not None:
            # Always available — needed to fix API URL when offline.
            self._settings_action.setEnabled(True)
        if self._updates_action is not None:
            self._updates_action.setEnabled(menus_enabled)
        if hasattr(self, "customize_menu"):
            self.customize_menu.menuAction().setEnabled(
                menus_enabled and self._has_permission("staffcheck")
            )
        if hasattr(self, "staffcheck"):
            self.staffcheck._set_customize_enabled(
                menus_enabled and self._has_permission("staffcheck")
            )

        if self.verified and self._verify_action is not None:
            self.menuBar().removeAction(self._verify_action)
            self._verify_action = None
        elif not self.verified:
            if self._verify_action is None:
                self._verify_action = self.menuBar().addAction("Verify account", self._run_verify)
            self._verify_action.setEnabled(self.connected)
            self._verify_action.setVisible(self.connected)

    def _open_settings(self):
        if SettingsDialog(self).exec() == QDialog.DialogCode.Accepted:
            self.staffcheck.rebuild_results_panel()
            # API URL (or other connection settings) may have changed.
            self._poll_status()

    def _run_verify(self):
        if not self.connected:
            return
        self._verification_in_progress = True
        self.toast_stack.show_toast(
            "verify",
            "Verification in progress. Do not touch your PC until it completes.",
            dismiss_ms=0,
        )
        threading.Thread(
            target=verification.start_verification,
            args=(self.staffcheck,),
            kwargs={"on_refresh": self._schedule_refresh_auth},
            daemon=True,
        ).start()

    def _schedule_refresh_auth(self):
        QTimer.singleShot(0, self._refresh_auth)

    def _sync_auth_from_login(self, *, log: bool = False) -> None:
        verified, username, permissions = auth.check_login()
        self.verified = verified
        self.username = username if verified else None
        self.permissions = list(permissions or []) if verified else []
        self._set_welcome_text(self.username)
        if log:
            logger.info(
                "Auth sync: verified=%s username=%s permissions=%s",
                self.verified,
                self.username or "none",
                self.permissions,
            )

    def _refresh_auth(self):
        self._verification_in_progress = False
        self._sync_auth_from_login()
        self._apply_gating()

    def _recheck_permissions(self):
        if not self.connected:
            return
        self._sync_auth_from_login(log=True)
        self._apply_gating()
        if self.verified and self.permissions:
            self.toast_stack.show_toast(
                "permissions_refresh",
                f"Permissions updated: {', '.join(self.permissions)}",
                dismiss_ms=5000,
            )
        elif self.verified:
            self.toast_stack.show_toast(
                "permissions_refresh",
                "Still no permissions granted.",
                dismiss_ms=4000,
            )

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

    @Slot(bool)
    def _on_poll_result(self, connected: bool):
        logger.debug("Status poll result: connected=%s", connected)
        was_connected = self.connected
        self.connected = connected
        if connected and not was_connected:
            self._sync_auth_from_login(log=True)
        self._apply_gating()

    def _apply_gating(self):
        has_staffcheck = self._has_permission("staffcheck")
        ready = self.connected and self.verified and has_staffcheck
        self.staffcheck.set_ready(ready)
        self.staffcheck.setVisible(True)

        if self.connected:
            self.status_label.setText("Connected")
            self.status_label.setObjectName("statusConnected")
        else:
            self.status_label.setText("Not connected")
            self.status_label.setObjectName("statusDisconnected")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self._update_welcome_header()
        self._update_menu_gating()

        if not self.connected:
            self.toast_stack.dismiss("verify")
            self.toast_stack.dismiss("permissions")
        elif not self.verified:
            self.toast_stack.dismiss("permissions")
            if not self._verification_in_progress:
                self.toast_stack.show_toast(
                    "verify",
                    "Verify your account to use the program.\n\n"
                    "After pressing Verify now, do not touch your PC until verification completes.",
                    on_click=self._run_verify,
                    action_label="Verify now",
                    dismiss_ms=0,
                )
        else:
            self._verification_in_progress = False
            self.toast_stack.dismiss("verify")
            if not self.permissions:
                self.toast_stack.show_toast(
                    "permissions",
                    "You are verified, but you do not have any permissions yet.\n"
                    "Ask Max to grant access, then press Recheck permissions.",
                    dismiss_ms=0,
                )
            else:
                self.toast_stack.dismiss("permissions")

        self._close_unauthorized_apps()

    def _close_unauthorized_apps(self):
        for key, win in list(self._open_apps.items()):
            entry = APP_BY_KEY.get(key)
            if entry is None or not app_allowed(entry, self.permissions):
                if isValid(win):
                    win.close()
                self._open_apps.pop(key, None)

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
                f"Update available (v{self._online_version}). "
                "Functionality may be reduced until you update.",
                on_click=self._download_update,
                dismiss_ms=0,
                action_label="Update now",
            )
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
        if not self._online_version:
            return
        self.toast_stack.show_toast(
            "update",
            f"Downloading update (v{self._online_version})…",
            dismiss_ms=0,
        )
        version = self._online_version
        worker = threading.Thread(
            target=self._download_update_worker,
            args=(version,),
            daemon=True,
        )
        worker.start()

    def _download_update_worker(self, online_version: str) -> None:
        try:
            installer_path = updates.download_update(online_version)
        except Exception:
            logger.exception("Update download failed")
            self._update_download_failed.emit()
            return
        # Marshal to the UI thread — QTimer.singleShot from a worker thread is a no-op.
        self._update_download_ready.emit(installer_path)

    def _on_update_download_failed(self) -> None:
        self.toast_stack.show_toast(
            "update",
            "Update download failed. Try again from Check for updates.",
            dismiss_ms=8000,
            on_click=self._download_update,
            action_label="Retry",
        )

    def _start_installer_and_quit(self, installer_path: str) -> None:
        try:
            updates.launch_installer_after_exit(installer_path)
        except Exception:
            logger.exception("Failed to schedule installer")
            self.toast_stack.show_toast(
                "update",
                "Could not start the installer. Try running Ashen.Macro.Installer.exe manually.",
                dismiss_ms=10000,
            )
            return
        self._quit_for_update()

    def _quit_for_update(self) -> None:
        """Fully exit so the installer can overwrite launcher files."""
        from PySide6.QtWidgets import QApplication

        self.toast_stack.show_toast(
            "update",
            "Update downloaded — closing to install…",
            dismiss_ms=0,
        )
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent):
        from core.settings import set_custom_value

        open_keys = [key for key, win in self._open_apps.items() if isValid(win)]
        set_custom_value("SESSION", "open_apps", ",".join(open_keys))
        logger.info("Closing hub with %s open app(s): %s", len(open_keys), open_keys or "none")

        for win in list(self._open_apps.values()):
            if isValid(win):
                save_window_geometry(win, force=True)
                win.close()
        self._open_apps.clear()

        save_window_geometry(self, force=True)
        super().closeEvent(event)
