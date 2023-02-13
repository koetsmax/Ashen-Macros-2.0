# pylint: disable=E1101, W0614, W0401
from tkinter import *
from tkinter import ttk as tk
import time
import mss
import mss.tools
import pyautogui
import cv2
import numpy as np
from pynput.mouse import Button


def screenshot(self, big_image_path):
    discord_window = pyautogui.getWindowsWithTitle("Discord")[0]
    x, y, width, height = (
        discord_window.left,
        discord_window.top,
        discord_window.width,
        discord_window.height,
    )

    with mss.mss() as sct:
        # Get the screenshot of the Discord window
        monitor = {"top": y, "left": x, "width": width, "height": height}
        sct_img = sct.grab(monitor)

        # Save the screenshot to a file
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=big_image_path)


# look for @ sign and click it
def search_image(self, small_image, big_image_path):
    # Read the small image
    small_image = cv2.imread(small_image)

    # Convert the small image to grayscale
    small_image = cv2.cvtColor(small_image, cv2.COLOR_BGR2GRAY)

    # take a screenshot
    screenshot(self, big_image_path)

    # Read the big image
    big_image = cv2.imread(big_image_path)

    # Convert the big image to grayscale
    big_image = cv2.cvtColor(big_image, cv2.COLOR_BGR2GRAY)

    # Use the matchTemplate function to search for the small image in the big image
    result = cv2.matchTemplate(small_image, big_image, cv2.TM_CCOEFF_NORMED)

    # get width and height of the image

    w = small_image.shape[1]
    h = small_image.shape[0]

    # Use the np.where function to get the locations of the matches
    yloc, xloc = np.where(result >= 0.8)
    click_locations = []

    for (x, y) in zip(xloc, yloc):
        cv2.rectangle(big_image, (x, y), (x + w, y + h), (255, 0, 0), 2)

    rectangles = []
    for (x, y) in zip(xloc, yloc):
        rectangles.append([int(x), int(y), int(w), int(h)])
        rectangles.append([int(x), int(y), int(w), int(h)])

    rectangles, weights = cv2.groupRectangles(rectangles, 1, 0.2)

    for (x, y, w, h) in rectangles:
        # append the center of the image to click locations
        click_locations.append((x + w / 2, y + h / 2))

    # Show the images
    cv2.imshow("Result", big_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # Return the list of match locations
    return click_locations


def click_on_matches(self, click_locations):
    unchecked_match = []
    for (x, y) in click_locations:
        print(x, y)

        # time.sleep(5)
        self.mouse.position = (x, y)
        self.mouse.click(Button.left)
        time.sleep(0.5)
        result = search_image(self, "img/staffchecked.png", "img/discord.png")
        if result != []:
            print("User is staffchecked")
        else:
            unchecked_match.append((x, y))
            print("User is not staffchecked")

    for (x, y) in unchecked_match:
        self.mouse.position = (x, y)
        self.mouse.click(Button.right)
        result = search_image(self, "img/profile.png", "img/discord.png")
        if result == []:
            print("Match must have been a role, skipping")
        else:
            print(result)


def staffcheck_finder(self):
    click_locations = search_image(self, "img/atsign.png", "img/discord.png")

    click_on_matches(self, click_locations)
