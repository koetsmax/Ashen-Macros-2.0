"""Appearance: Sun Valley ttk theme when available; Windows caption dark mode; fallbacks."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk

from modules.submodules.functions.settings import read_config, set_custom_value

LIGHT_BG = "#f0f0f0"
LIGHT_FG = "#000000"
DARK_BG = "#2b2b2b"
DARK_SURFACE = "#3c3c3c"
DARK_FG = "#e8e8e8"
DARK_ENTRY_BG = "#404040"


def is_dark_mode() -> bool:
    val = read_config().get("dark_mode", "false")
    return str(val).strip().lower() in ("true", "1", "yes")


def set_dark_mode(enabled: bool) -> None:
    set_custom_value("UI", "dark_mode", "true" if enabled else "false")


def _resolve_tk_root(widget: tk.Misc) -> tk.Tk:
    w = widget.winfo_toplevel()
    while w.master is not None:
        w = w.master
    return w  # type: ignore[return-value]


def _theme_name(root: tk.Tk) -> str:
    try:
        return ttk.Style(master=root).theme_use()
    except tk.TclError:
        return ""


def using_sun_valley(root: tk.Misc | None = None) -> bool:
    try:
        r = root or tk._default_root  # type: ignore[assignment]
        if r is None:
            return False
        return _theme_name(_resolve_tk_root(r)).startswith("sun-valley")
    except (tk.TclError, RuntimeError):
        return False


def label_foreground() -> str:
    root = tk._default_root
    if root is not None and using_sun_valley(root):
        try:
            fg = ttk.Style(master=_resolve_tk_root(root)).lookup("TLabel", "foreground")
            if fg:
                return fg
        except tk.TclError:
            pass
    return DARK_FG if is_dark_mode() else LIGHT_FG


def window_background() -> str:
    root = tk._default_root
    if root is not None and using_sun_valley(root):
        try:
            bg = ttk.Style(master=_resolve_tk_root(root)).lookup("TFrame", "background")
            if bg:
                return bg
        except tk.TclError:
            pass
    return DARK_BG if is_dark_mode() else LIGHT_BG


def _unsigned_hwnd(raw: int) -> int:
    """Tk may report HWND as a signed int; DWM expects an unsigned handle-sized value."""
    bits = ctypes.sizeof(ctypes.c_void_p) * 8
    return int(raw) & ((1 << bits) - 1)


def _caption_hwnd_candidates(win: tk.Misc) -> list[int]:
    """Collect HWNDs that might own the non-client (caption) area for this Tk window."""
    try:
        raw = win.winfo_id()
    except tk.TclError:
        return []
    if raw == 0:
        return []

    wid = _unsigned_hwnd(raw)
    candidates: list[int] = [wid]

    try:
        import win32gui
        import win32con

        parent = int(win32gui.GetParent(wid))
        if parent:
            candidates.append(_unsigned_hwnd(parent))
        try:
            owner = int(win32gui.GetWindow(wid, win32con.GW_OWNER))
            if owner:
                candidates.append(_unsigned_hwnd(owner))
        except (AttributeError, OSError, ValueError):
            pass
        try:
            root = int(win32gui.GetAncestor(wid, win32con.GA_ROOT))
            if root:
                candidates.append(_unsigned_hwnd(root))
        except (AttributeError, OSError, ValueError):
            pass
    except ImportError:
        user32 = ctypes.windll.user32
        GA_ROOT = 2
        GW_OWNER = 4
        parent = int(user32.GetParent(wid))
        if parent:
            candidates.append(_unsigned_hwnd(parent))
        try:
            owner = int(user32.GetWindow(wid, GW_OWNER))
            if owner:
                candidates.append(_unsigned_hwnd(owner))
        except (AttributeError, OSError, ValueError):
            pass
        root = int(user32.GetAncestor(wid, GA_ROOT))
        if root:
            candidates.append(_unsigned_hwnd(root))

    seen: set[int] = set()
    unique: list[int] = []
    for h in candidates:
        if h and h not in seen:
            seen.add(h)
            unique.append(h)
    return unique


def _apply_windows_immersive_titlebar(win: tk.Misc, dark: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    value = ctypes.c_int(1 if dark else 0)
    DWMWA_IMMERSIVE_PRE20H1 = 19
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    attrs = (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_IMMERSIVE_PRE20H1)

    dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute

    for hwnd_int in _caption_hwnd_candidates(win):
        hwnd = wintypes.HWND(hwnd_int)
        for attr in attrs:
            try:
                hr = dwm(
                    hwnd,
                    ctypes.c_uint(attr),
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
                if hr == 0:
                    break
            except (AttributeError, OSError, ValueError):
                continue


def _schedule_windows_titlebar(win: tk.Misc) -> None:
    """Apply caption colors once; repeated delayed DWM calls caused visible gradual transitions."""
    dark = is_dark_mode()

    def apply_once() -> None:
        _apply_windows_immersive_titlebar(win, dark)

    try:
        apply_once()
        win.after_idle(apply_once)
    except tk.TclError:
        pass


def reveal_root(widget: tk.Misc) -> None:
    """Use after building UI on a withdrawn root: caption before first visible frame."""
    tk_root = _resolve_tk_root(widget)
    dark = is_dark_mode()
    try:
        tk_root.configure(background=window_background())
        tk_root.update_idletasks()
        _apply_windows_immersive_titlebar(tk_root, dark)
        tk_root.deiconify()
        tk_root.lift()
        _apply_windows_immersive_titlebar(tk_root, dark)
        _repaint_nonclient_frame(tk_root)
        tk_root.update_idletasks()
    except tk.TclError:
        pass


def _apply_caption_now(win: tk.Misc) -> None:
    try:
        win.update_idletasks()
    except tk.TclError:
        return
    _apply_windows_immersive_titlebar(win, is_dark_mode())


def defer_dialog_show(win: tk.Toplevel) -> None:
    """Hide dialog until UI is built; pair with present_dialog (avoids white client flash)."""
    setattr(win, "_ashen_deferred_show", True)
    try:
        win.withdraw()
    except tk.TclError:
        pass


def _repaint_nonclient_frame(win: tk.Misc) -> None:
    """Ask Windows to refresh caption chrome after DWM attributes (reduces 1-frame light caption)."""
    if sys.platform != "win32":
        return
    try:
        raw = win.winfo_id()
        if raw == 0:
            return
        hwnd = _unsigned_hwnd(raw)
        SWP_FRAMECHANGED = 0x0020
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        flags = SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except (OSError, AttributeError, tk.TclError, ValueError, TypeError):
        pass


def present_dialog(win: tk.Toplevel) -> None:
    """Show a deferred dialog; set immersive caption before first visible composite."""
    setattr(win, "_ashen_deferred_show", False)
    dark = is_dark_mode()
    try:
        win.configure(background=window_background())
        win.update_idletasks()
        _apply_windows_immersive_titlebar(win, dark)
        win.deiconify()
        win.lift()
        _apply_windows_immersive_titlebar(win, dark)
        _repaint_nonclient_frame(win)
        win.update_idletasks()
    except tk.TclError:
        return


def _bind_toplevel_caption_on_map(win: tk.Toplevel) -> None:
    """One DWM apply when the dialog maps (HWND ready); avoid bursts that animate the caption."""

    def on_map(_evt: tk.Event | None = None) -> None:
        _apply_caption_now(win)

    if getattr(win, "_ashen_caption_map_bound", False):
        return
    setattr(win, "_ashen_caption_map_bound", True)
    try:
        win.bind("<Map>", on_map, add="+")
    except tk.TclError:
        pass


def tk_menubutton_options() -> dict:
    """Options for tk.Menubutton so the strip matches Sun Valley / fallback colors."""
    bg = window_background()
    fg = label_foreground()
    dark = is_dark_mode()
    active_bg = "#505050" if dark else "#d8d8d8"
    return {
        "background": bg,
        "foreground": fg,
        "activebackground": active_bg,
        "activeforeground": fg,
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 0,
    }


def configure_popup_menu(menu: tk.Menu) -> None:
    """Style tk.Menu dropdowns (Sun Valley does not style Menu on Windows)."""
    if is_dark_mode():
        menu.configure(
            background="#292929",
            foreground=DARK_FG,
            activebackground="#505050",
            activeforeground=DARK_FG,
            bd=0,
            relief="flat",
        )


def paint_toplevel(window: tk.Misc) -> None:
    top = window.winfo_toplevel()
    try:
        top.configure(background=window_background())
    except tk.TclError:
        pass
    if isinstance(top, tk.Toplevel):
        if getattr(top, "_ashen_deferred_show", False):
            return
        _bind_toplevel_caption_on_map(top)
        try:
            if int(top.winfo_viewable()):
                _apply_caption_now(top)
        except (tk.TclError, ValueError):
            pass
    else:
        _schedule_windows_titlebar(top)


def _pick_light_theme(style: ttk.Style) -> str:
    names = style.theme_names()
    if "vista" in names:
        return "vista"
    if "clam" in names:
        return "clam"
    return names[0] if names else "default"


def _apply_light_clam_palette(style: ttk.Style) -> None:
    style.configure(".", background=LIGHT_BG, foreground=LIGHT_FG)
    style.configure("TFrame", background=LIGHT_BG)
    style.configure("TLabel", background=LIGHT_BG, foreground=LIGHT_FG)
    style.configure("TButton", background=LIGHT_BG, foreground=LIGHT_FG)
    style.configure("TEntry", fieldbackground="#ffffff", foreground=LIGHT_FG, insertcolor=LIGHT_FG)
    style.configure(
        "TCombobox", fieldbackground="#ffffff", foreground=LIGHT_FG, insertcolor=LIGHT_FG
    )
    style.map("TCombobox", fieldbackground=[("readonly", "#ffffff")])
    style.configure("TCheckbutton", background=LIGHT_BG, foreground=LIGHT_FG)
    style.configure("TLabelframe", background=LIGHT_BG, foreground=LIGHT_FG)
    style.configure("TLabelframe.Label", background=LIGHT_BG, foreground=LIGHT_FG)
    style.configure("TMenubutton", background=LIGHT_BG, foreground=LIGHT_FG)


def _apply_dark_palette(style: ttk.Style) -> None:
    style.configure(".", background=DARK_BG, foreground=DARK_FG)
    style.configure("TFrame", background=DARK_BG)
    style.configure("TLabel", background=DARK_BG, foreground=DARK_FG)
    style.configure("TButton", background=DARK_SURFACE, foreground=DARK_FG)
    style.map(
        "TButton",
        background=[("active", "#4a4a4a"), ("pressed", "#555555")],
        foreground=[("disabled", "#888888")],
    )
    style.configure(
        "TEntry", fieldbackground=DARK_ENTRY_BG, foreground=DARK_FG, insertcolor=DARK_FG
    )
    style.configure(
        "TCombobox",
        fieldbackground=DARK_ENTRY_BG,
        foreground=DARK_FG,
        insertcolor=DARK_FG,
    )
    style.map("TCombobox", fieldbackground=[("readonly", DARK_ENTRY_BG)])
    style.configure("TCheckbutton", background=DARK_BG, foreground=DARK_FG)
    style.configure("TLabelframe", background=DARK_BG, foreground=DARK_FG)
    style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_FG)
    style.configure("TMenubutton", background=DARK_BG, foreground=DARK_FG)
    style.map(
        "TMenubutton",
        background=[("active", DARK_SURFACE)],
        foreground=[("disabled", "#888888")],
    )


def _apply_fallback_theme(tk_root: tk.Tk, dark: bool) -> None:
    style = ttk.Style(tk_root)
    if dark:
        style.theme_use("clam")
        _apply_dark_palette(style)
    else:
        light_theme = _pick_light_theme(style)
        style.theme_use(light_theme)
        if light_theme == "clam":
            _apply_light_clam_palette(style)


def apply_theme(root: tk.Misc) -> None:
    tk_root = _resolve_tk_root(root)
    dark = is_dark_mode()

    try:
        import sv_ttk

        sv_ttk.set_theme("dark" if dark else "light", root=tk_root)
    except (ImportError, RuntimeError, tk.TclError, TypeError, OSError):
        _apply_fallback_theme(tk_root, dark)

    paint_toplevel(tk_root)
    try:
        tk_root.update_idletasks()
    except tk.TclError:
        pass
