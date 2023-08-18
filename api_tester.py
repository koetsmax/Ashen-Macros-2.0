import requests
import json
import sys
import os

url = "http://127.0.0.1:8000/elemental"

payload = {"userID": "347067894741336064", "gamertag": "FlipperParty741"}

# send post request
r = requests.post(url=url, json=payload, timeout=30)
# get response
print(r.text)