"""
This module initiates the staffcheck process and determines which method to use
"""

from tkinter import DISABLED, NORMAL, StringVar, TclError

import threading
import requests

import modules.submodules.ashen_commands
import modules.submodules.check_message
import modules.submodules.elemental_commands
import modules.submodules.functions.widgets as widgets
import modules.submodules.invite_tracker
import modules.submodules.pre_check
import modules.submodules.sot_official
from modules.submodules.functions.settings import read_config


def validate_user_id(self) -> bool:
    """
    This function validates the user input
    """
    self.user_id.set(self.user_id.get().strip())

    # Check if the user id is a number
    if not isinstance(self.user_id.get(), str) or not self.user_id.get().isdigit():
        self.status_label.config(text="ID must be a number", foreground="Red")
        return False

    # Check if the user id is the correct length
    lengths = [17, 18, 19]
    if len(self.user_id.get()) in lengths:
        return True

    self.status_label.config(
        text=f"ID is an incorrect length at {len(self.user_id.get())} characters",
        foreground="Red",
    )
    return False


def start_check(self):
    """
    This function sets the currentstate to the appropriate value
    """
    if not validate_user_id(self):
        return

    request_error = False
    payload = {"userID": self.user_id.get()}
    try:
        self.status_label.config(text="Sending API request")
        self.mainframe.update()
        config = read_config()
        self.essential_data_response = requests.post(
            f"{config["api_url"]}/staffcheck/essential_data", json=payload, verify=False, timeout=20, headers=self.headers
        )

        if self.essential_data_response.status_code != 200:
            request_error = True
        else:
            self.user_name = self.essential_data_response.json()["discord_name"]

            self.mutual_guilds = self.essential_data_response.json()["mutual_guilds"]
            guild_list = "\n".join(self.mutual_guilds)
            self.mutual_guilds_label = widgets.create_label(
                self.mainframe, f"Mutual guilds:\n{guild_list}", 11, 1, "W, E", 1, 2
            )
            # Grab the first xbox account from the request
            self.xbox_gt = self.essential_data_response.json()["linked_xbox"][0]
            print(self.xbox_gt, len(self.essential_data_response.json()["linked_xbox"]))
            if len(self.essential_data_response.json()["linked_xbox"]) > 1:
                self.status_label.config(text="Warning: Has multiple accounts linked. Only showing the first one.", foreground="Red")
                print(f"Warning: {self.user_name} has multiple accounts linked. Only showing the first one.")
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as exc:
        request_error = True
        print(exc)
    if not request_error:
        continue_check(self, request_error)
    else:
        self.status_label.config(
            text="Error when trying to get GT. Enter GT manually instead!", foreground="Red"
        )
        self.xbox_gt = StringVar()
        self.gt_entry_label = widgets.create_label(self.mainframe, "Enter GT:", 9, 1, "E")
        self.gt_entry = widgets.create_entry(self.mainframe, self.xbox_gt, 9, 2, "W", 30)
        self.entered_gt_button = widgets.create_button(
            self.mainframe, "Entered GT", lambda: continue_check(self, request_error), 10, 2, "W"
        )
        self.gt_entry.focus()
        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)


