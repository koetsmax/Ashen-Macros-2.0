"""
This modules handles all of the ashen commands
"""
import requests

from tkinter import *
from tkinter import ttk as tk
import modules.submodules.start_check
from .check_message import not_good_to_check
from .functions.clear_typing_bar import clear_typing_bar
from .functions.switch_channel import switch_channel
from .functions.execute_command import execute_command


def ashen_commands(self):
    """
    This function makes changes to the GUI and applies commands to the buttons
    """
    request_error = False
    self.currentstate = "AshenCommands"
    switch_channel(self.channel.get())
    clear_typing_bar()
    search = ["/search ", f"member: {self.user_id.get()}", f"gamertag: {self.xbox_gt}"]
    execute_command(self, search[0], search[1:])
    if self.channel.get() == "#on-duty-commands":
        self.search_status_label.config(text="Sending API request", foreground="orange")
        self.mainframe.update()
        try:
            payload = {"userID": self.user_id.get()}
            response = requests.post(f"{self.api_url}/search", json=payload, timeout=10, verify=False)

            if response.status_code != 200:
                request_error = True
            elif response.json()["error"] == "User not found!":
                self.search_status_label.config(text="User not found", foreground="red")
            elif response.json()["error"] == "Xbox API error!":
                self.search_status_label.config(text="Xbox API error", foreground="red")
            else:
                response_json = response.json()
                self.gamertag_exists_label.config(text=f"{response_json['gamertag_exists']}", foreground="green" if response_json["gamertag_exists"] else "red")
                self.total_friends_label.config(text=f"{response_json['total_friends']}", foreground="green")
                # self.ban_ratio_label.config(text=f"{response_json['ban_ratio']}", foreground="red" if response_json["ban_ratio"] > 0 else "green")
                self.completion_label.config(text=f"{response_json['completion_percentage']}", foreground="green" if int(response_json["completion_percentage"]) > 10 else "red")
                self.total_matches_label.config(text=f"{response_json['total_matches']}", foreground="green" if int(response_json["total_matches"]) == 0 else "red")
                self.partial_matches_label.config(text=f"{response_json['partial_matches']}", foreground="green" if int(response_json["partial_matches"]) == 0 else "orange")
                self.exact_matches_label.config(text=f"{response_json['exact_matches']}", foreground="green" if int(response_json["exact_matches"]) == 0 else "red")
                self.alts_found_label.config(text=f"{response_json['alts_found']}", foreground="green" if int(response_json["alts_found"]) == 0 else "red")
                self.jump_to_message_search_button.state(["!disabled"])
                self.jump_to_message_search_button.config(command=lambda: switch_channel(response_json["jump_url"], kwargs=True))

                issues = {
                    "Gamertag Exists": not response_json["gamertag_exists"],
                    "Completion": int(response_json["completion_percentage"]) < 10,
                    "Total Matches": int(response_json["total_matches"]) > 0,
                    "Partial Matches": int(response_json["partial_matches"]) > 0,
                    "Exact Matches": int(response_json["total_bans"]) > 0,
                    "Alts Found": response_json["alts_found"] is not False,
                    "Has Verified": not response_json["has_verified"],
                }

                # Add the issues to the list
                self.search_issues = [issue for issue, has_issue in issues.items() if has_issue]
                self.search_status_label.config(text=f"{len(self.search_issues)} issue(s) found", foreground="red" if self.search_issues else "green")
                if self.search_issues:
                    self.search_fix_issues_button.state(["!disabled"])

        except (requests.exceptions.ConnectionError, TypeError):
            request_error = True

    if request_error:
        self.search_status_label.config(text="Request failed", foreground="red")

    self.start_button.state(["!disabled"])
    self.start_button.config(text="Continue", command=lambda: modules.submodules.start_check.continue_to_next(self))
    self.function_button.config(text="Needs to remove banned friends", command=lambda: needs_to_remove_friends(self))
    self.function_button.state(["!disabled"])
    self.function_button_2.config(text="Needs to verify account", command=lambda: needs_to_verify(self))
    self.function_button_2.state(["!disabled"])
    self.kill_button.config(text="Needs to unprivate Xbox", command=lambda: needs_to_unprivate_xbox(self))
    self.kill_button.state(["!disabled"])


def needs_to_remove_friends(self):
    """
    This function notes the member as not good to check if they have to remove banned friends
    """
    self.reason = StringVar(value="Needs to remove banned friends:")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=9, sticky="W, E")
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    not_good_to_check(self)


def needs_to_unprivate_xbox(self):
    """
    This function notes the member as not good to check if they have to unprivate their Xbox
    """
    self.reason = StringVar(value="Needs to unprivate xbox")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=9, sticky="W, E")
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    not_good_to_check(self)


def needs_to_verify(self):
    """
    This function notes the member as not good to check if they have to verify their account
    """
    self.reason = StringVar(value="Needs to verify account")
    self.reason_entry = tk.Entry(self.mainframe, textvariable=self.reason)
    self.reason_entry.grid(columnspan=2, column=1, row=9, sticky="W, E")
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)
    not_good_to_check(self)


def fix_issues(self):
    pass
