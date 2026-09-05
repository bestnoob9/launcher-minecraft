import tkinter as tk
from tkinter import ttk
import config

_NATIVE_TTK_THEME = None

_LIGHT_TO_DARK = {
    "#ffffff": "#1e1e1e",
    "white":   "#1e1e1e",
    "#f5f5f7": "#252526",
    "#f0f0f0": "#2a2a2a",
    "#eef3f9": "#2a2f3a",
    "#e1e4ea": "#3a3f4a",
    "#e0e0e0": "#3a3a3a",
    "#cfe3fb": "#2f4a6e",
    "#cfd3da": "#4a4f5a",
    "#c5cad3": "#555b66",
    "SystemButtonFace": "#2a2a2a",
    "SystemWindow":     "#1e1e1e",
    "SystemWindowText": "#e8e8e8",
    "SystemButtonText": "#e8e8e8",

    "#dde2e8": "#263238",

    "#1a1a1a": "#e8e8e8",
    "black":   "#e8e8e8",
    "#222":    "#d0d0d0",
    "#222222": "#d0d0d0",
    "#444":    "#cfcfcf",
    "#444444": "#cfcfcf",
    "#555":    "#b5b5b5",
    "#555555": "#b5b5b5",
    "#5b6b8c": "#9fb3d6",
    "#888":    "#9a9a9a",
    "#888888": "#9a9a9a",
    "gray":    "#a0a0a0",
    "grey":    "#a0a0a0",
    "#2e7d32": "#66bb6a",   
    "#b35900": "#ffb74d",   
}

_DARK_TO_LIGHT = {v: k for k, v in _LIGHT_TO_DARK.items()}

_DARK_TO_LIGHT.update({
    "#1e1e1e": "#ffffff",
    "#e8e8e8": "#1a1a1a",
    "#d0d0d0": "#222222",
    "#cfcfcf": "#444444",
    "#a0a0a0": "gray",
    "#66bb6a": "#2e7d32",
    "#ffb74d": "#b35900",
    "#263238": "#dde2e8",
})

def _norm(c):
    if c is None:
        return None
    return c.strip()

def get_theme_name():
    return config.current_config.get("theme", "light")

def is_dark():
    return get_theme_name() == "dark"

def set_theme(name):
    if name not in ("light", "dark"):
        name = "light"
    config.current_config["theme"] = name

def colors():
    if is_dark():
        return {
            "bg":        "#1e1e1e",
            "bg_alt":    "#252526",
            "row_bg":    "#1e1e1e",
            "row_sel":   "#2f4a6e",
            "row_sep":   "#3a3a3a",
            "fg_title":  "#e8e8e8",
            "fg_author": "#9fb3d6",
            "fg_desc":   "#cfcfcf",
            "fg_stat":   "#66bb6a",
            "fg_tag":    "#ffb74d",
            "icon_bg":   "#3a3f4a",
            "icon_border": "#555b66",
            "entry_bg":  "#2a2a2a",
            "entry_fg":  "#e8e8e8",
        }
    return {
        "bg":        "#ffffff",
        "bg_alt":    "#f5f5f7",
        "row_bg":    "#ffffff",
        "row_sel":   "#cfe3fb",
        "row_sep":   "#e0e0e0",
        "fg_title":  "#1a1a1a",
        "fg_author": "#5b6b8c",
        "fg_desc":   "#444444",
        "fg_stat":   "#2e7d32",
        "fg_tag":    "#b35900",
        "icon_bg":   "#e1e4ea",
        "icon_border": "#c5cad3",
        "entry_bg":  "#ffffff",
        "entry_fg":  "#1a1a1a",
    }

_BG_OPTS = ("bg", "background", "highlightbackground",
            "selectbackground", "activebackground", "readonlybackground",
            "insertbackground", "selectcolor")
_FG_OPTS = ("fg", "foreground", "activeforeground", "selectforeground")

def _remap(value, mapping):
    if value is None:
        return None
    key = value if value.startswith("#") else value.lower()
    return mapping.get(key) or mapping.get(value)

