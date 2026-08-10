"""Staffcheck training / labeling app (stepped labeling like a live check)."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.auth import auth_headers
from core.settings import read_config
from gui.views.app_window import AppWindow

logger = logging.getLogger(__name__)

_OUTCOMES = ("good", "not_good", "ban_request", "incomplete")
_GLOBAL_TAG_KINDS = frozenset({"identity", "ban_reason"})

_FRIEND_ACTIONS = (
    ("", "—"),
    ("must_remove", "Must remove"),
    ("ok_to_keep", "OK to keep"),
    ("ignore", "Ignore match"),
)
_GUILD_ACTIONS = (
    ("", "—"),
    ("cannot_be_in", "Cannot be in this server"),
    ("ok", "OK / allowed"),
    ("ignore", "Ignore server"),
)
_PANEL_RELEVANCE = (
    ("", "—"),
    ("evidence", "Direct evidence"),
    ("context_only", "Context only"),
    ("ignore", "Ignore signal"),
)

# Same order as a normal staffcheck pipeline.
_STEP_ORDER = (
    "mutual_guilds",
    "user_report",
    "search",
    "invite",
    "sotofficial",
    "outcome",
)

_DISCORD_TS_RE = re.compile(r"<t:(\d+)(?::[a-zA-Z])?>")
_MENTION_USER_RE = re.compile(r"<@!?(\d+)>")
_MENTION_ROLE_RE = re.compile(r"<@&(\d+)>")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")


def _ban_row_key(row: dict) -> str:
    return "|".join(
        [
            str(row.get("scope") or ""),
            str(row.get("match_class") or ""),
            str(row.get("sheet_row") or ""),
            str(row.get("xbox_id") or ""),
            str(row.get("gamertag") or ""),
            str(row.get("discord_name") or ""),
            str(row.get("association_kind") or ""),
            str(row.get("association_detail") or ""),
        ]
    )


def _ban_row_title(row: dict) -> str:
    name = (
        str(row.get("discord_name") or "").strip()
        or str(row.get("gamertag") or "").strip()
        or str(row.get("xbox_id") or "").strip()
        or "unknown"
    )
    scope = str(row.get("scope") or "?")
    klass = str(row.get("match_class") or "?")
    assoc = str(row.get("association_kind") or "").strip()
    detail = str(row.get("association_detail") or "").strip()
    assoc_bit = f" · {assoc}" + (f" {detail}" if detail else "") if assoc else ""
    reason = str(row.get("reason") or "").strip()
    reason_bit = f"\nReason: {reason}" if reason else ""
    return f"{name} ({scope} {klass}{assoc_bit}){reason_bit}"


def _clean_discord_text(text: str) -> str:
    raw = _INVISIBLE_RE.sub("", str(text or ""))
    raw = _MD_LINK_RE.sub(r"\1", raw)

    def _ts(match: re.Match[str]) -> str:
        try:
            dt = datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return match.group(0)

    raw = _DISCORD_TS_RE.sub(_ts, raw)
    # "<t:…:d> (<t:…:R>)" often becomes "YYYY-MM-DD (YYYY-MM-DD)".
    raw = re.sub(r"(\d{4}-\d{2}-\d{2})\s*\(\1\)", r"\1", raw)
    raw = _MENTION_USER_RE.sub(r"user:\1", raw)
    raw = _MENTION_ROLE_RE.sub(r"role:\1", raw)
    raw = raw.replace("\\_", "_")
    return re.sub(r"[ \t]+\n", "\n", raw).strip()


def _clean_author_name(name: str) -> str:
    text = _clean_discord_text(name)
    parts = re.split(r"\s*\|\|\s*", text, maxsplit=1)
    if len(parts) == 2 and parts[1].strip().isdigit():
        return f"{parts[0].strip()} ({parts[1].strip()})"
    return text


def _format_embed(embed: dict | None) -> str:
    if not isinstance(embed, dict) or not embed:
        return ""
    lines: list[str] = []
    author = embed.get("author") or {}
    if isinstance(author, dict) and author.get("name"):
        lines.append(_clean_author_name(str(author["name"])))
    title = embed.get("title")
    if title:
        lines.append(_clean_discord_text(str(title)))
    desc = embed.get("description")
    if desc:
        cleaned = _clean_discord_text(str(desc))
        # Drop avatar-only fluff from user_report descriptions.
        if cleaned and "avatar" not in cleaned.lower():
            lines.append(cleaned)
    for field in embed.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = _clean_discord_text(str(field.get("name") or "")).strip()
        value = _clean_discord_text(str(field.get("value") or "")).strip()
        if not name and not value:
            continue
        lines.append(f"{name}: {value}" if name else value)
    footer = embed.get("footer") or {}
    if isinstance(footer, dict) and footer.get("text"):
        lines.append(_clean_discord_text(str(footer["text"])))
    return "\n".join(line for line in lines if line).strip()


def _format_user_report(blob: dict) -> str:
    lines: list[str] = []
    structured = [
        ("Account age", blob.get("account_age"), "days"),
        ("Needs warning talk", blob.get("needs_warning_talk"), None),
        ("Gamertag in notes", blob.get("gamertag_in_notes"), None),
        ("Needs to be spoken to", blob.get("needs_to_be_spoken_to"), None),
        ("Needs mic check", blob.get("needs_mic_check"), None),
        ("Anti-alliance note", blob.get("anti_alliance_note"), None),
    ]
    for label, value, unit in structured:
        if value is None:
            continue
        suffix = f" {unit}" if unit and value != "" else ""
        lines.append(f"{label}: {value}{suffix}")

    embed_text = _format_embed(
        blob.get("embed") if isinstance(blob.get("embed"), dict) else None
    )
    if embed_text:
        if lines:
            lines.append("")
            lines.append("Profile")
        lines.append(embed_text)

    followups = blob.get("followup_count")
    if followups:
        lines.append("")
        lines.append(f"Follow-up embeds: {followups}")
    jump = blob.get("jump_url")
    if jump:
        lines.append(f"Jump: {jump}")
    return "\n".join(lines) if lines else "No readable user report fields."


def _format_search(blob: dict) -> str:
    lines = [
        f"Friends: {blob.get('total_friends', '—')}",
        f"Exact matches: {blob.get('exact_matches', '—')}",
        f"Partial matches: {blob.get('partial_matches', '—')}",
        f"Completed: {blob.get('completion_achieved', '—')}",
    ]
    jump = blob.get("jump_url")
    if jump:
        lines.append(f"Jump: {jump}")
    return "\n".join(lines)


def _format_generic_panel(blob: dict) -> str:
    lines: list[str] = []
    embed_text = _format_embed(
        blob.get("embed") if isinstance(blob.get("embed"), dict) else None
    )
    if embed_text:
        lines.append(embed_text)

    skip = {
        "error",
        "source",
        "cutoff",
        "cutoff_source",
        "command_message_id",
        "jump_url",
        "embed",
        "followup_count",
        "_persist_embeds",
        "flags",
        "type",
        "timestamp",
        "author",
        "proxy_icon_url",
        "icon_url",
    }
    for key, value in blob.items():
        if key in skip or isinstance(value, (dict, list)):
            continue
        if value in (None, "", "none"):
            continue
        pretty = key.replace("_", " ").title()
        lines.append(f"{pretty}: {value}")
    jump = blob.get("jump_url")
    if jump and not any(line.startswith("Jump:") for line in lines):
        lines.append(f"Jump: {jump}")
    return "\n".join(lines) if lines else "No readable fields on this panel."


def _format_panel_blob(panel_id: str, blob: object) -> str:
    if not isinstance(blob, dict):
        return str(blob or "")
    if panel_id == "user_report":
        return _format_user_report(blob)
    if panel_id == "search":
        return _format_search(blob)
    return _format_generic_panel(blob)


class StaffcheckTrainingWindow(AppWindow):
    DEFAULT_SIZE = (1200, 860)

    _result = Signal(object)

    def __init__(self):
        super().__init__("Staffcheck training")
        self._result.connect(self._on_result)
        self._busy = False
        self._check_id: str | None = None
        self._run: dict | None = None
        self._taxonomy: list[dict] = []
        self._tag_checks: dict[tuple[str, str], QCheckBox] = {}
        self._od_pick: dict | None = None
        self._friend_combos: dict[str, QComboBox] = {}
        self._guild_combos: dict[str, QComboBox] = {}
        self._panel_relevance: dict[str, QComboBox] = {}
        self._friend_meta: dict[str, dict] = {}
        self._guild_meta: dict[str, dict] = {}
        self._steps: list[str] = []
        self._step_index = 0

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        self.root_layout.addLayout(root)

        top = QHBoxLayout()
        self.user_entry = QLineEdit()
        self.user_entry.setPlaceholderText("Discord user id (blank = random OD check)")
        top.addWidget(self.user_entry, stretch=1)
        self.grab_btn = QPushButton("Grab training case")
        self.grab_btn.setToolTip(
            "With a user id: grab that user. "
            "Empty: pick a random OD check-message target not yet labeled. "
            "Hydrates search/user_report from history (no live re-scrape)."
        )
        self.grab_btn.clicked.connect(self._grab)
        top.addWidget(self.grab_btn)
        self.force_check = QCheckBox("Force refresh")
        top.addWidget(self.force_check)
        self.load_unlabeled_btn = QPushButton("Load unlabeled")
        self.load_unlabeled_btn.clicked.connect(self._load_unlabeled)
        top.addWidget(self.load_unlabeled_btn)
        self.od_btn = QPushButton("OD candidates")
        self.od_btn.clicked.connect(self._load_od_candidates)
        top.addWidget(self.od_btn)
        self.train_btn = QPushButton("Train model")
        self.train_btn.clicked.connect(self._train)
        top.addWidget(self.train_btn)
        root.addLayout(top)

        self.status = QLabel("Ready")
        root.addWidget(self.status)

        split = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.addWidget(QLabel("Cases / candidates"))
        self.list = QListWidget()
        self.list.itemClicked.connect(self._on_list_click)
        left_l.addWidget(self.list)
        self.model_status = QLabel("Model: —")
        left_l.addWidget(self.model_status)
        split.addWidget(left)

        # Main labeling wizard (staffcheck order).
        wizard = QWidget()
        wizard_l = QVBoxLayout(wizard)
        self.step_title = QLabel("Grab a case to start labeling")
        self.step_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        wizard_l.addWidget(self.step_title)
        self.step_hint = QLabel(
            "Steps follow a normal staffcheck: mutual servers → user report → "
            "search → invite → SoT → case outcome."
        )
        self.step_hint.setWordWrap(True)
        wizard_l.addWidget(self.step_hint)

        self.step_stack = QStackedWidget()
        wizard_l.addWidget(self.step_stack, stretch=1)

        nav = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._step_back)
        self.back_btn.setEnabled(False)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        self.step_progress = QLabel("")
        nav.addWidget(self.step_progress)
        nav.addStretch(1)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self._step_next)
        self.next_btn.setEnabled(False)
        nav.addWidget(self.next_btn)
        self.save_btn = QPushButton("Save label")
        self.save_btn.clicked.connect(self._save_label)
        self.save_btn.setEnabled(False)
        self.save_btn.setVisible(False)
        nav.addWidget(self.save_btn)
        wizard_l.addLayout(nav)

        split.addWidget(wizard)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 4)
        root.addWidget(split, stretch=1)

        self._refresh_model_status()
        self._load_taxonomy()

    def _headers(self) -> dict:
        return auth_headers()

    def _api(self) -> str:
        return read_config()["api_url"]

    def _set_busy(self, busy: bool, msg: str = "") -> None:
        self._busy = busy
        for w in (
            self.grab_btn,
            self.load_unlabeled_btn,
            self.od_btn,
            self.train_btn,
        ):
            w.setEnabled(not busy)
        if busy:
            self.back_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
        else:
            self._sync_nav_enabled()
        if msg:
            self.status.setText(msg)

    def _sync_nav_enabled(self) -> None:
        has = bool(self._steps)
        self.back_btn.setEnabled(has and self._step_index > 0)
        on_last = has and self._step_index >= len(self._steps) - 1
        self.next_btn.setVisible(has and not on_last)
        self.next_btn.setEnabled(has and not on_last)
        self.save_btn.setVisible(has and on_last)
        self.save_btn.setEnabled(has and on_last and bool(self._check_id))

    def _post(self, path: str, payload: dict) -> dict:
        r = requests.post(
            f"{self._api()}{path}",
            json=payload,
            headers=self._headers(),
            timeout=120,
        )
        if r.status_code == 403:
            return {"ok": False, "error": "Missing staffcheck_labeler permission"}
        if r.status_code == 401:
            return {"ok": False, "error": "Invalid token"}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        if not isinstance(data, dict):
            return {"ok": False, "error": "bad_response"}
        data.setdefault("ok", r.status_code < 400)
        return data

    def _grab(self) -> None:
        if self._busy:
            return
        uid = self.user_entry.text().strip()
        random_od = not uid
        if uid and not uid.isdigit():
            self.status.setText("Enter a numeric Discord user id, or leave blank for random OD")
            return
        self._set_busy(
            True,
            "Picking random unlabeled OD check…" if random_od else "Starting grab…",
        )
        force = self.force_check.isChecked()

        def work():
            try:
                payload = {
                    "force_refresh": force,
                    "method": "training",
                    "channel": "#on-duty-commands",
                    "random_from_od": random_od,
                }
                if uid:
                    payload["userID"] = uid
                    od_local = self._od_pick or {}
                    if str(od_local.get("target_user_id") or "") == uid:
                        if od_local.get("check_edited_at"):
                            payload["check_edited_at"] = od_local.get("check_edited_at")
                        if od_local.get("check_created_at"):
                            payload["check_created_at"] = od_local.get("check_created_at")
                        cutoff = od_local.get("check_edited_at") or od_local.get(
                            "check_posted_or_last_edited_at"
                        )
                        if cutoff:
                            payload["check_posted_or_last_edited_at"] = cutoff
                        payload["od_outcome_hint"] = od_local.get("od_outcome_hint")
                        payload["od_message_id"] = od_local.get("message_id")
                start = self._post("/staffcheck/training/grab", payload)
                if not start.get("ok"):
                    self._result.emit(
                        {
                            "kind": "error",
                            "error": start.get("error") or start.get("hint") or "grab_failed",
                        }
                    )
                    return
                picked = str(start.get("target_user_id") or uid or "").strip()
                od_pick = start.get("od_pick") or {}
                if not od_pick and (
                    payload.get("check_edited_at")
                    or payload.get("check_created_at")
                    or payload.get("check_posted_or_last_edited_at")
                ):
                    od_pick = {
                        "target_user_id": picked,
                        "od_outcome_hint": payload.get("od_outcome_hint"),
                        "message_id": payload.get("od_message_id"),
                        "check_edited_at": payload.get("check_edited_at"),
                        "check_created_at": payload.get("check_created_at"),
                        "check_posted_or_last_edited_at": payload.get(
                            "check_posted_or_last_edited_at"
                        ),
                    }
                check_id = start.get("check_id")
                reused = bool(start.get("reused"))
                xbox_gt = ""

                if not reused:
                    headers = self._headers()
                    api = self._api()
                    essential = requests.post(
                        f"{api}/staffcheck/essential_data",
                        json={
                            "userID": picked,
                            "check_id": check_id,
                            "source": "training_grab",
                            "method": "training",
                            "channel": "#on-duty-commands",
                        },
                        headers=headers,
                        timeout=60,
                    )
                    if essential.status_code != 200:
                        self._result.emit(
                            {
                                "kind": "error",
                                "error": f"essential_data HTTP {essential.status_code}",
                                "check_id": check_id,
                            }
                        )
                        return
                    try:
                        essential_body = essential.json()
                    except Exception:
                        essential_body = {}
                    if isinstance(essential_body, dict):
                        linked = essential_body.get("linked_xbox") or []
                        if linked:
                            xbox_gt = str(linked[0])

                    for path, body in (
                        (
                            "/staffcheck/invite",
                            {
                                "userID": picked,
                                "check_id": check_id,
                                "source": "training_grab",
                            },
                        ),
                        (
                            "/staffcheck/sotofficial",
                            {
                                "userID": picked,
                                "check_id": check_id,
                                "source": "training_grab",
                            },
                        ),
                    ):
                        try:
                            requests.post(
                                f"{api}{path}",
                                json=body,
                                headers=headers,
                                timeout=90,
                            )
                        except Exception:
                            logger.exception(
                                "training grab optional scrape %s failed", path
                            )

                cutoff_edited = (
                    od_pick.get("check_edited_at")
                    if isinstance(od_pick, dict)
                    else None
                )
                cutoff_created = (
                    od_pick.get("check_created_at")
                    if isinstance(od_pick, dict)
                    else None
                )
                # Legacy mashed field — only treat as last-edit ceiling when
                # check_edited_at is present (or equal to edited).
                legacy_cutoff = (
                    od_pick.get("check_posted_or_last_edited_at")
                    if isinstance(od_pick, dict)
                    else None
                )
                hydrate_payload = {
                    "check_id": check_id,
                    "userID": picked,
                    "only_if_missing": True,
                }
                if cutoff_edited:
                    hydrate_payload["check_edited_at"] = cutoff_edited
                    hydrate_payload["check_posted_or_last_edited_at"] = cutoff_edited
                    hydrate_payload["cutoff_is_last_edited"] = True
                elif legacy_cutoff and cutoff_created and legacy_cutoff != cutoff_created:
                    # Likely edited: legacy != created.
                    hydrate_payload["check_edited_at"] = legacy_cutoff
                    hydrate_payload["check_posted_or_last_edited_at"] = legacy_cutoff
                    hydrate_payload["cutoff_is_last_edited"] = True
                # If never edited: omit upper mash — hydrate uses now.
                if cutoff_created:
                    hydrate_payload["check_created_at"] = cutoff_created
                if xbox_gt:
                    hydrate_payload["gamertag"] = xbox_gt
                hydrate = self._post(
                    "/staffcheck/training/hydrate_history",
                    hydrate_payload,
                )
                found = (hydrate or {}).get("found") or {}
                missing = (hydrate or {}).get("missing") or []
                hydrate_note = (
                    f"History hydrate: user_report={found.get('user_report')} "
                    f"search={found.get('search')} "
                    f"cutoff_source={found.get('cutoff_source')}"
                )
                if found.get("user_report_message_id"):
                    hydrate_note += f" report_msg={found.get('user_report_message_id')}"
                if found.get("search_message_id"):
                    hydrate_note += f" search_msg={found.get('search_message_id')}"
                if found.get("skipped_existing"):
                    hydrate_note += f" skipped={found.get('skipped_existing')}"
                if missing:
                    hydrate_note += f" missing={','.join(missing)}"
                if hydrate and not hydrate.get("ok"):
                    hydrate_note += f" err={hydrate.get('error')}"

                detail = self._post(
                    "/staffcheck/training/run", {"check_id": check_id}
                )
                hint = od_pick.get("od_outcome_hint") if isinstance(od_pick, dict) else None
                note = hydrate_note
                if reused:
                    note = "Reused recent run; " + note
                if hint:
                    note = f"OD hint={hint} (not a label). " + note
                self._result.emit(
                    {
                        "kind": "run",
                        "check_id": check_id,
                        "detail": detail,
                        "reused": reused,
                        "target_user_id": picked,
                        "od_pick": od_pick,
                        "note": note,
                    }
                )
            except Exception as exc:
                logger.exception("grab failed")
                self._result.emit({"kind": "error", "error": str(exc)})

        threading.Thread(target=work, daemon=True).start()

    def _load_unlabeled(self) -> None:
        if self._busy:
            return
        self._set_busy(True, "Loading unlabeled runs…")

        def work():
            data = self._post(
                "/staffcheck/training/runs",
                {"unlabeled_only": True, "limit": 80},
            )
            self._result.emit({"kind": "list", "data": data})

        threading.Thread(target=work, daemon=True).start()

    def _load_od_candidates(self) -> None:
        if self._busy:
            return
        self._set_busy(True, "Scanning OD candidates…")

        def work():
            data = self._post("/staffcheck/training/od_candidates", {"limit": 40})
            self._result.emit({"kind": "od", "data": data})

        threading.Thread(target=work, daemon=True).start()

    def _train(self) -> None:
        if self._busy:
            return
        self._set_busy(True, "Training…")

        def work():
            data = self._post("/staffcheck/training/train", {"min_rows": 20})
            self._result.emit({"kind": "train", "data": data})

        threading.Thread(target=work, daemon=True).start()

    def _refresh_model_status(self) -> None:
        def work():
            data = self._post("/staffcheck/training/model_status", {})
            self._result.emit({"kind": "model", "data": data})

        threading.Thread(target=work, daemon=True).start()

    def _load_taxonomy(self) -> None:
        def work():
            data = self._post("/staffcheck/training/taxonomy", {})
            self._result.emit({"kind": "taxonomy", "data": data})

        threading.Thread(target=work, daemon=True).start()

    def _add_combo_row(
        self,
        layout: QVBoxLayout,
        title: str,
        options: tuple[tuple[str, str], ...],
    ) -> QComboBox:
        row = QHBoxLayout()
        lab = QLabel(title)
        lab.setWordWrap(True)
        lab.setMinimumWidth(220)
        combo = QComboBox()
        for code, text in options:
            combo.addItem(text, code)
        row.addWidget(lab, stretch=3)
        row.addWidget(combo, stretch=2)
        host = QWidget()
        host.setLayout(row)
        layout.addWidget(host)
        return combo

    def _clear_stack(self) -> None:
        while self.step_stack.count():
            w = self.step_stack.widget(0)
            self.step_stack.removeWidget(w)
            w.deleteLater()
        self._friend_combos.clear()
        self._guild_combos.clear()
        self._panel_relevance.clear()
        self._friend_meta.clear()
        self._guild_meta.clear()
        self._tag_checks.clear()
        self._steps = []
        self._step_index = 0

    def _wrap_scroll(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(inner)
        return scroll

    def _make_panel_step(
        self,
        *,
        panel_id: str,
        title: str,
        blob: object,
        missing: bool,
    ) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        if missing:
            lay.addWidget(QLabel(f"{title} is unavailable on this run — skip with Next."))
            lay.addStretch(1)
            return self._wrap_scroll(page)

        lay.addWidget(QLabel(f"How relevant is {title.lower()} for the outcome?"))
        combo = self._add_combo_row(lay, "Relevance", _PANEL_RELEVANCE)
        self._panel_relevance[panel_id] = combo

        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(_format_panel_blob(panel_id, blob))
        detail.setMinimumHeight(280)
        lay.addWidget(detail, stretch=1)
        return self._wrap_scroll(page)

    def _make_guilds_step(self, run: dict) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        essential = run.get("essential") if isinstance(run.get("essential"), dict) else {}
        guilds = list((essential or {}).get("mutual_guilds") or [])
        lay.addWidget(
            QLabel("Label each mutual server (same idea as reviewing mutuals in a check).")
        )
        if not guilds:
            lay.addWidget(QLabel("No mutual servers on this run — skip with Next."))
        else:
            for g in guilds:
                name = str(g).strip()
                if not name:
                    continue
                combo = self._add_combo_row(lay, name, _GUILD_ACTIONS)
                self._guild_combos[name] = combo
                self._guild_meta[name] = {"guild_name": name}
        lay.addStretch(1)
        return self._wrap_scroll(page)

    def _make_search_step(self, run: dict) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        search = run.get("search") if isinstance(run.get("search"), dict) else None
        if not search:
            lay.addWidget(QLabel("Search is unavailable on this run — skip with Next."))
            lay.addStretch(1)
            return self._wrap_scroll(page)

        lay.addWidget(QLabel("Overall search relevance, then label each ban match / friend."))
        combo = self._add_combo_row(lay, "Search relevance", _PANEL_RELEVANCE)
        self._panel_relevance["search"] = combo

        summary = QLabel(
            f"Friends: {search.get('total_friends', '—')} · "
            f"Exact: {search.get('exact_matches', '—')} · "
            f"Partial: {search.get('partial_matches', '—')}"
        )
        lay.addWidget(summary)

        ban_rows = list(search.get("ban_match_rows") or [])
        if not ban_rows:
            lay.addWidget(QLabel("No ban_match_rows on this search."))
        else:
            for row in ban_rows:
                if not isinstance(row, dict):
                    continue
                key = _ban_row_key(row)
                combo = self._add_combo_row(lay, _ban_row_title(row), _FRIEND_ACTIONS)
                self._friend_combos[key] = combo
                self._friend_meta[key] = dict(row)

        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(_format_panel_blob("search", search))
        detail.setMaximumHeight(180)
        lay.addWidget(detail)
        lay.addStretch(1)
        return self._wrap_scroll(page)

    def _make_outcome_step(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel("Case outcome (after reviewing each element)."))

        form = QFormLayout()
        self.outcome = QComboBox()
        self.outcome.addItems(list(_OUTCOMES))
        form.addRow("Outcome", self.outcome)
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason (required for deny/escalate if no tags)")
        form.addRow("Reason", self.reason)
        self.partial = QCheckBox("Partial evidence accepted")
        form.addRow(self.partial)
        lay.addLayout(form)

        tags_box = QGroupBox("Case-level tags (identity / ban reason)")
        tags_outer = QVBoxLayout(tags_box)
        self._tags_host = QWidget()
        self._tags_layout = QVBoxLayout(self._tags_host)
        self._tags_layout.setContentsMargins(4, 4, 4, 4)
        tags_outer.addWidget(self._tags_host)
        lay.addWidget(tags_box)
        self._rebuild_tag_buttons(self._taxonomy)

        self.evidence = QPlainTextEdit()
        self.evidence.setReadOnly(True)
        self.evidence.setPlaceholderText("Readable run summary")
        self.evidence.setMaximumHeight(200)
        lay.addWidget(self.evidence)
        lay.addStretch(1)
        return self._wrap_scroll(page)

    def _rebuild_tag_buttons(self, items: list[dict]) -> None:
        if not hasattr(self, "_tags_layout") or self._tags_layout is None:
            return
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._tag_checks.clear()
        by_kind: dict[str, list[dict]] = {}
        for row in items:
            kind = str(row.get("kind") or "other")
            if kind not in _GLOBAL_TAG_KINDS:
                continue
            by_kind.setdefault(kind, []).append(row)
        for kind in sorted(by_kind.keys()):
            box = QGroupBox(kind.replace("_", " ").title())
            box_lay = QVBoxLayout(box)
            for row in by_kind[kind]:
                code = str(row.get("code") or "")
                label = str(row.get("label") or code)
                check = QCheckBox(f"{label} ({code})")
                self._tag_checks[(kind, code)] = check
                box_lay.addWidget(check)
            self._tags_layout.addWidget(box)
        self._tags_layout.addStretch(1)

    def _build_steps_for_run(self, run: dict, note: str | None = None) -> None:
        self._clear_stack()
        self._run = run

        # Always include pipeline steps; missing panels are skippable pages.
        self._steps = list(_STEP_ORDER)
        for step_id in self._steps:
            if step_id == "mutual_guilds":
                page = self._make_guilds_step(run)
            elif step_id == "user_report":
                blob = run.get("user_report")
                page = self._make_panel_step(
                    panel_id="user_report",
                    title="User report",
                    blob=blob,
                    missing=not blob,
                )
            elif step_id == "search":
                page = self._make_search_step(run)
            elif step_id == "invite":
                blob = run.get("invite")
                page = self._make_panel_step(
                    panel_id="invite",
                    title="Invite tracker",
                    blob=blob,
                    missing=not blob,
                )
            elif step_id == "sotofficial":
                blob = run.get("sotofficial")
                page = self._make_panel_step(
                    panel_id="sotofficial",
                    title="SoT Official",
                    blob=blob,
                    missing=not blob,
                )
            else:
                page = self._make_outcome_step()
            self.step_stack.addWidget(page)

        panels = {
            "meta": {
                "id": run.get("id"),
                "target_user_id": run.get("target_user_id"),
                "xbox_gt": run.get("xbox_gt"),
                "outcome": run.get("outcome"),
                "source": run.get("source"),
            },
            "essential": run.get("essential"),
            "search": run.get("search"),
            "user_report": run.get("user_report"),
            "invite": run.get("invite"),
            "sotofficial": run.get("sotofficial"),
            "issue_flags": run.get("issue_flags"),
        }
        missing = [
            name
            for name in ("essential", "search", "user_report", "invite", "sotofficial")
            if not panels.get(name)
        ]
        summary_lines = [
            f"Target: {run.get('target_user_id') or '—'}",
            f"Xbox: {run.get('xbox_gt') or '—'}",
            f"Source: {run.get('source') or '—'}",
        ]
        if missing:
            summary_lines.append(f"Unavailable: {', '.join(missing)}")
        for panel_id, title in (
            ("user_report", "User report"),
            ("search", "Search"),
            ("invite", "Invite tracker"),
            ("sotofficial", "SoT Official"),
        ):
            blob = panels.get(panel_id)
            if not isinstance(blob, dict):
                continue
            summary_lines.append("")
            summary_lines.append(title)
            summary_lines.append(_format_panel_blob(panel_id, blob))
        essential = panels.get("essential") if isinstance(panels.get("essential"), dict) else {}
        guilds = list((essential or {}).get("mutual_guilds") or [])
        if guilds:
            summary_lines.append("")
            summary_lines.append("Mutual servers")
            summary_lines.append(", ".join(str(g) for g in guilds))
        text = "\n".join(summary_lines)
        if note:
            text = f"NOTE: {note}\n\n" + text
        if hasattr(self, "evidence"):
            self.evidence.setPlainText(text)

        self._step_index = 0
        self._show_step(0)

    def _step_titles(self) -> dict[str, str]:
        return {
            "mutual_guilds": "Mutual servers",
            "user_report": "User report",
            "search": "Search / friends",
            "invite": "Invite tracker",
            "sotofficial": "SoT Official",
            "outcome": "Case outcome",
        }

    def _show_step(self, index: int) -> None:
        if not self._steps:
            self.step_title.setText("Grab a case to start labeling")
            self.step_progress.setText("")
            self._sync_nav_enabled()
            return
        index = max(0, min(index, len(self._steps) - 1))
        self._step_index = index
        self.step_stack.setCurrentIndex(index)
        step_id = self._steps[index]
        title = self._step_titles().get(step_id, step_id)
        self.step_title.setText(f"Step {index + 1}/{len(self._steps)} — {title}")
        self.step_progress.setText(" → ".join(
            self._step_titles().get(s, s) for s in self._steps
        ))
        self._sync_nav_enabled()

    def _step_back(self) -> None:
        if self._step_index <= 0:
            return
        self._show_step(self._step_index - 1)

    def _step_next(self) -> None:
        if self._step_index >= len(self._steps) - 1:
            return
        self._show_step(self._step_index + 1)

    def _clear_feature_tags(self) -> None:
        for check in self._tag_checks.values():
            check.setChecked(False)

    def _selected_feature_tags(self) -> list[dict]:
        tags: list[dict] = []
        for (kind, code), check in self._tag_checks.items():
            if not check.isChecked():
                continue
            tags.append({"kind": kind, "code": code, "label": check.text()})

        for panel, combo in self._panel_relevance.items():
            code = str(combo.currentData() or "")
            if not code:
                continue
            tags.append(
                {
                    "kind": "relevance",
                    "code": code,
                    "label": combo.currentText(),
                    "panel": panel,
                }
            )

        for key, combo in self._friend_combos.items():
            code = str(combo.currentData() or "")
            if not code:
                continue
            meta = self._friend_meta.get(key) or {}
            tags.append(
                {
                    "kind": "friend_action",
                    "code": code,
                    "label": combo.currentText(),
                    "panel": "search",
                    "entity_type": "ban_match",
                    "entity_key": key,
                    "discord_name": meta.get("discord_name"),
                    "gamertag": meta.get("gamertag"),
                    "xbox_id": meta.get("xbox_id"),
                    "association_kind": meta.get("association_kind"),
                    "association_detail": meta.get("association_detail"),
                    "scope": meta.get("scope"),
                    "match_class": meta.get("match_class"),
                    "sheet_row": meta.get("sheet_row"),
                    "reason": meta.get("reason"),
                }
            )

        for key, combo in self._guild_combos.items():
            code = str(combo.currentData() or "")
            if not code:
                continue
            tags.append(
                {
                    "kind": "guild_action",
                    "code": code,
                    "label": combo.currentText(),
                    "panel": "essential",
                    "entity_type": "guild",
                    "entity_key": key,
                    "guild_name": key,
                }
            )
        return tags

    def _on_list_click(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole) or {}
        if payload.get("type") == "od":
            self.user_entry.setText(str(payload.get("target_user_id") or ""))
            self._od_pick = dict(payload)
            hint = payload.get("od_outcome_hint")
            self.status.setText(
                f"OD hint={hint} (not a label) — hydrate uses last-edited ceiling "
                "(commands after first post are OK)"
            )
            return
        check_id = payload.get("id") or payload.get("check_id")
        if not check_id:
            return
        self._set_busy(True, f"Loading {check_id}…")

        def work():
            detail = self._post("/staffcheck/training/run", {"check_id": check_id})
            self._result.emit({"kind": "run", "check_id": check_id, "detail": detail})

        threading.Thread(target=work, daemon=True).start()

    def _save_label(self) -> None:
        if not self._check_id:
            self.status.setText("No run loaded")
            return
        outcome = self.outcome.currentText()
        tags = self._selected_feature_tags()
        if outcome in ("not_good", "ban_request") and not tags and not self.reason.text().strip():
            self.status.setText(
                "Deny/escalate need friend/server/panel tags, identity tags, or reason"
            )
            return
        self._set_busy(True, "Saving label…")
        payload = {
            "check_id": self._check_id,
            "outcome": outcome,
            "reason": self.reason.text().strip() or None,
            "feature_tags": tags,
            "partial_evidence": self.partial.isChecked(),
        }

        def work():
            data = self._post("/staffcheck/training/label", payload)
            self._result.emit({"kind": "label", "data": data})

        threading.Thread(target=work, daemon=True).start()

    def _show_run(self, check_id: str, detail: dict, note: str | None = None) -> None:
        self._check_id = check_id
        run = (detail or {}).get("run") or {}
        self._build_steps_for_run(run, note)
        self.status.setText(f"Loaded {check_id}" + (f" — {note}" if note else ""))

    def _on_result(self, result: object) -> None:
        self._set_busy(False)
        if not isinstance(result, dict):
            return
        kind = result.get("kind")
        if kind == "error":
            self.status.setText(f"Error: {result.get('error')}")
            return
        if kind == "run":
            detail = result.get("detail") or {}
            if not detail.get("ok"):
                self.status.setText(f"Error: {detail.get('error')}")
                return
            picked = str(result.get("target_user_id") or "").strip()
            if picked:
                self.user_entry.setText(picked)
            self._show_run(str(result.get("check_id")), detail, result.get("note"))
            return
        if kind == "taxonomy":
            data = result.get("data") or {}
            items = data.get("items") or []
            self._taxonomy = list(items)
            if hasattr(self, "_tags_layout"):
                self._rebuild_tag_buttons(self._taxonomy)
            return
        if kind == "list":
            data = result.get("data") or {}
            self.list.clear()
            for row in data.get("runs") or []:
                item = QListWidgetItem(
                    f"{row.get('target_user_id')} · {row.get('outcome') or '—'} · {row.get('id')}"
                )
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.list.addItem(item)
            self.status.setText(f"Unlabeled: {self.list.count()}")
            return
        if kind == "od":
            data = result.get("data") or {}
            self.list.clear()
            for row in data.get("candidates") or []:
                item = QListWidgetItem(
                    f"OD {row.get('od_outcome_hint')} · {row.get('target_user_id')} (hint only)"
                )
                item.setData(
                    Qt.ItemDataRole.UserRole, {"type": "od", **row}
                )
                self.list.addItem(item)
            self.status.setText(
                f"OD candidates: {self.list.count()} — Grab fresh; never auto-label from OD"
            )
            return
        if kind == "label":
            data = result.get("data") or {}
            if data.get("ok"):
                self.status.setText(f"Labeled {self._check_id}")
                QMessageBox.information(self, "Saved", "Training label saved.")
            else:
                self.status.setText(f"Label failed: {data.get('error')}")
            return
        if kind == "train":
            data = result.get("data") or {}
            self.status.setText(json.dumps(data, default=str)[:300])
            self._refresh_model_status()
            return
        if kind == "model":
            data = result.get("data") or {}
            ver = data.get("version") or "none"
            self.model_status.setText(
                f"Model: {ver} (loaded={data.get('loaded')})"
            )
