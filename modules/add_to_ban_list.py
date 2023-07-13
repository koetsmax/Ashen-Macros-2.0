"""
This module adds the specified member to the ban list.
"""
import configparser
import re
import runpy
import time
import webbrowser
from tkinter import Menu, StringVar, Tk, FALSE, ttk

import keyboard

import launcher  # pylint: disable=unused-import
import modules.submodules.functions.widgets as widgets
import modules.submodules.functions.window_positions as window_positions


class AddToBanList:
    """
    class for the add_to_ban_list window
    """

    def __init__(self, root):
        # read the delay from the INI file
        self.config = configparser.ConfigParser()
        try:
            # parse config file
            self.config.read("settings.ini")
            self.delay = float(self.config["ADD_TO_BAN_LIST"]["delay"])
        except KeyError:
            self.config["ADD_TO_BAN_LIST"] = {"delay": "15"}
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.delay = float(self.config["ADD_TO_BAN_LIST"]["delay"])

        self.root = root
        self.root.title("Add To Ban List")
        self.root.option_add("*tearOff", FALSE)

        menubar = Menu(self.root)
        self.root["menu"] = menubar

        self.menu_settings = Menu(menubar)

        menubar.add_cascade(menu=self.menu_settings, label="Settings")

        self.menu_settings.add_command(label="Change delay", command=self.change_delay)

        # Create the menu
        self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="N, W, E, S")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # create the labels and entry boxes

        widgets.create_label(self.mainframe, "Entire Ban Entry as in AoA:", 1, 1, "W, E")

        self.requiem_ban = StringVar()
        self.requiem_ban_entry = widgets.create_entry(self.mainframe, self.requiem_ban, 1, 2, "W, E", 44, 2)  # pylint: disable=line-too-long

        widgets.create_label(self.mainframe, "Allows multiple bans. The macro automatically seperates it into multiple entries.", 2, 1, "W, E", 1, 6)  # pylint: disable=line-too-long

        self.discord_id = StringVar()
        self.discord_name = StringVar()
        self.xbox_gt = StringVar()
        self.xbox_id = StringVar()
        self.server = StringVar(value="Athena's Vanguard")
        self.reason = StringVar()

        widgets.create_label(self.mainframe, "Discord ID:", 3, 1, "E")
        self.user_id_entry = widgets.create_entry(self.mainframe, self.discord_id, 3, 2, "W, E", 30, 2)  # pylint: disable=line-too-long

        widgets.create_label(self.mainframe, "Discord Name:", 4, 1, "E")
        self.discord_name_entry = widgets.create_entry(self.mainframe, self.discord_name, 4, 2, "W, E", 30, 2)  # pylint: disable=line-too-long

        widgets.create_label(self.mainframe, "Xbox Gamertag:", 5, 1, "E")
        self.xbox_gamertag_entry = widgets.create_entry(self.mainframe, self.xbox_gt, 5, 2, "W, E", 30, 2)  # pylint: disable=line-too-long

        widgets.create_label(self.mainframe, "Xbox ID:", 6, 1, "E")
        self.xbox_id_entry = widgets.create_entry(self.mainframe, self.xbox_id, 6, 2, "W, E", 30, 2)  # pylint: disable=line-too-long

        widgets.create_label(self.mainframe, "Server:", 7, 1, "E")
        method_options = ["Athena's Vanguard", "Obsidian", "Sea of Grogs"]
        self.method_combo_box = widgets.create_listbox(self.mainframe, method_options, self.server, 7, 2, "W, E", 2)  # pylint: disable=line-too-long

        widgets.create_label(self.mainframe, "Reason:", 8, 1, "E")
        self.reason_entry = widgets.create_entry(self.mainframe, self.reason, 8, 2, "W, E", 30, 2)

        widgets.create_button(self.mainframe, "Back to launcher", self.back, 9, 1, "W, E")
        widgets.create_button(self.mainframe, "Add Requiem ban", lambda: self.start_requiem(self.requiem_ban.get()), 9, 2, "W, E")  # pylint: disable=line-too-long
        widgets.create_button(self.mainframe, "Add Other ban", self.add_to_ban_list_other, 9, 3, "W, E")  # pylint: disable=line-too-long

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def change_delay(self):
        """
        Changes the delay between the browser being opened and the macro starting.
        """
        config = [
            "Settings",
            "Customize the delay between the program launching after the browser is opened in seconds:",  # pylint: disable=line-too-long
            ["delay"],
            "ADD_TO_BAN_LIST",
            ["delay"],
            ["15"],
        ]
        widgets.CreateSettingsWIndow(self.root, config)

    def back(self):
        """
        Goes back to the launcher.
        """
        window_positions.save_window_position(self.root)
        self.root.destroy()
        # run the launcher using runpy
        runpy.run_module("launcher", run_name="__main__")

    def add_to_ban_list_other(self):
        """
        Add to ban list function for any other server that is not requiem
        """
        url = "https://docs.google.com/spreadsheets/d/1V5Z61CKmJoNZn7L3PWziJdbHRVzYuxaZU4qTOIRHfWg/edit#gid=125271616"  # pylint: disable=line-too-long
        # open the url in the default browser
        webbrowser.open(url, new=2)
        time.sleep(self.delay)
        keyboard.press_and_release("ctrl + down")
        time.sleep(2)

        fields = [self.discord_name, self.discord_id, self.xbox_gt, self.xbox_id, self.server, self.reason]  # pylint: disable=line-too-long

        for field in fields:
            for value in field.get().split(","):
                if value == "Athena's Vanguard":
                    value = "AV"
                elif value == "Sea of Grogs":
                    value = "SoG"
                if value == "AV" or value == "SoG" or value == "Obsidian":
                    for _value in self.discord_name.get().split(","):
                        keyboard.press_and_release("down")
                        time.sleep(0.5)
                        keyboard.write(value.strip())
                else:
                    keyboard.press_and_release("down")
                    time.sleep(0.5)
                    keyboard.write(value.strip())
            time.sleep(0.5)
            keyboard.press_and_release("right")
            time.sleep(0.5)
            keyboard.press_and_release("ctrl + up")
            time.sleep(0.5)

        keyboard.press_and_release("right")
        time.sleep(0.5)
        self.discord_id.set("")
        self.discord_name.set("")
        self.xbox_gt.set("")
        self.xbox_id.set("")
        self.reason.set("")

    def start_requiem(self, string):
        """
        Add to ban list function for requiem
        """
        url = "https://docs.google.com/spreadsheets/d/1V5Z61CKmJoNZn7L3PWziJdbHRVzYuxaZU4qTOIRHfWg/edit#gid=125271616"  # pylint: disable=line-too-long
        # open the url in the default browser
        webbrowser.open(url, new=2)
        time.sleep(self.delay)
        keyboard.press_and_release("ctrl + down")
        time.sleep(2)
        keyboard.press_and_release("down")

        bans = string.split(")")

        for ban in bans:
            # ignore the ban if it is empty
            if ban == "":
                continue
            print(ban)

            # Split the string by the '-' character
            parts = ban.split("-")

            # Extract the gamertag and Discord tag
            gamertag = "N/A"
            discord_tag = "N/A"
            xuid = "N/A"
            gamertag = parts[0].split(":")[1].strip() if parts[0].split(":")[1].strip().count("?") < 3 else "N/A"  # pylint: disable=line-too-long
            for i, part in enumerate(parts):
                if i == 2:
                    discord_tag = part.strip()
                elif "DC:" in part:
                    part = part.replace("DC:", "")
                    xuid = part.strip() if part.strip().count("?") < 3 else "N/A"

            # Extract the user ID using a regular expression
            user_id_pattern = r"\d{17,19}"
            user_id_matches = re.findall(user_id_pattern, ban)
            user_id = user_id_matches[-1] if user_id_matches else "N/A"

            # Extract the reason
            reason = parts[-1].strip()

            keyboard.write(discord_tag)
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write(user_id)
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write(gamertag)
            time.sleep(0.5)
            keyboard.press_and_release("right")
            keyboard.write(xuid)
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

        self.requiem_ban.set("")


def start_script():
    """
    Starts the script.
    """
    root = Tk()
    window_positions.load_window_position(root)

    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    AddToBanList(root)
    root.mainloop()
