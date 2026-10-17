from core.settings import read_config
from staffcheck.qt_ui import clear_status_issue, status_issue


def customize_messages_valid() -> bool:
    """True when both customize templates keep their required placeholders."""
    config = read_config()
    good = config["good_to_check_message"]
    not_good = config["not_good_to_check_message"]
    return (
        "userID" in good
        and "xboxGT" in good
        and "userID" in not_good
        and "xboxGT" in not_good
        and "Reason" in not_good
    )


def build_example_message(self, id_: int, status_label=None):
    config = read_config()

    good_to_check_message = config["good_to_check_message"]
    not_good_to_check_message = config["not_good_to_check_message"]
    final_string = ""

    if "userID" not in good_to_check_message or "xboxGT" not in good_to_check_message:
        status_issue(self, "customize", "Error! Bad Good to Check message!")
    elif (
        "userID" not in not_good_to_check_message
        or "xboxGT" not in not_good_to_check_message
        or "Reason" not in not_good_to_check_message
    ):
        status_issue(self, "customize", "Error! Bad Not Good to Check message!")
    else:
        clear_status_issue(self, "customize")

    # Start check! also depends on the Discord ID, so let the view decide.
    refresh = getattr(self, "refresh_start_enabled", None)
    if callable(refresh):
        refresh()

    if id_ == 0:
        s = good_to_check_message.replace("userID", "@Max").replace("xboxGT", "M A X10815")
        final_string = s
    elif id_ == 1:
        s = not_good_to_check_message.replace("userID", "@Max").replace("xboxGT", "Fleet Admin")
        final_string = s.replace("Reason", "Needs to remove banned friends")

    if id_ != 99 and hasattr(self, "customize_window"):
        from PySide6.QtWidgets import QLabel

        if hasattr(self, "example_label") and self.example_label:
            self.example_label.deleteLater()
        self.example_label = QLabel(final_string, self.customize_window)
        self.example_label.setWordWrap(True)
        self.customize_layout.addWidget(self.example_label)
