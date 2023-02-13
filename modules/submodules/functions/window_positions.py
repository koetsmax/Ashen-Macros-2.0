import configparser


def save_window_position(window, *args):
    config = configparser.ConfigParser()
    config.read("settings.ini")
    config["WINDOW"] = {
        "x_offset": str(window.winfo_x()),
        "y_offset": str(window.winfo_y()),
    }
    with open("settings.ini", "w", encoding="UTF-8") as file:
        config.write(file)
    if 1 in args:
        window.destroy()


def load_window_position(window):
    config = configparser.ConfigParser()
    config.read("settings.ini")
    if "WINDOW" in config:
        window.geometry(
            f"+{config['WINDOW']['x_offset']}+{config['WINDOW']['y_offset']}"
        )
