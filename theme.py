"""
theme.py
--------
He thong chuyen doi giao dien Sang / Toi cho toan bo ung dung.

Cach hoat dong:
  - Cac mau "trung tinh" (nen trang, nen xam nhat, chu den, vien xam...)
  - duoc anh xa (map) sang mau toi tuong ung khi che do Toi duoc chon.
  - Cac mau "accent" (nut xanh, do, vang, tim...) GIU NGUYEN vi da du
    tuong phan tren ca 2 nen.

Su dung:
    import theme
    theme.apply_theme(window)   # goi sau khi build xong widget cua window

Luu trang thai:
    config.current_config["theme"] = "light" | "dark"
"""

import tkinter as tk
from tkinter import ttk
import config

# Luu lai ten ttk theme goc cua he dieu hanh (vd 'vista') de khoi phuc
# khi nguoi dung chuyen ve giao dien Sang.
_NATIVE_TTK_THEME = None


# =====================================================================
# BANG MAU
# =====================================================================

# Mau nen / chu trung tinh dung trong toan bo code (light mode "goc")
# -> mau tuong ung khi o Dark mode.
_LIGHT_TO_DARK = {
    # --- nen ---
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

    # --- chu ---
    "#1a1a1a": "#e8e8e8",
    "black":   "#e8e8e8",
    "#444444": "#cfcfcf",
    "#555":    "#b5b5b5",
    "#555555": "#b5b5b5",
    "#5b6b8c": "#9fb3d6",
    "#888":    "#9a9a9a",
    "#888888": "#9a9a9a",
    "gray":    "#a0a0a0",
    "grey":    "#a0a0a0",
}

# Mau dark-mode -> light-mode (chieu nguoc, de doi lai khi ve Sang)
_DARK_TO_LIGHT = {v: k for k, v in _LIGHT_TO_DARK.items()}
# Uu tien khoi phuc mau "chuan" thay vi cac alias (white/black/gray)
_DARK_TO_LIGHT.update({
    "#1e1e1e": "#ffffff",
    "#e8e8e8": "#1a1a1a",
    "#a0a0a0": "gray",
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
    """name: 'light' | 'dark'. Luu vao config (khong tu ghi file)."""
    if name not in ("light", "dark"):
        name = "light"
    config.current_config["theme"] = name


# =====================================================================
# MAU CHINH DUNG CHO CUA SO / WIDGET MOI TAO
# =====================================================================

def colors():
    """Tra ve dict mau chinh theo theme hien tai — dung khi tao widget moi
    (vd ContentTableWidget trong widgets.py)."""
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


# =====================================================================
# AP DUNG THEME LEN CAY WIDGET (hoi quy)
# =====================================================================

# Cac option mau theo loai widget tk
_BG_OPTS = ("bg", "background", "highlightbackground",
            "selectbackground", "activebackground", "readonlybackground",
            "insertbackground")
_FG_OPTS = ("fg", "foreground", "activeforeground", "selectforeground")


def _remap(value, mapping):
    if value is None:
        return None
    key = value if value.startswith("#") else value.lower()
    return mapping.get(key) or mapping.get(value)


def _apply_to_widget(w, mapping):
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

    # Tat highlight mau xanh khi click/focus/select text: dat
    # selectbackground/selectforeground = bg/fg binh thuong cua widget
    # (tk.Entry, tk.Spinbox, tk.Text, tk.Listbox...).
    if "selectbackground" in opts and "bg" in opts:
        try:
            w.configure(selectbackground=w.cget("bg"))
        except Exception:
            pass
    if "selectforeground" in opts and "fg" in opts:
        try:
            w.configure(selectforeground=w.cget("fg"))
        except Exception:
            pass


def _apply_to_ttk_style(root, mapping, dark):
    """Cau hinh ttk.Style cho Notebook / Treeview / Combobox / Scrollbar /
    Progressbar de hop voi theme hien tai."""
    style = ttk.Style(root)

    # Theme ttk mac dinh cua he dieu hanh (vd 'vista'/'winnative' tren Windows)
    # KHONG ho tro doi mau Combobox/select-highlight qua ttk.Style. 'clam'
    # ho tro day du nen duoc dung cho CA 2 theme (Sang va Toi) de dam bao
    # khong con vung "highlight" mau xanh he thong khi click Combobox.
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

    try:
        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)

        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=trough, foreground=fg,
                        padding=(10, 4))
        style.map("TNotebook.Tab",
                  background=[("selected", bg)],
                  foreground=[("selected", fg)])

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

        # Treeview (ContentTableWidget cu / cac bang khac neu co)
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

    # Danh sach xo xuong (popdown) cua Combobox la mot Listbox rieng,
    # khong nam trong ttk.Style - phai chinh qua option_add.
    try:
        root.option_add("*TCombobox*Listbox.background", field)
        root.option_add("*TCombobox*Listbox.foreground", fg)
        root.option_add("*TCombobox*Listbox.selectBackground", sel)
        root.option_add("*TCombobox*Listbox.selectForeground", fg)

        # Mau "highlight" text khi Combobox dang focus / select-all -
        # dat bang dung mau nen/chu binh thuong de "an" hieu ung bem xanh
        # khi click vao combobox (ca 2 theme).
        root.option_add("*TCombobox*selectBackground", field)
        root.option_add("*TCombobox*selectForeground", fg)
        root.option_add("*TEntry*selectBackground", field)
        root.option_add("*TEntry*selectForeground", fg)
    except Exception:
        pass


def preload_combobox_options(root):
    """
    Goi SOM nhat co the (ngay sau khi tao root, TRUOC khi tao bat ky
    widget nao). Thiet lap option_add cho mau "select highlight" cua
    Combobox/Entry de khong bi mau xanh he thong khi click/focus —
    option_add chi anh huong widget tao SAU thoi diem goi nay.
    """
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
    """
    Ap dung theme hien tai (config.current_config['theme']) cho `widget`
    va toan bo widget con (hoi quy). Goi sau khi build xong UI cua mot
    window/frame, hoac sau khi nguoi dung doi theme trong Settings.
    """
    dark = is_dark()
    mapping = _LIGHT_TO_DARK if dark else _DARK_TO_LIGHT

    try:
        root = widget.winfo_toplevel()
    except Exception:
        root = widget

    _apply_to_ttk_style(root, mapping, dark)

    def _walk(w):
        _apply_to_widget(w, mapping)
        try:
            children = w.winfo_children()
        except Exception:
            children = []
        for c in children:
            _walk(c)

    _walk(widget)


def apply_theme_to_all_toplevels(root):
    """Ap dung theme cho root va toan bo cua so con (Toplevel) dang mo,
    bat ke Toplevel do duoc tao voi parent la root hay mot Frame con."""
    apply_theme(root)

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