def continue_check(self, request_error):
    """
    This function continues the check process
    """
    if not len(self.essential_data_response.json()["linked_xbox"]) > 1:
        self.status_label.config(text="Running Check", foreground="black")
    self.mainframe.update()
    if request_error:
        self.xbox_gt = self.xbox_gt.get().strip()
        self.gt_entry_label.destroy()
        self.gt_entry.destroy()
        self.entered_gt_button.destroy()
        self.mainframe.update()

    if self.xbox_gt != []:
        self.gamertag_label.config(text=self.xbox_gt)
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        try:
            self.save_button.state(["disabled"])
        except (AttributeError, TclError):
            pass
        try:
            self.reset_button.state(["disabled"])
        except (AttributeError, TclError):
            pass
        self.reason = ""
        self.kill_button.state(["!disabled"])
        self.menu_customize.entryconfigure("Good to check message", state=DISABLED)
        self.menu_customize.entryconfigure("Not good to check message", state=DISABLED)
        self.menu_customize.entryconfigure("Join AWR message", state=DISABLED)
        self.menu_customize.entryconfigure("Unprivate Xbox message", state=DISABLED)
        self.menu_customize.entryconfigure("Verify message", state=DISABLED)
        self.user_id_entry.config(state=[("disabled")])
        self.channel_combo_box.config(state=[("disabled")])
        self.method_combo_box.config(state=[("disabled")])
        self.pre_check_button.config(state=[("disabled")])
        self.mainframe.update()

        self.currentstate = None
        if "selected" in self.pre_check_button.state():
            modules.submodules.pre_check.pre_check(self)
        else:
            determine_method(self)
    else:
        self.gamertag_label.config(text="Not linked")
        modules.submodules.elemental_commands.elemental_commands(self, 1)


def reset_ui(self):
    """
    This function resets the UI to its default state
    """
    previous_user_id = self.user_id.get()
    self.function_button_2.config(
        text="Re-run last check", command=lambda: self.user_id.set(previous_user_id)
    )
    self.user_id.set("")
    self.status_label.config(text="Waiting for ID", foreground="black")
    self.gamertag_label.config(text="Unknown")
    self.stop_button.state(["disabled"])
    try:
        self.reason.set("")
        self.reason_entry.destroy()
    except AttributeError:
        pass

    self.account_age_label.config(text="N/A", foreground="orange")
    self.needs_warning_talk_label.config(text="N/A", foreground="orange")
    self.gamertag_in_notes_label.config(text="N/A", foreground="orange")
    self.needs_to_be_spoken_to_label.config(text="N/A", foreground="orange")
    self.needs_mic_check_label.config(text="N/A", foreground="orange")
    self.anti_alliance_note_label.config(text="N/A", foreground="orange")
    self.loghistory_status_label.config(text="Waiting", foreground="orange")
    self.loghistory_fix_issues_button.state(["disabled"])
    self.jump_to_message_button.state(["disabled"])

    self.invited_by_label.config(text="N/A", foreground="orange")
    self.times_invited_label.config(text="N/A", foreground="orange")
    self.num_people_invited_label.config(text="N/A", foreground="orange")
    self.invite_tracker_status_label.config(text="Waiting", foreground="orange")
    self.invited_by_loghistory_button.state(["disabled"])
    self.invited_users_loghistory_button.state(["disabled"])

    self.gamertag_exists_label.config(text="N/A", foreground="orange")
    self.total_friends_label.config(text="N/A", foreground="orange")
    # self.ban_ratio_label.config(text="N/A", foreground="orange")
    self.completion_label.config(text="N/A", foreground="orange")
    self.total_matches_label.config(text="N/A", foreground="orange")
    self.partial_matches_label.config(text="N/A", foreground="orange")
    self.exact_matches_label.config(text="N/A", foreground="orange")
    self.alts_found_label.config(text="N/A", foreground="orange")
    self.search_status_label.config(text="Waiting", foreground="orange")
    self.jump_to_message_search_button.state(["disabled"])
    self.search_fix_issues_button.state(["disabled"])

    self.total_messages_label.config(text="N/A", foreground="orange")
    self.messages_with_alliance_label.config(text="N/A", foreground="orange")
    self.messages_with_hourglass_label.config(text="N/A", foreground="orange")
    self.messages_with_bad_words_label.config(text="N/A", foreground="orange")
    self.sot_official_status_label.config(text="N/A", foreground="orange")
    self.check_for_yourself_button.state(["disabled"])

    self.function_button_2.state(["!disabled"])

    try:
        self.mutual_guilds_label.destroy()
    except AttributeError:
        pass

    self.start_button.state(["!disabled"])
    self.kill_button.state(["!disabled"])
    try:
        self.save_button.state(["!disabled"])
    except (AttributeError, TclError):
        pass
    try:
        self.reset_button.state(["!disabled"])
    except (AttributeError, TclError):
        pass
    try:
        self.reason_entry.destroy()
    except AttributeError:
        pass
    self.menu_customize.entryconfigure("Good to check message", state=NORMAL)
    self.menu_customize.entryconfigure("Not good to check message", state=NORMAL)
    self.menu_customize.entryconfigure("Join AWR message", state=NORMAL)
    self.menu_customize.entryconfigure("Unprivate Xbox message", state=NORMAL)
    self.menu_customize.entryconfigure("Verify message", state=NORMAL)
    self.user_id_entry.config(state=[("!disabled")])
    self.channel_combo_box.config(state=[("!disabled")])
    self.method_combo_box.config(state=[("!disabled")])
    self.pre_check_button.config(state=[("!disabled")])


