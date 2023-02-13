import time
import pyperclip
import keyboard


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


def add_queue_message(self):
    time.sleep(3)
    if self.queuemessage_ships == []:
        testtext = ":OoFAshen: :Tuck: **SHIPS ARE FULL, BUT QUEUE UP TO SECURE YOUR SPOT!** :Tuck: :OoFAshen:{```ansi{}[2;36mType }[2;33m!q }[2;32mACTIVITY }[2;36mOR select options from the dropdown menu!}[0m{```"
        type_queue_message(self, testtext)
    else:
        testtext = ":Gift: :Anchor: **SHIPS REQUIRING CREW! COME FILL THEM UP!** :Anchor: :Gift:{```ansi{}[2;36mType ^}[2;36mOR select options from the dropdown menu!}[0m{```"
        type_queue_message(self, testtext)
    testtext = "```ansi{}[2;31mAshen Alliance staff will }[4;31mNEVER}[0m}[2;31m message you on Xbox or Discord for an invite to the game. Do }[4;31mNOT}[0m}[2;31m invite anyone who is not in your voice channel.}[0m{```"
    type_queue_message(self, testtext)
    testtext = ":Ashen: **Pirates - We are looking for more officers! *Have you been here for at least 14 days?*- apply now in <#721293499185627146>** :Ashen:"
    type_queue_message(self, testtext)
