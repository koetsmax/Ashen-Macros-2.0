import openai
from fuzzywuzzy import fuzz

# Define the OpenAI API key

# Define the ship names and the activities
ships = ["fotd", "world events", "athena"]
activities = ["fort of the dammned", "world events", "athena's", "sea forts"]

ship_name_mapping = {
    "fotd": ["fotd", "fort of the damned"],
    "world events": ["world events", "we"],
    "athena": ["athena", "athena's", "af"],
    "gold hoarders": ["gold hoarders", "gold hoarder", "gh"],
    "order of souls": ["order of souls", "order of soul", "oos"],
    "merchant alliance": ["merchant alliance", "merchant", "ma"],
    "sea forts": ["sea forts", "sea fort", "sf"],
    "sunken kingdom": ["sunken kingdom", "shrine", "sk"],
    "adventure": ["adventure", "adventures", "adv"],
    "fishing": ["fishing", "fish", "hc"],
    "tall tales": ["tall tales", "tall tale", "tt"],
    # Add more ship name mappings here
}

print(ship_name_mapping.items())
# # Define the invalid requests
# invalid_requests = []

# # Iterate over the activities
# for activity in activities:
#     # Define a flag to check if the activity is valid
#     is_valid = False

#     # Check if the activity is valid using fuzzy matching
#     for ship in ships:
#         ratio = fuzz.token_set_ratio(ship, activity)
#         if ratio >= 80:
#             is_valid = True
#             print(f"{activity} is valid solved with fuzzy matching first try")
#             break

#     # If the activity is not valid and the ratio is less than 80%
#     if not is_valid:
#         for ship in ships:
#             if ship in ship_name_mapping:
#                 mapping = ship_name_mapping[ship]
#                 for mapped_name in mapping:
#                     if mapped_name in activity:
#                         is_valid = True
#                         break
#     if not is_valid:
#         # Ask GPT-3 to correct the spelling
#         response = openai.Completion.create(
#             engine="text-davinci-003",
#             prompt=(f"could you correct the spelling of '{activity}'?"),
#         )
#         corrected_activity = response["choices"][0]["text"]
#         corrected_activity = corrected_activity.strip().lower()
#         print(f"corrected activity: {corrected_activity}")
#         # Check if the corrected activity is valid using fuzzy matching and GPT-3
#         for ship in ships:
#             ratio = fuzz.token_set_ratio(ship, corrected_activity)
#             if ratio >= 80:
#                 is_valid = True
#                 print(f"{activity} is valid solved with fuzzy matching second try")
#                 break
#         if not is_valid:
#             for ship in ships:
#                 if ship in ship_name_mapping:
#                     mapping = ship_name_mapping[ship]
#                     for mapped_name in mapping:
#                         if mapped_name in corrected_activity:
#                             is_valid = True
#                             break

#     if not is_valid:
#         invalid_requests.append(activity)

# # Print the invalid requests
# print(invalid_requests)
