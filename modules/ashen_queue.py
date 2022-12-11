# image recognition

import time

import cv2
import keyboard
import mss
from pynput.mouse import Button, Controller
import numpy as np
import os
from PIL import Image
import pytesseract
import re

# Some images we will use to dynamically find active leaves
# dirname = os.path.dirname(__file__)
path = os.path.dirname(os.path.dirname(__file__))
img_path = os.path.join(path, "img")


mouse = Controller()


def screen_shot(left=-768, top=-387, width=720, height=1900):
    """
    Takes a screenshot of the screen and returns it as a numpy array.
    """
    stc = mss.mss()
    scr = stc.grab({"left": left, "top": top, "width": width, "height": height})

    img = np.array(scr)
    img = cv2.cvtColor(img, cv2.IMREAD_COLOR)
    return img


while True:
    # get the image
    img = screen_shot()
    # convert it to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # load the template
    template = cv2.imread(os.path.join(img_path, "active_leave.png"), 0)
    # get the dimensions of the template
    w, h = template.shape[::-1]
    # perform the match
    res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    # get the threshold
    threshold = 0.8
    # get the locations of the matches
    loc = np.where(res >= threshold)
    # draw the rectangles
    for pt in zip(*loc[::-1]):
        cv2.rectangle(img, pt, (pt[0] + w, pt[1] + h), (0, 255, 255), 2)
    # show the image
    cv2.imshow("test", img)
    # wait for a key press
    cv2.waitKey(0)
    # destroy the window
    cv2.destroyAllWindows()
    # perform OCR on the image
    break

# import the necessary packages


# load the example image and convert it to grayscale
# gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# check to see if we should apply thresholding to preprocess the image
# gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

# write the grayscale image to disk as a temporary file so we can apply OCR to it
filename = "{}.png".format(os.getpid())
cv2.imwrite(filename, img)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# load the image as a PIL/Pillow image, apply OCR, and then delete the temporary file
text = pytesseract.image_to_string(Image.open(filename))
os.remove(filename)
# convert the text to lowercase
text = text.lower()
# delete anything from the text that comes before the text: "the buttons."
text = text.split("the buttons.\n\n")[1]
# delete anything from the text after "(ested)"
text = text.split("(ested)")[0]

# write the text to a file
with open("output.txt", "w") as f:
    f.write(text)

# every ] character indicates a new queue entry
# we will use this to determine the number of entries
# in the queue
entries = text.count("]")
print("There are {} entries in the queue.".format(entries))
# add the entries to a list with the activity they are in queue for
queue = []
for i in range(entries):
    # get the index of the first ] character
    index = text.index("]")
    # get the activity
    activity = text[:index]
    print(activity)
    # add the activity to the list
    queue.append(activity)
    # delete the activity from the text
    text = text[index + 1 :]

# print the queue
# print(queue)


def _queue(activity1, activity2, activity_list):
    for i in queue:
        print(i)


__queue = []
fotdqueue = []
wequeue = []
athenaqueue = []
ghqueue = []
oosqueue = []
maqueue = []
hcqueue = []
skqueue = []
sfqueue = []
ttqueue = []
anyqueue = []

_queue("fotd", "fort of the damned", fotdqueue)
_queue("we", "world events", wequeue)
_queue("athena", "athena", athenaqueue)
_queue("gh", "gold hoarders", ghqueue)
_queue("oos", "order of souls", oosqueue)
_queue("ma", "merchant", maqueue)
_queue("hc", "fishing", hcqueue)
_queue("sk", "sunken kingdom", skqueue)
_queue("sf", "sea forts", sfqueue)
_queue("tt", "tall tales", ttqueue)
_queue("any", "anything", anyqueue)

# print(
#     f"fort of the damned = {fotdqueue}\nworld events = {wequeue}\nathena = {athenaqueue}\n\
# gold hoarders = {ghqueue}\norder of souls = {oosqueue}\nmerchant = {maqueue}\nfishing = {hcqueue}\n\
# sunken kingdom = {skqueue}\nsea forts = {sfqueue}\ntall tales = {ttqueue}\nanything = {anyqueue}"
# )
