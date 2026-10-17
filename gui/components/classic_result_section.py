from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.components.result_section import ResultField


class ClassicResultSection(QWidget):
    """Full field grid with per-value issue coloring (classic panel mode)."""

    def __init__(
        self,
        title: str,
        rows: list[tuple[str, str]],
        buttons: list[QPushButton] | None = None,
        *,
        absent_note: str = "",
    ):
        super().__init__()
        self._title = title
        self._row_keys = [key for _, key in rows]
        self._state = "idle"
        self._error_message = ""
        self._fields: dict[str, ResultField] = {}
        self._field_order: list[str] = []
        self._buttons = buttons or []
        self._value_labels: dict[str, QLabel] = {}

        # Boxed group like the old StaffCheck window (see #resultBox in gui/theme.py).
        self.setObjectName("resultBox")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 8)
        outer.setSpacing(4)

        self._header = QLabel(title)
        self._header.setObjectName("sectionHeader")
        outer.addWidget(self._header)

        # Shown instead of the rows when the section doesn't apply (e.g. not in SOT).
        self._absent_note = QLabel(absent_note)
        self._absent_note.setObjectName("resultSectionSummary")
        self._absent_note.setWordWrap(True)
        self._absent_note.setVisible(False)
        outer.addWidget(self._absent_note)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(1)
        grid.setColumnStretch(1, 1)

        for i, (label_text, key) in enumerate(rows):
            name = QLabel(label_text)
            name.setObjectName("resultLabel")
            value = QLabel("N/A")
            value.setObjectName("resultValue")
            value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            grid.addWidget(name, i, 0)
            grid.addWidget(value, i, 1)
            self._value_labels[key] = value

        status_row = len(rows)
        status_name = QLabel("Status")
        status_name.setObjectName("resultLabel")
        self._status_label = QLabel("Waiting")
        self._status_label.setObjectName("resultValue")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        grid.addWidget(status_name, status_row, 0)
        grid.addWidget(self._status_label, status_row, 1)
        self._summary = self._status_label

        body = QWidget()
        body.setObjectName("resultSection")
        body.setLayout(grid)
        outer.addWidget(body)
        self._body = body
        # Boxes in one grid row share a height; this keeps buttons on the bottom edge.
        outer.addStretch(1)

        self._button_row: QWidget | None = None
        if self._buttons:
            self._button_row = QWidget()
            btn_row = QHBoxLayout(self._button_row)
            btn_row.setContentsMargins(0, 2, 0, 0)
            btn_row.setSpacing(4)
            for btn in self._buttons:
                btn.setObjectName("classicPanelButton")
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn_row.addWidget(btn)
            outer.addWidget(self._button_row)

        self.reset()

    def set_body_visible(self, visible: bool) -> None:
        """Show or omit this section's own results."""
        self._body.setVisible(visible)
        if self._button_row is not None:
            self._button_row.setVisible(visible)
        self._absent_note.setVisible(not visible and bool(self._absent_note.text()))

    def set_membership(self, state: str) -> None:
        """'unknown' and 'member' show the rows; 'not_member' shows the absent note."""
        self.set_body_visible(state != "not_member")

    def set_loading(self) -> None:
        self._state = "loading"
        self._error_message = ""
        self.clear_fields()
        self._header.setText(f"{self._title} — Checking…")
        self._apply_header_style("loading")
        self._refresh()

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
        self._apply_header_style("idle")
        self._refresh()
        for btn in self._buttons:
            btn.setEnabled(False)

    def _apply_header_style(self, state: str) -> None:
        self._header.setProperty("state", state)
        self._header.style().unpolish(self._header)
        self._header.style().polish(self._header)

    def _refresh(self) -> None:
        from staffcheck.qt_ui import label_set

        if self._state in ("idle", "loading"):
            for key in self._row_keys:
                label_set(self._value_labels[key], "N/A", "orange")
                self._value_labels[key].setToolTip("")
        elif self._state == "failed":
            for key in self._row_keys:
                if key in self._fields:
                    field = self._fields[key]
                    label_set(self._value_labels[key], field.value, "red" if field.is_issue else "orange")
                    self._value_labels[key].setToolTip(field.detail)
                else:
                    label_set(self._value_labels[key], "N/A", "orange")
                    self._value_labels[key].setToolTip("")
        else:
            for key in self._row_keys:
                if key in self._fields:
                    field = self._fields[key]
                    label_set(
                        self._value_labels[key],
                        field.value,
                        "red" if field.is_issue else "green",
                    )
                    self._value_labels[key].setToolTip(field.detail)
                else:
                    label_set(self._value_labels[key], "N/A", "orange")
                    self._value_labels[key].setToolTip("")

        status_text, status_color = self._status_display()
        label_set(self._status_label, status_text, status_color)

    def _status_display(self) -> tuple[str, str]:
        if self._state == "loading":
            return "Checking…", "orange"
        if self._state == "failed":
            return self._error_message or "Failed", "red"
        if self._state == "idle":
            return "Waiting", "orange"
        issues = [f for f in self._ordered_fields() if f.is_issue]
        if issues:
            return f"{len(issues)} issue(s) found", "orange"
        return "OK", "green"

    def _ordered_fields(self) -> list[ResultField]:
        return [self._fields[key] for key in self._field_order if key in self._fields]
