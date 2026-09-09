import collections
import io
import queue
import threading
import time
import urllib.request
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from tkinter import filedialog
import config
import theme
from components import perf
try:
    from PIL import Image, ImageTk, ImageDraw
    _PIL_OK = True
except Exception:
    _PIL_OK = False
BG_DARK   = "#ffffff"
BG_SEL    = "#cfe3fb"
FG_TITLE  = "#1a1a1a"
ICON_SIZE = 72
ACCENT_MODRINTH   = "#00ACC1"
ACCENT_CURSEFORGE = "#00ACC1"
_LOADER_SLUGS = {"forge", "fabric", "quilt", "neoforge", "liteloader", "rift"}
_CF_LOADER_MAP = {
    1: "Forge", 2: "Cauldron", 3: "LiteLoader", 4: "Fabric",
    5: "Quilt", 6: "NeoForge",
}
def _dinh_dang_so_luot(n):
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
_COVER_SEL_BORDER = "#1E88E5"
class CoverPickerPanel(tk.Frame):
    _THUMB = 52     
    _PREVIEW = 80   
    _COLS = 6
    def __init__(self, parent, duong_dan_ban_dau=None, **kw):
        c = theme.colors()
        kw.setdefault("bg", c["bg_alt"])
        super().__init__(parent, **kw)
        self._duong_dan_chon = duong_dan_ban_dau
        self._thumb_refs = []          
        self._preview_ref = None
        self._holder_theo_duong_dan = {}   
        self._build()
    def _build(self):
        from components.instance_common import danh_sach_anh_instancefree
        c = theme.colors()
        tk.Label(self, text="Ảnh bìa (không bắt buộc):", font=("Arial", 10, "bold"),
                 bg=c["bg_alt"], fg=c["fg_title"], anchor="w").pack(fill="x", pady=(4, 4))
        ds_anh = danh_sach_anh_instancefree()
        if ds_anh:
            grid_holder = tk.Frame(self, bg=c["bg_alt"])
            grid_holder.pack(fill="x")
            for idx, duong_dan in enumerate(ds_anh):
                r, col = divmod(idx, self._COLS)
                holder = tk.Frame(grid_holder, bg=c["icon_bg"],
                                   width=self._THUMB + 8, height=self._THUMB + 8,
                                   highlightthickness=2, highlightbackground=c["icon_bg"])
                holder.grid(row=r, column=col, padx=3, pady=3)
                holder.grid_propagate(False)
                lbl = tk.Label(holder, bg=c["icon_bg"], cursor="hand2")
                photo = self._doc_anh(duong_dan, self._THUMB)
                if photo is not None:
                    lbl.configure(image=photo)
                    self._thumb_refs.append(photo)
                else:
                    lbl.configure(text="?", font=("Arial", 10, "bold"), fg=c["fg_title"])
                lbl.place(relx=0.5, rely=0.5, anchor="center")
                holder.bind("<Button-1>", lambda e, p=duong_dan: self._chon(p))
                lbl.bind("<Button-1>", lambda e, p=duong_dan: self._chon(p))
                self._holder_theo_duong_dan[duong_dan] = holder
        else:
            tk.Label(self, text="(Chưa có ảnh mẫu trong assets/iconinstance/instancefree/)",
                     font=("Arial", 8, "italic"), bg=c["bg_alt"], fg=c["fg_desc"],
                     anchor="w", wraplength=380, justify="left").pack(fill="x")
        row_duoi = tk.Frame(self, bg=c["bg_alt"])
        row_duoi.pack(fill="x", pady=(8, 0))
        self._preview_holder = tk.Frame(row_duoi, bg=c["icon_bg"],
                                         width=self._PREVIEW, height=self._PREVIEW)
        self._preview_holder.pack(side="left")
        self._preview_holder.pack_propagate(False)
        self._lbl_preview = tk.Label(self._preview_holder, bg=c["icon_bg"],
                                      font=("Arial", 14, "bold"), fg=c["fg_title"])
        self._lbl_preview.place(relx=0.5, rely=0.5, anchor="center")
        btns = tk.Frame(row_duoi, bg=c["bg_alt"])
        btns.pack(side="left", padx=(10, 0), fill="x", expand=True)
        tk.Button(btns, text="📁 Chọn ảnh từ máy...", font=("Arial", 9),
                  bg=c["icon_bg"], fg=c["fg_title"], relief="flat", padx=8, pady=5,
                  cursor="hand2", command=self._chon_tu_may).pack(side="left")
        tk.Button(btns, text="✕ Bỏ chọn", font=("Arial", 9),
                  bg=c["icon_bg"], fg=c["fg_desc"], relief="flat", padx=8, pady=5,
                  cursor="hand2", command=self._bo_chon).pack(side="left", padx=(6, 0))
        self._cap_nhat_highlight()
        self._cap_nhat_preview()
    def _doc_anh(self, duong_dan, size):
        if not _PIL_OK:
            return None
        try:
            img = Image.open(duong_dan).convert("RGBA").resize((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None
    def _chon(self, duong_dan):
        self._duong_dan_chon = duong_dan
        self._cap_nhat_highlight()
        self._cap_nhat_preview()
    def _chon_tu_may(self):
        duong_dan = filedialog.askopenfilename(
            title="Chọn ảnh bìa",
            filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp *.gif"),
                       ("Tất cả file", "*.*")])
        if duong_dan:
            self._duong_dan_chon = duong_dan
            self._cap_nhat_highlight()
            self._cap_nhat_preview()
    def _bo_chon(self):
        self._duong_dan_chon = None
        self._cap_nhat_highlight()
        self._cap_nhat_preview()
    def _cap_nhat_highlight(self):
        c = theme.colors()
        for duong_dan, holder in self._holder_theo_duong_dan.items():
            try:
                dang_chon = (duong_dan == self._duong_dan_chon)
                holder.configure(highlightbackground=(_COVER_SEL_BORDER if dang_chon else c["icon_bg"]))
            except Exception:
                pass
    def _cap_nhat_preview(self):
        if self._duong_dan_chon:
            photo = self._doc_anh(self._duong_dan_chon, self._PREVIEW)
            if photo is not None:
                self._preview_ref = photo
                self._lbl_preview.configure(image=photo, text="")
                return
        self._preview_ref = None
        self._lbl_preview.configure(image="", text="Aa")
    def get_duong_dan(self):
        return self._duong_dan_chon
class _CategoryMultiSelect(tk.Frame):
    def __init__(self, parent, bg, on_change):
        super().__init__(parent, bg=bg)
        self._on_change = on_change
        self._items = []
        self._checked = set()
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
    _ver_cache   = []
    _cache_ready = False
    _cache_busy  = False
    @classmethod
    def _load_versions_async(cls, on_done=None):
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
    def __init__(self, parent, on_filter_callback, accent_color="#00ACC1",
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
        self._rebuild_ver_list()
        FilterBar._load_versions_async(on_done=lambda: self.after(0, self._rebuild_ver_list))
    def _rebuild_ver_list(self):
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
        if not self.cbo_category:
            return
        if self._multi_category:
            self.cbo_category.set_items(categories)
            return
        names = ["Tất cả"] + [c["name"] for c in categories]
        self._category_id_map = {c["name"]: c["id"] for c in categories}
        cur = self.cbo_category.get()
        self.cbo_category.configure(values=names)
        self.cbo_category.set(cur if cur in names else "Tất cả")
    def get(self):
        ver_raw = self.cbo_mc.get().strip()
        ver     = "" if ver_raw in ("Tất cả", "") else ver_raw
        loader = self.cbo_loader.get() if self.cbo_loader else "Tất cả"
        if not self.cbo_category:
            category = ""
        elif self._multi_category:
            category = self.cbo_category.get_selected()
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
    _cache = collections.OrderedDict()
    _cache_lock = threading.Lock()
    _pending = {}
    _pending_lock = threading.Lock()
    _queue = queue.Queue()
    _workers_started = False
    _workers_lock = threading.Lock()
    @classmethod
    def _tran_cache(cls):
        return 64 if perf.get_perf()["profile"] == "weak" else 110
    @classmethod
    def _ensure_workers(cls):
        if cls._workers_started:
            return
        with cls._workers_lock:
            if cls._workers_started:
                return
            so_worker = perf.get_perf().get("tai_icon", 3)
            for _ in range(so_worker):
                threading.Thread(target=cls._worker_loop, daemon=True).start()
            cls._workers_started = True
    @classmethod
    def _worker_loop(cls):
        while True:
            url = cls._queue.get()
            try:
                if perf.dang_choi():
                    with cls._pending_lock:
                        cls._pending.pop(url, None)
                    continue
                cls._download(url)
            finally:
                cls._queue.task_done()
    @classmethod
    def _download(cls, url):
        photo = None
        for lan_thu in range(3):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "MinecraftLauncher/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read()
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
                img = img.resize((ICON_SIZE, ICON_SIZE), Image.BILINEAR)
                photo = ImageTk.PhotoImage(img)
                cls._store(url, photo)
                break
            except Exception:
                photo = None
                if lan_thu < 2:
                    time.sleep(0.6 * (lan_thu + 1))
        with cls._pending_lock:
            waiters = cls._pending.pop(url, [])
        for w, cb in waiters:
            try:
                w.after(0, lambda cb=cb, photo=photo, w=w: cls._safe_invoke(w, cb, photo))
            except Exception:
                pass
    @classmethod
    def _safe_invoke(cls, widget, cb, photo):
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        try:
            cb(photo)
        except tk.TclError:
            pass
    @classmethod
    def _store(cls, url, photo):
        with cls._cache_lock:
            cls._cache[url] = photo
            cls._cache.move_to_end(url)
            tran = cls._tran_cache()
            while len(cls._cache) > tran:
                cls._cache.popitem(last=False)
    @classmethod
    def get(cls, widget, url, on_ready):
        if not url or not _PIL_OK:
            on_ready(None)
            return
        with cls._cache_lock:
            photo = cls._cache.get(url)
            if photo is not None:
                cls._cache.move_to_end(url)
        if photo is not None:
            on_ready(photo)
            return
        with cls._pending_lock:
            if url in cls._pending:
                cls._pending[url].append((widget, on_ready))
                return
            cls._pending[url] = [(widget, on_ready)]
        cls._ensure_workers()
        cls._queue.put(url)
    @classmethod
    def placeholder(cls, widget):
        key = "__placeholder_" + theme.get_theme_name() + "__"
        with cls._cache_lock:
            cached = cls._cache.get(key)
            if cached is not None:
                cls._cache.move_to_end(key)
        if cached is not None:
            return cached
        if not _PIL_OK:
            return None
        c = theme.colors()
        img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), c["icon_bg"])
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, ICON_SIZE - 1, ICON_SIZE - 1], outline=c["icon_border"], width=1)
        photo = ImageTk.PhotoImage(img)
        cls._store(key, photo)
        return photo
