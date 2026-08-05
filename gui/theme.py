from types import SimpleNamespace

from catppuccin import PALETTE
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPalette, QColor
from PySide6.QtWidgets import QApplication

from core.settings import read_config, set_custom_value


class _SimpleColor:
    def __init__(self, hex: str):
        self.hex = hex


def _make_colors(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**{key: _SimpleColor(value) for key, value in kwargs.items()})


def _make_flavor(name: str, identifier: str, dark: bool, colors: dict) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        identifier=identifier,
        dark=dark,
        colors=_make_colors(**colors),
    )


MATRIX_FLAVOR = _make_flavor(
    "Matrix",
    "matrix",
    True,
    {
        "crust": "#000000",
        "base": "#050805",
        "mantle": "#030503",
        "surface0": "#0d140d",
        "surface1": "#142014",
        "surface2": "#1c2c1c",
        "overlay0": "#2a402a",
        "subtext0": "#00cc33",
        "text": "#00ff41",
        "lavender": "#66ff88",
        "blue": "#00aa33",
        "sapphire": "#008f2b",
        "green": "#00ff41",
        "yellow": "#99ff66",
        "peach": "#55ff77",
        "red": "#ff3355",
        "mauve": "#00ff66",
    },
)

ASHEN_FLAVOR = _make_flavor(
    "Ashen",
    "ashen",
    True,
    {
        "crust": "#0a0a0a",
        "base": "#121212",
        "mantle": "#0e0e0e",
        "surface0": "#1c1c1c",
        "surface1": "#262626",
        "surface2": "#303030",
        "overlay0": "#4a4a4a",
        "subtext0": "#a8a8a8",
        "text": "#ececec",
        "lavender": "#ff8533",
        "blue": "#cc5200",
        "sapphire": "#b34700",
        "green": "#4ade80",
        "yellow": "#ffaa33",
        "peach": "#ff6700",
        "red": "#ff4444",
        "mauve": "#ff6700",
    },
)

CUSTOM_FLAVORS = {
    "matrix": MATRIX_FLAVOR,
    "ashen": ASHEN_FLAVOR,
}

FLAVOR_IDS = tuple(flavor.identifier for flavor in PALETTE) + tuple(CUSTOM_FLAVORS)
PALETTE_FLAVORS = tuple(PALETTE) + tuple(CUSTOM_FLAVORS.values())
DEFAULT_FLAVOR = "mocha"

SEMANTIC_KEYS = {
    "red": "red",
    "green": "green",
    "orange": "peach",
    "yellow": "yellow",
    "blue": "blue",
    "mauve": "mauve",
    "peach": "peach",
    "lavender": "lavender",
    "muted": "subtext0",
    "text": "text",
}

# Populated from the active Catppuccin flavor via _refresh_palette_exports().
CRUST = ""
BASE = ""
MANTLE = ""
SURFACE0 = ""
SURFACE1 = ""
SURFACE2 = ""
OVERLAY0 = ""
SUBTEXT0 = ""
TEXT = ""
LAVENDER = ""
BLUE = ""
SAPPHIRE = ""
GREEN = ""
YELLOW = ""
PEACH = ""
RED = ""
MAUVE = ""


def get_flavor_identifier() -> str:
    flavor = str(read_config().get("catppuccin_flavor", DEFAULT_FLAVOR)).strip().lower()
    if flavor in FLAVOR_IDS:
        return flavor
    return DEFAULT_FLAVOR


def get_flavor():
    identifier = get_flavor_identifier()
    custom = CUSTOM_FLAVORS.get(identifier)
    if custom is not None:
        return custom
    return getattr(PALETTE, identifier)


def set_flavor(identifier: str):
    if identifier not in FLAVOR_IDS:
        identifier = DEFAULT_FLAVOR
    set_custom_value("UI", "catppuccin_flavor", identifier)


def resolve_color(name: str) -> str:
    if not name:
        return TEXT
    if name.startswith("#"):
        return name
    key = SEMANTIC_KEYS.get(name.lower())
    if key:
        return getattr(get_flavor().colors, key).hex
    return name


