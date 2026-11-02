import configparser
import os
from filelock import FileLock

from core.platform import IS_WINDOWS, keyboard_automation_supported


def _xdg_dir(env: str, fallback: str) -> str:
    base = os.environ.get(env, "").strip()
    if not base or not os.path.isabs(base):
        base = os.path.expanduser(fallback)
    return os.path.join(base, "ashen-macros")


if IS_WINDOWS:
    # settings.ini, logs and fault dumps all live together.
    DATA_DIR = os.path.expanduser("~/Documents/Ashen Macros")
    LOG_DIR = DATA_DIR
else:
    # XDG: settings in ~/.config/ashen-macros, logs in ~/.local/state/ashen-macros.
    DATA_DIR = _xdg_dir("XDG_CONFIG_HOME", "~/.config")
    LOG_DIR = _xdg_dir("XDG_STATE_HOME", "~/.local/state")

CONFIG_FILE_PATH = os.path.join(DATA_DIR, "settings.ini")
LOCK_FILE_PATH = CONFIG_FILE_PATH + ".lock"
LOCK_TIMEOUT = 30


def bridge_default() -> str:
    """Default for the Vencord plugin toggle: on where keyboard automation is missing."""
    return "false" if keyboard_automation_supported() else "true"


def ensure_data_dirs() -> None:
    """Create the settings / log folders (call before the first read_config)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)


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
            "queue_join_alert": "true",
            # Linux: run under XWayland so window positions restore (see core.platform).
            "native_wayland": "false",
            "leave_animated_emojis": "false",
        },
        "VENCORD": {
            "vencord_bridge": bridge_default(),
            "vencord_bridge_port": "47832",
            # Empty = automatic: read the plugin's generated token from Vencord's settings.json.
            "vencord_bridge_token": "",
            "vencord_install_path": "",
            "vencord_auto_update_check": "true",
        },
    }

    ui = config["UI"] if "UI" in config else {}
    if "catppuccin_flavor" not in ui and "dark_mode" in ui:
        default_config["UI"]["catppuccin_flavor"] = "mocha"

    # Scrapped feature — drop leftover customize key from older installs.
    if "STAFFCHECK" in config and "ban_request_message" in config["STAFFCHECK"]:
        del config["STAFFCHECK"]["ban_request_message"]
        changed = True

    if _migrate_legacy_vencord_section(config):
        changed = True

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


def _migrate_legacy_vencord_section(config) -> bool:
    """Move keys from the old [EXPERIMENTAL] section into [VENCORD] / [UI].

    read_config() flattens every section into one dict, so leaving both would
    let the freshly defaulted [VENCORD] values shadow the user's saved ones.
    """
    legacy = "EXPERIMENTAL"
    if legacy not in config:
        return False
    for option, value in config.items(legacy, raw=True):
        target = "UI" if option == "leave_animated_emojis" else "VENCORD"
        if target not in config:
            config[target] = {}
        if option not in config[target]:
            config[target][option] = value
    config.remove_section(legacy)
    return True


def _write_config_file(config):
    with open(CONFIG_FILE_PATH, "w", encoding="UTF-8") as configfile:
        config.write(configfile)
