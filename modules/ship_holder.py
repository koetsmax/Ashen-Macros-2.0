from tkinter import FALSE, BooleanVar, Menu, StringVar, Tk, Toplevel, ttk
from typing import Callable, Optional
import launcher  # pylint: disable=unused-import
from modules.submodules.functions import window_positions
from modules.submodules.functions import theme


class ShipHolder:
    def __init__(self, root, on_back: Optional[Callable[[], None]] = None):
        self.root = root
        self.on_back = on_back
        self.root.title("Ship Holder")
        self.root.option_add("*tearOff", FALSE)

        # Create the menu
        self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="N, W, E, S")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)


def start_script():
    root = Tk()
    root.withdraw()
    window_positions.load_window_position(root)
    theme.apply_theme(root)

    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    ShipHolder(root)
    theme.reveal_root(root)
    root.mainloop()
