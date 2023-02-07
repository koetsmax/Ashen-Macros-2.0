import time
import keyboard
import re
from tkinter import *
from tkinter import ttk as tk
import pyperclip
import keyboard
from pynput.mouse import Button, Controller
from fuzzywuzzy import fuzz
import openai

mouse = Controller()


class AshenQueue:
    def __init__(self, root):
        """
        This class is the main class of the program, initializing the GUI and the other modules.
        """

        # read the token from openai.token
        with open("openai.token", "r", encoding="UTF-8") as token_file:
            openai.api_key = token_file.read()
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

        self.add_queue_message_button = tk.Button(
            self.mainframe, text="Add queue message", command=self.add_queue_message
        )
        self.add_queue_message_button.grid(column=4, row=1, sticky=(W, E))

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

        self.fotdqueue = self.index_queue("fotd", "fort of the damned")
        self.wequeue = self.index_queue("we", "world event")
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
            match = re.search(
                ":(.*): (fl|cfl) (\d+) - (.*) (brig|sloop|gal) (\d+)", line
            )
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
        except:
            pass
        try:
            self.unrecognized_label.destroy()
        except:
            pass

        self.queuemessage_ships = []

        if self.ships != []:
            for ship in self.ships:
                print(ship["name"])
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

    def check_existing_activities(self):

        ship_name_mapping = {
            "fotd": ["fotd", "fort of the damned"],
            "world events": ["world events", "we"],
            "athena": ["athena", "athena's", "af"],
            "gold hoarders": ["gold hoarders", "gold hoarder", "gh"],
            "order of souls": ["order of souls", "order of soul", "oos", "oss"],
            "merchant alliance": ["merchant alliance", "merchant", "ma"],
            "sea forts": ["sea forts", "sea fort", "sf"],
            "sunken kingdom": ["sunken kingdom", "shrine", "sk"],
            "adventure": ["adventure", "adventures", "adv"],
            "fishing": ["fishing", "fish", "hc"],
            "tall tales": ["tall tales", "tall tale", "tt"],
            # Add more ship name mappings here
        }

        # Define the invalid requests
        invalid_requests = []

        # Iterate over the activities
        for person in self.queue:
            # Define a flag to check if the activity is valid
            is_valid = False

            if "any" in person["activity"]:
                is_valid = True

            # Use static mapping to check if the activity is valid
            if not is_valid:
                for ship in self.ships:
                    if ship["name"] in ship_name_mapping:
                        mapping = ship_name_mapping[ship["name"]]
                        for mapped_name in mapping:
                            if mapped_name in person["activity"]:
                                is_valid = True
                                print(
                                    f"{person['activity']} is valid solved with static mapping first try"
                                )
                                break

            # Check if the activity is valid using fuzzy matching
            if not is_valid:
                for ship in self.ships:
                    ratio = fuzz.token_set_ratio(ship["name"], person["activity"])
                    if ratio >= 80:
                        is_valid = True
                        print(
                            f"{person['activity']} is valid solved with fuzzy matching first try"
                        )
                        break

            if not is_valid:
                # Ask GPT-3 to correct the spelling
                response = openai.Completion.create(
                    engine="text-davinci-003",
                    prompt=(
                        f"could you correct the spelling of '{person['activity']}'?"
                    ),
                )
                corrected_activity = response["choices"][0]["text"]
                corrected_activity = corrected_activity.strip().lower()
                print(f"corrected activity: {corrected_activity}")
                # Check if the corrected activity is valid using fuzzy matching and GPT-3
                for ship in self.ships:
                    ratio = fuzz.token_set_ratio(ship, corrected_activity)
                    if ratio >= 80:
                        is_valid = True
                        print(
                            f"{person['activity']} is valid solved with fuzzy matching second try"
                        )
                        break
                if not is_valid:
                    for ship in self.ships:
                        if ship["name"] in ship_name_mapping:
                            mapping = ship_name_mapping[ship["name"]]
                            for mapped_name in mapping:
                                if mapped_name in corrected_activity:
                                    is_valid = True
                                    print(
                                        f"{corrected_activity} is valid solved with static mapping second try"
                                    )
                                    break

            if not is_valid:
                invalid_requests.append(person)

        # Print the invalid requests
        print(invalid_requests)

    def add_queue_message(self):
        time.sleep(3)
        if self.queuemessage_ships == []:
            testtext = ":OoFAshen: :Tuck: **SHIPS ARE FULL, BUT QUEUE UP TO SECURE YOUR SPOT!** :Tuck: :OoFAshen:{```ansi{}[2;36mType }[2;33m!q }[2;32mACTIVITY }[2;36mOR select options from the dropdown menu!}[0m{```"
            self.type_queue_message(testtext)
        else:
            testtext = ":Gift: :Anchor: **SHIPS REQUIRING CREW! COME FILL THEM UP!** :Anchor: :Gift:{```ansi{}[2;36mType ^ }[2;36mOR select options from the dropdown menu!}[0m{```"
            self.type_queue_message(testtext)
        testtext = "```ansi{}[2;31mAshen Alliance staff will }[4;31mNEVER}[0m}[2;31m message you on Xbox or Discord for an invite to the game. Do }[4;31mNOT}[0m}[2;31m invite anyone who is not in your voice channel.}[0m{```"
        self.type_queue_message(testtext)
        testtext = ":Ashen: **Pirates - We are looking for more officers! *Have you been here for at least 14 days?*- apply now in <#721293499185627146>** :Ashen:"
        self.type_queue_message(testtext)

    def type_queue_message(self, string):
        pyperclip.copy("")
        chars = [char for char in string]
        for char in chars:
            if char == "}":
                keyboard.press_and_release("ctrl+v")
            elif char == "{":
                keyboard.press_and_release("shift+enter")
            elif char == "^":
                unique_activities = set()
                for ship in self.queuemessage_ships:
                    if ship["name"] not in unique_activities:
                        unique_activities.add(ship["name"])

                        keyboard.press_and_release("ctrl+v")
                        keyboard.write("[2;33m !q ")
                        keyboard.press_and_release("ctrl+v")
                        text = "[2;32mACTIVITY"
                        text = text.replace("ACTIVITY", ship["name"])
                        keyboard.write(text)
                        keyboard.press_and_release("ctrl+v")
                        keyboard.write("[0m |")
                keyboard.press_and_release("backspace")
            else:
                keyboard.write(char)


root = Tk()
root.eval("tk::PlaceWindow . center")
AshenQueue(root)
root.mainloop()


# todo:

# suggest processing using same way we do check for existing activities
# move functions into seperate files

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