def perform_next_command(self):
    """
    This function determines which section of the macro to run next
    """
    method = self.method.get()
    current_state = self.currentstate

    if method == "All Commands":
        if current_state == "PreCheck":
            modules.submodules.elemental_commands.elemental_commands(self)
        elif current_state == "ElementalCommands":
            modules.submodules.ashen_commands.ashen_commands(self)
        elif current_state == "AshenCommands":
            modules.submodules.invite_tracker.invite_tracker(self)
        elif current_state == "InviteTracker":
            modules.submodules.sot_official.sot_official(self)
        elif current_state == "SOTOfficial":
            modules.submodules.check_message.check_message(self)

    elif method == "Purge Commands":
        if current_state == "PreCheck":
            modules.submodules.elemental_commands.elemental_commands(self)
        elif current_state == "ElementalCommands":
            modules.submodules.ashen_commands.ashen_commands(self)
        elif current_state == "AshenCommands":
            modules.submodules.check_message.check_message(self)


def continue_to_next(self):
    """
    This function makes the program continue to the next step
    """
    self.start_button.state(["disabled"])
    self.function_button.state(["disabled"])
    self.function_button_2.state(["disabled"])
    self.function_button.config(text="Cool Button", command=None)
    self.function_button_2.config(text="Re-run last check", command=None)
    self.kill_button.config(text="Back to launcher", command=self.back)
    self.start_button.config(text="Start Check!", command=lambda: start_check(self))

    if self.currentstate == "Done":
        reset_ui(self)
        return

    if self.method.get() not in ["Purge Commands", "All Commands"]:
        self.currentstate = "Done"
        continue_to_next(self)
    else:
        perform_next_command(self)


def make_api_requests(self):
    """
    Make the api requests to the bot to get the data
    from sea of thieves official and the invite tracker
    """
    try:
        modules.submodules.invite_tracker.api_request(self)
        modules.submodules.sot_official.api_request(self)
        # Add more API requests as needed

    except Exception as e:  # pylint: disable=broad-except
        print(f"API Request Error: {e}")


def determine_method(self):
    """
    This function determines which method to use
    """
    self.reason = StringVar(value="Reason for Not Good To Check")
    self.reason_entry = widgets.create_entry(self.mainframe, self.reason, 9, 1, "W, E", 55, 2)
    for child in self.mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)

    if self.method.get() == "All Commands":
        api_thread = threading.Thread(target=make_api_requests, args=(self,))
        api_thread.start()
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Purge Commands":
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Elemental Commands":
        modules.submodules.elemental_commands.elemental_commands(self)
    elif self.method.get() == "Ashen Commands":
        modules.submodules.ashen_commands.ashen_commands(self)
    elif self.method.get() == "Invite Tracker":
        modules.submodules.invite_tracker.invite_tracker(self)
    elif self.method.get() == "SOT Official":
        modules.submodules.sot_official.sot_official(self)
    elif self.method.get() == "Check Message":
        modules.submodules.check_message.check_message(self)
    else:
        self.start_button.state(["!disabled"])
