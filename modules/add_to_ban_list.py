"""
This module adds the specified member to the ban list.
"""

# pylint: disable=E0401, E0402, W0621, W0401, W0614, R0915, C0301, W0201
from tkinter import *
from tkinter import ttk as tk
import re
import runpy
import webbrowser
import keyboard
import time
import launcher
import configparser
import modules.submodules.functions.window_positions as window_positions


class AddToBanList:
    """
    This class creates the window where the user can fill out all the details about the member they want to add to the ban list.
    """

    def __init__(self, root):

        # read the delay from the INI file
        self.config = configparser.ConfigParser()
        try:
            # parse config file
            self.config.read("settings.ini")
            self.delay = self.config["ADD_TO_BAN_LIST"]["delay"]
        except KeyError:
            self.config["ADD_TO_BAN_LIST"] = {"delay": "15"}
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.delay = self.config["ADD_TO_BAN_LIST"]["delay"]

        self.delay = int(self.delay)

        self.root = root
        self.root.title("Add To Ban List")
        self.root.option_add("*tearOff", FALSE)

        # add a menu bar

        menubar = Menu(self.root)
        self.root["menu"] = menubar

        self.menu_settings = Menu(menubar)

        menubar.add_cascade(menu=self.menu_settings, label="Settings")

        self.menu_settings.add_command(label="Change delay", command=self.change_delay)

        # Create the menu
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create the tabbed menu for the diferent servers

        self.server_selector = tk.Notebook(root)
        self.server_selector.grid(row=0, column=0, sticky=(N, W, E, S))

        self.requiem = tk.Frame(self.server_selector)
        self.fortune = tk.Frame(self.server_selector)
        self.obsidian = tk.Frame(self.server_selector)

        self.server_selector.add(self.requiem, text="Requiem")
        self.server_selector.add(self.fortune, text="Fortune")
        self.server_selector.add(self.obsidian, text="Obsidian")

        # create the labels and entry boxes for the requiem tab

        self.ban_label = tk.Label(self.requiem, text="Entire Ban Entry as in AoA:")
        self.ban_label.grid(column=1, row=1, sticky=(W, E))

        self.ban_entry = StringVar()
        self.ban_entry_entry = tk.Entry(
            self.requiem, width=19, textvariable=self.ban_entry
        )
        self.ban_entry_entry.grid(column=2, row=1, sticky=(W, E))

        self.explanation_label = tk.Label(
            self.requiem,
            text="Allows multiple bans seperated by a comma\nExample: 123456789,987654321",
        )
        self.explanation_label.grid(columnspan=6, row=2, sticky=(W, E))

        self.start_button = tk.Button(self.requiem, text="Submit", command=self.start)
        self.start_button.grid(row=79, columnspan=5, sticky=(W, E))

        self.kill_button = tk.Button(
            self.requiem, text="Back to launcher", command=self.back
        )
        self.kill_button.grid(row=80, columnspan=5, sticky=(W, E))

        for child in self.requiem.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # Create the labels and entry boxes for the fortune tab
        tk.Label(self.fortune, text="Discord ID:").grid(column=1, row=2, sticky=E)
        self.user_id = StringVar()
        self.user_id_entry = tk.Entry(self.fortune, width=19, textvariable=self.user_id)
        self.user_id_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.fortune, text="Discord Name:").grid(column=1, row=3, sticky=E)
        self.discord_name = StringVar()
        self.discord_name_entry = tk.Entry(
            self.fortune, width=19, textvariable=self.discord_name
        )
        self.discord_name_entry.grid(column=2, row=3, sticky=(W, E))

        tk.Label(self.fortune, text="Xbox Gamertag:").grid(column=1, row=4, sticky=E)
        self.xbox_gamertag = StringVar()
        self.xbox_gamertag_entry = tk.Entry(
            self.fortune, width=19, textvariable=self.xbox_gamertag
        )
        self.xbox_gamertag_entry.grid(column=2, row=4, sticky=(W, E))

        tk.Label(self.fortune, text="Reason:").grid(column=1, row=5, sticky=E)
        self.reason = StringVar()
        self.reason_entry = tk.Entry(self.fortune, width=19, textvariable=self.reason)
        self.reason_entry.grid(column=2, row=5, sticky=(W, E))

        self.kill_button = tk.Button(
            self.fortune, text="Back to launcher", command=self.back
        )
        self.kill_button.grid(row=80, columnspan=5, sticky=(W, E))

        self.start_button = tk.Button(self.fortune, text="Submit", command=self.start)
        self.start_button.grid(row=79, columnspan=5, sticky=(W, E))

        for child in self.fortune.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # Create the labels and entry boxes for the obsidian tab
        tk.Label(self.obsidian, text="Discord ID:").grid(column=1, row=2, sticky=E)
        self.obsidian_user_id = StringVar()
        self.obsidian_user_id_entry = tk.Entry(
            self.obsidian, width=19, textvariable=self.user_id
        )
        self.obsidian_user_id_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.obsidian, text="Discord Name:").grid(column=1, row=3, sticky=E)
        self.obsidian_discord_name = StringVar()
        self.obsidian_discord_name_entry = tk.Entry(
            self.obsidian, width=19, textvariable=self.discord_name
        )
        self.obsidian_discord_name_entry.grid(column=2, row=3, sticky=(W, E))

        tk.Label(self.obsidian, text="Xbox Gamertag:").grid(column=1, row=4, sticky=E)
        self.obsidian_xbox_gamertag = StringVar()
        self.obsidian_xbox_gamertag_entry = tk.Entry(
            self.obsidian, width=19, textvariable=self.xbox_gamertag
        )
        self.obsidian_xbox_gamertag_entry.grid(column=2, row=4, sticky=(W, E))

        tk.Label(self.obsidian, text="Reason:").grid(column=1, row=5, sticky=E)
        self.obsidian_reason = StringVar()
        self.obsidian_reason_entry = tk.Entry(
            self.obsidian, width=19, textvariable=self.reason
        )
        self.obsidian_reason_entry.grid(column=2, row=5, sticky=(W, E))

        self.obsidian_kill_button = tk.Button(
            self.obsidian, text="Back to launcher", command=self.back
        )
        self.obsidian_kill_button.grid(row=80, columnspan=5, sticky=(W, E))

        self.obsidian_start_button = tk.Button(
            self.obsidian, text="Submit", command=self.start
        )
        self.obsidian_start_button.grid(row=79, columnspan=5, sticky=(W, E))

        for child in self.obsidian.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def change_delay(self):
        """
        Changes the delay between messages.
        """
        SettingsWindow("15", self.root, self.mainframe)

    def back(self):
        """
        Goes back to the launcher.
        """
        window_positions.save_window_position(self.root)
        self.root.destroy()
        # run the launcher using runpy
        runpy.run_module("launcher", run_name="__main__")

    def start(self):
        """
        Starts the add_to_ban_list script.
        """
        if self.server_selector.index(self.server_selector.select()) == 0:
            self.extract_info(self.ban_entry.get())
            self.ban_entry.set("")
        elif self.server_selector.index(self.server_selector.select()) == 1:
            self.ban_user_id = self.user_id_entry.get()
            self.ban_discord_name = self.discord_name_entry.get()
            self.ban_xbox_gamertag = self.xbox_gamertag_entry.get()
            self.ban_reason = self.reason_entry.get()
            self.server = "Fortune"
            self.add_to_ban_list_other()
            self.discord_name.set("")
            self.xbox_gamertag.set("")
            self.user_id.set("")
            self.reason.set("")
        elif self.server_selector.index(self.server_selector.select()) == 2:
            self.ban_user_id = self.obsidian_user_id_entry.get()
            self.ban_discord_name = self.obsidian_discord_name_entry.get()
            self.ban_xbox_gamertag = self.obsidian_xbox_gamertag_entry.get()
            self.ban_reason = self.obsidian_reason_entry.get()
            self.ban_server = "Obsidian"
            self.add_to_ban_list_other()
            self.obsidian_discord_name.set("")
            self.obsidian_xbox_gamertag.set("")
            self.obsidian_user_id.set("")
            self.obsidian_reason.set("")

    def add_to_ban_list_other(self):
        url = "https://docs.google.com/spreadsheets/d/1V5Z61CKmJoNZn7L3PWziJdbHRVzYuxaZU4qTOIRHfWg/edit#gid=125271616"
        # open the url in the default browser
        webbrowser.open(url, new=2)
        time.sleep(self.delay)
        keyboard.press_and_release("ctrl + down")
        time.sleep(2)
        keyboard.press_and_release("down")
        keyboard.write(self.ban_discord_name)
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.ban_xbox_gamertag)
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.ban_user_id)
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.server)
        time.sleep(0.5)
        keyboard.press_and_release("right")
        keyboard.write(self.ban_reason)
        time.sleep(0.5)
        keyboard.press_and_release("right")

    def extract_info(self, string):

        url = "https://docs.google.com/spreadsheets/d/1V5Z61CKmJoNZn7L3PWziJdbHRVzYuxaZU4qTOIRHfWg/edit#gid=125271616"
        # open the url in the default browser
        webbrowser.open(url, new=2)
        time.sleep(self.delay)
        keyboard.press_and_release("ctrl + down")
        time.sleep(2)
        keyboard.press_and_release("down")

        bans = string.split(",")

        for ban in bans:
            print(ban)

            # Split the string by the '-' character
            parts = ban.split("-")

            # Extract the gamertag and Discord tag
            gamertag = "N/A"
            discord_tag = "N/A"
            gamertag = (
                parts[0].split(":")[1].strip()
                if parts[0].split(":")[1].strip().count("?") < 3
                else "N/A"
            )
            for i, part in enumerate(parts):
                if "#" in part:
                    discord_tag = part.strip()

            # Extract the user ID using a regular expression
            user_id_pattern = r"\d{17,19}"
            user_id_matches = re.findall(user_id_pattern, ban)
            user_id = user_id_matches[-1] if user_id_matches else "N/A"

            # Extract the reason
            reason = parts[-1].strip()

            keyboard.write(discord_tag)
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write(gamertag)
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write(user_id)
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write("Requiem")
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write(reason)
            time.sleep(0.5)
            keyboard.press_and_release("down")
            time.sleep(0.5)
            keyboard.press_and_release("ctrl + left")
            time.sleep(0.5)

            # Return the extracted information as a tuple
        return gamertag, user_id, discord_tag, reason


