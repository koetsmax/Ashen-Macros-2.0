from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from core.auth import auth_headers
from core.settings import read_config
from gui import theme
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")
_XUID_RE = re.compile(r"^\d{5,20}$")


def _fmt_ts(unix: int | None) -> str:
    if not unix:
        return "—"
    try:
        return datetime.fromtimestamp(int(unix), tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except (TypeError, ValueError, OSError):
        return str(unix)


def _section_header(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionHeader")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("sectionDivider")
    line.setFixedHeight(1)
    return line


class GamertagLookupWindow(AppWindow):
    """Linked Xbox gamertag + mutual servers (ms), member info (mi), XUID → GT."""

    DEFAULT_SIZE = (520, 720)

    _profile_done = Signal(object)
    _xuid_done = Signal(object)
    _mi_done = Signal(object)

    def __init__(self):
        super().__init__("Gamertag / mutuals")
        self._profile_done.connect(self._on_profile_done)
        self._xuid_done.connect(self._on_xuid_done)
        self._mi_done.connect(self._on_mi_done)
        self._busy_profile = False
        self._busy_xuid = False
        self._busy_mi = False
        self._last_user_id = ""
        self._mutual_details: list[dict] = []

    def _build_ui(self) -> None:
        self.root_layout.addWidget(_section_header("Discord member"))

        id_row = QHBoxLayout()
        self.user_id_entry = QLineEdit()
        self.user_id_entry.setPlaceholderText("Discord user ID")
        self.user_id_entry.returnPressed.connect(self._lookup_profile)
        id_row.addWidget(self.user_id_entry, stretch=1)
        self.profile_btn = QPushButton("Lookup")
        self.profile_btn.clicked.connect(self._lookup_profile)
        id_row.addWidget(self.profile_btn)
        self.root_layout.addLayout(id_row)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
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
        self.root_layout.addLayout(form)

        self.root_layout.addWidget(_divider())

        mutuals_header = QHBoxLayout()
        mutuals_header.addWidget(_section_header("Mutual servers"))
        mutuals_header.addStretch(1)
        self.mi_btn = QPushButton("Member info (mi)")
        self.mi_btn.setToolTip(
            "Scan the selected mutual server for this member’s messages "
            "(same as Discord {p}mi)."
        )
        self.mi_btn.setEnabled(False)
        self.mi_btn.clicked.connect(self._lookup_mi)
        mutuals_header.addWidget(self.mi_btn)
        self.root_layout.addLayout(mutuals_header)

        hint = QLabel("Select a server, then Member info — or double-click a row.")
        hint.setObjectName("resultSectionSummary")
        self.root_layout.addWidget(hint)

        self.mutuals_table = QTableWidget(0, 2)
        self.mutuals_table.setObjectName("mutualServersTable")
        self.mutuals_table.setHorizontalHeaderLabels(["Server", "Tag"])
        self.mutuals_table.verticalHeader().setVisible(False)
        self.mutuals_table.setShowGrid(False)
        self.mutuals_table.setAlternatingRowColors(True)
        self.mutuals_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.mutuals_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.mutuals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mutuals_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        header = self.mutuals_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setHighlightSections(False)
        self.mutuals_table.setMinimumHeight(140)
        self.mutuals_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.mutuals_table.setStyleSheet(
            f"""
            QTableWidget#mutualServersTable {{
                background-color: {theme.BASE};
                alternate-background-color: {theme.SURFACE0};
                border: 1px solid {theme.SURFACE1};
                border-radius: 8px;
                gridline-color: transparent;
                outline: none;
            }}
            QTableWidget#mutualServersTable::item {{
                padding: 6px 10px;
                border: none;
            }}
            QTableWidget#mutualServersTable::item:selected {{
                background-color: {theme.SURFACE2};
                color: {theme.TEXT};
            }}
            QHeaderView::section {{
                background-color: {theme.SURFACE0};
                color: {theme.SUBTEXT0};
                border: none;
                border-bottom: 1px solid {theme.SURFACE1};
                padding: 6px 10px;
                font-weight: 600;
            }}
            """
        )
        self.mutuals_table.itemSelectionChanged.connect(self._sync_mi_button)
        self.mutuals_table.cellDoubleClicked.connect(
            lambda *_args: self._lookup_mi()
        )
        self.root_layout.addWidget(self.mutuals_table, stretch=1)

        self.root_layout.addWidget(_section_header("Member info"))
        self.mi_result = QTextEdit()
        self.mi_result.setObjectName("memberInfoResult")
        self.mi_result.setReadOnly(True)
        self.mi_result.setPlaceholderText(
            "Select a mutual server and click Member info (mi), or double-click a row."
        )
        self.mi_result.setMinimumHeight(140)
        self.mi_result.setStyleSheet(
            f"""
            QTextEdit#memberInfoResult {{
                background-color: {theme.BASE};
                border: 1px solid {theme.SURFACE1};
                border-radius: 8px;
                padding: 8px;
                color: {theme.TEXT};
            }}
            """
        )
        self.root_layout.addWidget(self.mi_result, stretch=2)

        self.root_layout.addWidget(_divider())
        self.root_layout.addWidget(_section_header("XUID → gamertag"))

        xuid_row = QHBoxLayout()
        self.xuid_entry = QLineEdit()
        self.xuid_entry.setPlaceholderText("Xbox XUID")
        self.xuid_entry.returnPressed.connect(self._lookup_xuid)
        xuid_row.addWidget(self.xuid_entry, stretch=1)
        self.xuid_btn = QPushButton("Lookup")
        self.xuid_btn.clicked.connect(self._lookup_xuid)
        xuid_row.addWidget(self.xuid_btn)
        self.root_layout.addLayout(xuid_row)

        xuid_form = QFormLayout()
        xuid_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.xuid_result_label = QLabel("—")
        self.xuid_result_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        xuid_form.addRow("Gamertag:", self.xuid_result_label)
        self.root_layout.addLayout(xuid_form)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.root_layout.addWidget(self.status_label)

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {theme.RED};" if error else f"color: {theme.SUBTEXT0};"
        )

    def _auth_headers(self) -> dict[str, str]:
        return auth_headers()

    def _sync_mi_button(self) -> None:
        can = (
            bool(self._last_user_id)
            and self.mutuals_table.currentRow() >= 0
            and bool(self._selected_guild_id())
            and not self._busy_mi
        )
        self.mi_btn.setEnabled(can)

    def _selected_guild_id(self) -> str:
        row = self.mutuals_table.currentRow()
        if row < 0:
            return ""
        item = self.mutuals_table.item(row, 0)
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _clear_mutuals(self) -> None:
        self.mutuals_table.setRowCount(0)

    def _add_mutual_row(self, name: str, tag: str = "", guild_id: str = "") -> None:
        row = self.mutuals_table.rowCount()
        self.mutuals_table.insertRow(row)
        name_item = QTableWidgetItem(name or "—")
        name_item.setData(Qt.ItemDataRole.UserRole, guild_id)
        tag_item = QTableWidgetItem(tag or "—")
        tag_item.setForeground(QBrush(QColor(theme.SUBTEXT0 or "#a8a8a8")))
        self.mutuals_table.setItem(row, 0, name_item)
        self.mutuals_table.setItem(row, 1, tag_item)

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
                result = {"ok": True, "data": response.json(), "user_id": user_id}
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
            self._last_user_id = ""
            self._mutual_details = []
            self.discord_name_label.setText("—")
            self.gamertag_label.setText("—")
            self._clear_mutuals()
            self.mi_result.clear()
            self._sync_mi_button()
            self._set_status(str(result.get("error") or "Lookup failed."), error=True)
            return

        data = result.get("data") or {}
        self._last_user_id = str(result.get("user_id") or "").strip()
        name = data.get("discord_name") or "—"
        self.discord_name_label.setText(str(name))

        linked = data.get("linked_xbox") or []
        if linked:
            self.gamertag_label.setStyleSheet("")
            self.gamertag_label.setText("\n".join(str(g) for g in linked))
        else:
            self.gamertag_label.setStyleSheet(f"color: {theme.RED};")
            self.gamertag_label.setText("Not linked")

        self._clear_mutuals()
        self.mi_result.clear()
        detail = data.get("mutual_guilds_detail") or []
        self._mutual_details = list(detail) if isinstance(detail, list) else []
        if self._mutual_details:
            for entry in self._mutual_details:
                if not isinstance(entry, dict):
                    continue
                self._add_mutual_row(
                    str(entry.get("name") or entry.get("label") or ""),
                    str(entry.get("tag") or ""),
                    str(entry.get("id") or ""),
                )
        else:
            # Back-compat: labels only (no guild id → mi disabled).
            guilds = data.get("mutual_guilds") or []
            if guilds:
                for g in guilds:
                    label = str(g)
                    if " (" in label and label.endswith(")"):
                        server, _, rest = label.partition(" (")
                        self._add_mutual_row(server, rest[:-1])
                    else:
                        self._add_mutual_row(label)
            else:
                self._add_mutual_row("No mutual servers")

        self._sync_mi_button()
        self._set_status(
            f"Loaded {name} — {self.mutuals_table.rowCount()} mutual server(s). "
            "Select one for Member info (mi)."
        )

    def _lookup_mi(self) -> None:
        if self._busy_mi:
            return
        user_id = self._last_user_id or self.user_id_entry.text().strip()
        guild_id = self._selected_guild_id()
        if not _SNOWFLAKE_RE.match(user_id):
            self._set_status("Lookup a Discord member first.", error=True)
            return
        if not _SNOWFLAKE_RE.match(guild_id):
            self._set_status(
                "Select a mutual server that has a guild id (re-run Lookup).",
                error=True,
            )
            return

        self._busy_mi = True
        self.mi_btn.setEnabled(False)
        self._set_status("Scanning member messages (this can take a while)…")
        self.mi_result.setPlainText("Scanning…")
        threading.Thread(
            target=self._fetch_mi, args=(user_id, guild_id), daemon=True
        ).start()

    def _fetch_mi(self, user_id: str, guild_id: str) -> None:
        result: dict = {}
        try:
            config = read_config()
            response = requests.post(
                f"{config['api_url']}/lookup/member_info",
                json={"userID": user_id, "guildID": guild_id},
                timeout=300,
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
            logger.warning("lookup/member_info request failed: %s", e)
            result = {"ok": False, "error": "Could not reach the API."}
        except Exception:
            logger.exception("lookup/member_info failed")
            result = {"ok": False, "error": "Member info scan failed."}
        self._mi_done.emit(result)

    def _on_mi_done(self, result: object) -> None:
        self._busy_mi = False
        self._sync_mi_button()
        if not isinstance(result, dict):
            self.mi_result.setPlainText("")
            self._set_status("Member info failed.", error=True)
            return
        if not result.get("ok"):
            self.mi_result.setPlainText("")
            self._set_status(
                str(result.get("error") or "Member info failed."), error=True
            )
            return

        data = result.get("data") or {}
        lines = list(data.get("messages") or [])
        connections = data.get("connections") or []
        conn_txt = (
            ", ".join(
                f"{c.get('type')}: {c.get('name')}"
                for c in connections
                if isinstance(c, dict)
            )
            or "none"
        )
        roles = data.get("roles") or []
        body_parts = [
            f"{data.get('display_name') or data.get('discord_name')} "
            f"({data.get('user_id')}) in {data.get('guild_name')}",
            f"Account created: {_fmt_ts(data.get('account_created'))}",
            f"Joined guild: {_fmt_ts(data.get('joined_guild'))}",
            f"Roles: {', '.join(str(r) for r in roles) or 'none'}",
            f"Connections: {conn_txt}",
            "",
            f"Total messages: {data.get('total', 0)}",
            f"Alliance: {data.get('alliance_count', 0)}",
            f"Hourglass: {data.get('hourglass_count', 0)}",
            f"Flagged: {data.get('flagged_count', 0)}",
        ]
        if lines:
            body_parts.append("")
            body_parts.append("Messages:")
            body_parts.extend(f"{i}. {line}" for i, line in enumerate(lines, start=1))
        else:
            body_parts.append("")
            body_parts.append("No member-authored messages found.")

        self.mi_result.setPlainText("\n".join(body_parts))
        self._set_status(
            f"Member info: {data.get('total', 0)} message(s) in "
            f"{data.get('guild_name') or 'guild'}."
        )

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
