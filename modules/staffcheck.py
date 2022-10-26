# pylint: disable=E0401, E0402
from tkinter import *
from tkinter import ttk as tk
import configparser
import modules.submodules.start_check
from .submodules.build_example_message import (
    build_example_message,
    test_check_messages,
)


class StaffCheck:
    def __init__(self, root):
        self.good_window = None
        self.good_to_check_entry = None
        self.save_button = None
        self.reset_button = None
        self.example_label = None
        self.not_good_to_check_entry = None
        self.not_good_window = None
        self.example_label1 = None
        self.root = root
        self.config = configparser.ConfigParser()
        try:
            # parse staffcheck config
            self.config.read("settings.ini")
            self.good_to_check_message = self.config["STAFFCHECK"]["goodtocheckmessage"]
            self.not_good_to_check_message = self.config["STAFFCHECK"][
                "notgoodtocheckmessage"
            ]
        except KeyError:
            self.config["STAFFCHECK"] = {
                "goodtocheckmessage": "userID Good to check -- GT: xboxGT",
                "notgoodtocheckmessage": "userID **Not** Good to check -- GT: xboxGT -- Reason",
            }
            with open("settings.ini", "w", encoding="UTF-8") as configfile:
                self.config.write(configfile)
            self.config.read("settings.ini")
            self.good_to_check_message = self.config["STAFFCHECK"]["goodtocheckmessage"]
            self.not_good_to_check_message = self.config["STAFFCHECK"][
                "notgoodtocheckmessage"
            ]
        self.root.title("StaffCheck")
        self.root.option_add("*tearOff", FALSE)

        menubar = Menu(self.root)
        self.root["menu"] = menubar

        self.menu_customize = Menu(menubar)
        self.menu_help = Menu(menubar)

        menubar.add_cascade(menu=self.menu_customize, label="Customize")
        menubar.add_cascade(menu=self.menu_help, label="Help")

        self.menu_customize.add_command(
            label="Good to check message", command=self.EditGoodToCheck
        )
        self.menu_customize.add_command(
            label="Not good to check message", command=self.EditNotGoodToCheck
        )
        self.menu_help.add_command(label="Help", command=self.ShowHelp)

        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        tk.Label(self.mainframe, text="Discord ID:").grid(column=1, row=1, sticky=E)
        self.user_id = StringVar()
        self.user_id_entry = tk.Entry(
            self.mainframe, width=19, textvariable=self.user_id
        )
        self.user_id_entry.grid(column=2, row=1, sticky=(W, E))

        tk.Label(self.mainframe, text="GamerTag:").grid(column=1, row=2, sticky=E)
        self.xbox_gt = StringVar()
        self.xbox_gt_entry = tk.Entry(self.mainframe, textvariable=self.xbox_gt)
        self.xbox_gt_entry.grid(column=2, row=2, sticky=(W, E))

        tk.Label(self.mainframe, text="Channel:").grid(column=1, row=3, sticky=E)
        self.channel = StringVar(value="#on-duty-commands")
        self.channel_combo_box = tk.Combobox(self.mainframe, textvariable=self.channel)
        self.channel_combo_box.grid(column=2, row=3, sticky=(W, E))
        self.channel_combo_box["values"] = (
            "#staff-commands",
            "#on-duty-commands",
            "#captain-commands",
            "#admin-commands",
        )

        tk.Label(self.mainframe, text="Method:").grid(column=1, row=4, sticky=E)
        self.method = StringVar(value="All Commands")
        self.method_combo_box = tk.Combobox(self.mainframe, textvariable=self.method)
        self.method_combo_box.grid(column=2, row=4, sticky=(W, E))
        self.method_combo_box["values"] = (
            "All Commands",
            "Elemental Commands",
            "Ashen Commands",
            "Invite Tracker",
            "SOT Official",
            "Check Message",
        )

        self.check = BooleanVar(value=False)
        self.check_button = tk.Checkbutton(
            self.mainframe,
            variable=self.check,
            text="Check ID/GT in on-duty-chat",
            onvalue=1,
            offvalue=0,
        )
        self.check_button.grid(column=2, row=5, sticky=(W, E))

        self.progressbar = tk.Progressbar(
            self.mainframe, orient=HORIZONTAL, length=200, mode="determinate"
        )
        self.progressbar.grid(column=1, columnspan=2, row=9, sticky=(W, E))

        self.log = Text(
            self.mainframe, state="disabled", width=20, height=3, wrap="word"
        )
        self.log.grid(column=1, columnspan=2, row=10, sticky=(E, W))
        self.log.tag_configure("highlightline", font=("TkTextFont:", 10))

        self.function_button = tk.Button(self.mainframe, text="Cool Button")
        self.function_button.grid(column=1, row=5, sticky=(W, E))
        self.function_button.state(["disabled"])

        self.kill_button = tk.Button(
            self.mainframe, text="Kill Program", command=self.kill
        )
        self.kill_button.grid(column=1, row=6, sticky=(W, E))

        self.start_button = tk.Button(
            self.mainframe,
            text="Start check!",
            command=lambda: modules.submodules.start_check.start_check(self),
        )
        self.start_button.grid(columnspan=2, column=2, row=6, sticky=(E, W))

        test_check_messages(self)

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.user_id_entry.focus()

    def EditGoodToCheck(self):

        self.good_window = Toplevel()

        explanation_label = tk.Label(
            self.good_window, text="Discord ID = userID\nGamertag = xboxGT"
        )
        explanation_label.grid(rowspan=2, column=1, row=1, sticky=(W))

        good_to_check_label = tk.Label(self.good_window, text="Good to check message:")
        good_to_check_label.grid(column=1, row=3, sticky=W)

        self.good_to_check_message = StringVar(
            value=self.config["STAFFCHECK"]["goodtocheckmessage"]
        )
        self.good_to_check_entry = tk.Entry(
            self.good_window, width=60, textvariable=self.good_to_check_message
        )
        self.good_to_check_entry.grid(column=1, row=4, sticky=(E, W))

        build_example_message(self, 1)
        test_check_messages(self)

        self.save_button = tk.Button(
            self.good_window, text="Save Changes!", command=self.SaveChangesGood
        )
        self.save_button.grid(column=1, row=6, sticky=W)

        self.reset_button = tk.Button(
            self.good_window, text="Reset To Default!", command=self.ResetToDefaultGood
        )
        self.reset_button.grid(column=1, row=6, sticky=E)

        for child in self.good_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.root.eval(f"tk::PlaceWindow {str(self.good_window)} center")

    def SaveChangesGood(self):
        with open("settings.ini", "w", encoding="UTF-8") as configfile:
            self.example_label.destroy()
            self.config["STAFFCHECK"][
                "goodtocheckmessage"
            ] = self.good_to_check_message.get()
            self.config.write(configfile)
            build_example_message(self, 1)
            test_check_messages(self)

    def ResetToDefaultGood(self):
        with open("settings.ini", "w", encoding="UTF-8") as configfile:
            self.example_label.destroy()
            self.config["STAFFCHECK"][
                "goodtocheckmessage"
            ] = "userID Good to check -- GT: xboxGT"
            self.config.write(configfile)
            self.good_to_check_message.set("userID Good to check -- GT: xboxGT")
            build_example_message(self, 1)
            test_check_messages(self)

    def EditNotGoodToCheck(self):
        self.not_good_window = Toplevel()

        explanation_label = tk.Label(
            self.not_good_window,
            text="Discord ID = userID\nGamertag = xboxGT\nreason = Reason",
        )
        explanation_label.grid(rowspan=3, column=1, row=1, sticky=(W))

        not_good_to_check_label = tk.Label(
            self.not_good_window, text="Not Good to check message:"
        )
        not_good_to_check_label.grid(column=1, row=4, sticky=W)

        self.not_good_to_check_message = StringVar(
            value=self.config["STAFFCHECK"]["notgoodtocheckmessage"]
        )
        self.not_good_to_check_entry = tk.Entry(
            self.not_good_window, width=60, textvariable=self.not_good_to_check_message
        )
        self.not_good_to_check_entry.grid(column=1, row=5, sticky=(E, W))

        build_example_message(self, 0)
        test_check_messages(self)

        self.save_button = tk.Button(
            self.not_good_window, text="Save Changes!", command=self.SaveChangesNotGood
        )
        self.save_button.grid(column=1, row=7, sticky=W)

        self.reset_button = tk.Button(
            self.not_good_window,
            text="Reset To Default!",
            command=self.ResetToDefaultNotGood,
        )
        self.reset_button.grid(column=1, row=7, sticky=E)

        for child in self.not_good_window.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.root.eval(f"tk::PlaceWindow {str(self.not_good_window)} center")

    def SaveChangesNotGood(self):
        with open("settings.ini", "w", encoding="UTF-8") as configfile:
            self.example_label1.destroy()
            self.config["STAFFCHECK"][
                "notgoodtocheckmessage"
            ] = self.not_good_to_check_message.get()
            self.config.write(configfile)
            build_example_message(self, 0)
            test_check_messages(self)

    def ResetToDefaultNotGood(self):
        with open("settings.ini", "w", encoding="UTF-8") as configfile:
            self.example_label1.destroy()
            self.config["STAFFCHECK"][
                "notgoodtocheckmessage"
            ] = "userID **Not** Good to check -- GT: xboxGT -- Reason"
            self.config.write(configfile)
            self.not_good_to_check_message.set(
                "userID **Not** Good to check -- GT: xboxGT -- Reason"
            )
            build_example_message(self, 0)
            test_check_messages(self)

    def kill(self):
        self.root.destroy()

    def ShowHelp(self):
        print("test")


root = Tk()
root.eval("tk::PlaceWindow . center")
StaffCheck(root)
root.mainloop()