def _refresh_palette_exports():
    colors = get_flavor().colors
    g = globals()
    g["CRUST"] = colors.crust.hex
    g["BASE"] = colors.base.hex
    g["MANTLE"] = colors.mantle.hex
    g["SURFACE0"] = colors.surface0.hex
    g["SURFACE1"] = colors.surface1.hex
    g["SURFACE2"] = colors.surface2.hex
    g["OVERLAY0"] = colors.overlay0.hex
    g["SUBTEXT0"] = colors.subtext0.hex
    g["TEXT"] = colors.text.hex
    g["LAVENDER"] = colors.lavender.hex
    g["BLUE"] = colors.blue.hex
    g["SAPPHIRE"] = colors.sapphire.hex
    g["GREEN"] = colors.green.hex
    g["YELLOW"] = colors.yellow.hex
    g["PEACH"] = colors.peach.hex
    g["RED"] = colors.red.hex
    g["MAUVE"] = colors.mauve.hex


def _palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BASE))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(MANTLE))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(CRUST))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(SURFACE0))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Highlight, QColor(BLUE))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(CRUST))
    return p


def _qss() -> str:
    return f"""
    QWidget {{
        background-color: {BASE};
        color: {TEXT};
        font-family: "Segoe UI", sans-serif;
        font-size: 9pt;
    }}
    QMainWindow, QDialog {{
        background-color: {BASE};
    }}
    QFrame#hubStatusBar {{
        background-color: {MANTLE};
        border-bottom: 1px solid {SURFACE0};
    }}
    QLabel#hubApiStatus {{
        font-weight: 600;
        color: {SUBTEXT0};
        background: transparent;
    }}
    QLabel#hubWelcome {{
        color: {SUBTEXT0};
        background: transparent;
    }}
    QLabel#hubNotVerified {{
        color: {PEACH};
        font-weight: 600;
        background: transparent;
    }}
    QPushButton#hubHeaderButton {{
        background-color: {SURFACE0};
        border: 1px solid {SURFACE1};
        border-radius: 6px;
        padding: 4px 12px;
        min-height: 22px;
        color: {TEXT};
        font-weight: 600;
    }}
    QPushButton#hubHeaderButton:hover {{
        background-color: {SURFACE1};
        border-color: {SURFACE2};
    }}
    QPushButton#hubHeaderButton:pressed {{
        background-color: {SURFACE2};
    }}
    QPushButton#hubHeaderButton:disabled {{
        color: {OVERLAY0};
        background-color: {MANTLE};
        border-color: {SURFACE0};
    }}
    QPushButton#hubHeaderButton:disabled:hover {{
        background-color: {MANTLE};
        border-color: {SURFACE0};
        color: {OVERLAY0};
    }}
    QGroupBox {{
        background-color: {MANTLE};
        border: 1px solid {SURFACE0};
        border-radius: 10px;
        margin-top: 12px;
        padding: 18px 12px 12px 12px;
        font-weight: 600;
        color: {SUBTEXT0};
    }}
    QWidget#resultsPanel, QWidget#resultSection {{
        background: transparent;
    }}
    QLabel#sectionHeader {{
        font-weight: 700;
        font-size: 9pt;
        padding: 0;
        background: transparent;
        color: {MAUVE};
    }}
    QLabel#sectionHeader[state="idle"],
    QLabel#sectionHeader[state="loading"] {{
        color: {PEACH};
    }}
    QLabel#sectionHeader[state="success"] {{
        color: {GREEN};
    }}
    QLabel#sectionHeader[state="issues"] {{
        color: {PEACH};
    }}
    QLabel#sectionHeader[state="failed"] {{
        color: {RED};
    }}
    QLabel#resultSectionSummary {{
        color: {SUBTEXT0};
        font-size: 9pt;
        background: transparent;
        padding: 0;
    }}
    QLabel#resultLabel {{
        color: {SUBTEXT0};
        background: transparent;
    }}
    QLabel#resultValue {{
        background: transparent;
    }}
    QFrame#sectionDivider {{
        background-color: {SURFACE0};
        border: none;
        max-height: 1px;
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QLineEdit, QComboBox {{
        background-color: {CRUST};
        border: 1px solid {SURFACE0};
        border-radius: 8px;
        padding: 7px 12px;
        min-height: 26px;
        color: {TEXT};
        selection-background-color: {BLUE};
        selection-color: {CRUST};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {MAUVE};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {SURFACE0};
        border: 1px solid {SURFACE1};
        border-radius: 8px;
        color: {TEXT};
        selection-background-color: {SURFACE1};
        selection-color: {TEXT};
        padding: 4px;
    }}
    QPushButton {{
        background-color: {SURFACE0};
        border: 1px solid {SURFACE1};
        border-radius: 8px;
        padding: 8px 18px;
        min-height: 26px;
        color: {TEXT};
    }}
    QPushButton:hover {{
        background-color: {SURFACE1};
        border-color: {SURFACE2};
    }}
    QPushButton:pressed {{
        background-color: {SURFACE2};
    }}
    QPushButton:disabled {{
        color: {OVERLAY0};
        background-color: {MANTLE};
        border-color: {SURFACE0};
    }}
    QPushButton#primary {{
        background-color: {MAUVE};
        color: {CRUST};
        border: none;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{
        background-color: {LAVENDER};
    }}
    QPushButton#primary:pressed {{
        background-color: {BLUE};
        color: {CRUST};
    }}
    QPushButton#classicPanelButton {{
        padding: 4px 8px;
        min-height: 22px;
        font-size: 8pt;
    }}
    QCheckBox {{
        spacing: 8px;
        color: {TEXT};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid {SURFACE1};
        background: {CRUST};
    }}
    QCheckBox::indicator:checked {{
        background: {MAUVE};
        border-color: {MAUVE};
    }}
    QCheckBox::indicator:hover {{
        border-color: {LAVENDER};
    }}
    QMenuBar {{
        background-color: {MANTLE};
        border-bottom: 1px solid {SURFACE0};
        padding: 3px 0;
        color: {TEXT};
    }}
    QMenuBar::item {{
        padding: 5px 12px;
        border-radius: 6px;
        background: transparent;
    }}
    QMenuBar::item:selected {{
        background-color: {SURFACE0};
    }}
    QMenu {{
        background-color: {SURFACE0};
        border: 1px solid {SURFACE1};
        border-radius: 8px;
        padding: 6px;
        color: {TEXT};
    }}
    QMenu::item {{
        padding: 7px 28px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background-color: {SURFACE1};
    }}
    QFrame#toast {{
        background-color: {MANTLE};
        border: 1px solid {SURFACE0};
        border-radius: 10px;
        color: {TEXT};
    }}
    QFrame#toast QLabel {{
        background: transparent;
        color: {TEXT};
    }}
    QFrame#toast QPushButton#toastDismiss {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        color: {OVERLAY0};
        font-size: 16px;
        font-weight: 600;
        padding: 0;
        min-width: 22px;
        max-width: 22px;
        min-height: 22px;
        max-height: 22px;
    }}
    QFrame#toast QPushButton#toastDismiss:hover {{
        background-color: {SURFACE0};
        color: {TEXT};
    }}
    QFrame#toast QPushButton#toastDismiss:pressed {{
        background-color: {SURFACE1};
        color: {TEXT};
    }}
    QFrame#toast QPushButton#toastAction {{
        background-color: transparent;
        border: none;
        color: {BLUE};
        padding: 2px 0;
        text-align: left;
        font-weight: 600;
    }}
    QFrame#toast QPushButton#toastAction:hover {{
        background-color: transparent;
        color: {LAVENDER};
    }}
    QFrame#toast QPushButton#toastAction:pressed {{
        background-color: transparent;
        color: {MAUVE};
    }}
    QLabel#versionBadge {{
        color: {OVERLAY0};
        font-size: 8pt;
    }}
    QLabel#versionBadge[outdated="true"] {{
        color: {RED};
    }}
    QLabel#prereleaseBadge {{
        color: {PEACH};
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 0.4px;
        margin-right: 8px;
    }}
    QLabel#statusConnected {{
        color: {GREEN};
    }}
    QLabel#statusDisconnected {{
        color: {RED};
    }}
    QScrollBar:vertical {{
        background: {MANTLE};
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {SURFACE1};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {SURFACE2};
    }}
    """


def apply_theme(app: QApplication):
    _refresh_palette_exports()
    scheme = Qt.ColorScheme.Dark if get_flavor().dark else Qt.ColorScheme.Light
    QGuiApplication.styleHints().setColorScheme(scheme)
    app.setStyle("Fusion")
    app.setPalette(_palette())
    app.setStyleSheet(_qss())


_refresh_palette_exports()
