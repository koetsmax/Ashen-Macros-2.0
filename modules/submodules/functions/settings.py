import configparser
import os
from filelock import FileLock, Timeout

CONFIG_FILE_PATH = os.path.expanduser("~/Documents/Ashen Macros/settings.ini")
LOCK_FILE_PATH = CONFIG_FILE_PATH + ".lock"
LOCK_TIMEOUT = 30  # Timeout duration in seconds


def read_config() -> dict:
    """
    Read the config file.
    """
    config = configparser.ConfigParser()
    with FileLock(LOCK_FILE_PATH, timeout=LOCK_TIMEOUT):
        try:
            _read_config_file(config)
        except (configparser.Error, FileNotFoundError):
            _set_default_values(config)
            _write_config_file(config)

        return _read_config_values(config)


def set_custom_value(section, option, value):
    """
    Set a custom value in the config.
    """
    config = configparser.ConfigParser()
    with FileLock(LOCK_FILE_PATH, timeout=LOCK_TIMEOUT):
        try:
            config.read(CONFIG_FILE_PATH)
        except (configparser.Error, FileNotFoundError):
            _set_default_values(config)

        if section not in config:
            config[section] = {}
        config[section][option] = value
        _write_config_file(config)


def _read_config_file(config) -> None:
    config.read(CONFIG_FILE_PATH)


def _read_config_values(config) -> dict:
    settings = {}
    for section in config.sections():
        for option, value in config.items(section):
            settings[option] = value
    return settings


def _set_default_values(config):
    default_config = {
        "STAFFCHECK": {
            "good_to_check_message": "userID Good to check -- GT: xboxGT",
            "not_good_to_check_message": "userID **Not** Good to check -- GT: xboxGT -- Reason",
            "join_awr_message": "userID has been requested to join the <#702904587027480607> - Good to remove from the queue if they don't join within 10 minutes (Time)",
            "unprivate_xbox_message": "userID has been asked to unprivate their xbox - Good to remove from the queue if they don't unprivate their xbox within 10 minutes (Time)",
            "verify_message": "userID has been asked to verify their account - Good to remove from the queue if they don't verify within 10 minutes (Time)",
        },
        "COMMANDS": {"initial_command": "2", "follow_up": "0.4"},
        "ADD_TO_BAN_LIST": {"delay": "15"},
        "WINDOW": {"x_offset": "0", "y_offset": "0"},
        "API": {"api_url": "http://ashen_api.famkoets.nl"},
    }

    for section, options in default_config.items():
        if section not in config:
            config[section] = options
        else:
            for option, value in options.items():
                if option not in config[section]:
                    config[section][option] = value


def _write_config_file(config):
    with open(CONFIG_FILE_PATH, "w", encoding="UTF-8") as configfile:
        config.write(configfile)
