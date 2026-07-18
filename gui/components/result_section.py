from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


@dataclass
class ResultField:
    label: str
    value: str
    is_issue: bool = False
    detail: str = ""


class ResultSection(QWidget):
    """Section header, issues-only summary, full stats in hover tooltip."""

    def __init__(
        self,
        title: str,
        buttons: list[QPushButton] | None = None,
        *,
        idle_tooltip: str = "",
        show_all_results: bool = False,
        always_show_keys: frozenset[str] | None = None,
    ):
        super().__init__()
        self._title = title
        self._idle_tooltip = idle_tooltip or f"{title}\nStart a check to see results."
        self._show_all_results = show_all_results
        self._always_show_keys = always_show_keys or frozenset()
        self._state = "idle"
        self._error_message = ""
        self._fields: dict[str, ResultField] = {}
        self._field_order: list[str] = []
        self._buttons = buttons or []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        self._header = QLabel(title)
        self._header.setObjectName("sectionHeader")
        outer.addWidget(self._header)

        self._summary_host = QWidget()
        self._summary_host.setObjectName("resultSection")
        self._summary_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        summary_layout = QVBoxLayout(self._summary_host)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)

        self._summary = QLabel("—")
        self._summary.setObjectName("resultSectionSummary")
        self._summary.setWordWrap(True)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._summary.setMinimumHeight(18)
        self._summary.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._summary.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        summary_layout.addWidget(self._summary)
        outer.addWidget(self._summary_host)

        self._button_row = QWidget()
        self._button_row.setMinimumHeight(42)
        btn_layout = QHBoxLayout(self._button_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)
        for btn in self._buttons:
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        outer.addWidget(self._button_row)

        self._divider = QFrame()
        self._divider.setObjectName("sectionDivider")
        self._divider.setFixedHeight(1)
        self._divider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        outer.addWidget(self._divider)

        for btn in self._buttons:
            btn.raise_()
        self._button_row.raise_()

        self.reset()

    def set_loading(self) -> None:
        self._state = "loading"
        self._error_message = ""
        self.clear_fields()
        self._header.setText(f"{self._title} — Checking…")
        self._summary.setText("—")
        self._apply_header_style("loading")
        # No tooltip while empty placeholder is showing.
        self._apply_tooltip("")

    def set_state(self, state: str, *, error_message: str = "") -> None:
        self._state = state
        self._error_message = error_message
        self._header.setText(self._title)
        self._apply_header_style(state)
        self._refresh()

    def set_success_or_issues(self) -> None:
        """Green when clean; orange when any field is flagged as an issue."""
        has_issues = any(f.is_issue for f in self._fields.values())
        self.set_state("issues" if has_issues else "success")

    def set_field(
        self,
        key: str,
        label: str,
        value: str,
        *,
        is_issue: bool = False,
        detail: str = "",
    ) -> None:
        if key not in self._field_order:
            self._field_order.append(key)
        self._fields[key] = ResultField(
            label=label,
            value=value,
            is_issue=is_issue,
            detail=detail or f"{label}: {value}",
        )

    def clear_fields(self) -> None:
        self._fields.clear()
        self._field_order.clear()

    def reset(self) -> None:
        self.clear_fields()
        self._error_message = ""
        self._state = "idle"
        self._header.setText(self._title)
        self._summary.setText("—")
        self._apply_header_style("idle")
        self._apply_tooltip("")
        for btn in self._buttons:
            btn.setEnabled(False)

    def _apply_header_style(self, state: str) -> None:
        self._header.setProperty("state", state)
        self._header.style().unpolish(self._header)
        self._header.style().polish(self._header)

    def _apply_tooltip(self, text: str) -> None:
        """Tooltip only when there is real content — never on empty '—' placeholders."""
        tip = (text or "").strip()
        if self._state in ("idle", "loading"):
            tip = ""
        elif self._state in ("success", "issues") and not self._fields:
            tip = ""
        # Header + section so hover over summary/"—" area only tips when populated.
        self.setToolTip(tip)
        self._header.setToolTip(tip)
        self._summary_host.setToolTip(tip)
        self._summary.setToolTip(tip)
        for btn in self._buttons:
            btn.setToolTip("")

    def _refresh(self) -> None:
        text = self._build_summary()
        self._summary.setText(text)
        self._apply_tooltip(self._build_tooltip())

    def _build_summary(self) -> str:
        if self._state == "failed":
            return self._error_message or "Failed"

        if self._state not in ("success", "issues"):
            return "—"

        fields = self._ordered_fields()
        if self._show_all_results:
            if not fields:
                return "—"
            return "\n".join(self._summary_line(f) for f in fields)

        visible = [
            self._fields[key]
            for key in self._field_order
            if key in self._fields
            and (key in self._always_show_keys or self._fields[key].is_issue)
        ]
        if not visible:
            return "—"
        return "\n".join(self._summary_line(f) for f in visible)

    def _summary_line(self, field: ResultField) -> str:
        name = field.label
        value = field.value.strip()
        if value and value.lower() not in ("true", "false", "n/a"):
            return f"{name}: {value}"
        return name

    def _ordered_fields(self) -> list[ResultField]:
        return [self._fields[key] for key in self._field_order if key in self._fields]

    def _build_tooltip(self) -> str:
        if self._state == "loading":
            return ""
        if self._state == "idle":
            return ""

        lines = [self._title]
        if self._state == "failed":
            lines.append(self._error_message or "Request failed.")
            return "\n".join(lines)

        if not self._fields:
            return ""
        for field in self._ordered_fields():
            lines.append(field.detail)
        return "\n".join(lines)
