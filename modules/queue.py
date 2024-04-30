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

        self.root.title("Queue Monitor")
        self.root.option_add("*tearOff", FALSE)

        @self.sio.event()
        def connect():
            print("Connected to server")

        @self.sio.event()
        def disconnect():
            print("Disconnected from server")

        @self.sio.event()
        def queue(data):
            print(data)

        @self.sio.event()
        def info(data):
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


# on duty staff
# number of fleets
# number of ships
# any unidentifiable ships
# number of ships that need people

# number of people in queue normal
# number of people in queue per activity
# number of people shipswap vs normal
# any unidentifiable queue requests


# Need to spike another fleet?
# Spike difficulty (time of day, people in queue, day of week)
# Discord API status (use ping command from bot or scrape discordstatus.com)

# Pings in fleet chat without reaction (account for no read access)
# Pings in bot notices without reaction (account for no read access)
# New pings in last 15 seconds in queue
