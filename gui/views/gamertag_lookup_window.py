from __future__ import annotations

import logging
import re
import threading

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from core.auth import get_token
from core.settings import read_config
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")
_XUID_RE = re.compile(r"^\d{5,20}$")


class GamertagLookupWindow(AppWindow):
    """Linked Xbox gamertag + mutual servers (ms) and XUID → gamertag (gt)."""

    DEFAULT_SIZE = (480, 560)

    _profile_done = Signal(object)
    _xuid_done = Signal(object)

    def __init__(self):
        super().__init__("Gamertag / mutuals")
        self._profile_done.connect(self._on_profile_done)
        self._xuid_done.connect(self._on_xuid_done)
        self._busy_profile = False
        self._busy_xuid = False

    def _build_ui(self) -> None:
        # --- Discord profile (ms + linked GT) ---
        profile_box = QGroupBox("Discord member")
        profile_layout = QVBoxLayout(profile_box)

        id_row = QHBoxLayout()
        self.user_id_entry = QLineEdit()
        self.user_id_entry.setPlaceholderText("Discord user ID")
        self.user_id_entry.returnPressed.connect(self._lookup_profile)
        id_row.addWidget(self.user_id_entry, stretch=1)
        self.profile_btn = QPushButton("Lookup")
        self.profile_btn.clicked.connect(self._lookup_profile)
        id_row.addWidget(self.profile_btn)
        profile_layout.addLayout(id_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.discord_name_label = QLabel("—")
        self.discord_name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Discord:", self.discord_name_label)

        self.gamertag_label = QLabel("—")
        self.gamertag_label.setWordWrap(True)
        self.gamertag_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Linked Xbox:", self.gamertag_label)
        profile_layout.addLayout(form)

        profile_layout.addWidget(QLabel("Mutual servers"))
        self.mutuals_list = QListWidget()
        self.mutuals_list.setMinimumHeight(140)
        self.mutuals_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        profile_layout.addWidget(self.mutuals_list, stretch=1)

        self.root_layout.addWidget(profile_box, stretch=1)

        # --- XUID → gamertag (gt) ---
        xuid_box = QGroupBox("XUID → gamertag")
        xuid_layout = QVBoxLayout(xuid_box)

        xuid_row = QHBoxLayout()
        self.xuid_entry = QLineEdit()
        self.xuid_entry.setPlaceholderText("Xbox XUID")
        self.xuid_entry.returnPressed.connect(self._lookup_xuid)
        xuid_row.addWidget(self.xuid_entry, stretch=1)
        self.xuid_btn = QPushButton("Lookup")
        self.xuid_btn.clicked.connect(self._lookup_xuid)
        xuid_row.addWidget(self.xuid_btn)
        xuid_layout.addLayout(xuid_row)

        xuid_form = QFormLayout()
        self.xuid_result_label = QLabel("—")
        self.xuid_result_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        xuid_form.addRow("Gamertag:", self.xuid_result_label)
        xuid_layout.addLayout(xuid_form)

        self.root_layout.addWidget(xuid_box)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #c44;" if error else "")

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": get_token() or ""}

    def _lookup_profile(self) -> None:
        if self._busy_profile:
            return
        raw = self.user_id_entry.text().strip()
        # Allow paste of mention <@id> or <@!id>
        mention = re.fullmatch(r"<@!?(\d{17,20})>", raw)
        if mention:
            raw = mention.group(1)
            self.user_id_entry.setText(raw)
        if not _SNOWFLAKE_RE.match(raw):
            self._set_status("Enter a valid Discord user ID.", error=True)
            return

        self._busy_profile = True
        self.profile_btn.setEnabled(False)
        self._set_status("Looking up Discord profile…")
        threading.Thread(
            target=self._fetch_profile, args=(raw,), daemon=True
        ).start()

    def _fetch_profile(self, user_id: str) -> None:
        result: dict = {}
        try:
            config = read_config()
            response = requests.post(
                f"{config['api_url']}/lookup/profile",
                json={"userID": user_id},
                timeout=30,
                headers=self._auth_headers(),
            )
            if response.status_code == 200:
                result = {"ok": True, "data": response.json()}
            else:
                result = {
                    "ok": False,
                    "error": response.text.strip() or f"HTTP {response.status_code}",
                }
        except requests.RequestException as e:
            logger.warning("lookup/profile request failed: %s", e)
            result = {"ok": False, "error": "Could not reach the API."}
        except Exception:
            logger.exception("lookup/profile failed")
            result = {"ok": False, "error": "Lookup failed."}
        self._profile_done.emit(result)

    def _on_profile_done(self, result: object) -> None:
        self._busy_profile = False
        self.profile_btn.setEnabled(True)
        if not isinstance(result, dict):
            self._set_status("Lookup failed.", error=True)
            return
        if not result.get("ok"):
            self.discord_name_label.setText("—")
            self.gamertag_label.setText("—")
            self.mutuals_list.clear()
            self._set_status(str(result.get("error") or "Lookup failed."), error=True)
            return

        data = result.get("data") or {}
        name = data.get("discord_name") or "—"
        self.discord_name_label.setText(str(name))

        linked = data.get("linked_xbox") or []
        if linked:
            self.gamertag_label.setText("\n".join(str(g) for g in linked))
        else:
            self.gamertag_label.setText("Not linked")

        self.mutuals_list.clear()
        guilds = data.get("mutual_guilds") or []
        if guilds:
            self.mutuals_list.addItems([str(g) for g in guilds])
        else:
            self.mutuals_list.addItem("No mutual servers")

        self._set_status(f"Loaded {name} — {len(guilds)} mutual server(s).")

    def _lookup_xuid(self) -> None:
        if self._busy_xuid:
            return
        xuid = self.xuid_entry.text().strip()
        if not _XUID_RE.match(xuid):
            self._set_status("Enter a valid Xbox XUID (digits only).", error=True)
            return

        self._busy_xuid = True
        self.xuid_btn.setEnabled(False)
        self._set_status("Looking up XUID…")
        threading.Thread(target=self._fetch_xuid, args=(xuid,), daemon=True).start()

    def _fetch_xuid(self, xuid: str) -> None:
        result: dict = {}
        try:
            config = read_config()
            response = requests.post(
                f"{config['api_url']}/lookup/xuid",
                json={"xuid": xuid},
                timeout=60,
                headers=self._auth_headers(),
            )
            if response.status_code == 200:
                result = {"ok": True, "data": response.json()}
            else:
                try:
                    body = response.json()
                    err = body.get("error") or response.text
                except Exception:
                    err = response.text.strip() or f"HTTP {response.status_code}"
                result = {"ok": False, "error": str(err)}
        except requests.RequestException as e:
            logger.warning("lookup/xuid request failed: %s", e)
            result = {"ok": False, "error": "Could not reach the API."}
        except Exception:
            logger.exception("lookup/xuid failed")
            result = {"ok": False, "error": "Lookup failed."}
        self._xuid_done.emit(result)

    def _on_xuid_done(self, result: object) -> None:
        self._busy_xuid = False
        self.xuid_btn.setEnabled(True)
        if not isinstance(result, dict):
            self._set_status("Lookup failed.", error=True)
            return
        if not result.get("ok"):
            self.xuid_result_label.setText("—")
            err = str(result.get("error") or "Lookup failed.")
            if err == "rate_limited":
                err = "Xbox API rate limited — try again in a moment."
            elif err == "not_found":
                err = "No gamertag found for that XUID."
            self._set_status(err, error=True)
            return

        data = result.get("data") or {}
        gt = data.get("gamertag") or "—"
        self.xuid_result_label.setText(str(gt))
        self._set_status(f"XUID {data.get('xuid')} → {gt}")
