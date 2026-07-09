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
from tkinter import font as tkfont
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
ICON_SIZE = 72

# Mau accent theo nguon - dung cho nut "Cai dat", cham bullet truoc ten,
# vien chip loader... giong phong cach the CurseForge / Modrinth.
ACCENT_MODRINTH   = "#1E88E5"
ACCENT_CURSEFORGE = "#F16436"

# Cac slug loader thuong tron trong "categories"/"display_categories" cua
# Modrinth, hoac gia tri modLoader (int) cua CurseForge - dung de tach
# rieng "loader" ra khoi danh sach tag hien thi va ve thanh mot chip rieng.
_LOADER_SLUGS = {"forge", "fabric", "quilt", "neoforge", "liteloader", "rift"}
_CF_LOADER_MAP = {
    1: "Forge", 2: "Cauldron", 3: "LiteLoader", 4: "Fabric",
    5: "Quilt", 6: "NeoForge",
}
_MAX_TAGS_HIEN = 4   # so tag toi da hien truoc khi rut gon thanh "+N"


def _dinh_dang_so_luot(n):
    """1234 -> '1.2K', 1234567 -> '1.2M' (giong bo dem tren CurseForge)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}K".replace(".0K", "K")
    return str(n)


def _dinh_dang_dung_luong(so_byte):
    """so byte -> '93.93 MB' / '512 KB' ..., None neu khong co du lieu."""
    try:
        b = float(so_byte)
    except (TypeError, ValueError):
        return None
    if b <= 0:
        return None
    if b >= 1024 * 1024:
        return f"{b / (1024 * 1024):.2f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{int(b)} B"


def _dinh_dang_ngay_tuong_doi(chuoi_iso):
    """'2026-07-05T10:00:00Z' -> 'Hôm nay' / '3 ngày trước' / '2 tháng trước'."""
    if not chuoi_iso:
        return ""
    try:
        import datetime
        s = chuoi_iso.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
        delta_ngay = (now - dt).days
        if delta_ngay <= 0:
            return "Hôm nay"
        if delta_ngay == 1:
            return "Hôm qua"
        if delta_ngay < 30:
            return f"{delta_ngay} ngày trước"
        if delta_ngay < 365:
            return f"{delta_ngay // 30} tháng trước"
        return f"{delta_ngay // 365} năm trước"
    except Exception:
        return ""


class _CategoryMultiSelect(tk.Frame):
    """
    Nut mo popup danh sach the loai (category) co the tick NHIEU cai cung
    luc - giong dung hanh vi cua Modrinth that (xem sidebar "Loai" trong
    Modrinth App: co the tick ca "Nhe" + "Nhieu nguoi choi" + "Toi uu hoa"
    cung mot luc). Day la diem khac biet co ban voi CurseForge trong app
    nay, ta chi cho chon 1 category qua combobox don (giong cach loc don
    gian, dung voi kieu "Filters" 1-gia-tri cua CurseForge o day).
    """

    def __init__(self, parent, bg, on_change):
        super().__init__(parent, bg=bg)
        self._on_change = on_change
        self._items = []        # list[dict]: {"name": slug, "header": nhom}
        self._checked = set()   # cac slug dang duoc tick
        self._popup = None
        self._vars = {}

        self.btn = tk.Button(
            self, text="Loại: Tất cả", font=("Arial", 9), anchor="w",
            relief="groove", bd=1, padx=6, pady=1, bg="white",
            command=self._toggle_popup)
        self.btn.pack(side="left")

    def set_items(self, items):
        self._items = items or []
        valid_names = {i["name"] for i in self._items}
        self._checked &= valid_names
        self._refresh_btn_text()

    def get_selected(self):
        return list(self._checked)

    def reset(self):
        self._checked = set()
        for v in self._vars.values():
            v.set(False)
        self._refresh_btn_text()

    def _refresh_btn_text(self):
        n = len(self._checked)
        self.btn.configure(text="Loại: Tất cả" if n == 0 else f"Loại: {n} đã chọn")

    def _toggle_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._close_popup()
            return
        self._open_popup()

    def _open_popup(self):
        # Lay mau theo THEME HIEN TAI (Sang/Toi) - popup nay la 1 Toplevel
        # duoc tao MOI LAN bam nut, KHONG nam san trong cay widget luc
        # theme.apply_theme() chay o dau chuong trinh, nen phai tu chon
        # mau ngay tai day thay vi de mac dinh trang/den nhu truoc (gay
        # loi popup luon trang du dang o Dark mode).
        c = theme.colors()
        dark = theme.is_dark()
        pop_bg     = c["bg_alt"]
        item_bg    = c["bg"]
        fg         = c["fg_title"]
        fg_muted   = c["fg_author"]
        border_col = c["icon_border"]
        btn_bg     = "#455A64" if dark else "#78909C"

        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=border_col)
        x = self.btn.winfo_rootx()
        y = self.btn.winfo_rooty() + self.btn.winfo_height()
        top.geometry(f"+{x}+{y}")
        self._popup = top

        outer = tk.Frame(top, bg=border_col)
        outer.pack()
        frame = tk.Frame(outer, bg=item_bg)
        frame.pack(padx=1, pady=1)

        canvas = tk.Canvas(frame, width=210, height=260, bg=item_bg, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=item_bg)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._vars = {}
        last_header = None
        if not self._items:
            tk.Label(inner, text="(Đang tải...)", font=("Arial", 9),
                     bg=item_bg, fg=fg_muted).pack(anchor="w", padx=6, pady=6)
        for it in self._items:
            name = it.get("name", "")
            header = it.get("header", "") or "categories"
            if header != last_header:
                tk.Label(inner, text=header.replace("_", " ").capitalize(),
                         font=("Arial", 8, "bold"), bg=item_bg, fg=fg_muted
                         ).pack(anchor="w", padx=6, pady=(6, 0))
                last_header = header
            var = tk.BooleanVar(value=name in self._checked)
            self._vars[name] = var
            tk.Checkbutton(
                inner, text=name.replace("-", " ").replace("_", " ").title(),
                variable=var, bg=item_bg, fg=fg, activebackground=item_bg,
                activeforeground=fg, selectcolor=item_bg,
                highlightthickness=0, anchor="w", font=("Arial", 9),
                command=lambda n=name, v=var: self._on_check(n, v)
            ).pack(anchor="w", fill="x", padx=4)

        btns = tk.Frame(outer, bg=item_bg)
        btns.pack(fill="x")
        tk.Button(btns, text="Xóa lọc", font=("Arial", 8), bg=btn_bg, fg="white",
                  activebackground=btn_bg, activeforeground="white",
                  relief="flat", command=self._clear_all).pack(side="left", padx=4, pady=4)
        tk.Button(btns, text="Đóng", font=("Arial", 8), bg=btn_bg, fg="white",
                  activebackground=btn_bg, activeforeground="white",
                  relief="flat", command=self._close_popup).pack(side="right", padx=4, pady=4)

        top.bind("<FocusOut>", lambda e: self._close_popup())
        top.focus_force()

    def _on_check(self, name, var):
        if var.get():
            self._checked.add(name)
        else:
            self._checked.discard(name)
        self._refresh_btn_text()
        self._on_change()

    def _clear_all(self):
        self._checked.clear()
        for v in self._vars.values():
            v.set(False)
        self._refresh_btn_text()
        self._on_change()

    def _close_popup(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None


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
                 show_loader=True, show_category=False, multi_category=False, **kwargs):
        super().__init__(parent, **kwargs)
        self._cb = on_filter_callback
        self._incl_snap = tk.BooleanVar(value=False)
        self._multi_category = multi_category

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
            if multi_category:
                # Modrinth: cho tick NHIEU category cung luc (giong Modrinth
                # that), khac voi CurseForge chi chon 1 qua combobox don.
                self.cbo_category = _CategoryMultiSelect(self, bg=self["bg"], on_change=self._cb)
                self.cbo_category.pack(side="left", padx=(0, 8))
            else:
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
        Cap nhat lai danh sach category hien trong bo loc sau khi widget da
        duoc tao, vi category that phai tai bat dong bo tu API.

        - CurseForge (multi_category=False): categories la
          [{"id": 421, "name": "Adventure and RPG"}, ...] - fill vao combobox
          chon 1 (giong het cach cu, khong doi hanh vi CurseForge).
        - Modrinth (multi_category=True): categories la
          [{"name": "adventure", "header": "categories"}, ...] - fill vao
          popup chon-nhieu (_CategoryMultiSelect), giu nguyen cac muc dang
          duoc tick neu van con trong danh sach moi.
        """
        if not self.cbo_category:
            return
        if self._multi_category:
            self.cbo_category.set_items(categories)
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
        'category' co the la:
          - "" khi khong loc theo category
          - chuoi ten hoac id so, neu multi_category=False (CurseForge/
            Modrinth cu, chi chon 1 gia tri)
          - list[str] cac slug da tick, neu multi_category=True (Modrinth,
            cho phep chon nhieu the loai cung luc)
        """
        ver_raw = self.cbo_mc.get().strip()
        ver     = "" if ver_raw in ("Tất cả", "") else ver_raw
        loader = self.cbo_loader.get() if self.cbo_loader else "Tất cả"
        if not self.cbo_category:
            category = ""
        elif self._multi_category:
            category = self.cbo_category.get_selected()  # list[str], co the rong
        else:
            cat_ten = self.cbo_category.get()
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
            if self._multi_category:
                self.cbo_category.reset()
            else:
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

    ROW_H = 118  # chieu cao moi dong (icon + ten/tac gia + mo ta + dong tag/so lieu)

    def __init__(self, parent, source, on_select_cb, style_name="Modpack.Treeview",
                 accent_color=None, **kwargs):
        self._c = theme.colors()
        bg = kwargs.pop("bg", self._c["row_bg"])
        super().__init__(parent, bg=bg, **kwargs)
        self._source   = source
        self._cb       = on_select_cb
        self._data     = []
        self._rows     = []   # list of dict: frame, icon_label, ...
        self._selected = -1
        self._accent   = accent_color or (
            ACCENT_MODRINTH if source == "modrinth" else ACCENT_CURSEFORGE)

        # Instance ModMcWindow/ModMcFrame dung ham select cb ("_select_mr"...)
        # nay - lay ra qua __self__ de co the tu kiem tra "dang co tac vu
        # chay khong" (_dang_co_tac_vu) va tu goi huy (_huy_tac_vu) ngay tu
        # widget nay, KHONG can sua modrinthmod.py / forgemod.py.
        self._owner          = getattr(on_select_cb, "__self__", None)
        self._installing_row = None   # idx dong dang hien nut "Hủy", None = khong co
        self._poll_after_id  = None

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

        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None
        self._installing_row = None

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
        size_str = None
        updated_str = ""
        if self._source == "modrinth":
            name      = d.get("title", "")
            author    = d.get("author", "")
            downloads = d.get("downloads", 0)
            versions  = d.get("versions", [])
            mc_ver    = versions[-1] if versions else ""
            desc      = d.get("description", "")
            icon_url  = d.get("icon_url", "")

            cats   = d.get("display_categories") or d.get("categories") or []
            cats   = [str(c) for c in cats]
            loader = next((c.title() for c in cats if c.lower() in _LOADER_SLUGS), "")
            tags   = [c.title() for c in cats if c.lower() not in _LOADER_SLUGS]
            updated_str = _dinh_dang_ngay_tuong_doi(d.get("date_modified", ""))

        else:  # curseforge
            name      = d.get("name", "")
            authors   = d.get("authors", [])
            author    = authors[0].get("name", "") if authors else ""
            downloads = d.get("downloadCount", 0)
            idx_files = d.get("latestFilesIndexes", [])
            mc_ver    = idx_files[0].get("gameVersion", "") if idx_files else ""
            loader_id = idx_files[0].get("modLoader") if idx_files else None
            loader    = _CF_LOADER_MAP.get(loader_id, "")
            desc      = d.get("summary", "")
            logo      = d.get("logo") or {}
            icon_url  = logo.get("thumbnailUrl", "") or logo.get("url", "")

            tags = [c.get("name", "") for c in d.get("categories", []) if c.get("name")]
            updated_str = _dinh_dang_ngay_tuong_doi(d.get("dateModified", ""))

            latest_files = d.get("latestFiles") or []
            if latest_files:
                size_str = _dinh_dang_dung_luong(latest_files[0].get("fileLength"))

        desc_short = (desc or "").replace("\n", " ").strip()
        if len(desc_short) > 100:
            desc_short = desc_short[:97].rstrip() + "..."

        return {
            "name": name, "author": author, "downloads": int(downloads or 0),
            "mc_ver": mc_ver, "loader": loader, "desc": desc_short,
            "icon_url": icon_url, "tags": [t for t in tags if t],
            "updated": updated_str, "size": size_str,
        }

    def _make_chip(self, parent, text, bg, fg):
        return tk.Label(parent, text=text, font=("Arial", 8, "bold"),
                         bg=bg, fg=fg, padx=6, pady=1)

    def _show_hidden_tags_popup(self, event, hidden_tags):
        """
        Hien popup nho liet ke DAY DU cac the loai bi an sau chip "+N" -
        giong dung hanh vi cua CurseForge that (hover vao "Hardcore +6" tren
        mot card se xo ra dropdown liet ke ca 6 the loai con lai).
        """
        c = theme.colors()
        pop_bg  = c["bg_alt"]
        border  = c["icon_border"]
        fg      = c["fg_title"]

        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=border)
        top.geometry(f"+{event.x_root}+{event.y_root + 4}")

        outer = tk.Frame(top, bg=border)
        outer.pack()
        inner = tk.Frame(outer, bg=pop_bg)
        inner.pack(padx=1, pady=1)
        for t in hidden_tags:
            tk.Label(inner, text=t, font=("Arial", 9), bg=pop_bg, fg=fg,
                     anchor="w", padx=10, pady=3).pack(fill="x")

        def _close(_e=None):
            try: top.destroy()
            except Exception: pass
        top.bind("<FocusOut>", _close)
        top.bind("<Leave>", lambda e: top.after(150, _close))
        top.focus_force()
        top.after(4000, _close)  # tu dong dong sau 4s de tranh treo popup mai

    def _build_row(self, i, d):
        info = self._extract(d)
        name, author   = info["name"], info["author"]
        downloads      = info["downloads"]
        mc_ver, loader = info["mc_ver"], info["loader"]
        desc, icon_url = info["desc"], info["icon_url"]
        tags, updated, size = info["tags"], info["updated"], info["size"]
        c      = self._c
        accent = self._accent

        row = tk.Frame(self.inner, bg=c["row_bg"], height=self.ROW_H)
        row.pack(fill="x")
        row.pack_propagate(False)

        # --- Icon lon ben trai, choan het chieu cao dong (giong the CF) ---
        icon_holder = tk.Frame(row, bg=c["row_bg"])
        icon_holder.pack(side="left", fill="y", padx=(10, 10), pady=10)
        ph = _IconCache.placeholder(self)
        icon_lbl = tk.Label(icon_holder, bg=c["row_bg"], bd=0)
        if ph is not None:
            icon_lbl.configure(image=ph)
            icon_lbl.image = ph
        icon_lbl.pack(expand=True)

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
        text_col.pack(side="left", fill="both", expand=True, pady=(10, 8))

        # --- Dong 1: ten + tac gia (trai)  ...  nut Cai dat (phai) ---
        header_row = tk.Frame(text_col, bg=c["row_bg"])
        header_row.pack(fill="x", anchor="w")

        head_left = tk.Frame(header_row, bg=c["row_bg"])
        head_left.pack(side="left", fill="x", expand=True)

        tk.Label(head_left, text="◆", font=("Arial", 10), fg=accent,
                 bg=c["row_bg"]).pack(side="left", padx=(0, 4))
        lbl_name = tk.Label(head_left, text=name, font=("Arial", 12, "bold"),
                             fg=c["fg_title"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_name.pack(side="left")

        sub = f"  ·  của {author}" if author else ""
        lbl_author = tk.Label(head_left, text=sub, font=("Arial", 9),
                               fg=c["fg_author"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_author.pack(side="left")
        # Luon giu ten/tac gia tren MOT dong duy nhat (giong the CurseForge/
        # Modrinth that) - KHONG dung wraplength o day, vi head_left chua
        # ca 3 label (icon + ten + tac gia) tren cung mot hang ngang nen
        # wraplength tinh theo be rong ca cum se lam tk tu xuong dong tung
        # chu mot cach roi rac (vd "Fabulo/usly/Optimiz/ed"). Thay vao do,
        # ten/tac gia se duoc CAT BOT bang "..." khi khong du cho, tinh lai
        # moi khi dong duoc resize (xem _refresh_wraps).

        btn_install = tk.Button(
            header_row, text="Cài đặt", font=("Arial", 9, "bold"),
            bg=accent, fg="white", activebackground=accent, activeforeground="white",
            relief="flat", bd=0, padx=12, pady=3, cursor="hand2",
            command=lambda idx=i: self._on_btn_install_click(idx))
        btn_install.pack(side="right", padx=(8, 4))

        # --- Dong 2: mo ta ngan ---
        lbl_desc = tk.Label(text_col, text=desc, font=("Arial", 9),
                             fg=c["fg_desc"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_desc.pack(fill="x", anchor="w", pady=(3, 4))

        # --- Dong 3: tag/category (trai)  ...  so lieu tai/cap nhat/loader (phai) ---
        footer_row = tk.Frame(text_col, bg=c["row_bg"])
        footer_row.pack(fill="x", anchor="w")

        tags_box = tk.Frame(footer_row, bg=c["row_bg"])
        tags_box.pack(side="left")
        shown = tags[:_MAX_TAGS_HIEN]
        for t in shown:
            self._make_chip(tags_box, t, c.get("chip_bg", "#e1e4ea"), c["fg_tag"]
                             ).pack(side="left", padx=(0, 4))
        hidden = tags[len(shown):]
        if hidden:
            more_chip = self._make_chip(
                tags_box, f"+{len(hidden)}", c.get("chip_bg", "#e1e4ea"), c["fg_tag"])
            more_chip.configure(cursor="hand2")
            more_chip.pack(side="left")
            # Bam vao "+N" se hien popup liet ke DAY DU cac the loai con lai
            # (giong hanh vi hover-dropdown cua CurseForge that khi ban tro
            # chuot vao "Hardcore +6" tren mot the mod).
            more_chip.bind("<Button-1>", lambda e, hd=hidden: self._show_hidden_tags_popup(e, hd))

        stats_box = tk.Frame(footer_row, bg=c["row_bg"])
        stats_box.pack(side="right")

        stat_bits = [f"⬇ {_dinh_dang_so_luot(downloads)}"]
        if updated:
            stat_bits.append(updated)
        if size:
            stat_bits.append(size)
        ver_bit = mc_ver
        if loader:
            ver_bit = f"{ver_bit} · {loader}" if ver_bit else loader
        if ver_bit:
            stat_bits.append(ver_bit)

        lbl_stats = tk.Label(stats_box, text="   |   ".join(stat_bits), font=("Arial", 9),
                              fg=c["fg_stat"], bg=c["row_bg"], anchor="e")
        lbl_stats.pack(side="right")

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

        widgets = [row, icon_holder, icon_lbl, text_col, header_row, head_left,
                   lbl_name, lbl_author, lbl_desc, footer_row, tags_box, stats_box,
                   lbl_stats, sep]
        for w in widgets:
            w.bind("<Button-1>", lambda e, idx=i: self._select(idx))
            w.bind("<Double-1>", lambda e, idx=i: self._on_row_double_click(idx))
            self._bind_scroll(w)

        self._rows.append({
            "frame": row, "sep": sep, "widgets": widgets,
            "text_col": text_col, "head_left": head_left,
            "lbl_name": lbl_name, "lbl_author": lbl_author, "lbl_desc": lbl_desc,
            "name_full": name, "author_full": sub,
            "btn_install": btn_install, "accent": accent,
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
                w_full = max(text_col.winfo_width() - 4, 60)
                row["lbl_desc"].configure(wraplength=w_full)
                self._elide_name_author(row, w_full)
            except tk.TclError:
                pass  # dong da bi destroy (vd danh sach da duoc load() lai)

    def _elide_name_author(self, row, w_full):
        """Cat bot ten mod / tac gia bang '...' de LUON nam tren MOT dong
        (giong the CurseForge/Modrinth that), thay vi dung wraplength.

        Ly do KHONG dung wraplength o day: head_left chua CA BA label
        (icon ◆ + ten + tac gia) tren cung mot hang ngang (pack side="left"),
        nen wraplength tinh theo be rong ca cum head_left neu ap cho rieng
        lbl_name/lbl_author se qua hep va khien Tk tu ngat dong NGAY GIUA
        TU, chu khong ngat theo tu - gay loi hien thi vd "Fabulo/usly/
        Optimiz/ed" thay vi "Fabulously Optimized" tren mot dong.
        """
        lbl_name   = row.get("lbl_name")
        lbl_author = row.get("lbl_author")
        if lbl_name is None or lbl_author is None:
            return

        name_full   = row.get("name_full", "")
        author_full = row.get("author_full", "")

        # Bo lai wraplength=0 (khong wrap) phong khi code cu da tung set.
        lbl_name.configure(wraplength=0)
        lbl_author.configure(wraplength=0)

        # Uoc luong khong gian danh cho ca cum "◆ ten  ·  cua tac gia":
        # tru di phan icon ◆ + nut "Cai dat" da chiem o header_row.
        # Dung mot ty le "hao phong" cua w_full lam gioi han, vi header_row
        # con phai chia cho nut Cai dat ben phai (khong the do chinh xac
        # tuyet doi bang winfo_width() cua head_left ngay luc resize).
        max_w = max(int(w_full * 0.62), 80)

        font_name   = tkfont.Font(font=lbl_name["font"])
        font_author = tkfont.Font(font=lbl_author["font"])

        def _elide(text, font, budget):
            if not text:
                return text
            if font.measure(text) <= budget:
                return text
            lo, hi = 0, len(text)
            best = ""
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = text[:mid].rstrip() + "..."
                if font.measure(cand) <= budget:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best or (text[:1] + "...")

        name_w = font_name.measure(name_full)
        author_w = font_author.measure(author_full)

        if name_w + author_w <= max_w:
            lbl_name.configure(text=name_full)
            lbl_author.configure(text=author_full)
            return

        # Uu tien giu ten mod day du hon, cat tac gia truoc; neu van khong
        # vua thi cat ca ten.
        name_budget = min(name_w, int(max_w * 0.7))
        author_budget = max(max_w - name_budget, 0)

        new_author = _elide(author_full, font_author, author_budget)
        remaining = max_w - font_author.measure(new_author)
        new_name = _elide(name_full, font_name, max(remaining, 40))

        lbl_name.configure(text=new_name)
        lbl_author.configure(text=new_author)

    def _on_row_double_click(self, idx):
        """Double-click vao mot dong -> mo man chi tiet (ModDetailWindow) de
        xem mo ta/doi phien ban, KHONG cai dat ngay va KHONG dong bo voi
        trang thai nut 'Cai dat' ben phai (viec cai dat that su van chi xay
        ra khi nguoi dung bam nut 'Cai dat' trong man chi tiet do)."""
        self._select(idx, install=False, view=True)

    def _on_btn_install_click(self, idx):
        """Bam nut 'Cai dat' ben phai moi dong -> cai dat TRUC TIEP (tu
        dong tai va chon phien ban moi nhat phu hop, KHONG mo man chi tiet):
        - Neu dong nay CHUA cai -> bat dau cai (goi _select(install=True))
          va doi text nut thanh "Hủy".
        - Neu dong nay DANG cai (nut dang la "Hủy") -> goi huy tac vu
          (co hoi xac nhan, dung ham _huy_tac_vu() da co san o ModMcWindow/
          ModMcFrame, lay qua __self__ cua on_select_cb - xem __init__)."""
        if self._installing_row == idx:
            if self._owner is not None and hasattr(self._owner, "_huy_tac_vu"):
                try:
                    self._owner._huy_tac_vu()
                except Exception:
                    pass
            return

        self._select(idx, install=True)
        self._set_btn_install_state(idx, installing=True)
        self._installing_row = idx
        self._schedule_poll_busy()

    def _set_btn_install_state(self, idx, installing):
        if idx < 0 or idx >= len(self._rows):
            return
        row = self._rows[idx]
        btn = row.get("btn_install")
        if btn is None:
            return
        try:
            if installing:
                btn.configure(text="Hủy", bg="#E53935", activebackground="#E53935")
            else:
                acc = row.get("accent", self._accent)
                btn.configure(text="Cài đặt", bg=acc, activebackground=acc)
        except tk.TclError:
            pass  # nut da bi destroy (vd danh sach da duoc load() lai)

    def _schedule_poll_busy(self):
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
        self._poll_after_id = self.after(400, self._poll_busy)

    def _poll_busy(self):
        """Kiem tra xem tac vu cai dat cua dong dang 'Hủy' da xong chua
        (thanh cong / loi / bi huy deu tinh la xong) - dua vao
        owner._dang_co_tac_vu() da co san, khong can modrinthmod.py /
        forgemod.py bao lai truc tiep cho widget nay."""
        self._poll_after_id = None
        idx = self._installing_row
        if idx is None:
            return
        busy = True
        try:
            if self._owner is not None and hasattr(self._owner, "_dang_co_tac_vu"):
                busy = bool(self._owner._dang_co_tac_vu())
        except Exception:
            busy = False
        if not busy:
            self._installing_row = None
            self._set_btn_install_state(idx, installing=False)
            return
        self._schedule_poll_busy()

    def sync_installing_state(self):
        """Doi chieu lai trang thai nut Cai dat/Hủy cua dong DANG DUOC CHON
        (self._selected) voi trang thai "dang co tac vu chay" thuc te cua
        owner (ModMcWindow/ModMcFrame) - dung khi bang danh sach nay duoc
        hien lai (vd sau khi nguoi dung bam "Quay lai danh sach" tu
        ModDetailWindow, noi ma viec cai dat/huy co the da duoc bat dau/ket
        thuc TU DO chu khong phai tu nut tren dong nay).

        Goi ham nay moi khi frame chua bang nay duoc pack() tro lai (xem
        _swap_to_list() trong mod_mc.py)."""
        if self._owner is None or not hasattr(self._owner, "_dang_co_tac_vu"):
            return
        try:
            dang_ban = bool(self._owner._dang_co_tac_vu())
        except Exception:
            dang_ban = False

        if dang_ban:
            # Chi co the biet CHINH XAC dong nao dang cai neu do la dong
            # dang duoc chon (self._selected) - vi day la thiet ke 1 tac vu
            # tai 1 thoi diem cua ca ung dung (xem _dang_co_tac_vu()/
            # _huy_tac_vu() o ModMcWindow/ModMcFrame).
            if self._selected != -1 and self._installing_row != self._selected:
                if self._installing_row is not None:
                    self._set_btn_install_state(self._installing_row, installing=False)
                self._installing_row = self._selected
                self._set_btn_install_state(self._selected, installing=True)
                self._schedule_poll_busy()
        else:
            if self._installing_row is not None:
                self._set_btn_install_state(self._installing_row, installing=False)
                self._installing_row = None
            if self._poll_after_id is not None:
                try:
                    self.after_cancel(self._poll_after_id)
                except Exception:
                    pass
                self._poll_after_id = None

    def _select(self, idx, install=False, view=False):
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
        self._cb(idx, install=install, view=view)

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