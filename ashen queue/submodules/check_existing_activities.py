from fuzzywuzzy import fuzz
import openai


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
                prompt=(f"could you correct the spelling of '{person['activity']}'?"),
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
