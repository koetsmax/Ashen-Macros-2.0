# pylint: disable=W1401, W0614, W0401
import re
from tkinter import *
from tkinter import ttk as tk


def index_queue(self):

    self.queue = []
    with open("queue.txt", "r", encoding="UTF-8") as queuemessage:
        queuemessagelines = queuemessage.readlines()
    for line in queuemessagelines:
        line = line.lower()
        match = re.search(
            "^(?P<number>\d+): @(?P<name>.*) -- (?P<activity>.*) \[(?P<time>\d+) minutes\]$",
            line,
        )

        if match:
            self.queue.append(
                {
                    "position": match.group("number"),
                    "name": match.group("name"),
                    "activity": match.group("activity"),
                    "time": match.group("time"),
                }
            )

    print(self.queue)


def index_ships(self):
    with open("infomessage.txt", "r", encoding="UTF-8") as infomessage:
        infomessage_lines = infomessage.readlines()
    self.ships = []

    for line in infomessage_lines:
        line = line.lower()
        match = re.search(":(.*): (fl|cfl) (\d+) - (.*) (brig|sloop|gal) (\d+)", line)
        if match:
            status, _type, fleet, name, _class, number = match.groups()
            self.ships.append(
                {
                    "status": status,
                    "type": _type,
                    "fleet": fleet,
                    "name": name,
                    "class": _class,
                    "number": number,
                }
            )
    print(self.ships)


def check_ships(self):

    index_queue(self)

    index_ships(self)

    try:
        self.processlabel.destroy()
    except AttributeError:
        pass
    try:
        self.unrecognized_label.destroy()
    except AttributeError:
        pass

    self.queuemessage_ships = []

    if self.ships != []:
        for ship in self.ships:
            # print(ship["name"])
            if "warn" in ship["status"]:
                # print(ship)
                for member in self.queue:
                    if member["activity"].find(ship["name"]) != -1:
                        print(
                            f"{ship['type']} {ship['fleet']} {ship['name']} {ship['type']} {ship['number']} needs {member}"
                        )
                        self.queue.remove(member)
                        break
                    else:
                        print(member["activity"], ship["name"])
                else:
                    self.queuemessage_ships.append(ship)
                    print(
                        f"{ship['type']} {ship['fleet']} {ship['name']} {ship['type']} {ship['number']} needs people, but no one is in queue"
                    )
            else:
                print(
                    f"{ship['type']} {ship['fleet']} {ship['name']} {ship['type']} {ship['number']} does not need people"
                )
    else:
        self.processlabel = tk.Label(self.mainframe, text="no ships need people")
        self.processlabel.grid(row=1, column=0, sticky="w")
