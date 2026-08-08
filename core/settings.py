import configparser
import os
from filelock import FileLock

DATA_DIR = os.path.expanduser("~/Documents/Ashen Macros")
CONFIG_FILE_PATH = os.path.join(DATA_DIR, "settings.ini")
LOCK_FILE_PATH = CONFIG_FILE_PATH + ".lock"
LOCK_TIMEOUT = 30


def read_config() -> dict:
    config = configparser.ConfigParser()
    with FileLock(LOCK_FILE_PATH, timeout=LOCK_TIMEOUT):
        file_missing = False
        try:
            _read_config_file(config)
        except (configparser.Error, FileNotFoundError):
            file_missing = True

        defaults_added = _set_default_values(config)
        if file_missing or defaults_added:
            _write_config_file(config)

        return _read_config_values(config)


def config_bool(key: str, default: str = "false") -> bool:
    """Parse a settings.ini string flag as bool (1/true/yes/on)."""
    return str(read_config().get(key, default)).lower() in ("1", "true", "yes", "on")


def read_section(section: str) -> dict:
    config = configparser.ConfigParser()
    with FileLock(LOCK_FILE_PATH, timeout=LOCK_TIMEOUT):
        try:
            _read_config_file(config)
        except (configparser.Error, FileNotFoundError):
            _set_default_values(config)
        if section not in config:
            return {}
        return dict(config.items(section))


def set_custom_value(section, option, value):
    set_custom_values(section, {option: value})


def set_custom_values(section, values: dict):
    """Write multiple keys in one lock/read/write cycle."""
    if not values:
        return
    config = configparser.ConfigParser()
    with FileLock(LOCK_FILE_PATH, timeout=LOCK_TIMEOUT):
        try:
            config.read(CONFIG_FILE_PATH)
        except (configparser.Error, FileNotFoundError):
            _set_default_values(config)

        if section not in config:
            config[section] = {}
        for option, value in values.items():
            config[section][option] = value
        _write_config_file(config)


def _read_config_file(config) -> None:
    if not os.path.exists(CONFIG_FILE_PATH):
        raise FileNotFoundError("Config file not found")
    config.read(CONFIG_FILE_PATH)


def _read_config_values(config) -> dict:
    settings = {}
    for section in config.sections():
        for option, value in config.items(section):
            settings[option] = value
    return settings


def _set_default_values(config) -> bool:
    changed = False
    default_config = {
        "STAFFCHECK": {
            "good_to_check_message": "userID Good to check -- GT: xboxGT",
            "not_good_to_check_message": "userID **Not** Good to check -- GT: xboxGT -- Reason",
            "edit_check_message": "true",
            "edit_check_nav_test_offset": "4",
        },
        "COMMANDS": {"initial_command": "2", "follow_up": "0.4", "abort_key": "escape"},
        "ADD_TO_BAN_LIST": {"delay": "15"},
        "WINDOW": {
            "x": "0",
            "y": "0",
            "width": "0",
            "height": "0",
            "x_offset": "0",
            "y_offset": "0",
        },
        "SESSION": {"open_apps": ""},
        "API": {"api_url": "https://ashen.api.famkoets.nl"},
        "UPDATES": {"prefer_prerelease": "false"},
        "UI": {
            "catppuccin_flavor": "mocha",
            "compact_panels": "true",
            "queue_debug": "false",
            "queue_splitter_sizes": "",
        },
    }

    ui = config["UI"] if "UI" in config else {}
    if "catppuccin_flavor" not in ui and "dark_mode" in ui:
        default_config["UI"]["catppuccin_flavor"] = "mocha"

    for section, options in default_config.items():
        if section not in config:
            config[section] = options
            changed = True
        else:
            for option, value in options.items():
                if option not in config[section]:
                    config[section][option] = value
                    changed = True
    return changed


def _write_config_file(config):
    with open(CONFIG_FILE_PATH, "w", encoding="UTF-8") as configfile:
        config.write(configfile)
