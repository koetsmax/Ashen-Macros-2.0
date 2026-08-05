"""Macros Permissions app — grant/revoke keys; gated by `administrator`."""

from __future__ import annotations

import logging
import threading

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.auth import get_token
from core.settings import read_config
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)


class PermissionsWindow(AppWindow):
    DEFAULT_SIZE = (720, 560)

    _loaded = Signal(object)
    _mutated = Signal(object)

    def __init__(self):
        super().__init__("Permissions")
        self._loaded.connect(self._on_loaded)
        self._mutated.connect(self._on_mutated)
        self._busy = False
        self._keys: list[str] = []
        self._users: list[dict] = []
        self._selected_userid: str | None = None
        self._checks: dict[str, QCheckBox] = {}
        self._suppress_toggles = False
        self._reload()

    def _build_ui(self) -> None:
        header = QHBoxLayout()
        self.status_label = QLabel("Loading…")
        self.status_label.setWordWrap(True)
        header.addWidget(self.status_label, stretch=1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._reload)
        header.addWidget(refresh_btn)
        self.root_layout.addLayout(header)

        body = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Users"))
        self.users_list = QListWidget()
        self.users_list.currentItemChanged.connect(self._on_user_selected)
        left.addWidget(self.users_list, stretch=1)
        body.addLayout(left, stretch=2)

        right = QVBoxLayout()
        right.addWidget(QLabel("Permissions"))
        self.user_heading = QLabel("Select a user")
        self.user_heading.setWordWrap(True)
        right.addWidget(self.user_heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.checks_host = QWidget()
        self.checks_layout = QVBoxLayout(self.checks_host)
        self.checks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.checks_host)
        right.addWidget(scroll, stretch=1)

        bulk = QHBoxLayout()
        grant_all_btn = QPushButton("Grant all")
        grant_all_btn.clicked.connect(lambda: self._bulk("grant"))
        bulk.addWidget(grant_all_btn)
        revoke_all_btn = QPushButton("Revoke all")
        revoke_all_btn.clicked.connect(lambda: self._bulk("revoke"))
        bulk.addWidget(revoke_all_btn)
        right.addLayout(bulk)

        body.addLayout(right, stretch=3)
        self.root_layout.addLayout(body, stretch=1)

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": get_token() or ""}

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #c44;" if error else "")

    def _reload(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status("Loading users and keys…")
        threading.Thread(target=self._fetch_all, daemon=True).start()

    def _api_post(self, path: str, payload: dict | None = None) -> dict:
        config = read_config()
        response = requests.post(
            f"{config['api_url']}{path}",
            json=payload or {},
            timeout=30,
            headers=self._auth_headers(),
        )
        if response.status_code == 401:
            return {"ok": False, "error": "Invalid token"}
        if response.status_code == 403:
            return {"ok": False, "error": "Missing administrator permission"}
        if response.status_code != 200:
            return {
                "ok": False,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }
        data = response.json()
        if isinstance(data, dict) and data.get("ok") is False:
            return {
                "ok": False,
                "error": str(data.get("error") or "Request failed"),
            }
        return {"ok": True, "data": data}

    def _fetch_all(self) -> None:
        result: dict = {"ok": False}
        try:
            keys_res = self._api_post("/permissions/keys")
            if not keys_res.get("ok"):
                result = keys_res
            else:
                users_res = self._api_post("/permissions/users")
                if not users_res.get("ok"):
                    result = users_res
                else:
                    result = {
                        "ok": True,
                        "keys": list((keys_res.get("data") or {}).get("keys") or []),
                        "users": list((users_res.get("data") or {}).get("users") or []),
                    }
        except Exception as exc:
            logger.exception("permissions load failed")
            result = {"ok": False, "error": str(exc)}
        self._loaded.emit(result)

    def _on_loaded(self, result: object) -> None:
        self._busy = False
        if not isinstance(result, dict) or not result.get("ok"):
            err = (
                str(result.get("error") or "Load failed")
                if isinstance(result, dict)
                else "Load failed"
            )
            self._set_status(err, error=True)
            return

        self._keys = [str(k) for k in (result.get("keys") or [])]
        self._users = list(result.get("users") or [])
        self._rebuild_checks()
        self._rebuild_user_list()
        self._set_status(f"{len(self._users)} users · {len(self._keys)} keys")

    def _rebuild_user_list(self) -> None:
        prev = self._selected_userid
        self.users_list.blockSignals(True)
        self.users_list.clear()
        select_row = 0
        for i, user in enumerate(self._users):
            userid = str(user.get("userid") or "")
            username = str(user.get("username") or "") or "(no name)"
            item = QListWidgetItem(f"{username}  ·  {userid}")
            item.setData(Qt.ItemDataRole.UserRole, userid)
            self.users_list.addItem(item)
            if prev and userid == prev:
                select_row = i
        self.users_list.blockSignals(False)
        if self.users_list.count():
            self.users_list.setCurrentRow(select_row)
        else:
            self._selected_userid = None
            self._render_selected_user()

    def _rebuild_checks(self) -> None:
        while self.checks_layout.count():
            item = self.checks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checks.clear()
        for key in self._keys:
            check = QCheckBox(key)
            check.toggled.connect(
                lambda checked, k=key: self._on_permission_toggled(k, checked)
            )
            self.checks_layout.addWidget(check)
            self._checks[key] = check
        self._render_selected_user()

    def _user_by_id(self, userid: str | None) -> dict | None:
        if not userid:
            return None
        for user in self._users:
            if str(user.get("userid") or "") == userid:
                return user
        return None

    def _on_user_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        self._selected_userid = (
            str(current.data(Qt.ItemDataRole.UserRole) or "") if current else None
        ) or None
        self._render_selected_user()

    def _render_selected_user(self) -> None:
        user = self._user_by_id(self._selected_userid)
        self._suppress_toggles = True
        try:
            if user is None:
                self.user_heading.setText("Select a user")
                for check in self._checks.values():
                    check.setChecked(False)
                    check.setEnabled(False)
                return

            username = str(user.get("username") or "") or "(no name)"
            userid = str(user.get("userid") or "")
            self.user_heading.setText(f"{username} ({userid})")
            granted = set(user.get("permissions") or [])
            locked = set(user.get("locked_permissions") or [])
            for key, check in self._checks.items():
                check.setEnabled(key not in locked and not self._busy)
                check.setChecked(key in granted)
                if key in locked:
                    check.setToolTip("Owner always has administrator")
                else:
                    check.setToolTip("")
        finally:
            self._suppress_toggles = False

    def _on_permission_toggled(self, key: str, checked: bool) -> None:
        if self._suppress_toggles or self._busy or not self._selected_userid:
            return
        action = "grant" if checked else "revoke"
        self._mutate(action, key)

    def _bulk(self, action: str) -> None:
        if self._busy or not self._selected_userid:
            return
        self._mutate(action, "all")

    def _mutate(self, action: str, permission: str) -> None:
        userid = self._selected_userid
        if not userid:
            return
        self._busy = True
        self._set_status(f"{action.title()}ing `{permission}`…")
        for check in self._checks.values():
            check.setEnabled(False)
        threading.Thread(
            target=self._run_mutate,
            args=(action, userid, permission),
            daemon=True,
        ).start()

    def _run_mutate(self, action: str, userid: str, permission: str) -> None:
        path = "/permissions/grant" if action == "grant" else "/permissions/revoke"
        result: dict = {"ok": False}
        try:
            res = self._api_post(
                path, {"userid": userid, "permission": permission}
            )
            if not res.get("ok"):
                result = res
            else:
                data = res.get("data") or {}
                result = {
                    "ok": True,
                    "userid": userid,
                    "permissions": list(data.get("permissions") or []),
                }
        except Exception as exc:
            logger.exception("permissions %s failed", action)
            result = {"ok": False, "error": str(exc)}
        self._mutated.emit(result)

    def _on_mutated(self, result: object) -> None:
        self._busy = False
        if not isinstance(result, dict) or not result.get("ok"):
            err = (
                str(result.get("error") or "Update failed")
                if isinstance(result, dict)
                else "Update failed"
            )
            self._set_status(err, error=True)
            self._render_selected_user()
            return

        userid = str(result.get("userid") or "")
        permissions = list(result.get("permissions") or [])
        for user in self._users:
            if str(user.get("userid") or "") == userid:
                user["permissions"] = permissions
                break
        self._set_status("Updated")
        self._render_selected_user()