class ContentTableWidget(tk.Frame):
    ROW_H = 118
    def __init__(self, parent, source, on_select_cb, style_name="Modpack.Treeview",
                 accent_color=None, is_installed_cb=None, **kwargs):
        self._c = theme.colors()
        bg = kwargs.pop("bg", self._c["row_bg"])
        super().__init__(parent, bg=bg, **kwargs)
        self._source   = source
        self._cb       = on_select_cb
        self._data     = []
        self._rows     = []
        self._selected = -1
        self._accent   = accent_color or (
            ACCENT_MODRINTH if source == "modrinth" else ACCENT_CURSEFORGE)
        self._is_installed_cb = is_installed_cb
        self._owner          = getattr(on_select_cb, "__self__", None)
        self._installing_row = None
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
        self._current_wrap_width = None
        self._font_name   = None
        self._build_after_id = None
        self._load_gen = 0
    def _on_inner_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._schedule_visible_check()
    _WRAP_MIN_DELTA_PX = 24
    def _on_canvas_configure(self, e):
        last_w = self._pending_canvas_width
        if last_w is None:
            last_w = self._current_wrap_width
        if last_w is not None and abs(e.width - last_w) < self._WRAP_MIN_DELTA_PX:
            return
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
        if self._visible_check_id is not None:
            try:
                self.after_cancel(self._visible_check_id)
            except Exception:
                pass
        self._visible_check_id = self.after(50, self._load_visible_icons)
    def _load_visible_icons(self):
        self._visible_check_id = None
        if not self._rows:
            return
        top    = self.canvas.canvasy(0)
        bottom = top + self.canvas.winfo_height()
        buffer = self.ROW_H * 3
        for row in self._rows:
            y0 = row["y"]
            y1 = y0 + self.ROW_H
            if y1 < top - buffer or y0 > bottom + buffer:
                continue
            if not row.get("icon_loaded"):
                row["icon_loaded"] = True
                _IconCache.get(self, row["icon_url"], row["on_icon_ready"])
            if (self._current_wrap_width is not None
                    and row.get("wrap_width") != self._current_wrap_width):
                self._apply_row_wrap(row, self._current_wrap_width)
    _BUILD_CHUNK = 18
    def load(self, data_list):
        self._c         = theme.colors()
        self._data      = data_list
        self._selected  = -1
        self._load_gen += 1
        my_gen = self._load_gen
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
        if self._build_after_id is not None:
            try:
                self.after_cancel(self._build_after_id)
            except Exception:
                pass
            self._build_after_id = None
        for r in self._rows:
            try:
                r["frame"].destroy()
            except Exception:
                pass
        self._rows = []
        self.canvas.yview_moveto(0)
        self._build_rows_chunk(data_list, 0, my_gen)
    def _build_rows_chunk(self, data_list, start_idx, gen):
        if gen != self._load_gen:
            return
        end_idx = min(start_idx + self._BUILD_CHUNK, len(data_list))
        for i in range(start_idx, end_idx):
            self._build_row(i, data_list[i])
        self._schedule_visible_check()
        if end_idx < len(data_list):
            self._build_after_id = self.after(
                1, lambda: self._build_rows_chunk(data_list, end_idx, gen))
        else:
            self._build_after_id = None
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
        else:
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
    def _build_row(self, i, d):
        info = self._extract(d)
        name, author   = info["name"], info["author"]
        downloads      = info["downloads"]
        mc_ver, loader = info["mc_ver"], info["loader"]
        desc, icon_url = info["desc"], info["icon_url"]
        tags, updated, size = info["tags"], info["updated"], info["size"]
        c      = self._c
        accent = self._accent
        row = tk.Frame(self.inner, bg=c["row_bg"], height=self.ROW_H,
                        highlightthickness=1, highlightbackground=c["row_sep"],
                        highlightcolor=c["row_sep"])
        row.pack(fill="x")
        row.pack_propagate(False)
        ph = _IconCache.placeholder(self)
        icon_lbl = tk.Label(row, bg=c["row_bg"], bd=0)
        if ph is not None:
            icon_lbl.configure(image=ph)
            icon_lbl.image = ph
        icon_lbl.pack(side="left", fill="y", padx=(10, 10), pady=10)
        def _on_icon_ready(photo, lbl=icon_lbl):
            if photo is None:
                return
            try:
                lbl.configure(image=photo)
                lbl.image = photo
            except tk.TclError:
                pass
        text_col = tk.Frame(row, bg=c["row_bg"])
        text_col.pack(side="left", fill="both", expand=True, pady=(10, 8))
        header_row = tk.Frame(text_col, bg=c["row_bg"])
        header_row.pack(fill="x", anchor="w")
        title_full = f"{name}  ·  của {author}" if author else name
        lbl_title = tk.Label(header_row, text=title_full, font=("Arial", 12, "bold"),
                              fg=c["fg_title"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_title.pack(side="left", fill="x", expand=True)
        installed = False
        if self._is_installed_cb:
            try:
                installed = bool(self._is_installed_cb(d))
            except Exception:
                installed = False
        btn_install = tk.Button(
            header_row, text=("Đã cài đặt" if installed else "Cài đặt"),
            font=("Arial", 9, "bold"),
            bg=("#9e9e9e" if installed else accent), fg="white",
            activebackground=("#9e9e9e" if installed else accent), activeforeground="white",
            disabledforeground="white",
            relief="flat", bd=0, padx=12, pady=3, highlightthickness=0,
            cursor=("arrow" if installed else "hand2"),
            state=(tk.DISABLED if installed else tk.NORMAL),
            command=lambda idx=i: self._on_btn_install_click(idx))
        btn_install.pack(side="right", padx=(8, 4))
        lbl_desc = tk.Label(text_col, text=desc, font=("Arial", 9),
                             fg=c["fg_desc"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_desc.pack(fill="x", anchor="w", pady=(3, 4))
        footer_bits = []
        shown_tags = tags[:3]
        if shown_tags:
            footer_bits.append(" · ".join(shown_tags))
        footer_bits.append(f"⬇ {_dinh_dang_so_luot(downloads)}")
        if updated:
            footer_bits.append(updated)
        if size:
            footer_bits.append(size)
        ver_bit = mc_ver
        if loader:
            ver_bit = f"{ver_bit} · {loader}" if ver_bit else loader
        if ver_bit:
            footer_bits.append(ver_bit)
        footer_full = "   |   ".join(footer_bits)
        lbl_footer = tk.Label(text_col, text=footer_full, font=("Arial", 9),
                               fg=c["fg_stat"], bg=c["row_bg"], anchor="w", justify="left")
        lbl_footer.pack(fill="x", anchor="w")
        text_col.bind("<Configure>", lambda e: self._schedule_wrap_refresh())
        widgets = [row, icon_lbl, text_col, header_row,
                   lbl_title, lbl_desc, lbl_footer]
        for w in widgets:
            w.bind("<Button-1>", lambda e, idx=i: self._select(idx))
            w.bind("<Double-1>", lambda e, idx=i: self._on_row_double_click(idx))
            self._bind_scroll(w)
        self._rows.append({
            "frame": row, "widgets": widgets,
            "text_col": text_col, "header_row": header_row,
            "lbl_title": lbl_title, "lbl_desc": lbl_desc, "lbl_footer": lbl_footer,
            "title_full": title_full, "footer_full": footer_full,
            "name_full": name, "author_full": author,
            "btn_install": btn_install, "accent": accent, "installed": installed,
            "icon_url": icon_url, "on_icon_ready": _on_icon_ready,
            "icon_loaded": False, "y": i * self.ROW_H,
            "wrap_width": None,
            "progress_row": None,
            "progress_widgets": None,
            "progress_shown": False,
        })
    def _schedule_wrap_refresh(self):
        if getattr(self, "_wrap_after_id", None) is not None:
            try:
                self.after_cancel(self._wrap_after_id)
            except Exception:
                pass
        self._wrap_after_id = self.after(180, self._refresh_wraps)
    def _refresh_wraps(self):
        self._wrap_after_id = None
        if self._pending_canvas_width is not None:
            try:
                self.canvas.itemconfig(self._inner_id, width=self._pending_canvas_width)
            except tk.TclError:
                pass
            self._current_wrap_width = self._pending_canvas_width
            self._pending_canvas_width = None
            try:
                self.update_idletasks()
            except tk.TclError:
                pass
        if self._current_wrap_width is None:
            return
        self._load_visible_icons()
    def _get_font_name(self):
        if self._font_name is None:
            self._font_name = tkfont.Font(font=("Arial", 12, "bold"))
        return self._font_name
    def _apply_row_wrap(self, row, canvas_width):
        text_col = row.get("text_col")
        if text_col is None:
            return
        try:
            w_full = max(text_col.winfo_width() - 4, 60)
            row["lbl_desc"].configure(wraplength=w_full)
            row["lbl_footer"].configure(wraplength=w_full)
            self._elide_name_author(row, w_full)
            row["wrap_width"] = canvas_width
        except tk.TclError:
            pass
    def _elide_name_author(self, row, w_full):
        lbl_title = row.get("lbl_title")
        if lbl_title is None:
            return
        title_full = row.get("title_full", "")
        lbl_title.configure(wraplength=0)
        max_w = max(w_full - 90, 80)  
        font_title = self._get_font_name()
        if font_title.measure(title_full) <= max_w:
            lbl_title.configure(text=title_full)
            return
        lo, hi = 0, len(title_full)
        best = title_full[:1] + "..."
        while lo <= hi:
            mid = (lo + hi) // 2
            cand = title_full[:mid].rstrip() + "..."
            if font_title.measure(cand) <= max_w:
                best = cand
                lo = mid + 1
            else:
                hi = mid - 1
        lbl_title.configure(text=best)
    def _on_row_double_click(self, idx):
        self._select(idx, install=False, view=True)
    def _on_btn_install_click(self, idx):
        if idx < 0 or idx >= len(self._rows):
            return
        if self._rows[idx].get("installed"):
            return
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
        self._show_row_progress(idx, True)
        self._update_row_progress(idx)
        self._schedule_poll_busy()
    def _set_btn_install_state(self, idx, installing):
        if idx < 0 or idx >= len(self._rows):
            return
        row = self._rows[idx]
        if row.get("installed") and not installing:
            return
        btn = row.get("btn_install")
        if btn is None:
            return
        try:
            if installing:
                btn.configure(text="Hủy", bg="#E53935", activebackground="#E53935",
                               state=tk.NORMAL, cursor="hand2")
            else:
                acc = row.get("accent", self._accent)
                btn.configure(text="Cài đặt", bg=acc, activebackground=acc,
                               state=tk.NORMAL, cursor="hand2")
        except tk.TclError:
            pass
    _PROGRESS_STYLE = "AppRowInstall.Horizontal.TProgressbar"
    def _build_progress_row(self, row, idx):
        text_col = row["text_col"]
        c = self._c
        accent = row.get("accent", self._accent)
        try:
            style = ttk.Style(self)
            style.configure(
                self._PROGRESS_STYLE,
                troughcolor=c.get("row_sep", c["row_bg"]),
                background=accent, bordercolor=c["row_bg"],
                lightcolor=accent, darkcolor=accent, borderwidth=0)
        except Exception:
            pass
        progress_row = tk.Frame(text_col, bg=c["row_bg"], highlightthickness=0)
        lbl_installing = tk.Label(
            progress_row, text="Đang cài đặt...", font=("Arial", 9, "bold"),
            fg=accent, bg=c["row_bg"], anchor="w", highlightthickness=0)
        lbl_installing.pack(fill="x", anchor="w", pady=(2, 1))
        lbl_installing_sub = tk.Label(
            progress_row, text="", font=("Arial", 8), fg=c["fg_desc"],
            bg=c["row_bg"], anchor="w", highlightthickness=0)
        lbl_installing_sub.pack(fill="x", anchor="w", pady=(0, 4))
        pb_bar_row = tk.Frame(progress_row, bg=c["row_bg"], highlightthickness=0)
        pb_bar_row.pack(fill="x", anchor="w")
        progress_var = tk.DoubleVar(value=0)
        pb_install = ttk.Progressbar(
            pb_bar_row, orient="horizontal", mode="determinate",
            variable=progress_var, maximum=100, style=self._PROGRESS_STYLE)
        pb_install.pack(side="left", fill="x", expand=True)
        lbl_installing_pct = tk.Label(
            pb_bar_row, text="0%", font=("Arial", 8, "bold"),
            fg=c["fg_desc"], bg=c["row_bg"], width=5, anchor="e",
            highlightthickness=0)
        lbl_installing_pct.pack(side="left", padx=(8, 0))
        new_widgets = [progress_row, lbl_installing, lbl_installing_sub,
                       pb_bar_row, lbl_installing_pct]
        for w in new_widgets:
            w.bind("<Button-1>", lambda e, i=idx: self._select(i, install=True))
            w.bind("<Double-1>", lambda e, i=idx: self._on_row_double_click(i))
            self._bind_scroll(w)
        row["widgets"].extend(new_widgets)
        row["progress_row"] = progress_row
        row["progress_widgets"] = new_widgets
        row["lbl_installing_sub"] = lbl_installing_sub
        row["progress_var"] = progress_var
        row["lbl_installing_pct"] = lbl_installing_pct
    def _destroy_progress_row(self, row):
        progress_row = row.get("progress_row")
        if progress_row is None:
            return
        stale_ids = {id(w) for w in row.get("progress_widgets", []) or []}
        row["widgets"] = [w for w in row["widgets"] if id(w) not in stale_ids]
        try:
            progress_row.destroy()
        except Exception:
            pass
        row["progress_row"] = None
        row["progress_widgets"] = None
        row["lbl_installing_sub"] = None
        row["progress_var"] = None
        row["lbl_installing_pct"] = None
    def _show_row_progress(self, idx, show):
        if idx < 0 or idx >= len(self._rows):
            return
        row = self._rows[idx]
        if row.get("progress_shown") == show:
            return
        try:
            if show:
                if row.get("progress_row") is None:
                    self._build_progress_row(row, idx)
                row["lbl_desc"].pack_forget()
                row["lbl_footer"].pack_forget()
                row["progress_row"].pack(fill="x", anchor="w")
            else:
                if row.get("progress_row") is not None:
                    row["progress_row"].pack_forget()
                    self._destroy_progress_row(row)
                row["lbl_desc"].pack(fill="x", anchor="w", pady=(3, 4))
                row["lbl_footer"].pack(fill="x", anchor="w")
            row["progress_shown"] = show
        except tk.TclError:
            pass
    def _update_row_progress(self, idx):
        if idx < 0 or idx >= len(self._rows):
            return
        row = self._rows[idx]
        if not row.get("progress_shown") or row.get("progress_row") is None:
            return
        pct = 0
        label = ""
        try:
            if self._owner is not None:
                pct_raw = getattr(self._owner, "_last_progress_pct", None)
                label = getattr(self._owner, "_last_progress_label", "") or ""
                if pct_raw is not None:
                    pct = max(0, min(100, int(pct_raw)))
        except Exception:
            pct, label = 0, ""
        try:
            row["progress_var"].set(pct)
            row["lbl_installing_pct"].configure(text=f"{pct}%")
            if label:
                row["lbl_installing_sub"].configure(text=f"Đang tải: {label}")
            else:
                ten = row.get("name_full", "")
                row["lbl_installing_sub"].configure(text=f"Đang xử lý: {ten}")
        except tk.TclError:
            pass
    def refresh_installed_states(self):
        if not self._is_installed_cb:
            return
        for i, row in enumerate(self._rows):
            if i >= len(self._data):
                continue
            d = self._data[i]
            try:
                installed = bool(self._is_installed_cb(d))
            except Exception:
                installed = False
            row["installed"] = installed
            btn = row.get("btn_install")
            if btn is None:
                continue
            try:
                if installed:
                    btn.configure(text="Đã cài đặt", bg="#9e9e9e", activebackground="#9e9e9e",
                                  state=tk.DISABLED, cursor="arrow")
                elif self._installing_row == i:
                    btn.configure(text="Hủy", bg="#E53935", activebackground="#E53935",
                                  state=tk.NORMAL, cursor="hand2")
                else:
                    acc = row.get("accent", self._accent)
                    btn.configure(text="Cài đặt", bg=acc, activebackground=acc,
                                  state=tk.NORMAL, cursor="hand2")
            except tk.TclError:
                pass
    def _schedule_poll_busy(self):
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
        self._poll_after_id = self.after(400, self._poll_busy)
    def _poll_busy(self):
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
            self._show_row_progress(idx, False)
            self.refresh_installed_states()
            return
        self._update_row_progress(idx)
        self._schedule_poll_busy()
    def sync_installing_state(self):
        if self._owner is None or not hasattr(self._owner, "_dang_co_tac_vu"):
            return
        try:
            dang_ban = bool(self._owner._dang_co_tac_vu())
        except Exception:
            dang_ban = False
        if dang_ban:
            if self._selected != -1 and self._installing_row != self._selected:
                if self._installing_row is not None:
                    self._set_btn_install_state(self._installing_row, installing=False)
                    self._show_row_progress(self._installing_row, False)
                self._installing_row = self._selected
                self._c = theme.colors()
                self._set_row_bg(self._selected, self._c["row_bg"])
                self._set_btn_install_state(self._selected, installing=True)
                self._show_row_progress(self._selected, True)
                self._update_row_progress(self._selected)
                self._schedule_poll_busy()
        else:
            if self._installing_row is not None:
                self._set_btn_install_state(self._installing_row, installing=False)
                self._show_row_progress(self._installing_row, False)
                self._installing_row = None
            if self._poll_after_id is not None:
                try:
                    self.after_cancel(self._poll_after_id)
                except Exception:
                    pass
                self._poll_after_id = None
        self.refresh_installed_states()
    def _select(self, idx, install=False, view=False):
        if idx < 0 or idx >= len(self._rows):
            return
        self._c = theme.colors()
        if self._selected != -1 and self._selected < len(self._rows):
            self._set_row_bg(self._selected, self._c["row_bg"])
        self._selected = idx
        if install:
            self._set_row_bg(idx, self._c["row_bg"])
        else:
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
def make_instance_ctl(combo, no_inst_label):
    def _get_list():
        return list(config.current_config.get("danh_sach_instances", {}).keys())
    def _get():
        try:
            v = combo.get().strip()
        except tk.TclError:
            return ""
        return "" if v == no_inst_label else v
    def _set(v):
        try:
            combo.set(v if v else no_inst_label)
        except tk.TclError:
            pass
    def _get_mc_loader():
        ten = _get()
        if not ten:
            return "", ""
        info = config.current_config.get("danh_sach_instances", {}).get(ten, {})
        return info.get("version_goc", ""), info.get("loai_game", "")
    return {"get_list": _get_list, "get": _get, "set": _set, "get_mc_loader": _get_mc_loader}