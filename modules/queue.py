import threading
from tkinter import FALSE, BooleanVar, Menu, StringVar, Tk, Toplevel, ttk, IntVar

import requests
from modules.threadedsio import ThreadedSocketClient

import modules.submodules.functions.window_positions as window_positions
import traceback
import modules.submodules.functions.widgets as widgets


class Queue:
    def __init__(self, root, sio=None):
        self.root = root
        self.sio = sio or ThreadedSocketClient(
            url="http://192.168.1.3:5000", auth="Controller"
        )
        self.mainframe = ttk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky="NWES")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.root.title("Queue Monitor")
        self.root.option_add("*tearOff", FALSE)

        # create a stringvar with the value Initializing...
        self.active = StringVar(value="Initializing...")

        print(self.active.get())

        # Create the variables for the queue options
        self.queue_total = IntVar(value=0)
        self.queue_any = IntVar(value=0)
        self.queue_fotd = IntVar(value=0)
        self.queue_we = IntVar(value=0)
        self.queue_gh = IntVar(value=0)
        self.queue_mrcnt = IntVar(value=0)
        self.queue_oos = IntVar(value=0)
        self.queue_rpr = IntVar(value=0)
        self.queue_atn = IntVar(value=0)
        self.queue_hc = IntVar(value=0)
        self.queue_sk = IntVar(value=0)
        self.queue_sf = IntVar(value=0)
        self.queue_tt = IntVar(value=0)
        self.queue_ss = IntVar(value=0)
        self.queue_unk = IntVar(value=0)

        # Create the variables for the ship options
        self.ships_total = IntVar(value=0)
        self.ships_fotd = IntVar(value=0)
        self.ships_we = IntVar(value=0)
        self.ships_gh = IntVar(value=0)
        self.ships_mrcnt = IntVar(value=0)
        self.ships_oos = IntVar(value=0)
        self.ships_rpr = IntVar(value=0)
        self.ships_atn = IntVar(value=0)
        self.ships_hc = IntVar(value=0)
        self.ships_sk = IntVar(value=0)
        self.ships_sf = IntVar(value=0)
        self.ships_tt = IntVar(value=0)
        self.ships_ss = IntVar(value=0)
        self.ships_unk = IntVar(value=0)

        self.label_active = widgets.create_label(
            self.mainframe, f"Queue: {self.active.get()}", 0, 0
        )
        self.label_total = widgets.create_label(
            self.mainframe,
            f"Total ({self.ships_total.get()}): {self.queue_total.get()}",
            1,
            0,
        )
        self.label_any = widgets.create_label(
            self.mainframe, f"Anything: {self.queue_any.get()}", 2, 0
        )
        self.label_fotd = widgets.create_label(
            self.mainframe,
            f"Fort of the Damned ({self.ships_fotd.get()}): {self.queue_fotd.get()}",
            3,
            0,
        )
        self.label_we = widgets.create_label(
            self.mainframe,
            f"World Events ({self.ships_we.get()}): {self.queue_we.get()}",
            4,
            0,
        )
        self.label_gh = widgets.create_label(
            self.mainframe,
            f"Gold Hoarders ({self.ships_gh.get()}): {self.queue_gh.get()}",
            5,
            0,
        )
        self.label_mrcnt = widgets.create_label(
            self.mainframe,
            f"Merchant ({self.ships_mrcnt.get()}): {self.queue_mrcnt.get()}",
            6,
            0,
        )
        self.label_oos = widgets.create_label(
            self.mainframe,
            f"Order of Souls ({self.ships_oos.get()}): {self.queue_oos.get()}",
            7,
            0,
        )
        self.label_rpr = widgets.create_label(
            self.mainframe,
            f"Reaper ({self.ships_rpr.get()}): {self.queue_rpr.get()}",
            8,
            0,
        )
        self.label_atn = widgets.create_label(
            self.mainframe,
            f"Athena ({self.ships_atn.get()}): {self.queue_atn.get()}",
            9,
            0,
        )
        self.label_hc = widgets.create_label(
            self.mainframe,
            f"Fishing ({self.ships_hc.get()}): {self.queue_hc.get()}",
            10,
            0,
        )
        self.label_sk = widgets.create_label(
            self.mainframe,
            f"Sunken Kingdom ({self.ships_sk.get()}): {self.queue_sk.get()}",
            11,
            0,
        )
        self.label_sf = widgets.create_label(
            self.mainframe,
            f"Sea Forts ({self.ships_sf.get()}): {self.queue_sf.get()}",
            12,
            0,
        )
        self.label_tt = widgets.create_label(
            self.mainframe,
            f"Tall Tales ({self.ships_tt.get()}): {self.queue_tt.get()}",
            13,
            0,
        )
        self.label_ss = widgets.create_label(
            self.mainframe,
            f"Siren Song ({self.ships_ss.get()}): {self.queue_ss.get()}",
            14,
            0,
        )
        self.label_unk = widgets.create_label(
            self.mainframe,
            f"Unknown ({self.ships_unk.get()}): {self.queue_unk.get()}",
            15,
            0,
        )

        @self.sio.event()
        def connect():
            print("Connected to server")

        @self.sio.event()
        def disconnect():
            print("Disconnected from server")

        @self.sio.event()
        def queue(data):
            print(f"queue: {data}")
            print(data.get("active"))
            if data.get("active"):
                self.active.set("Active")
            else:
                self.active.set("Stopped")

            self.queue_total.set(len(data.get("queue")))
            self.queue_any.set(0)
            self.queue_fotd.set(0)
            self.queue_we.set(0)
            self.queue_gh.set(0)
            self.queue_mrcnt.set(0)
            self.queue_oos.set(0)
            self.queue_rpr.set(0)
            self.queue_atn.set(0)
            self.queue_hc.set(0)
            self.queue_sk.set(0)
            self.queue_sf.set(0)
            self.queue_tt.set(0)
            self.queue_ss.set(0)
            self.queue_unk.set(0)

            for entry in data.get("queue"):
                if "anything" in entry["activity"].lower():
                    self.queue_any.set(self.queue_any.get() + 1)
                if "fort of the damned" in entry["activity"].lower():
                    self.queue_fotd.set(self.queue_fotd.get() + 1)
                if "world events" in entry["activity"].lower():
                    self.queue_we.set(self.queue_we.get() + 1)
                if "athena" in entry["activity"].lower():
                    self.queue_atn.set(self.queue_atn.get() + 1)
                if "gold hoarders" in entry["activity"].lower():
                    self.queue_gh.set(self.queue_gh.get() + 1)
                if "order of souls" in entry["activity"].lower():
                    self.queue_oos.set(self.queue_oos.get() + 1)
                if "merchant alliance" in entry["activity"].lower():
                    self.queue_mrcnt.set(self.queue_mrcnt.get() + 1)
                if "sea forts" in entry["activity"].lower():
                    self.queue_sf.set(self.queue_sf.get() + 1)
                if "sunken kingdom" in entry["activity"].lower():
                    self.queue_sk.set(self.queue_sk.get() + 1)
                if "fishing" in entry["activity"].lower():
                    self.queue_hc.set(self.queue_hc.get() + 1)
                if "tall tale" in entry["activity"].lower():
                    self.queue_tt.set(self.queue_tt.get() + 1)
                if "siren song" in entry["activity"].lower():
                    self.queue_tt.set(self.queue_tt.get() + 1)
                if "reaper" in entry["activity"].lower():
                    self.queue_rpr.set(self.queue_rpr.get() + 1)
                if not entry["is_known"] and not entry["manual_override"]:
                    self.queue_unk.set(self.queue_unk.get() + 1)

            self.label_active.config(text=f"Queue: {self.active.get()}")
            self.label_total.config(
                text=f"Total ({self.ships_total.get()}): {self.queue_total.get()}"
            )
            self.label_any.config(text=f"Anything: {self.queue_any.get()}")
            self.label_fotd.config(
                text=f"Fort of the Damned ({self.ships_fotd.get()}): {self.queue_fotd.get()}"
            )
            self.label_we.config(
                text=f"World Events ({self.ships_we.get()}): {self.queue_we.get()}"
            )
            self.label_gh.config(
                text=f"Gold Hoarders ({self.ships_gh.get()}): {self.queue_gh.get()}"
            )
            self.label_mrcnt.config(
                text=f"Merchant ({self.ships_mrcnt.get()}): {self.queue_mrcnt.get()}"
            )
            self.label_oos.config(
                text=f"Order of Souls ({self.ships_oos.get()}): {self.queue_oos.get()}"
            )
            self.label_rpr.config(
                text=f"Reaper ({self.ships_rpr.get()}): {self.queue_rpr.get()}"
            )
            self.label_atn.config(
                text=f"Athena ({self.ships_atn.get()}): {self.queue_atn.get()}"
            )
            self.label_hc.config(
                text=f"Fishing ({self.ships_hc.get()}): {self.queue_hc.get()}"
            )
            self.label_sk.config(
                text=f"Sunken Kingdom ({self.ships_sk.get()}): {self.queue_sk.get()}"
            )
            self.label_sf.config(
                text=f"Sea Forts ({self.ships_sf.get()}): {self.queue_sf.get()}"
            )
            self.label_tt.config(
                text=f"Tall Tales ({self.ships_tt.get()}): {self.queue_tt.get()}"
            )
            self.label_ss.config(
                text=f"Siren Song ({self.ships_ss.get()}): {self.queue_ss.get()}"
            )
            self.label_unk.config(
                text=f"Unknown ({self.ships_unk.get()}): {self.queue_unk.get()}"
            )

        @self.sio.event()
        def info(data):
            print(f"info: {data}")
            self.ships_total.set(len(data))
            self.ships_fotd.set(0)
            self.ships_we.set(0)
            self.ships_gh.set(0)
            self.ships_mrcnt.set(0)
            self.ships_oos.set(0)
            self.ships_rpr.set(0)
            self.ships_atn.set(0)
            self.ships_hc.set(0)
            self.ships_sk.set(0)
            self.ships_sf.set(0)
            self.ships_tt.set(0)
            self.ships_ss.set(0)
            self.ships_unk.set(0)

            for ship in data:
                if "fotd" in ship["activity"].lower():
                    self.ships_fotd.set(self.ships_fotd.get() + 1)
                if "world event" in ship["activity"].lower():
                    self.ships_we.set(self.ships_we.get() + 1)
                if "athena" in ship["activity"].lower():
                    self.ships_atn.set(self.ships_atn.get() + 1)
                if "gold hoarder" in ship["activity"].lower():
                    self.ships_gh.set(self.ships_gh.get() + 1)
                if (
                    "order of souls" in ship["activity"].lower()
                    or "oos" in ship["activity"].lower()
                ):
                    self.ships_oos.set(self.ships_oos.get() + 1)
                if "merchant" in ship["activity"].lower():
                    self.ships_mrcnt.set(self.ships_mrcnt.get() + 1)
                if "sea fort" in ship["activity"].lower():
                    self.ships_sf.set(self.ships_sf.get() + 1)
                if "sunken kingdom" in ship["activity"].lower():
                    self.ships_sk.set(self.ships_sk.get() + 1)
                if "fishing" in ship["activity"].lower():
                    self.ships_hc.set(self.ships_hc.get() + 1)
                if "tall tale" in ship["activity"].lower():
                    self.ships_tt.set(self.ships_tt.get() + 1)
                if "reaper" in ship["activity"].lower():
                    self.ships_rpr.set(self.ships_rpr.get() + 1)
                if ship["siren_song"]:
                    self.ships_ss.set(self.ships_ss.get() + 1)

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=2, pady=2)


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

        root.protocol(
            "WM_DELETE_WINDOW", lambda: window_positions.save_window_position(root, 1)
        )

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
