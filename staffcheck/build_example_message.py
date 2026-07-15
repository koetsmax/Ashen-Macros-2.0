from core.settings import read_config
from staffcheck.qt_ui import Var, btn_enable, label_set


def build_example_message(self, id_: int, status_label):
    config = read_config()

    good_to_check_message = config["good_to_check_message"]
    not_good_to_check_message = config["not_good_to_check_message"]
    join_awr_message = config["join_awr_message"]
    unprivate_xbox_message = config["unprivate_xbox_message"]
    verify_message = config["verify_message"]
    final_string = ""
    btn_enable(self.start_button, True)
    label_set(status_label, "Waiting for ID")

    if "userID" not in good_to_check_message or "xboxGT" not in good_to_check_message:
        btn_enable(self.start_button, False)
        label_set(status_label, "Error! Bad Good to Check message!", "red")

    if (
        "userID" not in not_good_to_check_message
        or "xboxGT" not in not_good_to_check_message
        or "Reason" not in not_good_to_check_message
    ):
        btn_enable(self.start_button, False)
        label_set(status_label, "Error! Bad Not Good to Check message!", "red")

    if (
        "userID" not in join_awr_message
        or "<#702904587027480607>" not in join_awr_message
        or "Time" not in join_awr_message
    ):
        if join_awr_message.lower() != "delete":
            btn_enable(self.start_button, False)
            label_set(status_label, "Error! Bad Join AWR message!", "red")

    if "userID" not in unprivate_xbox_message or "Time" not in unprivate_xbox_message:
        if unprivate_xbox_message.lower() != "delete":
            btn_enable(self.start_button, False)
            label_set(status_label, "Error! Bad Unprivate Xbox message!", "red")

    if "userID" not in verify_message or "Time" not in verify_message:
        if verify_message.lower() != "delete":
            btn_enable(self.start_button, False)
            label_set(status_label, "Error! Bad Verify message!", "red")

    if id_ == 0:
        s = good_to_check_message.replace("userID", "@Max").replace("xboxGT", "M A X10815")
        final_string = s
    elif id_ == 1:
        s = not_good_to_check_message.replace("userID", "@Max").replace("xboxGT", "Fleet Admin")
        final_string = s.replace("Reason", "Needs to remove banned friends")
    elif id_ == 2:
        s = join_awr_message.replace("userID", "@Max").replace("<#702904587027480607>", "Alliance Waiting Room")
        final_string = s.replace("Time", "in 10 minutes")
    elif id_ == 3:
        s = unprivate_xbox_message.replace("userID", "@Max")
        final_string = s.replace("Time", "in 10 minutes")
    elif id_ == 4:
        s = verify_message.replace("userID", "@Max")
        final_string = s.replace("Time", "in 10 minutes")

    if id_ != 99 and hasattr(self, "customize_window"):
        from PySide6.QtWidgets import QLabel

        if hasattr(self, "example_label") and self.example_label:
            self.example_label.deleteLater()
        self.example_label = QLabel(final_string, self.customize_window)
        self.example_label.setWordWrap(True)
        self.customize_layout.addWidget(self.example_label)
