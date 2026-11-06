"""Compact staffcheck "Verdict" card: Start → Good / Not good → reason, one click each.

The card only shows state; the staffcheck pipeline tells it which stage it is in
(``StaffcheckView.set_verdict_stage``) and the view turns clicks into pipeline calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from staffcheck.verdict_followups import (
    FOLLOWUP_JOIN_AWR,
    FOLLOWUP_LINK_XBOX,
    FOLLOWUP_NONE,
    FOLLOWUP_TELL_VERIFY,
    FOLLOWUP_UNPRIVATE,
    FOLLOWUP_VERIFY,
)

FOLLOWUP_LABELS = {
    FOLLOWUP_NONE: "Nothing",
    FOLLOWUP_JOIN_AWR: "Join AWR",
    FOLLOWUP_VERIFY: "Verify account",
    FOLLOWUP_UNPRIVATE: "Unprivate Xbox",
    FOLLOWUP_LINK_XBOX: "Link Xbox",
    FOLLOWUP_TELL_VERIFY: "Verify account",
}


@dataclass(frozen=True)
class Reason:
    label: str
    reason: str  # text posted in the Not good message; "" = use the reason box
    followup: str
    hint: str


REASONS = (
    Reason(
        "Needs to verify",
        "Needs to verify account",
        FOLLOWUP_VERIFY,
        "Posts not good, then /verify in #on-duty-chat",
    ),
    Reason(
        "Needs to unprivate",
        "Needs to unprivate xbox",
        FOLLOWUP_UNPRIVATE,
        "Posts not good, then opens modmail and recalls Unprivate Xbox",
    ),
    Reason(
        "Remove banned friends",
        "Needs to remove banned friends",
        FOLLOWUP_JOIN_AWR,
        "Posts not good, then /joinawr so they can be spoken to",
    ),
    Reason("Other…", "", FOLLOWUP_NONE, "Type a reason and pick what runs after it"),
)

NO_XBOX_REASONS = (
    Reason(
        "Needs to link Xbox",
        "Needs to link xbox",
        FOLLOWUP_LINK_XBOX,
        "Runs /verify verify_type:link_xbox, then posts not good",
    ),
    Reason(
        "Needs to verify",
        "Needs to verify account",
        FOLLOWUP_TELL_VERIFY,
        "Runs /verify verify_type:verify, then posts not good",
    ),
    Reason("Other…", "", FOLLOWUP_NONE, "Type a reason and pick what runs after it"),
)

_OTHER_FOLLOWUPS = (FOLLOWUP_NONE, FOLLOWUP_JOIN_AWR, FOLLOWUP_VERIFY, FOLLOWUP_UNPRIVATE)
_NO_XBOX_OTHER_FOLLOWUPS = (FOLLOWUP_NONE, FOLLOWUP_LINK_XBOX, FOLLOWUP_TELL_VERIFY, FOLLOWUP_JOIN_AWR)

STAGES = ("idle", "running", "decide", "good", "not_good", "no_xbox", "busy")


def _wide(btn: QPushButton) -> QPushButton:
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return btn


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class VerdictCard(QWidget):
    """Bottom card of the compact staffcheck layout."""

    good_clicked = Signal()
    not_good_clicked = Signal()
    post_good_clicked = Signal()
    dont_post_clicked = Signal()
    back_clicked = Signal()
    # reason text, follow-up key, post check message?, run follow-up?
    reason_chosen = Signal(str, str, bool, bool)

    def __init__(self, start_button: QPushButton, reason_entry: QLineEdit):
        super().__init__()
        self.setObjectName("resultCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._stage = "idle"
        self._reasons = REASONS
        self._other_selected = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        # Header: "Verdict › Not good to check" ......... "← Back"
        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel("Verdict")
        title.setObjectName("sectionHeader")
        head.addWidget(title)
        self._sep = QLabel("›")
        self._sep.setObjectName("verdictCrumb")
        head.addWidget(self._sep)
        self._crumb = QLabel()
        self._crumb.setObjectName("verdictCrumb")
        head.addWidget(self._crumb)
        head.addStretch(1)
        self._back = QPushButton("← Back")
        self._back.setObjectName("verdictBack")
        self._back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back.clicked.connect(self.back_clicked.emit)
        head.addWidget(self._back)
        outer.addLayout(head)

        self._stack = QStackedWidget()
        self._stack.setObjectName("verdictPane")
        self._stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        outer.addWidget(self._stack)
        self._pages: dict[str, QWidget] = {}

        # idle: the view's own Start check! button (keeps its enable/tooltip logic).
        self._start_button = start_button
        self._add_page("idle", [start_button])

        # running: verdict buttons visible but greyed.
        self._run_good = _wide(QPushButton("Good to check"))
        self._run_good.setObjectName("verdictGood")
        self._run_bad = _wide(QPushButton("Not good to check"))
        self._run_bad.setObjectName("verdictBad")
        for btn in (self._run_good, self._run_bad):
            btn.setEnabled(False)
        self._add_page("running", [self._run_good, self._run_bad])

        good = _wide(QPushButton("✓  Good to check"))
        good.setObjectName("verdictGood")
        good.clicked.connect(self.good_clicked.emit)
        bad = _wide(QPushButton("✕  Not good to check"))
        bad.setObjectName("verdictBad")
        bad.clicked.connect(self.not_good_clicked.emit)
        self._add_page("decide", [good, bad])

        self._post_good = _wide(QPushButton("Post good to check"))
        self._post_good.setObjectName("primary")
        self._post_good.clicked.connect(self.post_good_clicked.emit)
        dont = _wide(QPushButton("Don't post"))
        dont.clicked.connect(self.dont_post_clicked.emit)
        self._add_page("good", [self._post_good, dont])

        # not_good / no_xbox share one reason page; the buttons are relabelled.
        reason_page = QWidget()
        reason_page.setObjectName("verdictPane")
        grid = QGridLayout(reason_page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self._reason_buttons: list[QPushButton] = []
        for col in range(4):
            btn = _wide(QPushButton())
            btn.setObjectName("verdictReason")
            btn.installEventFilter(self)
            btn.clicked.connect(lambda _=False, i=col: self._on_reason(i))
            grid.addWidget(btn, 0, col)
            self._reason_buttons.append(btn)
        self._stack.addWidget(reason_page)
        self._pages["not_good"] = reason_page
        self._pages["no_xbox"] = reason_page

        self._busy_label = QLabel("Working…")
        self._busy_label.setObjectName("verdictHint")
        busy = QWidget()
        busy.setObjectName("verdictPane")
        busy_layout = QHBoxLayout(busy)
        busy_layout.setContentsMargins(0, 4, 0, 4)
        busy_layout.addWidget(self._busy_label)
        self._stack.addWidget(busy)
        self._pages["busy"] = busy

        # Other…: reason box + "Then:" follow-up + Post.
        self._other_row = QWidget()
        self._other_row.setObjectName("verdictOtherRow")
        other = QHBoxLayout(self._other_row)
        other.setContentsMargins(0, 0, 0, 0)
        other.setSpacing(8)
        self._reason_entry = reason_entry
        other.addWidget(reason_entry, 5)
        then = QLabel("Then:")
        then.setObjectName("resultLabel")
        other.addWidget(then)
        self._then_combo = QComboBox()
        self._then_combo.setMinimumHeight(30)
        other.addWidget(self._then_combo, 2)
        self._post_other = _wide(QPushButton("Post not good"))
        self._post_other.setObjectName("primary")
        self._post_other.clicked.connect(self._on_post_other)
        other.addWidget(self._post_other, 2)
        reason_entry.returnPressed.connect(self._on_post_other)
        reason_entry.textChanged.connect(self._on_reason_text)
        outer.addWidget(self._other_row)

        # Ticks + hint under the reasons.
        self._options_row = QWidget()
        self._options_row.setObjectName("verdictPane")
        opts = QHBoxLayout(self._options_row)
        opts.setContentsMargins(0, 0, 0, 0)
        opts.setSpacing(16)
        self.post_check = QCheckBox("Post check message")
        self.run_followup = QCheckBox("Run the follow-up command")
        opts.addWidget(self.post_check)
        opts.addWidget(self.run_followup)
        opts.addStretch(1)
        self._hint = QLabel()
        self._hint.setObjectName("verdictHint")
        opts.addWidget(self._hint)
        self.post_check.toggled.connect(self._on_reason_text)
        outer.addWidget(self._options_row)

        self.set_stage("idle")

    # ------------------------------------------------------------------ pages
    def _add_page(self, name: str, buttons: list[QPushButton]) -> None:
        page = QWidget()
        page.setObjectName("verdictPane")
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for btn in buttons:
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(btn)
        self._stack.addWidget(page)
        self._pages[name] = page

    @property
    def stage(self) -> str:
        return self._stage

    def set_stage(self, stage: str, *, busy_text: str = "", editable: bool = False) -> None:
        if stage not in STAGES:
            raise ValueError(stage)
        previous = self._stage
        self._stage = stage
        if stage in ("not_good", "no_xbox"):
            self._reasons = NO_XBOX_REASONS if stage == "no_xbox" else REASONS
            if previous != stage:
                self._select_other(False)
        if stage == "idle":
            # Fresh check: everything back to defaults.
            self.post_check.setChecked(True)
            self.run_followup.setChecked(True)
            self._select_other(False)
        if stage == "busy":
            self._busy_label.setText(busy_text or "Working…")
        self._post_good.setText("Edit: Post good to check" if editable else "Post good to check")

        crumbs = {
            "running": ("Running the check…", "verdictCrumb", ""),
            "good": ("Good to check", "verdictCrumb", "good"),
            "not_good": ("Not good to check", "verdictCrumb", "bad"),
            "no_xbox": ("No Xbox linked", "verdictCrumb", "bad"),
        }
        text, _name, tone = crumbs.get(stage, ("", "verdictCrumb", ""))
        self._crumb.setText(text)
        self._crumb.setProperty("tone", tone)
        _repolish(self._crumb)
        self._sep.setVisible(bool(text) and stage != "running")
        self._crumb.setVisible(bool(text))
        self._back.setVisible(stage in ("good", "not_good"))

        self._stack.setCurrentWidget(self._pages[stage])
        reasons_visible = stage in ("not_good", "no_xbox")
        self._options_row.setVisible(reasons_visible)
        if reasons_visible:
            for btn, reason in zip(self._reason_buttons, self._reasons):
                btn.setText(reason.label)
                btn.setVisible(True)
            for btn in self._reason_buttons[len(self._reasons):]:
                btn.setVisible(False)
        self._other_row.setVisible(reasons_visible and self._other_selected)
        self._refresh_hint()
        self._refresh_post_other()

    # ---------------------------------------------------------------- reasons
    def _select_other(self, on: bool) -> None:
        self._other_selected = on
        for btn in self._reason_buttons:
            btn.setProperty("chosen", False)
            _repolish(btn)
        if on:
            index = len(self._reasons) - 1
            self._reason_buttons[index].setProperty("chosen", True)
            _repolish(self._reason_buttons[index])
            options = _NO_XBOX_OTHER_FOLLOWUPS if self._stage == "no_xbox" else _OTHER_FOLLOWUPS
            self._then_combo.clear()
            for key in options:
                self._then_combo.addItem(FOLLOWUP_LABELS[key], key)
        self._other_row.setVisible(on)
        # The Other path picks its follow-up in the combo instead.
        self.run_followup.setVisible(not on)
        if on:
            self._reason_entry.setFocus()

    def _on_reason(self, index: int) -> None:
        if index >= len(self._reasons):
            return
        reason = self._reasons[index]
        if not reason.reason:
            self._select_other(True)
            self._refresh_hint()
            self._refresh_post_other()
            return
        self.reason_chosen.emit(
            reason.reason,
            reason.followup,
            self.post_check.isChecked(),
            self.run_followup.isChecked(),
        )

    def _on_post_other(self) -> None:
        if not (self._other_selected and self._stage in ("not_good", "no_xbox")):
            return
        if not self._post_other.isEnabled():
            return
        followup = self._then_combo.currentData() or FOLLOWUP_NONE
        self.reason_chosen.emit(
            self._reason_entry.text().strip(),
            followup,
            self.post_check.isChecked(),
            bool(followup),
        )

    def _on_reason_text(self, *_args) -> None:
        self._refresh_post_other()

    def _refresh_post_other(self) -> None:
        posting = self.post_check.isChecked()
        self._post_other.setText("Post not good" if posting else "Run")
        # Posting needs a reason; running only the command doesn't.
        self._post_other.setEnabled(bool(self._reason_entry.text().strip()) or not posting)

    def _refresh_hint(self, hovered: int | None = None) -> None:
        if self._stage not in ("not_good", "no_xbox"):
            self._hint.setText("")
            return
        if hovered is not None and hovered < len(self._reasons):
            self._hint.setText(self._reasons[hovered].hint)
        elif self._other_selected:
            self._hint.setText("Untick Post check message to only run the command")
        elif self._stage == "no_xbox":
            self._hint.setText("Search and Invite Tracker were skipped (no gamertag)")
        else:
            self._hint.setText("One click posts and runs the follow-up")

    def eventFilter(self, watched, event):
        if watched in self._reason_buttons:
            if event.type() == QEvent.Type.Enter:
                self._refresh_hint(self._reason_buttons.index(watched))
            elif event.type() == QEvent.Type.Leave:
                self._refresh_hint()
        return super().eventFilter(watched, event)