class SettingsWindow:
    """
    class for the customize window
    """

    def __init__(self, default, root, mainframe):
        def save_changes(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                try:
                    self.config["ADD_TO_BAN_LIST"]["delay"] = self.message_entry.get()
                except AttributeError:
                    pass
                self.config.write(configfile)

        def reset_to_default(self):
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config["ADD_TO_BAN_LIST"]["delay"] = default
                self.config.write(configfile)
                self.message.set(default)

        self.mainframe = mainframe
        self.root = root
        self.config = configparser.ConfigParser()
        self.config.read("settings.ini")
        self.customize_window = Toplevel()
        self.customize_window.title("Settings")
        explanation_label = tk.Label(
            self.customize_window,
            text="Customize the delay between the program launching after the browser is opened in seconds:",
        )
        explanation_label.grid(rowspan=2, column=1, row=1, sticky=W)

        self.message = StringVar(value=self.config["ADD_TO_BAN_LIST"]["delay"])
        self.message_entry = tk.Entry(
            self.customize_window, width=75, textvariable=self.message
        )
        self.message_entry.grid(column=1, row=4, sticky=(E, W))

        self.save_button = tk.Button(
            self.customize_window,
            text="Save Changes!",
            command=lambda: save_changes(self),
        )
        self.save_button.grid(column=1, row=7, sticky=W)

        self.reset_button = tk.Button(
            self.customize_window,
            text="Reset To Default!",
            command=lambda: reset_to_default(self),
        )
        self.reset_button.grid(column=1, row=7, sticky=E)

        for child in self.customize_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.root.eval(f"tk::PlaceWindow {str(self.customize_window)} center")


def start_script():
    root = Tk()
    window_positions.load_window_position(root)
    # root.eval("tk::PlaceWindow . center")
    root.protocol(
        "WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1)
    )
    AddToBanList(root)
    root.mainloop()
