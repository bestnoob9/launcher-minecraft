"""
widgets.py
----------
Cac widget UI tai su dung duoc:
  - FilterBar           : thanh loc MC version / loader / category
  - ContentTableWidget  : bang danh sach Treeview (nhanh, khong lag)

Khong co phu thuoc vong: chi dung tkinter + config.
"""

import tkinter as tk
from tkinter import ttk
import config

# =====================================================================
# MAU SAC GIAO DIEN
# =====================================================================

BG_DARK   = "#ffffff"
BG_HOVER  = "#eef3f9"
BG_SEL    = "#cfe3fb"
BG_SEP    = "#e0e0e0"
FG_TITLE  = "#1a1a1a"
FG_AUTHOR = "#5b6b8c"
FG_DESC   = "#444444"
FG_STAT   = "#2e7d32"
FG_TAG    = "#b35900"


# =====================================================================
# WIDGET: FILTER BAR
# =====================================================================

class FilterBar(tk.Frame):
    LOADERS = ["Tat ca", "Fabric", "Forge", "Quilt", "NeoForge"]
    CATEGORIES = [
        "Tat ca", "Adventure", "Combat", "Decoration", "Economy",
        "Equipment", "Fantasy", "Game Mechanics", "Library",
        "Lightweight", "Magic", "Multiplayer", "Optimization",
        "Quests", "Realistic", "RPG", "Simulation", "Social",
        "Storage", "Technology", "Transportation", "Utility", "Worldgen",
    ]

    def __init__(self, parent, on_filter_callback, accent_color="#1E88E5",
                 show_loader=True, show_category=False, **kwargs):
        super().__init__(parent, **kwargs)
        self._cb = on_filter_callback

        tk.Label(self, text="MC Ver:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
        self.ent_ver = tk.Entry(self, font=("Arial", 9), width=8)
        self.ent_ver.pack(side="left", padx=(0, 8))
        self.ent_ver.bind("<Return>", lambda e: self._cb())

        if show_loader:
            tk.Label(self, text="Loader:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
            self.cbo_loader = ttk.Combobox(
                self, values=self.LOADERS, font=("Arial", 9), state="readonly", width=10)
            self.cbo_loader.set("Tat ca")
            self.cbo_loader.pack(side="left", padx=(0, 8))
            self.cbo_loader.bind("<<ComboboxSelected>>", lambda e: self._cb())
        else:
            self.cbo_loader = None

        if show_category:
            tk.Label(self, text="Loai:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
            self.cbo_category = ttk.Combobox(
                self, values=self.CATEGORIES, font=("Arial", 9), state="readonly", width=14)
            self.cbo_category.set("Tat ca")
            self.cbo_category.pack(side="left", padx=(0, 8))
            self.cbo_category.bind("<<ComboboxSelected>>", lambda e: self._cb())
        else:
            self.cbo_category = None

        tk.Button(self, text="Loc", font=("Arial", 8, "bold"),
                  bg=accent_color, fg="white", activebackground=accent_color,
                  activeforeground="white", pady=1, command=self._cb).pack(side="left", padx=(0, 4))
        tk.Button(self, text="Xoa", font=("Arial", 8),
                  bg="#78909C", fg="white", activebackground="#78909C",
                  activeforeground="white", pady=1, command=self._reset).pack(side="left")

    def get(self):
        """Tra ve (mc_version, loader, category)."""
        ver      = self.ent_ver.get().strip()
        loader   = self.cbo_loader.get() if self.cbo_loader else "Tat ca"
        category = self.cbo_category.get() if self.cbo_category else "Tat ca"
        return ver, loader, category

    def _reset(self):
        self.ent_ver.delete(0, "end")
        if self.cbo_loader:
            self.cbo_loader.set("Tat ca")
        if self.cbo_category:
            self.cbo_category.set("Tat ca")
        self._cb()


# =====================================================================
# WIDGET: CONTENT TABLE (Treeview - nhanh, khong lag)
# =====================================================================

class ContentTableWidget(tk.Frame):
    """
    Bang danh sach dang Treeview — render rat nhanh, khong tao widget
    rieng cho moi dong nen khong bi lag voi danh sach lon.

    source: 'modrinth' | 'curseforge'
    on_select_cb(idx, install=False) — goi khi chon / double-click dong.
    """

    COLS    = ("name", "author", "downloads", "mcver", "desc")
    HEADERS = {
        "name": "Tên", "author": "Tác giả", "downloads": "Lượt tải",
        "mcver": "MC Ver", "desc": "Mô tả",
    }
    WIDTHS  = {"name": 220, "author": 110, "downloads": 80, "mcver": 70, "desc": 320}
    ANCHORS = {"name": "w", "author": "w", "downloads": "e", "mcver": "center", "desc": "w"}

    def __init__(self, parent, source, on_select_cb, style_name="Modpack.Treeview", **kwargs):
        super().__init__(parent, **kwargs)
        self._source = source
        self._cb     = on_select_cb
        self._data   = []

        self.tree = ttk.Treeview(
            self, columns=self.COLS, show="headings",
            selectmode="browse", style=style_name,
        )
        for c in self.COLS:
            self.tree.heading(c, text=self.HEADERS[c])
            self.tree.column(c, width=self.WIDTHS[c], anchor=self.ANCHORS[c],
                             stretch=(c == "desc"))

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",          self._on_double)

    def load(self, data_list):
        self._data = data_list
        self.tree.delete(*self.tree.get_children())

        for i, d in enumerate(data_list):
            if self._source == "modrinth":
                name      = d.get("title", "")
                author    = d.get("author", "")
                downloads = d.get("downloads", 0)
                versions  = d.get("versions", [])
                mc_ver    = versions[-1] if versions else ""
                desc      = d.get("description", "")
            else:  # curseforge
                name      = d.get("name", "")
                authors   = d.get("authors", [])
                author    = authors[0].get("name", "") if authors else ""
                downloads = d.get("downloadCount", 0)
                idx_files = d.get("latestFilesIndexes", [])
                mc_ver    = idx_files[0].get("gameVersion", "") if idx_files else ""
                desc      = d.get("summary", "")

            desc_short = (desc or "").replace("\n", " ").strip()
            self.tree.insert(
                "", "end", iid=str(i),
                values=(name, author, f"{int(downloads):,}", mc_ver, desc_short),
            )

    def _on_select(self, e=None):
        sel = self.tree.selection()
        if sel:
            self._cb(int(sel[0]), install=False)

    def _on_double(self, e=None):
        sel = self.tree.selection()
        if sel:
            self._cb(int(sel[0]), install=True)

    def get_selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else -1


# =====================================================================
# HELPER: tao bottom panel chon phien ban + instance
# =====================================================================

def make_install_panel(parent, bg, lbl_phien_ban, lbl_instance, btn_text, btn_color, btn_cmd):
    """
    Tao panel chon phien ban + instance + nut cai.
    Tra ve (cbo_ver, cbo_inst).
    """
    bp = tk.Frame(parent, bg=bg)
    bp.pack(fill="x", padx=10, pady=(4, 8))

    tk.Label(bp, text=lbl_phien_ban, font=("Arial", 9), bg=bg).grid(row=0, column=0, sticky="w")
    cbo_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
    cbo_ver.grid(row=0, column=1, padx=6)

    tk.Label(bp, text=lbl_instance, font=("Arial", 9), bg=bg).grid(row=1, column=0, sticky="w", pady=4)
    ds_inst  = list(config.current_config.get("danh_sach_instances", {}).keys())
    cbo_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
    cur = config.current_config.get("current_instance", "")
    if cur in ds_inst:  cbo_inst.set(cur)
    elif ds_inst:       cbo_inst.set(ds_inst[0])
    cbo_inst.grid(row=1, column=1, padx=6)

    tk.Button(
        bp, text=btn_text, font=("Arial", 9, "bold"),
        bg=btn_color, fg="white", activebackground=btn_color,
        activeforeground="white", width=14, pady=4,
        command=btn_cmd,
    ).grid(row=0, column=2, rowspan=2, padx=8)

    return cbo_ver, cbo_inst
