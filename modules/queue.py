import threading
from tkinter import FALSE, BooleanVar, Menu, StringVar, Tk, Toplevel, ttk

import requests
from modules.threadedsio import ThreadedSocketClient

import modules.submodules.functions.window_positions as window_positions
import traceback


class Queue:
    def __init__(self, root, sio=None):
        self.root = root
        self.sio = sio or ThreadedSocketClient(url="http://localhost:5000", auth="Controller")

        self.root.title("Queue")

        @self.sio.event()
        def connect():
            print("Connected to server")

        @self.sio.event()
        def disconnect():
            print("Disconnected from server")

        @self.sio.event()
        def queue(data):
            print(data)


def start_script():
    """
    Starts the script.
    """
    try:
        root = Tk()
        client = Queue(root)

        def events():
            client.sio.events.processEvents()
            root.after(50, events)

        events()

        window_positions.load_window_position(root)

        root.protocol("WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1))

        root.mainloop()
    except Exception:
        traceback.print_exc()
