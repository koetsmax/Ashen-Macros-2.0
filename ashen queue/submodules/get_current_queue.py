# pylint: disable=W0614, W0401
import time
import keyboard
from tkinter import *
from pynput.mouse import Button


def get_current_queue(self):
    # Get the current queue

    self.mouse.position = (-19, 1448)
    time.sleep(0.5)
    self.mouse.press(Button.left)
    time.sleep(0.5)
    self.mouse.position = (-923, -382)
    time.sleep(0.5)
    self.mouse.release(Button.left)
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
