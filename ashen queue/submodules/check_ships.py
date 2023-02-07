import re
from tkinter import *
from tkinter import ttk as tk


def index_queue(self, activity1, activity2):
    return list(
        filter(
            lambda member: member["activity"] in [activity1, activity2],
            self.queue,
        )
    )


def check_ship(self, ship, _activity, queue, anyqueue):
    if queue and anyqueue:
        if queue[0] > anyqueue[0]:
            print(
                f"{anyqueue[0]} is in queue for anything which is needed on {ship['fleet']} {ship['name']}"
            )
            anyqueue.remove(anyqueue[0])
        else:
            print(
                f"{queue[0]} is in queue for {_activity} which is needed on {ship['fleet']} {ship['name']}"
            )
            queue.remove(queue[0])
    elif queue:
        print(
            f"{queue[0]} is in queue for {_activity} which is needed on {ship['fleet']} {ship['name']}"
        )
        queue.remove(queue[0])
    elif anyqueue:
        print(
            f"{anyqueue[0]} is in queue for anything which is needed on {ship['fleet']} {ship['name']}"
        )
        anyqueue.remove(anyqueue[0])
    else:
        self.queuemessage_ships.append(ship)
        print(
            f"no one in queue for {_activity} which is needed on {ship['fleet']} {ship['name']}"
        )


def check_ships(self):

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

    self.fotdqueue = index_queue(self, "fotd", "fort of the damned")
    self.wequeue = index_queue(self, "we", "world event")
    self.athenaqueue = index_queue(self, "af", "athena")
    self.ghqueue = index_queue(self, "gh", "gold hoarders")
    self.oosqueue = index_queue(self, "oos", "order of souls")
    self.maqueue = index_queue(self, "ma", "merchant")
    self.hcqueue = index_queue(self, "hc", "fish")
    self.skqueue = index_queue(self, "sk", "sunken kingdom")
    self.sfqueue = index_queue(self, "sf", "sea fort")
    self.ttqueue = index_queue(self, "tt", "tall tale")
    self.anyqueue = index_queue(self, "any", "anything")

    # check if any of the ships need people
    with open("infomessage.txt", "r", encoding="UTF-8") as infomessage:
        infomessage_lines = infomessage.readlines()
    self.ships = []

    for line in infomessage_lines:
        line = line.lower()
        match = re.search(":(.*): (fl|cfl) (\d+) - (.*) (brig|sloop|gal) (\d+)", line)
        if match:
            status, ship_type, fleet, name, ship_class, ship_number = match.groups()
            self.ships.append(
                {
                    "status": status,
                    "ship_type": ship_type,
                    "fleet": fleet,
                    "name": name,
                    "ship_class": ship_class,
                    "ship_number": ship_number,
                }
            )
    print(self.ships)

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
            print(ship["name"])
            if "warn" in ship["status"]:
                print(ship)
                if "fotd" in ship["name"] or "fort" in ship["name"]:
                    check_ship(
                        self, ship, "fort of the damned", self.fotdqueue, self.anyqueue
                    )
                elif "we" in ship["name"] or "world" in ship["name"]:
                    check_ship(self, ship, "world events", self.wequeue, self.anyqueue)
                elif "af" in ship["name"] or "athena" in ship["name"]:
                    check_ship(self, ship, "athena", self.athenaqueue, self.anyqueue)
                elif "gh" in ship["name"] or "gold" in ship["name"]:
                    check_ship(self, ship, "gold hoarders", self.ghqueue, self.anyqueue)
                elif "oos" in ship["name"] or "order" in ship["name"]:
                    check_ship(
                        self, ship, "order of souls", self.oosqueue, self.anyqueue
                    )
                elif "ma" in ship["name"] or "merchant" in ship["name"]:
                    check_ship(self, ship, "merchant", self.maqueue, self.anyqueue)
                elif "hc" in ship["name"] or "fishing" in ship["name"]:
                    check_ship(self, ship, "fishing", self.hcqueue, self.anyqueue)
                elif "sk" in ship["name"] or "sunken" in ship["name"]:
                    check_ship(
                        self, ship, "sunken kingdom", self.skqueue, self.anyqueue
                    )
                elif "sf" in ship["name"] or "sea" in ship["name"]:
                    check_ship(self, ship, "sea forts", self.sfqueue, self.anyqueue)
                elif "tt" in ship["name"] or "tall" in ship["name"]:
                    check_ship(self, ship, "tall tales", self.ttqueue, self.anyqueue)
                else:
                    self.unrecognized_label = tk.Label(
                        self.mainframe,
                        text=f"activity {ship['name']} not recognized (full name = {ship})",
                    )
                    self.unrecognized_label.grid(row=1, column=0, sticky="w")
            else:
                print(f"{ship['fleet']} {ship['name']} does not need people")
    else:
        self.processlabel = tk.Label(self.mainframe, text="no ships need people")
        self.processlabel.grid(row=1, column=0, sticky="w")
