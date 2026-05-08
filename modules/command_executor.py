from tkinter import FALSE, BooleanVar, Menu, StringVar, Tk, Toplevel, ttk
import launcher  # pylint: disable=unused-import
from modules.submodules.functions import window_positions
import time
import keyboard
import threading
import ast
from modules.submodules.functions import widgets
from modules.submodules.functions import theme
from modules.submodules.functions.execute_command import execute_command
from modules.submodules.functions.clear_typing_bar import clear_typing_bar
from modules.submodules.functions.switch_channel import switch_channel


class CommandExecutor:
    def __init__(self, root):
        self.root = root
        self.root.title("Command Executor")
        self.root.option_add("*tearOff", FALSE)

        self.keyboard_lock = threading.Lock()

        # Create the menu
        self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="N, W, E, S")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        widgets.create_label(self.mainframe, "Command:", 1, 1, "E")
        self.command = StringVar()
        self.command_entry = widgets.create_entry(
            self.mainframe, self.command, 1, 2, "W, E", width=20
        )

        widgets.create_label(self.mainframe, "Parameters, max 1:", 2, 1, "E")
        self.params = StringVar()
        self.params_entry = widgets.create_entry(
            self.mainframe, self.params, 2, 2, "W, E", width=20
        )

        widgets.create_label(self.mainframe, "Members", 3, 1, "E")
        self.members = StringVar()
        self.members_entry = widgets.create_entry(
            self.mainframe, self.members, 3, 2, "W, E", width=20
        )

        self.start_button = widgets.create_button(
            self.mainframe,
            "Start!",
            lambda: self.start_command_executor(),  # pylint: disable=unnecesary-lambda
            4,
            2,
            "W, E",
        )

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def start_command_executor(self):
        print(self.command.get())
        print(self.params.get())
        time.sleep(5)
        print(self.members.get())
        members = ast.literal_eval(self.members.get())
        print(members)

        switch_channel(self, "#lieutenant-commands")
        clear_typing_bar()
        for member in members:
            member = str(member)
            command = [f"/{self.command.get()}", member]
            print(command)
            execute_command(self, command[0], command[1:])


def start_script():
    root = Tk()
    root.withdraw()
    window_positions.load_window_position(root)
    theme.apply_theme(root)

    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    CommandExecutor(root)
    theme.reveal_root(root)
    root.mainloop()