def _style_combobox_popdown(cb, dark):
    try:
        field = "#2a2a2a" if dark else "#ffffff"
        fg = "#e8e8e8" if dark else "#1a1a1a"
        popdown = cb.tk.call("ttk::combobox::PopdownWindow", cb)
        listbox = f"{popdown}.f.l"
        cb.tk.call(
            listbox, "configure",
            "-background", field,
            "-foreground", fg,
            "-selectbackground", "#03A9F4",
            "-selectforeground", "#ffffff",
            "-borderwidth", 0,
            "-highlightthickness", 0,
            "-activestyle", "none",
        )
    except Exception:
        pass

def _apply_to_widget(w, mapping, dark):
    try:
        opts = w.keys()
    except Exception:
        return

    for opt in _BG_OPTS:
        if opt in opts:
            try:
                cur = w.cget(opt)
            except Exception:
                continue
            new = _remap(cur, mapping)
            if new:
                try:
                    w.configure(**{opt: new})
                except Exception:
                    pass

    for opt in _FG_OPTS:
        if opt in opts:
            try:
                cur = w.cget(opt)
            except Exception:
                continue
            new = _remap(cur, mapping)
            if new:
                try:
                    w.configure(**{opt: new})
                except Exception:
                    pass

    is_combobox_entry = False
    try:
        parent = w.nametowidget(w.winfo_parent())
        if isinstance(parent, ttk.Combobox):
            is_combobox_entry = True
    except Exception:
        pass

    if isinstance(w, ttk.Combobox):
        _style_combobox_popdown(w, dark)

    if "selectbackground" in opts:
        try:
            if is_combobox_entry and "bg" in opts:
                w.configure(selectbackground=w.cget("bg"))
            else:
                w.configure(selectbackground="#1E88E5")
        except Exception:
            pass
    if "selectforeground" in opts:
        try:
            if is_combobox_entry and "fg" in opts:
                w.configure(selectforeground=w.cget("fg"))
            else:
                w.configure(selectforeground="white")
        except Exception:
            pass

    if isinstance(w, (tk.Entry, tk.Spinbox)):
        def _select_all_entry(event, widget=w):
            widget.selection_range(0, "end")
            widget.icursor("end")
            return "break"
        w.bind("<Control-a>", _select_all_entry)
        w.bind("<Control-A>", _select_all_entry)
    elif isinstance(w, tk.Text):
        def _select_all_text(event, widget=w):
            widget.tag_add("sel", "1.0", "end")
            return "break"
        w.bind("<Control-a>", _select_all_text)
        w.bind("<Control-A>", _select_all_text)

