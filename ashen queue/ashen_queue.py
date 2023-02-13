# pylint: disable=W0614, W0401
from tkinter import *
from tkinter import ttk as tk
import openai
import submodules.add_queue_message
import submodules.check_existing_activities
import submodules.check_ships
import submodules.get_current_queue
import submodules.staffcheck_finder
from pynput.mouse import Controller


class AshenQueue:
    def __init__(self, root):
        """
        This class is the main class of the program, initializing the GUI and the other modules.
        """

        # read the token from openai.token
        with open("openai.token", "r", encoding="UTF-8") as token_file:
            openai.api_key = token_file.read()
        self.mouse = Controller()
        self.root = root
        self.queue = []
        self.info = []
        self.together = []
        self.captaincy = []
        self.queuelabel = None
        self.infolabel = None
        self.processlabel = None
        self.unrecognized_label = None
        # ship name mappings
        self.ship_name_mapping = {
            "fotd": ["fotd", "fort of the damned"],
            "world events": ["world event", "world events", "we"],
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
            self.mainframe,
            text="Check ships",
            command=lambda: submodules.check_ships.check_ships(self),
        )
        self.check_ships_button.grid(column=2, row=1, sticky=(W, E))

        self.check_existing_activities_button = tk.Button(
            self.mainframe,
            text="Check existing activities",
            command=lambda: submodules.check_existing_activities.check_existing_activities(
                self
            ),
        )
        self.check_existing_activities_button.grid(column=3, row=1, sticky=(W, E))

        self.add_queue_message_button = tk.Button(
            self.mainframe,
            text="Add queue message",
            command=lambda: submodules.add_queue_message.add_queue_message(self),
        )
        self.add_queue_message_button.grid(column=4, row=1, sticky=(W, E))

        self.staffcheck_finder_button = tk.Button(
            self.mainframe,
            text="Staffcheck finder",
            command=lambda: submodules.staffcheck_finder.staffcheck_finder(self),
        )
        self.staffcheck_finder_button.grid(column=5, row=1, sticky=(W, E))

    def start(self):
        submodules.get_current_queue.get_current_queue(self)
        try:
            self.queuelabel.destroy()
        except AttributeError:
            pass
        self.queuelabel = tk.Label(self.mainframe, text=self.queue)
        self.queuelabel.grid(column=1, row=2, sticky=(W, E))


root = Tk()
root.eval("tk::PlaceWindow . center")
AshenQueue(root)
root.mainloop()


# todo:
# full rewrite of check_ships
# suggest processing using same way we do check for existing activities


# get the gui looking less shit
# replace some print statements with gui labels
# create some sort of other decentralized gui that can run basically all commands


# create semi-auto staffchecker. runs staffchecked queue search and grab data from that
# to grab data grab everything and only keep data inside brackets
# then do @data in public channel to get user mention
# then copy that to get userid
# then do some magic to grab the xbox
# do staffcheck procedure
