from tkinter import FALSE, BooleanVar, Menu, StringVar, Tk, Toplevel, ttk
import modules.submodules.functions.window_positions as window_positions


class Queue:
    def __init__(self, root):
        self.root = root


def start_script():
    """
    Starts the script.
    """
    root = Tk()
    window_positions.load_window_position(root)

    root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))
    Queue(root)
    root.mainloop()
