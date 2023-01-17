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
    def index_queue(self, x, y, list):
        with open("queue.txt", "r", encoding="UTF-8") as queuemessage:
            queuemessagelines = queuemessage.readlines()
        for line in queuemessagelines:
            # remove everything in between the : and -- and remove the : and -- from the line
            part1 = line.split(":")
            part2 = line.split("--")
            try:
                line = part1[0] + part2[1]
            except IndexError:
                pass
            # check if the line contains the activity

            if x in line.casefold() or y in line.casefold():
                try:
                    queuenum = re.findall(r"\d+", line)[0]
                    list.append(queuenum)
                    print(f"number {queuenum} is in queue for {y}")
                except:
                    pass

    def check_ship(self, ship, _activity, queue, anyqueue):
        if queue and anyqueue:
            if queue[0] > anyqueue[0]:
                print(
                    f"{anyqueue[0]} is in queue for anything which is needed on ship {ship[0]} {ship[1]}"
                )
                anyqueue.remove(anyqueue[0])
            else:
                print(
                    f"{queue[0]} is in queue for {_activity} which is needed on ship {ship[0]} {ship[1]}"
                )
                queue.remove(queue[0])
        elif queue:
            print(
                f"{queue[0]} is in queue for {_activity} which is needed on ship {ship[0]} {ship[1]}"
            )
            queue.remove(queue[0])
        elif anyqueue:
            print(
                f"{anyqueue[0]} is in queue for anything which is needed on ship {ship[0]} {ship[1]}"
            )
            anyqueue.remove(anyqueue[0])
        else:
            print(
                f"no one in queue for {_activity} which is needed on ship {ship[0]} {ship[1]}"
            )

    def check_ships(self):
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

        self.index_queue("fotd", "fort of the damned", self.fotdqueue)
        self.index_queue("we", "world event", self.wequeue)
        self.index_queue("af", "athena", self.athenaqueue)
        self.index_queue("gh", "gold hoarders", self.ghqueue)
        self.index_queue("oos", "order of souls", self.oosqueue)
        self.index_queue("ma", "merchant", self.maqueue)
        self.index_queue("hc", "fishing", self.hcqueue)
        self.index_queue("sk", "sunken kingdom", self.skqueue)
        self.index_queue("sf", "sea forts", self.sfqueue)
        self.index_queue("tt", "tall tales", self.ttqueue)
        self.index_queue("any", "anything", self.anyqueue)

        print(
            f"fort of the damned = {self.fotdqueue}\nworld events = {self.wequeue}\nathena = {self.athenaqueue}\n\
        gold hoarders = {self.ghqueue}\norder of souls = {self.oosqueue}\nmerchant = {self.maqueue}\nfishing = {self.hcqueue}\n\
        sunken kingdom = {self.skqueue}\nsea forts = {self.sfqueue}\ntall tales = {self.ttqueue}\nanything = {self.anyqueue}"
        )

        # check if any of the ships need people
        with open("infomessage.txt", "r", encoding="UTF-8") as infomessage:
            infomessage_lines = infomessage.readlines()
        self.ships = []
        self.allships = []

        for line in infomessage_lines:

            if "warn" in line:
                line = line.lower()
                ship = []
                fleet = re.findall(r"\d+", line)[0]
                shipnum = re.findall(r"\d+", line)[1]
                ship.append(fleet)
                ship.append(shipnum)
                activity = line.split(" ")
                ship.append(activity[4])
                ship.append(activity[5])
                self.ships.append(ship)

            line = line.lower()
            self.allships.append(line)

        print(self.ships)

        self.ships = []
        for ship in self.allships:
            match = re.search(":(.*): (.*) - (.*)", ship)
            if match:
                status, fleet, name = match.groups()
                self.ships.append({"status": status, "fleet": fleet, "name": name})
        print(self.ships)

        # activity1 = "fotd"
        # activity2 = "fort of the damned"
        # if any(activity1 in ship['name'] or activity2 in ship['name'] for ship in ships):
        #     print("Activity found in a ship")
        # else:
        #     print("Activity not found in any ship")

        # check if there are people in queue for the ships that need people

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
                print(ship)
                if ship[2] == "fotd" or ship[2] == "fort":
                    self.check_ship(
                        ship, "fort of the damned", self.fotdqueue, self.anyqueue
                    )
                elif ship[2] == "world" or ship[2] == "we":
                    self.check_ship(ship, "world events", self.wequeue, self.anyqueue)
                elif ship[2] == "athena" or ship[2] == "af":
                    self.check_ship(ship, "athena", self.athenaqueue, self.anyqueue)
                elif ship[2] == "gold" or ship[2] == "gh":
                    self.check_ship(ship, "gold hoarders", self.ghqueue, self.anyqueue)
                elif ship[2] == "oos" or ship[2] == "order":
                    self.check_ship(
                        ship, "order of souls", self.oosqueue, self.anyqueue
                    )
                elif ship[2] == "merchant" or ship[2] == "ma":
                    self.check_ship(ship, "merchant", self.maqueue, self.anyqueue)
                elif ship[2] == "fishing":
                    self.check_ship(ship, "fishing", self.hcqueue, self.anyqueue)
                elif ship[2] == "sunken" or ship[2] == "sk":
                    self.check_ship(ship, "sunken kingdom", self.skqueue, self.anyqueue)
                elif ship[2] == "sea" or ship[2] == "sf":
                    self.check_ship(ship, "sea forts", self.sfqueue, self.anyqueue)
                elif ship[2] == "tall" or ship[2] == "tt":
                    self.check_ship(ship, "tall tales", self.ttqueue, self.anyqueue)
                else:
                    self.unrecognized_label = tk.Label(
                        self.mainframe,
                        text=f"activity {ship[2]} {ship[3]} not recognized (full name = {ship})",
                    )
                    self.unrecognized_label.grid(row=1, column=0, sticky="w")
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
        print(self.allships)
        for ship in self.allships:
            print(ship)
            if activity1 not in ship or activity2 not in ship or "voyage" in ship:
                if unique_elements != []:
                    print(
                        f"there is someone in queue for {activity2} which does not exist"
                    )
            else:
                print(f"dingdingding {activity2}")

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
        # self.check_activity("world", "we", unique_elements[1])
        # self.check_activity("athena", "af", unique_elements[2])
        # self.check_activity("gold", "gh", unique_elements[3])
        # self.check_activity("order", "oos", unique_elements[4])
        # self.check_activity("merchant", "ma", unique_elements[5])
        # self.check_activity("fishing", "hc", unique_elements[6])
        # self.check_activity("sunken", "sk", unique_elements[7])
        # self.check_activity("sea", "sf", unique_elements[8])
        # self.check_activity("tall", "tt", unique_elements[9])


root = Tk()
root.eval("tk::PlaceWindow . center")
AshenQueue(root)
root.mainloop()

# todo:
# fix check_activity function
# ^^ rework this to do it for every person in queue rather than every ship
# get the gui looking not shit
# replace print statements with gui labels
# sort the queue
# add a button for processing
# create some sort of other decentralized gui that can run basically all commands
# check if there are people in queue for unrecognized activities


# create semi-auto staffchecker. runs staffchecked queue search and grab data from that
# to grab data grab everything and only keep data inside brackets
# then do @data in public channel to get user mention
# then copy that to get userid
# then do some magic to grab the xbox
# do staffcheck procedure
