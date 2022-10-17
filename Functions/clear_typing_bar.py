import keyboard
from activate_window import activate_window

def clear_typing_bar():
    activate_window("discord")
    keyboard.press_and_release("ctrl+a")
    keyboard.press_and_release("backspace")

if __name__ == "__main__":
    print("---TESTING MODULE---")
    clear_typing_bar()