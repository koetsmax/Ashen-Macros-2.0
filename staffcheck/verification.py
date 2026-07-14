import time

import keyboard
import keyring

from core.auth import get_token
from core.keyboard import clear_typing_bar, switch_channel


def start_verification(ctx, on_refresh=None):
    time.sleep(3)
    token = get_token()

    switch_channel(ctx, "derry_fastulfr", kwargs=True)
    clear_typing_bar()
    keyboard.write(f"!verifymeprettyplease {token}")
    time.sleep(3)
    keyboard.press_and_release("enter")
    time.sleep(2)
    if on_refresh:
        on_refresh()