def _apply_to_ttk_style(root, mapping, dark):
    style = ttk.Style(root)

    global _NATIVE_TTK_THEME
    try:
        if _NATIVE_TTK_THEME is None:
            _NATIVE_TTK_THEME = style.theme_use()
    except Exception:
        _NATIVE_TTK_THEME = "vista"

    try:
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    if dark:
        bg, fg, field, sel = "#252526", "#e8e8e8", "#2a2a2a", "#2f4a6e"
        trough, sep = "#1e1e1e", "#3a3a3a"
    else:
        bg, fg, field, sel = "#f5f5f7", "#1a1a1a", "#ffffff", "#cfe3fb"
        trough, sep = "#e9e9e9", "#e0e0e0"

    combo_hl_bg = "#03A9F4"
    combo_hl_fg = "#ffffff"

    try:
        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)

        tab_inactive_bg = "#37474F" if dark else "#dde2e8"
        tab_inactive_fg = "#b0bac4" if dark else "#5a6470"
        tab_active_bg   = "#1E88E5"
        tab_active_fg   = "white"

        style.configure("TNotebook", background=bg, borderwidth=0,
                        tabmargins=(4, 4, 4, 0))
        style.configure("TNotebook.Tab", background=tab_inactive_bg,
                        foreground=tab_inactive_fg, padding=(14, 6),
                        borderwidth=0, font=("Arial", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", tab_active_bg)],
                  foreground=[("selected", tab_active_fg)],
                  expand=[("selected", (1, 1, 1, 0))])

        style.configure("TCombobox", fieldbackground=field, background=field,
                        foreground=fg, arrowcolor=fg,
                        selectbackground=field, selectforeground=fg,
                        insertcolor=fg)
        style.map("TCombobox",
                  fieldbackground=[("readonly", field), ("!disabled", field)],
                  foreground=[("readonly", fg), ("!disabled", fg)],
                  selectbackground=[("readonly", field), ("!disabled", field),
                                     ("focus", field)],
                  selectforeground=[("readonly", fg), ("!disabled", fg),
                                     ("focus", fg)])

        style.configure("Vertical.TScrollbar", background=trough, troughcolor=trough,
                        arrowcolor=fg, bordercolor=trough)
        style.configure("Horizontal.TScrollbar", background=trough, troughcolor=trough,
                        arrowcolor=fg, bordercolor=trough)

        style.configure("TProgressbar", background="#1E88E5", troughcolor=trough)

        style.configure("Treeview", background=field, fieldbackground=field,
                        foreground=fg, rowheight=24)
        style.configure("Treeview.Heading", background=trough, foreground=fg)
        style.map("Treeview",
                  background=[("selected", sel)],
                  foreground=[("selected", fg)])

        style.configure("Modpack.Treeview", background=field, fieldbackground=field,
                        foreground=fg, rowheight=24)
        style.map("Modpack.Treeview",
                  background=[("selected", sel)],
                  foreground=[("selected", fg)])
    except Exception:
        pass

    try:
        root.option_add("*TCombobox*Listbox.background", field)
        root.option_add("*TCombobox*Listbox.foreground", fg)
        root.option_add("*TCombobox*Listbox.selectBackground", combo_hl_bg)
        root.option_add("*TCombobox*Listbox.selectForeground", combo_hl_fg)

        root.option_add("*TCombobox*selectBackground", field)
        root.option_add("*TCombobox*selectForeground", fg)
        root.option_add("*TEntry*selectBackground", field)
        root.option_add("*TEntry*selectForeground", fg)
    except Exception:
        pass

def preload_combobox_options(root):
    dark = is_dark()
    field = "#2a2a2a" if dark else "#ffffff"
    fg    = "#e8e8e8" if dark else "#1a1a1a"
    try:
        for pat in ("*TCombobox*selectBackground", "*Combobox*selectBackground",
                     "*selectBackground"):
            root.option_add(pat, field, "interactive")
        for pat in ("*TCombobox*selectForeground", "*Combobox*selectForeground",
                     "*selectForeground"):
            root.option_add(pat, fg, "interactive")
        for pat in ("*TEntry*selectBackground", "*Entry*selectBackground"):
            root.option_add(pat, field, "interactive")
        for pat in ("*TEntry*selectForeground", "*Entry*selectForeground"):
            root.option_add(pat, fg, "interactive")
        root.option_add("*TCombobox*Listbox.background", field)
        root.option_add("*TCombobox*Listbox.foreground", fg)
        root.option_add("*TCombobox*Listbox.selectBackground", field)
        root.option_add("*TCombobox*Listbox.selectForeground", fg)
    except Exception:
        pass

def apply_theme(widget):
    dark = is_dark()
    mapping = _LIGHT_TO_DARK if dark else _DARK_TO_LIGHT

    try:
        root = widget.winfo_toplevel()
    except Exception:
        root = widget

    _apply_to_ttk_style(root, mapping, dark)

    def _walk(w):
        _apply_to_widget(w, mapping, dark)
        try:
            children = w.winfo_children()
        except Exception:
            children = []
        for c in children:
            _walk(c)

    _walk(widget)

def apply_theme_to_all_toplevels(root):

    def _find_toplevels(w):
        found = []
        try:
            children = w.winfo_children()
        except Exception:
            children = []
        for c in children:
            if isinstance(c, tk.Toplevel):
                found.append(c)
            found.extend(_find_toplevels(c))
        return found

    for tl in _find_toplevels(root):
        apply_theme(tl)
