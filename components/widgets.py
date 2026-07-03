"""
widgets.py
----------
Cac widget UI tai su dung duoc:
  - FilterBar           : thanh loc MC version / loader / category
  - ContentTableWidget  : bang danh sach Treeview (nhanh, khong lag)

Khong co phu thuoc vong: chi dung tkinter + config.
"""

import io
import threading
import urllib.request

import tkinter as tk
from tkinter import ttk
import config
import theme

try:
    from PIL import Image, ImageTk, ImageDraw
    _PIL_OK = True
except Exception:
    _PIL_OK = False

BG_DARK   = "#ffffff"
BG_HOVER  = "#eef3f9"
BG_SEL    = "#cfe3fb"
BG_SEP    = "#e0e0e0"
FG_TITLE  = "#1a1a1a"
FG_AUTHOR = "#5b6b8c"
FG_DESC   = "#444444"
FG_STAT   = "#2e7d32"
FG_TAG    = "#b35900"
ICON_BG   = "#e1e4ea"
ICON_SIZE = 56


class FilterBar(tk.Frame):
    LOADERS = ["Tất cả", "Fabric", "Forge", "Quilt", "NeoForge"]
    CATEGORIES = [
        "Tất cả", "Adventure", "Combat", "Decoration", "Economy",
        "Equipment", "Fantasy", "Game Mechanics", "Library",
        "Lightweight", "Magic", "Multiplayer", "Optimization",
        "Quests", "Realistic", "RPG", "Simulation", "Social",
        "Storage", "Technology", "Transportation", "Utility", "Worldgen",
    ]

    # Fallback khi chua/khong goi duoc API Mojang
    _MC_FALLBACK = [
        "26.3","26.2", "26.1",
        "1.21.5", "1.21.4", "1.21.3", "1.21.2", "1.21.1", "1.21",
        "1.20.6", "1.20.4", "1.20.2", "1.20.1", "1.20",
        "1.19.4", "1.19.2", "1.19",
        "1.18.2", "1.18", "1.17.1", "1.17",
        "1.16.5", "1.16.1", "1.16",
        "1.15.2", "1.15", "1.14.4", "1.14",
        "1.13.2", "1.13", "1.12.2", "1.12",
        "1.11.2", "1.10.2", "1.9.4", "1.8.9", "1.7.10",
    ]

    # Cache dung chung cho ca chuong trinh
    _ver_cache   = []    # list[dict]: {"id": "...", "type": "release"/"snapshot"/...}
    _cache_ready = False
    _cache_busy  = False

    @classmethod
    def _load_versions_async(cls, on_done=None):
        """Goi API Mojang 1 lan, luu vao _ver_cache, goi on_done() khi xong."""
        if cls._cache_ready:
            if on_done: on_done()
            return
        if cls._cache_busy:
            return
        cls._cache_busy = True
        def _t():
            import urllib.request, json as _json
            try:
                req = urllib.request.Request(
                    "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json",
                    headers={"User-Agent": "MinecraftLauncher/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = _json.loads(r.read())
                cls._ver_cache = data.get("versions", [])
            except Exception:
                cls._ver_cache = [{"id": v, "type": "release"} for v in cls._MC_FALLBACK]
            cls._cache_ready = True
            cls._cache_busy  = False
            if on_done:
                try: on_done()
                except Exception: pass
        threading.Thread(target=_t, daemon=True).start()

    def __init__(self, parent, on_filter_callback, accent_color="#1E88E5",
                 show_loader=True, show_category=False, **kwargs):
        super().__init__(parent, **kwargs)
        self._cb = on_filter_callback
        self._incl_snap = tk.BooleanVar(value=False)

        tk.Label(self, text="MC Ver:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
        self.cbo_mc = ttk.Combobox(
            self, font=("Arial", 9), state="readonly", width=10, height=12)
        self.cbo_mc.set("Tất cả")
        self.cbo_mc.pack(side="left", padx=(0, 4))
        self.cbo_mc.bind("<<ComboboxSelected>>", lambda e: self._cb())
        # Alias tuong thich nguoc
        self.ent_ver = self.cbo_mc

        tk.Checkbutton(
            self, text="Snapshot", font=("Arial", 8),
            variable=self._incl_snap, bg=self["bg"],
            command=self._rebuild_ver_list,
        ).pack(side="left", padx=(0, 8))

        if show_loader:
            tk.Label(self, text="Loader:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
            self.cbo_loader = ttk.Combobox(
                self, values=self.LOADERS, font=("Arial", 9), state="readonly", width=10)
            self.cbo_loader.set("Tất cả")
            self.cbo_loader.pack(side="left", padx=(0, 8))
            self.cbo_loader.bind("<<ComboboxSelected>>", lambda e: self._cb())
        else:
            self.cbo_loader = None

        if show_category:
            tk.Label(self, text="Loại:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
            self.cbo_category = ttk.Combobox(
                self, values=self.CATEGORIES, font=("Arial", 9), state="readonly", width=14)
            self.cbo_category.set("Tất cả")
            self.cbo_category.pack(side="left", padx=(0, 8))
            self.cbo_category.bind("<<ComboboxSelected>>", lambda e: self._cb())
        else:
            self.cbo_category = None

        self._category_id_map = {}

        tk.Button(self, text="Lọc", font=("Arial", 8, "bold"),
                  bg=accent_color, fg="white", activebackground=accent_color,
                  activeforeground="white", pady=1, command=self._cb).pack(side="left", padx=(0, 4))
        tk.Button(self, text="Xóa", font=("Arial", 8),
                  bg="#78909C", fg="white", activebackground="#78909C",
                  activeforeground="white", pady=1, command=self._reset).pack(side="left")

        # Hien danh sach fallback ngay, sau do cap nhat khi API xong
        self._rebuild_ver_list()
        FilterBar._load_versions_async(on_done=lambda: self.after(0, self._rebuild_ver_list))

    def _rebuild_ver_list(self):
        """Cap nhat dropdown phien ban tuy theo checkbox Snapshot."""
        cur = self.cbo_mc.get()
        incl = self._incl_snap.get()
        if FilterBar._cache_ready:
            allowed = {"release", "snapshot"} if incl else {"release"}
            vers = ["Tất cả"] + [v["id"] for v in FilterBar._ver_cache if v["type"] in allowed]
        else:
            vers = ["Tất cả"] + list(self._MC_FALLBACK)
        self.cbo_mc.config(values=vers)
        self.cbo_mc.set(cur if cur in vers else "Tất cả")

    def set_categories(self, categories):
        """
        Cap nhat lai danh sach category hien trong dropdown sau khi widget
        da duoc tao - dung cho CurseForge, vi category that phai tai bat
        dong bo tu API (lay_category_curseforge), khac voi Modrinth co list
        CATEGORIES co dinh san co tu luc khoi tao.
        categories: list[dict] dang [{"id": 421, "name": "Adventure and RPG"}, ...]
        """
        if not self.cbo_category:
            return
        names = ["Tất cả"] + [c["name"] for c in categories]
        self._category_id_map = {c["name"]: c["id"] for c in categories}
        cur = self.cbo_category.get()
        self.cbo_category.configure(values=names)
        # Giu lai lua chon cu neu ten do van con trong danh sach moi
        self.cbo_category.set(cur if cur in names else "Tất cả")

    def get(self):
        """
        Tra ve (mc_version, loader, category).
        'category' la chuoi ten (Modrinth) HOAC id so (CurseForge, neu
        set_categories() da duoc goi truoc do voi du lieu that tu API) -
        tra ve None/"" khi dang chon "Tất cả" (khong loc theo category).
        """
        ver_raw = self.cbo_mc.get().strip()
        ver     = "" if ver_raw in ("Tất cả", "") else ver_raw
        loader = self.cbo_loader.get() if self.cbo_loader else "Tất cả"
        cat_ten = self.cbo_category.get() if self.cbo_category else "Tất cả"
        if cat_ten in ("Tất cả", ""):
            category = ""
        elif self._category_id_map:
            category = self._category_id_map.get(cat_ten, "")
        else:
            category = cat_ten
        return ver, loader, category

    def _reset(self):
        self._incl_snap.set(False)
        self._rebuild_ver_list()
        self.cbo_mc.set("Tất cả")
        if self.cbo_loader:
            self.cbo_loader.set("Tất cả")
        if self.cbo_category:
            self.cbo_category.set("Tất cả")
        self._cb()


class _IconCache:
    """
    Tai anh icon tu URL trong thread phu, resize vuong ve ICON_SIZE,
    cache theo URL de khong tai lai. Khi xong se goi callback(photo)
    tren main thread qua widget.after().
    """
    _cache = {}      # url -> ImageTk.PhotoImage
    _pending = {}    # url -> list of (widget, on_ready) dang doi

    @classmethod
    def get(cls, widget, url, on_ready):
        """
        Tra ve ngay PhotoImage neu da co trong cache (va goi on_ready).
        Neu chua co va url hop le -> tai nen, goi on_ready khi xong.
        Neu khong co url -> goi on_ready(None).
        """
        if not url or not _PIL_OK:
            on_ready(None)
            return

        if url in cls._cache:
            on_ready(cls._cache[url])
            return

        if url in cls._pending:
            cls._pending[url].append((widget, on_ready))
            return

        cls._pending[url] = [(widget, on_ready)]

        def _t():
            photo = None
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "MinecraftLauncher/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read()
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
                img = img.resize((ICON_SIZE, ICON_SIZE), Image.BILINEAR)
                photo = ImageTk.PhotoImage(img)
                cls._cache[url] = photo
            except Exception:
                photo = None
            waiters = cls._pending.pop(url, [])
            for w, cb in waiters:
                try:
                    w.after(0, lambda cb=cb, photo=photo: cb(photo))
                except Exception:
                    pass

        threading.Thread(target=_t, daemon=True).start()

    @classmethod
    def placeholder(cls, widget):
        """Anh placeholder mau xam (khong co icon / dang tai)."""
        key = "__placeholder_" + theme.get_theme_name() + "__"
        if key in cls._cache:
            return cls._cache[key]
        if not _PIL_OK:
            return None
        c = theme.colors()
        img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), c["icon_bg"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, ICON_SIZE - 1, ICON_SIZE - 1], outline=c["icon_border"], width=1)
        photo = ImageTk.PhotoImage(img)
        cls._cache[key] = photo
        return photo


class ContentTableWidget(tk.Frame):
    """
    Bang danh sach dang cac dong (row) co anh icon ben trai + thong tin
    ten / tac gia / mo ta ben canh, luot tai + MC ver ben phai.

    Render bang Canvas + scrollbar (khong dung Treeview) de co the
    chen anh thumbnail cho moi dong, anh duoc tai bat dong bo + cache.

    Icon chi duoc tai khi dong nam trong (hoac gan) khung nhin, tranh
    tai hang chuc anh cung luc khi mo tab / load danh sach moi.

    source: 'modrinth' | 'curseforge'
    on_select_cb(idx, install=False) — goi khi chon / double-click dong.
    """

    ROW_H = 78  # chieu cao moi dong (>= ICON_SIZE + padding)

    def __init__(self, parent, source, on_select_cb, style_name="Modpack.Treeview", **kwargs):
        self._c = theme.colors()
        bg = kwargs.pop("bg", self._c["row_bg"])
        super().__init__(parent, bg=bg, **kwargs)
        self._source   = source
        self._cb       = on_select_cb
        self._data     = []
        self._rows     = []   # list of dict: frame, icon_label, ...
        self._selected = -1

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self._on_scrollbar)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self._inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_scroll(self.canvas)

        self._visible_check_id = None
        self._wrap_after_id = None
        self._pending_canvas_width = None

    def _on_inner_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._schedule_visible_check()

    def _on_canvas_configure(self, e):
        # QUAN TRONG: KHONG goi itemconfig(width=...) ngay tai day. Lam vay
        # ep Tk sap xep lai (re-pack) TOAN BO cac dong (row) ben trong inner
        # NGAY LAP TUC tren MOI tick resize - trong luc keo chuot thay doi
        # kich thuoc cua so, co the co hang chuc tick/giay, nhan voi hang
        # chuc dong trong danh sach -> day chinh la nguyen nhan gay giat/lag
        # ro ret (nang hon nhieu so voi viec tinh lai wraplength). Thay vao
        # do chi luu lai chieu rong moi nhat va debounce - sap xep lai CHI
        # MOT LAN sau khi nguoi dung ngung keo ~70ms.
        self._pending_canvas_width = e.width
        self._schedule_wrap_refresh()

    def _on_scrollbar(self, *args):
        self.canvas.yview(*args)
        self._schedule_visible_check()

    def _bind_scroll(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", lambda e: self._scroll_units(-3))
        widget.bind("<Button-5>", lambda e: self._scroll_units(3))

    def _on_mousewheel(self, e):
        delta = -1 if e.delta > 0 else 1
        self._scroll_units(delta * 3)

    def _scroll_units(self, units):
        self.canvas.yview_scroll(units, "units")
        self._schedule_visible_check()

    def _schedule_visible_check(self):
        """Debounce nho: cho UI on dinh roi moi quet icon hien thi."""
        if self._visible_check_id is not None:
            try:
                self.after_cancel(self._visible_check_id)
            except Exception:
                pass
        self._visible_check_id = self.after(50, self._load_visible_icons)

    def _load_visible_icons(self):
        """Tai icon cho cac dong dang hien trong khung nhin (+ vung dem)."""
        self._visible_check_id = None
        if not self._rows:
            return
        top    = self.canvas.canvasy(0)
        bottom = top + self.canvas.winfo_height()
        buffer = self.ROW_H * 3  # tai truoc/sau 3 dong de cuon muot hon

        for row in self._rows:
            if row.get("icon_loaded"):
                continue
            y0 = row["y"]
            y1 = y0 + self.ROW_H
            if y1 < top - buffer or y0 > bottom + buffer:
                continue
            row["icon_loaded"] = True
            _IconCache.get(self, row["icon_url"], row["on_icon_ready"])

    def load(self, data_list):
        self._c         = theme.colors()
        self._data      = data_list
        self._selected  = -1

        if self._wrap_after_id is not None:
            try:
                self.after_cancel(self._wrap_after_id)
            except Exception:
                pass
            self._wrap_after_id = None

        for r in self._rows:
            try:
                r["sep"].destroy()
            except Exception:
                pass
            r["frame"].destroy()
        self._rows = []

        for i, d in enumerate(data_list):
            self._build_row(i, d)

        self.canvas.yview_moveto(0)
        self._schedule_visible_check()

    def _extract(self, d):
        if self._source == "modrinth":
            name      = d.get("title", "")
            author    = d.get("author", "")
            downloads = d.get("downloads", 0)
            versions  = d.get("versions", [])
            mc_ver    = versions[-1] if versions else ""
            desc      = d.get("description", "")
            icon_url  = d.get("icon_url", "")
        else:  # curseforge
            name      = d.get("name", "")
            authors   = d.get("authors", [])
            author    = authors[0].get("name", "") if authors else ""
            downloads = d.get("downloadCount", 0)
            idx_files = d.get("latestFilesIndexes", [])
            mc_ver    = idx_files[0].get("gameVersion", "") if idx_files else ""
            desc      = d.get("summary", "")
            logo      = d.get("logo") or {}
            icon_url  = logo.get("thumbnailUrl", "") or logo.get("url", "")

        desc_short = (desc or "").replace("\n", " ").strip()
        if len(desc_short) > 80:
            desc_short = desc_short[:77].rstrip() + "..."
        return name, author, int(downloads or 0), mc_ver, desc_short, icon_url

    def _build_row(self, i, d):
        name, author, downloads, mc_ver, desc, icon_url = self._extract(d)
        c = self._c

        row = tk.Frame(self.inner, bg=c["row_bg"], height=self.ROW_H)
        row.pack(fill="x")
        row.pack_propagate(False)

        ph = _IconCache.placeholder(self)
        icon_lbl = tk.Label(row, bg=c["row_bg"], bd=0)
        if ph is not None:
            icon_lbl.configure(image=ph)
            icon_lbl.image = ph
        icon_lbl.pack(side="left", padx=(10, 10), pady=11)

        def _on_icon_ready(photo, lbl=icon_lbl):
            if photo is None:
                return
            try:
                lbl.configure(image=photo)
                lbl.image = photo
            except tk.TclError:
                pass  # widget da bi destroy

        # Khong tai icon ngay - se duoc tai khi dong nay vao khung nhin
        # (xem _load_visible_icons), tranh tai hang chuc anh cung luc.

        text_col = tk.Frame(row, bg=c["row_bg"])
        text_col.pack(side="left", fill="both", expand=True, pady=8)

        lbl_name = tk.Label(text_col, text=name, font=("Arial", 12, "bold"),
                             fg=c["fg_title"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_name.pack(fill="x", anchor="w")

        sub = f"by {author}" if author else ""
        lbl_author = tk.Label(text_col, text=sub, font=("Arial", 9),
                               fg=c["fg_author"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_author.pack(fill="x", anchor="w", pady=(1, 2))

        lbl_desc = tk.Label(text_col, text=desc, font=("Arial", 9),
                             fg=c["fg_desc"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_desc.pack(fill="x", anchor="w")

        right_col = tk.Frame(row, bg=c["row_bg"])
        right_col.pack(side="right", padx=(8, 14), pady=8)

        lbl_dl = tk.Label(right_col, text=f"⬇ {downloads:,}", font=("Arial", 10, "bold"),
                           fg=c["fg_stat"], bg=c["row_bg"], anchor="e")
        lbl_dl.pack(anchor="e")

        lbl_mc = tk.Label(right_col, text=mc_ver, font=("Arial", 9),
                           fg=c["fg_tag"], bg=c["row_bg"], anchor="e")
        lbl_mc.pack(anchor="e", pady=(2, 0))

        sep = tk.Frame(self.inner, bg=c["row_sep"], height=1)
        sep.pack(fill="x")

        # Tinh lai wraplength khi text_col doi kich thuoc (vd cua so duoc
        # keo rong/hep). KHONG tinh ngay lap tuc trong lambda nay - trong
        # luc keo chuot, Tk phat ra rat nhieu su kien <Configure> lien tiep
        # cho MOI dong dang co trong bang, neu xu ly ngay se gay giat/lag
        # ro ret voi danh sach nhieu dong. Thay vao do chi "danh dau can
        # cap nhat" va goi _schedule_wrap_refresh() - gom (debounce) tat ca
        # cac lan trigger lien tiep thanh DUY NHAT mot lan tinh lai sau khi
        # nguoi dung ngung keo ~70ms (xem _schedule_wrap_refresh / _refresh_wraps).
        text_col.bind("<Configure>", lambda e: self._schedule_wrap_refresh())

        widgets = [row, icon_lbl, text_col, lbl_name, lbl_author, lbl_desc,
                   right_col, lbl_dl, lbl_mc, sep]
        for w in widgets:
            w.bind("<Button-1>", lambda e, idx=i: self._select(idx))
            w.bind("<Double-1>", lambda e, idx=i: self._select(idx, install=True))
            self._bind_scroll(w)

        self._rows.append({
            "frame": row, "sep": sep, "widgets": widgets,
            "text_col": text_col, "lbl_name": lbl_name, "lbl_author": lbl_author,
            "icon_url": icon_url, "on_icon_ready": _on_icon_ready,
            "icon_loaded": False, "y": i * self.ROW_H,
        })

    def _schedule_wrap_refresh(self):
        """Gom nhieu su kien <Configure> lien tiep (vd trong luc keo chuot
        thay doi kich thuoc cua so) thanh MOT lan tinh lai wraplength duy
        nhat cho tat ca cac dong, thay vi tinh lai ngay lap tuc cho tung
        dong tren tung su kien - day la nguyen nhan chinh gay giat/lag khi
        keo rong cua so o danh sach Mod/Modpack/Resource Pack/Shader."""
        if getattr(self, "_wrap_after_id", None) is not None:
            try:
                self.after_cancel(self._wrap_after_id)
            except Exception:
                pass
        self._wrap_after_id = self.after(70, self._refresh_wraps)

    def _refresh_wraps(self):
        self._wrap_after_id = None

        # Ap dung chieu rong canvas moi nhat (bi hoan lai o _on_canvas_configure)
        # NGAY TAI DAY - chi MOT LAN duy nhat cho ca danh sach, thay vi tren
        # moi tick resize. Day la buoc gay "re-pack" toan bo cac dong nen can
        # gom lai nhu the nay de tranh giat/lag.
        if self._pending_canvas_width is not None:
            try:
                self.canvas.itemconfig(self._inner_id, width=self._pending_canvas_width)
            except tk.TclError:
                pass
            self._pending_canvas_width = None

        for row in self._rows:
            text_col = row.get("text_col")
            if text_col is None:
                continue
            try:
                w = max(text_col.winfo_width() - 4, 60)
                row["lbl_name"].configure(wraplength=w)
                row["lbl_author"].configure(wraplength=w)
            except tk.TclError:
                pass  # dong da bi destroy (vd danh sach da duoc load() lai)

    def _select(self, idx, install=False):
        if idx < 0 or idx >= len(self._rows):
            return
        # Doc mau theme MOI NHAT moi lan chon/bo chon, tranh dung mau
        # da cu (cache tu luc khoi tao) gay sai mau (vd den) khi theme
        # (app hoac he thong) da doi sau khi bang duoc dung.
        self._c = theme.colors()
        if self._selected != -1 and self._selected < len(self._rows):
            self._set_row_bg(self._selected, self._c["row_bg"])
        self._selected = idx
        self._set_row_bg(idx, self._c["row_sel"])
        self._cb(idx, install=install)

    def _set_row_bg(self, idx, color):
        row = self._rows[idx]
        for w in row["widgets"]:
            if w is row["frame"] or isinstance(w, (tk.Frame, tk.Label)):
                try:
                    w.configure(bg=color)
                except tk.TclError:
                    pass

    def get_selected(self):
        return self._selected


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