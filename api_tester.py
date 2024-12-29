"""Simple program that tests the API endpoints"""

import requests

LOCAL_URL = "https://localhost:8000"
TESTING_URL = "https://192.168.1.2:8000"
PRODUCTION_URL = "https://ashen_api.famkoets.nl"

# print all 3 of the urls and let the user pick a number one to 3 for which one to use
print("1) Localhost (https://localhost:8000)")
print("2) Testing (ttps://192.168.1.2:8000)")
print("3) Production (https://ashen_api.famkoets.nl)")
url = input("Enter the number of the URL you want to use: ")

if url == "1":
    URL = LOCAL_URL
elif url == "2":
    URL = TESTING_URL
elif url == "3":
    URL = PRODUCTION_URL
else:
    print("Invalid input")
    exit()

payload = {"test": "true"}
# test the connection GET endpoint

endpoints = {
    "auth/connection": "get",
    "auth/validate_token": "post",
    "staffcheck/essential_data": "post",
    "staffcheck/elemental": "post",
    "staffcheck/search": "post",
    "staffcheck/sotofficial": "post",
    "staffcheck/invite": "post",
}

results = []

for endpoint, method in endpoints.items():
    if method == "get":
        response = requests.get(url=URL + "/" + endpoint, timeout=30, verify=False)
    else:
        response = requests.post(
            url=URL + "/" + endpoint, json=payload, timeout=30, verify=False
        )
    try:
        if response.json()["test"] == "success":
            results.append(f"{endpoint} is working")
        else:
            results.append(f"{endpoint} is not working")
    except Exception:  # pylint: disable=broad-except
        if response.status_code == 200 and method == "get":
            results.append(f"{endpoint} is working")
        else:
            results.append(f"{endpoint} is not working")

print("\n\n\n~~~~~~~~~~~~~~~RESULTS~~~~~~~~~~~~~~~\n")

# make the text green if it is working and red if it is not
for result in results:
    if "working" in result:
        print(f"\033[92m{result}\033[0m")
    else:
        print(f"\033[91m{result}\033[0m")

input("\n\nPress Enter to exit")
