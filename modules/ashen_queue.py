import time

import re
from tkinter import *
from tkinter import ttk as tk
import keyboard
from pynput.mouse import Button, Controller

mouse = Controller()


class AshenQueue:
    def __init__(self, root):
        """
        This class is the main class of the program, initializing the GUI and the other modules.
        """
        self.root = root
        self.fotdqueue = []
        self.wequeue = []
        self.athenaqueue = []
        self.ghqueue = []
        self.oosqueue = []
        self.maqueue = []
        self.hcqueue = []
        self.skqueue = []
        self.sfqueue = []
        self.ttqueue = []
        self.anyqueue = []
        self.queue = []
        self.info = []
        self.together = []
        self.captaincy = []
        self.queuelabel = None
        self.infolabel = None
        self.processlabel = None
        self.unrecognized_label = None

        self.root.title("AshenQueue")
        self.root.option_add("*tearOff", FALSE)

        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.get_queue_buttom = tk.Button(
            self.mainframe, text="Get current queue", command=self.start
        )
        self.get_queue_buttom.grid(column=1, row=1, sticky=(W, E))

        self.check_ships_button = tk.Button(
            self.mainframe, text="Check ships", command=self.check_ships
        )
        self.check_ships_button.grid(column=2, row=1, sticky=(W, E))

        self.check_existing_activities_button = tk.Button(
            self.mainframe,
            text="Check existing activities",
            command=self.check_existing_activities,
        )
        self.check_existing_activities_button.grid(column=3, row=1, sticky=(W, E))

    def start(self):
        self.get_current_queue()
        try:
            self.queuelabel.destroy()
        except:
            pass
        self.queuelabel = tk.Label(self.mainframe, text=self.queue)
        self.queuelabel.grid(column=1, row=2, sticky=(W, E))

    def get_current_queue(self):
        # Get the current queue

        mouse.position = (-19, 1448)
        time.sleep(0.5)
        mouse.press(Button.left)
        time.sleep(0.5)
        mouse.position = (-923, -382)
        time.sleep(0.5)
        mouse.release(Button.left)
        time.sleep(0.5)
        keyboard.press_and_release("ctrl + c")
        time.sleep(0.5)
        # copy the clipboard into a variable
        full_queue = Tk().clipboard_get()

        # locate the text "Ashen Alliance Queue" and remove everything before it
        start = full_queue.find("Ashen Alliance Queue")
        self.queue = full_queue[start:]

        # locate the first | and remove everything after it
        if "|" in self.queue:
            first_pipe = self.queue.find("|")
            self.queue = self.queue[: first_pipe - 30]
        else:
            # locate the text "SHIPS ARE FULL, BUT QUEUE UP TO SECURE YOUR SPOT!" and remove everything after it
            first_pipe = self.queue.find(
                "SHIPS ARE FULL, BUT QUEUE UP TO SECURE YOUR SPOT!"
            )
            self.queue = self.queue[:first_pipe]

        # locate the last ] and remove everything after it
        last_bracket = self.queue.rfind("]")
        self.queue = self.queue[: last_bracket + 1]

        # put the new queue in a text file
        with open("queue.txt", "w", encoding="UTF-8") as f:
            f.write(self.queue)

        # locate the text "Closed Ships" and remove everything before it
        start = full_queue.find("Closed Ships")
        self.info = full_queue[start:]

        # locate the text "Ashen Alliance Queue" and remove everything after it
        end = self.info.find("Ashen Alliance Queue")
        self.info = self.info[:end]

        # put the new info in a text file
        with open("infomessage.txt", "w", encoding="UTF-8") as f:
            f.write(self.info)

    #     # only a true shipswap if in bold but program wont know that
    #     self.together = together
    #     self.captaincy = captaincy
    #     pass

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

        self.fotdqueue = self.index_queue("fotd", "fort of the damned")
        self.wequeue = self.index_queue("we", "world event")
        print(self.wequeue)
        self.athenaqueue = self.index_queue("af", "athena")
        self.ghqueue = self.index_queue("gh", "gold hoarders")
        self.oosqueue = self.index_queue("oos", "order of souls")
        self.maqueue = self.index_queue("ma", "merchant")
        self.hcqueue = self.index_queue("hc", "fish")
        self.skqueue = self.index_queue("sk", "sunken kingdom")
        self.sfqueue = self.index_queue("sf", "sea fort")
        self.ttqueue = self.index_queue("tt", "tall tale")
        self.anyqueue = self.index_queue("any", "anything")

        # print(
        #     f"fort of the damned = {self.fotdqueue}\nworld events = {self.wequeue}\nathena = {self.athenaqueue}\n\
        # gold hoarders = {self.ghqueue}\norder of souls = {self.oosqueue}\nmerchant = {self.maqueue}\nfishing = {self.hcqueue}\n\
        # sunken kingdom = {self.skqueue}\nsea forts = {self.sfqueue}\ntall tales = {self.ttqueue}\nanything = {self.anyqueue}"
        # )

        # check if any of the ships need people
        with open("infomessage.txt", "r", encoding="UTF-8") as infomessage:
            infomessage_lines = infomessage.readlines()
        self.ships = []

        for line in infomessage_lines:
            line = line.lower()
            match = re.search(":(.*): (.*) - (.*)", line)
            if match:
                status, fleet, name = match.groups()
                self.ships.append({"status": status, "fleet": fleet, "name": name})
        print(self.ships)

        try:
            self.processlabel.destroy()
        except:
            pass
        try:
            self.unrecognized_label.destroy()
        except:
            pass

        if self.ships != []:
            for ship in self.ships:
                if "warn" in ship["status"]:
                    print(ship)
                    if "fotd" in ship["name"] or "fort" in ship["name"]:
                        self.check_ship(
                            ship, "fort of the damned", self.fotdqueue, self.anyqueue
                        )
                    elif "we" in ship["name"] or "world" in ship["name"]:
                        self.check_ship(
                            ship, "world events", self.wequeue, self.anyqueue
                        )
                    elif "af" in ship["name"] or "athena" in ship["name"]:
                        self.check_ship(ship, "athena", self.athenaqueue, self.anyqueue)
                    elif "gh" in ship["name"] or "gold" in ship["name"]:
                        self.check_ship(
                            ship, "gold hoarders", self.ghqueue, self.anyqueue
                        )
                    elif "oos" in ship["name"] or "order" in ship["name"]:
                        self.check_ship(
                            ship, "order of souls", self.oosqueue, self.anyqueue
                        )
                    elif "ma" in ship["name"] or "merchant" in ship["name"]:
                        self.check_ship(ship, "merchant", self.maqueue, self.anyqueue)
                    elif "hc" in ship["name"] or "fishing" in ship["name"]:
                        self.check_ship(ship, "fishing", self.hcqueue, self.anyqueue)
                    elif "sk" in ship["name"] or "sunken" in ship["name"]:
                        self.check_ship(
                            ship, "sunken kingdom", self.skqueue, self.anyqueue
                        )
                    elif "sf" in ship["name"] or "sea" in ship["name"]:
                        self.check_ship(ship, "sea forts", self.sfqueue, self.anyqueue)
                    elif "tt" in ship["name"] or "tall" in ship["name"]:
                        self.check_ship(ship, "tall tales", self.ttqueue, self.anyqueue)
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

    def compare_lists(self, lists):
        # Create a list to store the unique elements for each input list
        unique_elements = []

        # Iterate over the input lists
        for i, list1 in enumerate(lists):
            # Create an empty list to store the unique elements for this input list
            only_in_list1 = []

            # Iterate over the elements in list1
            for element in list1:
                # Initialize a flag to track whether the element is unique to list1
                is_unique = True

                # Iterate over the other input lists
                for j, list2 in enumerate(lists):
                    # Skip the current list (list1) and lists that have already been processed
                    if i == j:
                        continue

                    # If the element is in one of the other lists, it is not unique to list1
                    if element in list2:
                        is_unique = False
                        break

                # If the element is unique to list1, add it to the only_in_list1 list
                if is_unique:
                    only_in_list1.append(element)

            # Add the list of unique elements for this input list to the unique_elements list
            unique_elements.append(only_in_list1)

        # Return the list of lists of unique elements
        return unique_elements

    def check_activity(self, activity1, activity2, unique_elements):
        if not any(
            activity1 in ship["name"]
            or activity2 in ship["name"]
            or "voyage" in ship["name"]
            for ship in self.ships
        ):
            if unique_elements != []:
                print(f"there is someone in queue for {activity1} which does not exist")

    def check_existing_activities(self):
        # compare two lists and check if there are numbers that are only in one list

        # Add all queues to one list
        allqueue = []
        allqueue.append(self.fotdqueue)
        allqueue.append(self.wequeue)
        allqueue.append(self.athenaqueue)
        allqueue.append(self.ghqueue)
        allqueue.append(self.oosqueue)
        allqueue.append(self.maqueue)
        allqueue.append(self.hcqueue)
        allqueue.append(self.skqueue)
        allqueue.append(self.sfqueue)
        allqueue.append(self.ttqueue)
        allqueue.append(self.anyqueue)
        # Check if anyone is in queue for only one activity
        unique_elements = self.compare_lists(allqueue)
        print(f"unique_elements = {unique_elements}")

        # check if there are people in queue for an activity that does not exist
        self.check_activity("fort", "fotd", unique_elements[0])
        self.check_activity("world", "we", unique_elements[1])
        self.check_activity("athena", "af", unique_elements[2])
        self.check_activity("gold", "gh", unique_elements[3])
        self.check_activity("order", "oos", unique_elements[4])
        self.check_activity("merchant", "ma", unique_elements[5])
        self.check_activity("fishing", "hc", unique_elements[6])
        self.check_activity("sunken", "sk", unique_elements[7])
        self.check_activity("sea", "sf", unique_elements[8])
        self.check_activity("tall", "tt", unique_elements[9])


root = Tk()
root.eval("tk::PlaceWindow . center")
AshenQueue(root)
root.mainloop()

# todo:
# rework check_activity function
# ^^ rework this to do it for every person in queue rather than every ship
# get the gui looking not shit
# replace print statements with gui labels
# sort the queue
# add a button for processing
# create some sort of other decentralized gui that can run basically all commands


# create semi-auto staffchecker. runs staffchecked queue search and grab data from that
# to grab data grab everything and only keep data inside brackets
# then do @data in public channel to get user mention
# then copy that to get userid
# then do some magic to grab the xbox
# do staffcheck procedure
