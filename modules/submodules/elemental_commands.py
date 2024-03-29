"""
This module executes all elemental commands.
"""

import threading

import requests

import modules.submodules.start_check

from .functions.clear_typing_bar import clear_typing_bar
from .functions.execute_command import execute_command
from .functions.switch_channel import switch_channel


def elemental_commands(self, *args):
    """
    This function executes all elemental commands.
    """
    self.currentstate = "ElementalCommands"
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    loghistory = ["/user_report", self.user_id.get()]
    execute_command(self, loghistory[0], loghistory[1:])
    start_elemental_api_requests_thread(self)

    self.stop_button.state(["!disabled"])
    self.function_button.state(["!disabled"])

    # self.notespage = 2
    if not args:
        # self.function_button.config(text="Add GT to Notes", command=lambda: add_note(self))
        # self.kill_button.config(text=f"Check notes page {self.notespage}", command=lambda: check_notes_page(self))
        # self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))
        # self.start_button.state(["!disabled"])
        modules.submodules.start_check.continue_to_next(self)
    else:
        self.function_button.config(text="Tell to link xbox", command=lambda: tell_to_link_xbox(self))
        self.kill_button.config(text="Tell to verify + link xbox", command=lambda: tell_to_verify_link_xbox(self))
        self.start_button.state(["disabled"])


def add_note(self):
    """
    Adds note to specified userID and GT if needed.
    """
    switch_channel(self, self.channel.get())
    clear_typing_bar()
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    noteadd = ["/add_note", self.user_id.get(), f"GT: {self.xbox_gt}"]
    execute_command(self, noteadd[0], noteadd[1:])
    self.function_button.state(["disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])


# def check_notes_page(self):
#     """
#     Checks additional pages of notes if needed for the specified userID.
#     """
#     self.function_button.state(["disabled"])
#     self.kill_button.state(["disabled"])
#     self.start_button.state(["disabled"])
#     notescheck = ["/list_notes", self.user_id.get(), f"page_number: {self.notespage}"]
#     clear_typing_bar()
#     execute_command(self, notescheck[0], notescheck[1:])
#     self.notespage += 1
#     self.kill_button.config(text=f"Check notes page {self.notespage}")
#     self.function_button.state(["!disabled"])
#     self.kill_button.state(["!disabled"])
#     self.start_button.state(["!disabled"])


def tell_to_link_xbox(self):
    """
    Tells the user to link their xbox account.
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    verify = ["/verify", self.user_id.get(), "verify_type: link_xbox"]
    clear_typing_bar()
    execute_command(self, verify[0], verify[1:])
    self.function_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])
    self.currentstate = "SOTOfficial"
    self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))


def tell_to_verify_link_xbox(self):
    """
    Tells the user to verify and link their xbox account.
    """
    self.function_button.state(["disabled"])
    self.kill_button.state(["disabled"])
    self.start_button.state(["disabled"])
    verify = ["/verify", self.user_id.get(), "verify_type: both"]
    clear_typing_bar()
    execute_command(self, verify[0], verify[1:])
    self.function_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    self.start_button.state(["!disabled"])
    self.currentstate = "SOTOfficial"
    self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))


def make_api_request(self):
    try:
        if self.method.get() == "All Commands":
            elemental_api_request(self)

    except Exception as e:
        print(f"API Request Error: {e}")


# Create a function to start API requests in a separate thread
def start_elemental_api_requests_thread(self):
    api_thread = threading.Thread(target=make_api_request, args=(self,))
    api_thread.start()


def elemental_api_request(self):
    request_error = False
    if self.channel.get() == "#on-duty-commands":
        self.loghistory_status_label.config(text="Sending API request", foreground="orange")
        self.mainframe.update()
        try:
            #! still perform the request even if the user has no gamertag, so we can run the loghistory API
            payload = {"userID": self.user_id.get(), "gamertag": self.xbox_gt if self.xbox_gt else "abcdefghij"}
            response = requests.post(f"{self.api_url}/elemental", json=payload, verify=False)

            if response.status_code != 200:
                request_error = True
            else:
                response_json = response.json()
                self.account_age_label.config(text=f"{response_json['account_age']} Days", foreground="red" if response_json["account_age"] < 60 else "green")
                self.needs_warning_talk_label.config(text=f"{response_json['needs_warning_talk']}", foreground="red" if response_json["needs_warning_talk"] else "green")
                self.gamertag_in_notes_label.config(text=f"{response_json['gamertag_in_notes']}", foreground="green" if response_json["gamertag_in_notes"] else "red")
                self.needs_to_be_spoken_to_label.config(text=f"{response_json['needs_to_be_spoken_to']}", foreground="red" if response_json["needs_to_be_spoken_to"] else "green")
                self.needs_mic_check_label.config(text=f"{response_json['needs_mic_check']}", foreground="red" if response_json["needs_mic_check"] else "green")
                self.anti_alliance_note_label.config(text=f"{response_json['anti_alliance_note']}", foreground="red" if response_json["anti_alliance_note"] else "green")
                self.jump_to_message_button.state(["!disabled"])
                self.jump_to_message_button.config(command=lambda: switch_channel(self, response_json["jump_url"], kwargs=True))

                issues = {
                    "Account Age": response_json["account_age"] < 60,
                    "Needs Warning Talk": response_json["needs_warning_talk"],
                    "Gamertag in Notes": not response_json["gamertag_in_notes"],
                    "Needs to be Spoken To": response_json["needs_to_be_spoken_to"],
                    "Needs Mic Check": response_json["needs_mic_check"],
                    "Anti Alliance Note": response_json["anti_alliance_note"],
                }

                # Add the issues to the list
                self.loghistory_issues = [issue for issue, has_issue in issues.items() if has_issue]
                self.loghistory_status_label.config(text=f"{len(self.loghistory_issues)} issue(s) found", foreground="red" if self.loghistory_issues else "green")
                if self.loghistory_issues:
                    self.loghistory_fix_issues_button.state(["!disabled"])

        except (requests.exceptions.ConnectionError, TypeError, requests.exceptions.ReadTimeout):
            request_error = True
    else:
        self.loghistory_status_label.config(text="Not sending request", foreground="red")

    if request_error:
        self.loghistory_status_label.config(text="API request failed", foreground="red")


def fix_issues(self):
    if "Gamertag in Notes" in self.loghistory_issues:
        add_note(self)
        self.loghistory_issues.remove("Gamertag in Notes")
        self.gamertag_in_notes_label.config(text="True", foreground="green")

    self.loghistory_status_label.config(text=f"{len(self.loghistory_issues)} issue(s) found", foreground="red" if self.loghistory_issues else "green")
    if not self.loghistory_issues:
        self.loghistory_fix_issues_button.state(["disabled"])
