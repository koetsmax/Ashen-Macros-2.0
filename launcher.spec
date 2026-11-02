# -*- mode: python ; coding: utf-8 -*-
import sys

IS_WINDOWS = sys.platform == "win32"
# Linux: lowercase name without spaces (binary, folder, Wayland app id).
APP_NAME = "Ashen Macros" if IS_WINDOWS else "ashen-macros"

hiddenimports = ["pyperclip", "websocket", "websocket.websocket"]
if not IS_WINDOWS:
    # keyring picks its backend at runtime (KWallet / GNOME Keyring via Secret Service).
    hiddenimports += [
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
        "secretstorage",
        "jeepney",
    ]

block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ("version", "."),
        ("images", "images"),
        ("scripts/vencord_setup", "scripts/vencord_setup"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Windows-only automation deps must not be pulled into the Linux build.
    excludes=[] if IS_WINDOWS else ["keyboard", "win32con", "win32gui", "pywintypes"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/AshenAllianceLogo.ico' if IS_WINDOWS else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
