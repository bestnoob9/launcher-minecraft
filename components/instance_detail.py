import os
import re
import shutil
import threading
import concurrent.futures
import tkinter as tk
from tkinter import ttk, messagebox
import config
import theme
from components import perf
from components.instance_common import (
    LOADER_ICON, thu_muc_instance, tim_anh_bia, lay_gia_tri_instance,
    doc_meta_jar, duong_dan_icon_da_tai, duong_dan_icon_notfind,
    luu_anh_bia, phien_ban_tu_ten_file,
)
from components.install_utils import (
    doc_index_instance, upsert_meta_nhan_dien,
    lap_day_meta_hang_loat_mods, lay_trang_thai_da_cai,
    luu_muc_da_cai, cai_rsp_shader_tu_file, cai_mod_tu_file, tai_file,
)
from components.api_helpers import (
    lay_nhieu_mod_curseforge, lay_project_modrinth,
    lay_phien_ban_modrinth, lay_phien_ban_curseforge, lay_nhieu_project_modrinth,
)
from components.Mod.forgemod import _MC_TO_CF
from components.widgets import _IconCache, CoverPickerPanel
from components.context_menu import ThemedDropdownMenu
from components.mod_detail_window import ModDetailWindow
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False
ACCENT = "#FF6D00"          
ACCENT_DIM = "#8a4a1c"
_ROW_ICON_SIZE = 36
_ICON_BATCH_SIZE = 6
_COL_CHECK_PX = 34                 
_COL_ICON_PX = _ROW_ICON_SIZE + 8  
_COL_ACTIONS_PX = 90               
_COL_VERSION_CHARS = 28            
_COL_UPDATE_CHARS = 13             
_FONT_VERSION = ("Arial", 9, "bold")   
_FONT_FILENAME = ("Arial", 9)          
_FONT_UPDATE = ("Arial", 8)            
_SUB_TABS = [
    ("mods",   "Mods",           "mods",          (".jar",),  True),
    ("dp",     "Data Packs",     "datapacks",     (".zip",),  True),
    ("rp",     "Resource Packs", "resourcepacks", (".zip",),  True),
    ("sh",     "Shaders",        "shaderpacks",   (".zip",),  True),
    ("worlds", "Worlds",         "saves",         (),         False),
]
_INDEX_LOAI_THEO_TAB = {
    "mods": "mods",
    "rp":   "resourcepacks",
    "sh":   "shaderpacks",
}
_LOAI_CAI_DAT_TOI_SUB_TAB = {
    "mods":          "mods",
    "resourcepacks": "rp",
    "shaderpacks":   "sh",
}
_CACHE_KIEM_TRA_CAP_NHAT = {}
_TTL_CACHE_CAP_NHAT_GIAY = 60
def _khoa_cache_cap_nhat(ten_instance, loai_thu_muc, project_id):
    return f"{ten_instance}|{loai_thu_muc}|{project_id}"
def _phien_ban_khac_nhau(new_vid, old_vid, new_vnum, old_vnum):
    if new_vid and old_vid:
        return new_vid != old_vid
    if new_vnum and old_vnum:
        return new_vnum.lower() != old_vnum.lower()
    return False
def _lam_stem(ten_file: str) -> str:
    stem = os.path.splitext(ten_file)[0]
    return stem.lower()
def _bo_hau_to_phien_ban_tho(stem: str) -> str:
    m = re.match(r'^(.*?)-\d[\w.\-+]*$', stem)
    if m and m.group(1):
        return m.group(1)
    return stem
def _rut_gon_giua(ten: str, max_len: int = 32) -> str:
    if len(ten) <= max_len:
        return ten
    giu = max_len - 3          
    trai = (giu + 1) // 2
    phai = giu - trai
    if phai <= 0:
        return ten[:giu] + "..."
    return f"{ten[:trai]}...{ten[-phai:]}"
class _RowTooltip:
    def __init__(self, widget, text_fn):
        self._widget = widget
        self._text_fn = text_fn
        self._win = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Destroy>", self._on_leave, add="+")
    def _on_enter(self, event=None):
        self._on_leave()
        try:
            text = self._text_fn()
        except Exception:
            text = ""
        if not text:
            return
        try:
            x = self._widget.winfo_rootx()
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        except Exception:
            return
        try:
            win = tk.Toplevel(self._widget)
            win.wm_overrideredirect(True)
            try:
                win.wm_attributes("-topmost", True)
            except Exception:
                pass
            win.geometry(f"+{x}+{y}")
            tk.Label(win, text=text, font=("Arial", 8), bg="#222222", fg="white",
                     padx=6, pady=3, relief="solid", bd=1, justify="left").pack()
            self._win = win
        except Exception:
            self._win = None
    def _on_leave(self, event=None):
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
class _ToggleSwitch(tk.Canvas):
    def __init__(self, parent, value=True, on_toggle=None, bg=None):
        super().__init__(parent, width=38, height=20, highlightthickness=0,
                          bd=0, bg=bg or parent["bg"], cursor="hand2")
        self._value = value
        self._on_toggle = on_toggle
        self.bind("<Button-1>", self._flip)
        self._draw()
    def _draw(self):
        self.delete("all")
        track_color = ACCENT if self._value else "#777777"
        self.create_oval(1, 1, 19, 19, fill=track_color, outline=track_color)
        self.create_oval(19, 1, 37, 19, fill=track_color, outline=track_color)
        self.create_rectangle(10, 1, 28, 19, fill=track_color, outline=track_color)
        cx = 29 if self._value else 10
        self.create_oval(cx - 8, 2, cx + 8, 18, fill="white", outline="white")
    def _flip(self, event=None):
        self._value = not self._value
        self._draw()
        if self._on_toggle:
            self._on_toggle(self._value)
    def set(self, value):
        self._value = value
        self._draw()
class InstanceDetailFrame(tk.Frame):
    def __init__(self, parent, app, ten_instance):
        super().__init__(parent)
        self.app = app
        self.ten_instance = ten_instance
        self._current_main_tab = "content"
        self._current_sub_tab = "mods"
        self._img_refs = {}
        self._scan_seq = 0     
        self._icon_seq = 0     
        self._row_icon_cache = {}   
        self._tu_khoa_cu = ""       
        self._menu = ThemedDropdownMenu(self)   
        self._build_ui()
        self._refresh_header()
        self._highlight_sub_tab("mods")
        self._render_loading_placeholder()
        self._quet_toan_bo()
    def _build_ui(self):
        c = theme.colors()
        self.configure(bg=c["bg"])
        header = tk.Frame(self, bg=c["bg_alt"])
        header.pack(fill="x")
        self._header = header
        top = tk.Frame(header, bg=c["bg_alt"])
        top.pack(fill="x", padx=16, pady=(14, 8))
        left = tk.Frame(top, bg=c["bg_alt"])
        left.pack(side="left", fill="x", expand=True)
        btn_back = tk.Button(
            left, text="← Trang chủ", font=("Arial", 9, "bold"),
            bg=c["bg_alt"], fg=c["fg_author"], relief="flat",
            cursor="hand2", command=self.app.back_to_library)
        btn_back.pack(anchor="w", pady=(0, 6))
        info_row = tk.Frame(left, bg=c["bg_alt"])
        info_row.pack(fill="x")
        self._thumb_holder = tk.Frame(info_row, bg=c["bg_alt"], width=76, height=76)
        self._thumb_holder.pack(side="left")
        self._thumb_holder.pack_propagate(False)
        self._lbl_thumb = tk.Label(self._thumb_holder, bg=c["icon_bg"])
        self._lbl_thumb.place(relx=0, rely=0, relwidth=1, relheight=1)
        text_block = tk.Frame(info_row, bg=c["bg_alt"])
        text_block.pack(side="left", fill="x", padx=(12, 0))
        self._lbl_title = tk.Label(text_block, text=self.ten_instance,
                                    font=("Arial", 17, "bold"), bg=c["bg_alt"],
                                    fg=c["fg_title"], anchor="w")
        self._lbl_title.pack(anchor="w")
        right = tk.Frame(top, bg=c["bg_alt"])
        right.pack(side="right", anchor="n")
        self._right_actions = right   
        self.btn_play = tk.Button(
            right, text="▶ Chơi", font=("Arial", 11, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=18, pady=8, cursor="hand2", command=self._choi)
        self.btn_play.pack(side="left")
        btn_menu = tk.Button(
            right, text="▾", font=("Arial", 11, "bold"), bg=c["icon_bg"],
            fg=c["fg_title"], relief="flat", padx=8, pady=8, cursor="hand2",
            command=self._mo_menu_hanh_dong)
        btn_menu.pack(side="left", padx=(6, 0))
        self._btn_menu = btn_menu   
        self._lbl_meta = tk.Label(header, text="", font=("Arial", 10),
                                   bg=c["bg_alt"], fg=c["fg_desc"], anchor="w")
        self._lbl_meta.pack(fill="x", padx=16, pady=(0, 12))
        sep = tk.Frame(header, bg=c["row_sep"], height=1)
        sep.pack(fill="x")
        maintab_bar = tk.Frame(self, bg=c["bg"])
        maintab_bar.pack(fill="x", padx=16, pady=(8, 0))
        self._maintab_buttons = {}
        self._maintab_underlines = {}
        for key, label in (("content", "Content"), ("logs", "Logs"),
                            ("shots", "Screenshots")):
            col = tk.Frame(maintab_bar, bg=c["bg"])
            col.pack(side="left", padx=(0, 18))
            b = tk.Label(col, text=label, font=("Arial", 11, "bold"),
                         bg=c["bg"], fg=c["fg_desc"], cursor="hand2", pady=6)
            b.pack(fill="x")
            underline = tk.Frame(col, bg=c["bg"], height=2)
            underline.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=key: self._show_main_tab(k))
            self._maintab_buttons[key] = b
            self._maintab_underlines[key] = underline
        main_sep = tk.Frame(self, bg=c["row_sep"], height=1)
        main_sep.pack(fill="x", padx=0, pady=(0, 0))
        self._body = tk.Frame(self, bg=c["bg"])
        self._body.pack(fill="both", expand=True)
        self._content_tab = self._build_content_tab(self._body)
        self._logs_tab = self._build_logs_tab(self._body)
        self._shots_tab = self._build_shots_tab(self._body)
        self._show_main_tab("content")
    def _mo_menu_hanh_dong(self):
        self.update_idletasks()
        anchor = self._right_actions
        width = 190
        x = anchor.winfo_rootx() + anchor.winfo_width() - width
        y = anchor.winfo_rooty() + anchor.winfo_height()
        items = [
            ("📂 Mở thư mục", self._mo_thu_muc, False),
            ("🛠 Sửa loader",
             lambda: self.app.instance_frame.sua_instance_theo_ten(self.ten_instance), False),
            ("🖼 Đổi ảnh bìa", self._doi_anh_bia, False),
            ("🗑 Xóa", self._xoa_instance, True),
        ]
        self._menu.toggle(items, x, y, width=width, exclude_widget=self._btn_menu)
    def _mo_thu_muc(self):
        import subprocess, sys
        folder = thu_muc_instance(self.ten_instance)
        if not os.path.exists(folder):
            self.app.modal.alert("Chú ý", "Thư mục instance chưa tồn tại.")
            return
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    def _xoa_instance(self):
        self.app.instance_frame.xoa_instance_theo_ten(self.ten_instance)
    def _doi_anh_bia(self):
        modal = getattr(self.app, "modal", None)
        if modal is None:
            return
        modal.open(self._build_panel_doi_anh_bia, width=460)
    def _build_panel_doi_anh_bia(self, parent, close):
        colors = theme.colors()
        parent.configure(bg=colors["bg_alt"])
        content = tk.Frame(parent, bg=colors["bg_alt"])
        content.pack(fill="both", expand=True, padx=18, pady=16)
        bar = tk.Frame(content, bg=colors["bg_alt"])
        bar.pack(fill="x", pady=(0, 10))
        tk.Label(bar, text="🖼 Đổi ảnh bìa", font=("Arial", 12, "bold"),
                  bg=colors["bg_alt"], fg=colors["fg_title"]).pack(side="left")
        tk.Button(bar, text="✕", font=("Arial", 9, "bold"), bg=colors["bg_alt"],
                  fg=colors["fg_desc"], relief="flat", bd=0, cursor="hand2",
                  command=close).pack(side="right")
        anh_hien_tai = tim_anh_bia(self.ten_instance)
        picker = CoverPickerPanel(content, duong_dan_ban_dau=anh_hien_tai)
        picker.pack(fill="x")
        def _luu():
            duong_dan = picker.get_duong_dan()
            if not duong_dan:
                self.app.modal.alert("Chú ý", "Vui lòng chọn 1 ảnh bìa trước khi lưu.")
                return
            ok = luu_anh_bia(self.ten_instance, duong_dan)
            if not ok:
                self.app.modal.alert("Lỗi", "Không thể lưu ảnh bìa đã chọn.")
                return
            close()
            self._refresh_header()
            try:
                home_lib = getattr(self.app, "_home_library", None)
                if home_lib is not None:
                    home_lib.cap_nhat_cover(self.ten_instance)
            except Exception:
                pass
        btn_bar = tk.Frame(content, bg=colors["bg_alt"])
        btn_bar.pack(fill="x", pady=(16, 0))
        tk.Button(btn_bar, text="Hủy", font=("Arial", 10), bg=colors["bg"],
                  fg=colors["fg_title"], relief="flat", padx=14, pady=8,
                  command=close).pack(side="right", padx=(8, 0))
        tk.Button(btn_bar, text="✔ Lưu ảnh bìa", font=("Arial", 10, "bold"),
                  bg="#4CAF50", fg="white", relief="flat", padx=14, pady=8,
                  command=_luu).pack(side="right")
    def _choi(self):
        if self.app.instance_frame.get_current_instance() != self.ten_instance:
            self.app.instance_frame.selector.set(self.ten_instance)
            self.app.instance_frame._khi_chon_selector(self.ten_instance)
        self.app.bat_dau_hoac_tat_game()
    def set_instance(self, ten_instance):
        if ten_instance == self.ten_instance:
            return
        self.ten_instance = ten_instance
        self._refresh_header()
        self._quet_toan_bo()
    def _refresh_header(self):
        info = lay_gia_tri_instance(self.ten_instance)
        self._lbl_title.config(text=self.ten_instance)
        loai_game = info.get("loai_game", "Vanilla")
        version_goc = info.get("version_goc", "")
        version_mod = info.get("version_mod", "")
        loader_txt = f"{loai_game}" if loai_game == "Vanilla" else f"{loai_game} - {version_mod}"
        meta = f"🎮 {version_goc}   •   🏷 {loader_txt}"
        self._lbl_meta.config(text=meta)
        c = theme.colors()
        photo = None
        if _PIL_OK:
            path = tim_anh_bia(self.ten_instance)
            if path:
                try:
                    img = Image.open(path).convert("RGB").resize((76, 76), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self._img_refs["thumb"] = photo
                except Exception:
                    photo = None
        if photo is not None:
            self._lbl_thumb.configure(image=photo, text="")
        else:
            self._lbl_thumb.configure(
                image="", text=LOADER_ICON.get(loai_game, "🟫"), font=("Arial", 28),
                bg=c["icon_bg"], fg=c["fg_title"])
    def _show_main_tab(self, key):
        self._current_main_tab = key
        c = theme.colors()
        for k, btn in self._maintab_buttons.items():
            active = (k == key)
            btn.configure(fg=(ACCENT if active else c["fg_desc"]))
            self._maintab_underlines[k].configure(bg=(ACCENT if active else c["bg"]))
        self._content_tab.pack_forget()
        self._logs_tab.pack_forget()
        self._shots_tab.pack_forget()
        if key == "content":
            self._content_tab.pack(fill="both", expand=True)
        elif key == "logs":
            self._logs_tab.pack(fill="both", expand=True)
            self._load_logs()
        else:
            self._shots_tab.pack(fill="both", expand=True)
            self._load_screenshots()
    def _build_content_tab(self, parent):
        c = theme.colors()
        frame = tk.Frame(parent, bg=c["bg"])
        subtab_bar = tk.Frame(frame, bg=c["bg"])
        subtab_bar.pack(fill="x", padx=16, pady=(10, 0))
        self._subtab_buttons = {}
        for key, label, *_ in _SUB_TABS:
            b = tk.Label(subtab_bar, text=label, font=("Arial", 9, "bold"),
                         bg=c["bg"], fg=c["fg_desc"], cursor="hand2", padx=2)
            b.pack(side="left", padx=(0, 16))
            b.bind("<Button-1>", lambda e, k=key: self._show_sub_tab(k))
            self._subtab_buttons[key] = b
        toolbar = tk.Frame(frame, bg=c["bg"])
        toolbar.pack(fill="x", padx=16, pady=(8, 4))
        self._btn_update_all = tk.Button(
            toolbar, text="⟳ Cập nhật tất cả", font=("Arial", 9),
            bg=c["icon_bg"], fg=c["fg_title"], relief="flat", padx=8, pady=4,
            cursor="hand2", command=self._kiem_tra_cap_nhat_tat_ca)
        self._btn_update_all.pack(side="left")
        right_tools = tk.Frame(toolbar, bg=c["bg"])
        right_tools.pack(side="right")
        tk.Button(right_tools, text="+ Add Content", font=("Arial", 9, "bold"),
                  bg="#1E88E5", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2", command=lambda: self.app._switch_view("modpack")
                  ).pack(side="left", padx=(0, 6))
        self.ent_content_search = tk.Entry(right_tools, font=("Arial", 9), width=16,
                                            bg=c["entry_bg"], fg=c["entry_fg"])
        self.ent_content_search.pack(side="left", padx=(0, 6), ipady=2)
        self.ent_content_search.bind("<KeyRelease>", self._khi_go_tim)
        tk.Button(right_tools, text="⟳", font=("Arial", 9, "bold"),
                  bg=c["icon_bg"], fg=c["fg_title"], relief="flat", padx=6,
                  cursor="hand2", command=lambda: self._quet_toan_bo()
                  ).pack(side="left")
        table_wrap = tk.Frame(frame, bg=c["bg"])
        table_wrap.pack(fill="both", expand=True, padx=16, pady=(4, 10))
        head = tk.Frame(table_wrap, bg=c["bg_alt"])
        head.pack(fill="x")
        tk.Frame(head, width=_COL_ACTIONS_PX, height=1, bg=c["bg_alt"]
                  ).pack(side="right")
        tk.Label(head, text="Cập nhật", font=_FONT_UPDATE, bg=c["bg_alt"],
                  fg=c["fg_desc"], anchor="w", width=_COL_UPDATE_CHARS
                  ).pack(side="right", padx=4, pady=6)
        tk.Label(head, text="Phiên bản", font=_FONT_VERSION, bg=c["bg_alt"],
                  fg=c["fg_desc"], anchor="w", width=_COL_VERSION_CHARS
                  ).pack(side="right", padx=4, pady=6)
        tk.Frame(head, width=_COL_CHECK_PX, height=1, bg=c["bg_alt"]
                  ).pack(side="left")
        tk.Frame(head, width=_COL_ICON_PX, height=1, bg=c["bg_alt"]
                  ).pack(side="left")
        tk.Label(head, text="Tiện ích bổ sung", font=("Arial", 9, "bold"),
                  bg=c["bg_alt"], fg=c["fg_desc"], anchor="w"
                  ).pack(side="left", fill="x", expand=True, padx=4, pady=6)
        self._table_canvas = tk.Canvas(table_wrap, bg=c["row_bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self._table_canvas.yview)
        self._table_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._table_canvas.pack(side="left", fill="both", expand=True)
        self._table_inner = tk.Frame(self._table_canvas, bg=c["row_bg"])
        self._table_inner_id = self._table_canvas.create_window((0, 0), window=self._table_inner, anchor="nw")
        self._table_inner.bind("<Configure>", lambda e: self._table_canvas.configure(
            scrollregion=self._table_canvas.bbox("all")))
        self._table_canvas.bind("<Configure>", lambda e: self._table_canvas.itemconfigure(
            self._table_inner_id, width=e.width))
        def _on_wheel(event):
            canvas = self._table_canvas
            self.update_idletasks()
            inner_h = self._table_inner.winfo_height()
            canvas_h = canvas.winfo_height()
            if inner_h <= canvas_h:
                canvas.yview_moveto(0)
                return "break"
            delta = -1 if getattr(event, "num", None) == 4 else \
                    1 if getattr(event, "num", None) == 5 else -event.delta // 120
            canvas.yview_scroll(delta, "units")
            if canvas.yview()[0] < 0:
                canvas.yview_moveto(0)
            return "break"
        self._on_wheel_ban = _on_wheel
        self._table_canvas.bind("<MouseWheel>", _on_wheel)
        self._table_canvas.bind("<Button-4>", _on_wheel)
        self._table_canvas.bind("<Button-5>", _on_wheel)
        self._scan_cache = {}   
        self._row_widgets = {}  
        self._dang_cap_nhat_don = set()  
        return frame
    def _khi_go_tim(self, event=None):
        if event is not None and event.keysym in (
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Caps_Lock", "Num_Lock",
            "Scroll_Lock", "Win_L", "Win_R",
        ):
            return
        kw = self.ent_content_search.get()
        if kw == getattr(self, "_tu_khoa_cu", None):
            return
        self._tu_khoa_cu = kw
        self._render_table()
    def _bind_wheel_tree(self, widget):
        try:
            widget.bind("<MouseWheel>", self._on_wheel_ban)
            widget.bind("<Button-4>", self._on_wheel_ban)
            widget.bind("<Button-5>", self._on_wheel_ban)
        except Exception:
            pass
        try:
            con = widget.winfo_children()
        except Exception:
            con = []
        for w in con:
            self._bind_wheel_tree(w)
    def _show_sub_tab(self, key):
        self._current_sub_tab = key
        self._highlight_sub_tab(key)
        if key in self._scan_cache:
            self._render_table()
        else:
            self._render_loading_placeholder()
    def _highlight_sub_tab(self, key):
        c = theme.colors()
        for k, btn in self._subtab_buttons.items():
            btn.configure(fg=(ACCENT if k == key else c["fg_desc"]))
    def _render_loading_placeholder(self):
        for w in self._table_inner.winfo_children():
            w.destroy()
        c = theme.colors()
        tk.Label(self._table_inner, text="Đang quét...", font=("Arial", 9, "italic"),
                 bg=c["row_bg"], fg=c["fg_desc"]).pack(anchor="w", padx=8, pady=10)
    def _thu_muc_sub_tab(self, key):
        cfg = next(t for t in _SUB_TABS if t[0] == key)
        return os.path.join(thu_muc_instance(self.ten_instance), cfg[2])
    def _quet_toan_bo(self):
        self._scan_seq += 1
        seq = self._scan_seq
        ten_instance = self.ten_instance
        self._scan_cache = {}
        self._row_widgets = {}
        self._dang_cap_nhat_don = set()
        self._render_loading_placeholder()
        def _worker_mods():
            items = self._quet_thu_muc(ten_instance, "mods")
            self.after(0, lambda: self._nhan_ket_qua_mods(seq, ten_instance, items))
        threading.Thread(target=_worker_mods, daemon=True).start()
    def _nhan_ket_qua_mods(self, seq, ten_instance, items):
        if seq != self._scan_seq:
            return
        self._scan_cache["mods"] = items
        self._cap_nhat_nhan_so_luong()
        if self._current_sub_tab == "mods":
            self._render_table()
        can_lap = [it for it in items if self._thieu_meta_hien_thi(it)]
        if can_lap:
            def _worker_authors():
                self._lap_day_meta_pha_a(seq, can_lap)
                if seq != self._scan_seq:
                    return
                self.after(0, lambda: self._lap_lich_tu_dong_kiem_tra_cap_nhat(seq, "mods", items))
                if perf.get_perf()["profile"] == "weak":
                    import time
                    time.sleep(2.5)
                if seq != self._scan_seq:
                    return
                self._lap_day_meta_pha_b(seq, can_lap)
            threading.Thread(target=_worker_authors, daemon=True).start()
        else:
            self._lap_lich_tu_dong_kiem_tra_cap_nhat(seq, "mods", items)
        self._quet_cac_tab_con_lai(seq, ten_instance, ["dp", "rp", "sh", "worlds"])
    def _thieu_meta_hien_thi(self, it):
        if it.get("kind") != "file":
            return False
        path = it.get("path", "")
        duoi_hop_le = (".jar", ".jar.disabled", ".zip", ".zip.disabled")
        if not path.endswith(duoi_hop_le):
            return False
        return not self._du_meta_hien_thi(it)
    def _du_meta_hien_thi(self, it):
        filename = it.get("filename", "")
        base = filename[: -len(".disabled")] if filename.endswith(".disabled") else filename
        ten_file_khong_duoi = os.path.splitext(base)[0]
        display = it.get("display") or ""
        co_title = bool(display) and display != ten_file_khong_duoi
        co_author = it.get("author") not in (None, "", "—")
        co_version = bool(it.get("version_number"))
        return co_title and co_author and co_version
    def _dien_o_trong(self, item, ten=None, tac_gia=None, phien_ban=None,
                       nguon_dang_tin=False):
        filename = item.get("filename", "")
        base = filename[: -len(".disabled")] if filename.endswith(".disabled") else filename
        ten_file_khong_duoi = os.path.splitext(base)[0]
        thay_doi = {"title": False, "author": False, "version": False}
        display_hien = item.get("display") or ""
        co_title = bool(display_hien) and display_hien != ten_file_khong_duoi
        if not co_title and ten:
            item["display"] = ten
            thay_doi["title"] = True
        co_author = item.get("author") not in (None, "", "—")
        if not co_author and tac_gia and tac_gia != "—":
            item["author"] = tac_gia
            thay_doi["author"] = True
        co_version = bool(item.get("version_number"))
        if not co_version and phien_ban:
            item["version_number"] = phien_ban
            thay_doi["version"] = True
            if nguon_dang_tin:
                item["version_reliable"] = True
        if thay_doi["title"] or thay_doi["author"] or thay_doi["version"]:
            item["matched"] = True
        return thay_doi
    def _lam_moi_hang(self, seq, item, thay_doi):
        if seq != self._scan_seq or not thay_doi:
            return
        if not (thay_doi.get("title") or thay_doi.get("author") or thay_doi.get("version")):
            return
        widgets = self._row_widgets.get(id(item))
        if widgets is None:
            return
        try:
            if thay_doi.get("author") and widgets.get("author") is not None:
                widgets["author"].config(text=item.get("author"))
            if thay_doi.get("title") and widgets.get("name") is not None:
                widgets["name"].config(text=item.get("display"))
            if thay_doi.get("version") and widgets.get("version") is not None:
                widgets["version"].config(text=item.get("version_number"))
            if thay_doi.get("version") and widgets.get("update") is not None:
                item["_co_ban_moi"] = False
                item["_ban_moi"] = None
                self._dang_cap_nhat_don.discard(id(item))
                try:
                    widgets["update"].unbind("<Button-1>")
                except Exception:
                    pass
                if item.get("version_reliable"):
                    widgets["update"].config(text="Đã cài", fg=theme.colors()["fg_desc"],
                                              cursor="arrow")
        except Exception:
            pass
    def _lap_day_meta_pha_a(self, seq, can_lap):
        def _xu_ly_1(it):
            if seq != self._scan_seq:
                return
            if perf.dang_choi():
                return
            path = it.get("path", "")
            la_jar = path.endswith(".jar") or path.endswith(".jar.disabled")
            if la_jar:
                ten, tac_gia, phien_ban = doc_meta_jar(path)
            else:
                ten, tac_gia, phien_ban = None, None, None
            thay_doi = self._dien_o_trong(it, ten=ten, tac_gia=tac_gia,
                                           phien_ban=phien_ban, nguon_dang_tin=False)
            if not it.get("version_number"):
                pb = phien_ban_tu_ten_file(it.get("filename", ""))
                if pb:
                    td2 = self._dien_o_trong(it, phien_ban=pb, nguon_dang_tin=False)
                    thay_doi["version"] = thay_doi["version"] or td2["version"]
            if thay_doi["title"] or thay_doi["author"] or thay_doi["version"]:
                self.after(0, lambda it=it, td=thay_doi: self._lam_moi_hang(seq, it, td))
        so_luong = perf.get_perf()["doc_jar"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=so_luong) as ex:
            list(ex.map(_xu_ly_1, can_lap))
    def _lap_day_meta_pha_b(self, seq, can_lap, loai="mods"):
        con_lai = [it for it in can_lap if self._thieu_meta_hien_thi(it)]
        if not con_lai or seq != self._scan_seq:
            return
        nhom1 = [it for it in con_lai if it.get("project_id") and it.get("source") == "modrinth"]
        nhom2 = [it for it in con_lai if not it.get("project_id")]
        nhom_cf = [it for it in con_lai
                   if it.get("project_id") and it.get("source") == "curseforge"]
        ket_qua = lap_day_meta_hang_loat_mods(
            nhom1, nhom2, lambda: seq == self._scan_seq and not perf.dang_choi())
        if seq != self._scan_seq or perf.dang_choi():
            return
        if nhom_cf:
            self._lap_day_meta_cf_pha_b(seq, nhom_cf, loai=loai)
            if seq != self._scan_seq or perf.dang_choi():
                return
        for kq in ket_qua:
            it = kq["item"]
            thay_doi = self._dien_o_trong(
                it, ten=kq.get("title"), tac_gia=kq.get("author"),
                phien_ban=kq.get("version_number"), nguon_dang_tin=True,
            )
            if kq.get("project_id") and not it.get("project_id"):
                it["project_id"] = kq["project_id"]
                it["source"] = kq.get("source", "modrinth")
                it["matched"] = True
            if kq.get("icon_url") and not it.get("icon_url"):
                it["icon_url"] = kq["icon_url"]
            if thay_doi["title"] or thay_doi["author"] or thay_doi["version"]:
                self.after(0, lambda it=it, td=thay_doi: self._lam_moi_hang(seq, it, td))
            pid = it.get("project_id")
            if not pid:
                continue
            filename = it.get("filename", "")
            base = filename[: -len(".disabled")] if filename.endswith(".disabled") else filename
            try:
                upsert_meta_nhan_dien(
                    self.ten_instance, loai, pid, it.get("source", "modrinth"),
                    kq.get("version_id"), it.get("version_number"), base,
                    title=(it.get("display") if thay_doi["title"] else None),
                    author=(it.get("author") if thay_doi["author"] else None),
                    icon_url=kq.get("icon_url"),
                )
            except Exception:
                pass
    def _lap_day_meta_cf_pha_b(self, seq, nhom_cf, loai="mods"):
        ids = list(dict.fromkeys(it["project_id"] for it in nhom_cf))
        theo_id = {}
        for i in range(0, len(ids), 50):
            if seq != self._scan_seq or perf.dang_choi():
                return
            lo = ids[i:i + 50]
            try:
                for m in lay_nhieu_mod_curseforge(lo):
                    mid = m.get("id")
                    if mid is not None:
                        theo_id[mid] = m
            except Exception:
                continue
        if seq != self._scan_seq or perf.dang_choi() or not theo_id:
            return
        for it in nhom_cf:
            m = theo_id.get(it.get("project_id"))
            if not m:
                continue
            authors_cf = m.get("authors") or []
            tens = [a.get("name", "") for a in authors_cf
                    if isinstance(a, dict) and a.get("name")]
            ten_tac_gia = ", ".join(tens[:2]) if tens else None
            logo = m.get("logo") or {}
            icon_url = logo.get("thumbnailUrl") or logo.get("url")
            thay_doi = self._dien_o_trong(
                it, ten=m.get("name"), tac_gia=ten_tac_gia, nguon_dang_tin=True)
            if icon_url and not it.get("icon_url"):
                it["icon_url"] = icon_url
            if thay_doi["title"] or thay_doi["author"] or thay_doi["version"]:
                self.after(0, lambda it=it, td=thay_doi: self._lam_moi_hang(seq, it, td))
            filename = it.get("filename", "")
            base = filename[: -len(".disabled")] if filename.endswith(".disabled") else filename
            try:
                upsert_meta_nhan_dien(
                    self.ten_instance, loai, it["project_id"], "curseforge",
                    None, it.get("version_number"), base,
                    title=(it.get("display") if thay_doi["title"] else None),
                    author=(it.get("author") if thay_doi["author"] else None),
                    icon_url=icon_url,
                )
            except Exception:
                pass
    def _quet_cac_tab_con_lai(self, seq, ten_instance, keys):
        def _worker():
            for key in keys:
                if seq != self._scan_seq:
                    return
                items = self._quet_thu_muc(ten_instance, key)
                if seq != self._scan_seq:
                    return
                self.after(0, lambda key=key, items=items:
                           self._nhan_ket_qua_mot_tab(seq, key, items))
        threading.Thread(target=_worker, daemon=True).start()
    def _nhan_ket_qua_mot_tab(self, seq, key, items):
        if seq != self._scan_seq:
            return
        self._scan_cache[key] = items
        self._cap_nhat_nhan_so_luong()
        if self._current_sub_tab == key:
            self._render_table()
        if key in ("rp", "sh"):
            loai = _INDEX_LOAI_THEO_TAB[key]
            can_lap = [it for it in items if self._thieu_meta_hien_thi(it)]
            if can_lap:
                def _worker_meta_zip():
                    self._lap_day_meta_pha_a(seq, can_lap)
                    if seq != self._scan_seq:
                        return
                    self.after(0, lambda: self._lap_lich_tu_dong_kiem_tra_cap_nhat(seq, key, items))
                    if perf.get_perf()["profile"] == "weak":
                        import time
                        time.sleep(2.5)
                    if seq != self._scan_seq:
                        return
                    self._lap_day_meta_pha_b(seq, can_lap, loai=loai)
                threading.Thread(target=_worker_meta_zip, daemon=True).start()
            else:
                self._lap_lich_tu_dong_kiem_tra_cap_nhat(seq, key, items)
    def nap_lai_tab(self, loai, ten_instance=None):
        key = _LOAI_CAI_DAT_TOI_SUB_TAB.get(loai)
        if key is None:
            return
        if ten_instance is not None and ten_instance != self.ten_instance:
            return
        if key not in self._scan_cache:
            return
        seq = self._scan_seq
        ten_instance_hien_tai = self.ten_instance
        def _worker():
            items = self._quet_thu_muc(ten_instance_hien_tai, key)
            if seq != self._scan_seq:
                return
            self.after(0, lambda: self._nhan_ket_qua_nap_lai_tab(seq, key, items))
        threading.Thread(target=_worker, daemon=True).start()
    def _nhan_ket_qua_nap_lai_tab(self, seq, key, items):
        if seq != self._scan_seq:
            return
        self._scan_cache[key] = items
        self._cap_nhat_nhan_so_luong()
        if self._current_sub_tab == key:
            self._render_table()
    def _quet_thu_muc(self, ten_instance, key):
        cfg = next(t for t in _SUB_TABS if t[0] == key)
        _, _, ten_folder, exts, la_file = cfg
        folder = os.path.join(thu_muc_instance(ten_instance), ten_folder)
        items = []
        if not os.path.isdir(folder):
            return items
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name.lower())
        except Exception:
            return items
        file_index_map = {}
        idx_stem_list = []
        index_loai = _INDEX_LOAI_THEO_TAB.get(key)
        if index_loai:
            idx = doc_index_instance(ten_instance)
            for pid, rec in (idx.get(index_loai) or {}).items():
                ten_file_idx = rec.get("filename")
                if ten_file_idx:
                    file_index_map[ten_file_idx] = (pid, rec)
                    idx_stem_list.append((_lam_stem(ten_file_idx), pid, rec))
        for entry in entries:
            if la_file:
                if entry.is_dir():
                    continue
                name = entry.name
                enabled = True
                base = name
                if name.endswith(".disabled"):
                    enabled = False
                    base = name[: -len(".disabled")]
                _, ext = os.path.splitext(base)
                if ext.lower() not in exts:
                    continue
                cap = file_index_map.get(base)
                if not cap and idx_stem_list:
                    local_stem = _lam_stem(base)
                    truc_tiep = [(pid, rec) for stem, pid, rec in idx_stem_list
                                 if stem == local_stem]
                    if len(truc_tiep) == 1:
                        cap = truc_tiep[0]
                    else:
                        prefix = _bo_hau_to_phien_ban_tho(local_stem)
                        if prefix != local_stem:
                            tien_to_khop = [(pid, rec) for stem, pid, rec in idx_stem_list
                                            if stem.startswith(prefix)]
                            if len(tien_to_khop) == 1:
                                cap = tien_to_khop[0]
                if cap:
                    pid, rec = cap
                    display = rec.get("title") or os.path.splitext(base)[0]
                    author = rec.get("author") or "—"
                    version_number = rec.get("version_number")
                    version_reliable = bool(version_number)
                    if not version_number:
                        version_number = phien_ban_tu_ten_file(name)
                    items.append({
                        "kind": "file", "filename": name, "display": display,
                        "path": entry.path, "enabled": enabled, "author": author,
                        "matched": True, "project_id": pid, "source": rec.get("source"),
                        "version_number": version_number,
                        "version_reliable": version_reliable,
                        "version_id": rec.get("version_id"),
                        "icon_url": rec.get("icon_url"),
                    })
                else:
                    items.append({
                        "kind": "file", "filename": name,
                        "display": os.path.splitext(base)[0],
                        "path": entry.path, "enabled": enabled, "author": "—",
                        "matched": False,
                        "version_number": phien_ban_tu_ten_file(name),
                        "version_reliable": False,
                    })
            else:
                if not entry.is_dir():
                    continue
                items.append({
                    "kind": "dir", "filename": entry.name, "display": entry.name,
                    "path": entry.path, "enabled": True, "author": "—",
                    "matched": True,
                })
        return items
    def _cap_nhat_nhan_so_luong(self):
        for key, label, *_ in _SUB_TABS:
            items = self._scan_cache.get(key)
            if items is None:
                continue
            so_luong = sum(1 for it in items if it["enabled"])
            self._subtab_buttons[key].configure(text=f"{label} ({so_luong})")
    def _kiem_tra_cap_nhat_tat_ca(self):
        key = self._current_sub_tab
        items = self._scan_cache.get(key) or []
        ung_vien = [it for it in items if it.get("kind") == "file"
                    and it.get("project_id") and it.get("source") in ("modrinth", "curseforge")]
        if not ung_vien:
            self.app.modal.alert(
                "Chú ý", "Không có mục nào (đã nhận diện nguồn Modrinth/CurseForge) "
                         "để kiểm tra cập nhật.")
            return
        seq = self._scan_seq
        loai_thu_muc = _INDEX_LOAI_THEO_TAB.get(key, "mods")
        info = lay_gia_tri_instance(self.ten_instance)
        mc_ver = info.get("version_goc", "")
        loader = info.get("loai_game", "")
        try:
            self._btn_update_all.configure(state="disabled", text="⏳ Đang kiểm tra...")
        except tk.TclError:
            pass
        def _t():
            ket_qua = self._tim_ban_cap_nhat(ung_vien, loai_thu_muc, mc_ver, loader, force=True)
            self.after(0, lambda: self._sau_khi_kiem_tra_cap_nhat(seq, key, ung_vien, ket_qua))
        threading.Thread(target=_t, daemon=True).start()
    def _tim_ban_cap_nhat(self, ung_vien, loai_thu_muc, mc_ver, loader, force=False):
        import time
        mc_l = (mc_ver or "").strip().lower()
        ld_l = (loader or "").strip().lower()
        if ld_l == "vanilla":
            ld_l = ""
        if loai_thu_muc in ("resourcepacks", "shaderpacks"):
            ld_l = ""
        cf_ver = _MC_TO_CF.get(mc_ver, mc_ver) if mc_ver else None
        ket_qua = []
        now = time.time()
        def _ap_dung_cache(it):
            khoa = _khoa_cache_cap_nhat(self.ten_instance, loai_thu_muc, it.get("project_id"))
            cache = _CACHE_KIEM_TRA_CAP_NHAT.get(khoa)
            if not cache or (now - cache["ts"]) > _TTL_CACHE_CAP_NHAT_GIAY:
                return False
            it["_co_ban_moi"] = cache["co_ban_moi"]
            it["_ban_moi"] = cache["ban_moi"]
            if cache["co_ban_moi"] is True and cache["ban_moi"] is not None:
                ket_qua.append((it, loai_thu_muc, cache["ban_moi"]["source"],
                                 cache["ban_moi"]["version_data"]))
            return True
        def _ghi_cache(it, co_ban_moi, ban_moi):
            it["_co_ban_moi"] = co_ban_moi
            it["_ban_moi"] = ban_moi
            khoa = _khoa_cache_cap_nhat(self.ten_instance, loai_thu_muc, it.get("project_id"))
            _CACHE_KIEM_TRA_CAP_NHAT[khoa] = {"ts": now, "co_ban_moi": co_ban_moi, "ban_moi": ban_moi}
        mr_items = [it for it in ung_vien if it.get("source") == "modrinth"]
        cf_items = [it for it in ung_vien if it.get("source") == "curseforge"]
        if not force:
            mr_items = [it for it in mr_items if not _ap_dung_cache(it)]
            cf_items = [it for it in cf_items if not _ap_dung_cache(it)]
        if mr_items:
            ids = list(dict.fromkeys(it["project_id"] for it in mr_items))
            try:
                projs = lay_nhieu_project_modrinth(ids)
                ton_tai = {p.get("id") for p in projs if p.get("id")}
            except Exception:
                ton_tai = set(ids)  
            for it in mr_items:
                if it["project_id"] not in ton_tai:
                    continue  
                try:
                    vs = lay_phien_ban_modrinth(it["project_id"])
                except Exception:
                    continue
                phu_hop = [
                    v for v in vs
                    if (not mc_l or mc_l in
                        [str(g).strip().lower() for g in v.get("game_versions", [])])
                    and (not ld_l or ld_l in
                         [str(l).strip().lower() for l in v.get("loaders", [])])
                ]
                if not phu_hop:
                    continue  
                moi_nhat = phu_hop[0]
                new_vid  = str(moi_nhat.get("id") or "")
                new_vnum = str(moi_nhat.get("version_number") or "").strip()
                old_vid  = str(it.get("version_id") or "")
                old_vnum = str(it.get("version_number") or "").strip()
                if _phien_ban_khac_nhau(new_vid, old_vid, new_vnum, old_vnum):
                    ban_moi = {"version_data": moi_nhat, "loai_thu_muc": loai_thu_muc,
                               "source": "modrinth"}
                    _ghi_cache(it, True, ban_moi)
                    ket_qua.append((it, loai_thu_muc, "modrinth", moi_nhat))
                else:
                    _ghi_cache(it, False, None)
        for it in cf_items:
            try:
                files = lay_phien_ban_curseforge(it["project_id"])
            except Exception:
                continue
            phu_hop = [
                f for f in files
                if (not mc_l or mc_l in [str(g).strip().lower() for g in f.get("gameVersions", [])]
                    or (cf_ver and cf_ver in f.get("gameVersions", [])))
                and (not ld_l or ld_l in
                     [str(g).strip().lower() for g in f.get("gameVersions", [])])
            ]
            if not phu_hop:
                continue
            moi_nhat = phu_hop[0]
            new_vid  = str(moi_nhat.get("id") or "")
            new_vnum = str(moi_nhat.get("displayName") or moi_nhat.get("fileName") or "").strip()
            old_vid  = str(it.get("version_id") or "")
            old_vnum = str(it.get("version_number") or "").strip()
            if _phien_ban_khac_nhau(new_vid, old_vid, new_vnum, old_vnum):
                ban_moi = {"version_data": moi_nhat, "loai_thu_muc": loai_thu_muc,
                           "source": "curseforge"}
                _ghi_cache(it, True, ban_moi)
                ket_qua.append((it, loai_thu_muc, "curseforge", moi_nhat))
            else:
                _ghi_cache(it, False, None)
        return ket_qua
    def _cap_nhat_nhan_cot(self, ung_vien):
        c = theme.colors()
        for it in ung_vien:
            w = self._row_widgets.get(id(it))
            if not w or w.get("update") is None:
                continue
            lbl = w["update"]
            try:
                lbl.unbind("<Button-1>")
            except Exception:
                pass
            trang_thai = it.get("_co_ban_moi")
            try:
                if trang_thai is True:
                    lbl.config(text="⬆ Cập nhật", fg="#FFB300", cursor="hand2")
                    lbl.bind("<Button-1>", lambda e, x=it: self._cap_nhat_mot_hang(x))
                elif trang_thai is False:
                    lbl.config(text="Đã cài", fg=c["fg_desc"], cursor="arrow")
                else:
                    lbl.config(text="—", fg=c["fg_desc"], cursor="arrow")
            except Exception:
                pass
    def _lap_lich_tu_dong_kiem_tra_cap_nhat(self, seq, key, items):
        ung_vien = [it for it in items if it.get("kind") == "file"
                    and it.get("project_id") and it.get("source") in ("modrinth", "curseforge")]
        if not ung_vien:
            return
        loai_thu_muc = _INDEX_LOAI_THEO_TAB.get(key, "mods")
        def _thu_chay():
            if seq != self._scan_seq or key != self._current_sub_tab:
                return
            if perf.dang_choi():
                self.after(1000, _thu_chay)
                return
            info = lay_gia_tri_instance(self.ten_instance)
            mc_ver = info.get("version_goc", "")
            loader = info.get("loai_game", "")
            def _t():
                self._tim_ban_cap_nhat(ung_vien, loai_thu_muc, mc_ver, loader, force=False)
                self.after(0, lambda: self._sau_khi_tu_dong_kiem_tra(seq, key, ung_vien))
            threading.Thread(target=_t, daemon=True).start()
        if perf.get_perf()["profile"] == "weak":
            self.after(2500, _thu_chay)
        else:
            self.after(0, _thu_chay)
    def _sau_khi_tu_dong_kiem_tra(self, seq, key, ung_vien):
        if seq != self._scan_seq or key != self._current_sub_tab:
            return
        self._cap_nhat_nhan_cot(ung_vien)
    def _sau_khi_kiem_tra_cap_nhat(self, seq, key, ung_vien, ket_qua):
        try:
            self._btn_update_all.configure(state="normal", text="⟳ Cập nhật tất cả")
        except tk.TclError:
            pass
        if seq != self._scan_seq or key != self._current_sub_tab:
            return  
        self._cap_nhat_nhan_cot(ung_vien)
        if not ket_qua:
            self.app.modal.alert("Cập nhật", "Tất cả đều đang ở phiên bản mới nhất.")
            return
        ten_ds = ", ".join(it.get("display", "?") for it, *_ in ket_qua[:5])
        if len(ket_qua) > 5:
            ten_ds += f" và {len(ket_qua) - 5} mục khác"
        self.app.modal.confirm(
            title="Có bản cập nhật",
            message=f"Tìm thấy {len(ket_qua)} mục có bản mới hơn:\n{ten_ds}\n\nCập nhật ngay?",
            on_confirm=lambda: self._ap_dung_cap_nhat_tat_ca(seq, list(ket_qua)),
            confirm_text="Cập nhật")
    def _ap_dung_cap_nhat_tat_ca(self, seq, danh_sach):
        if seq != self._scan_seq:
            return
        danh_sach = [d for d in danh_sach if id(d[0]) not in self._dang_cap_nhat_don]
        if not danh_sach:
            try:
                self._btn_update_all.configure(state="normal", text="⟳ Cập nhật tất cả")
            except tk.TclError:
                pass
            self.app.modal.alert("Cập nhật", "Đã cập nhật xong.")
            return
        if perf.dang_choi():
            try:
                self._btn_update_all.configure(text="⏸ Đợi thoát game để cập nhật...")
            except tk.TclError:
                pass
            self.after(1000, lambda: self._ap_dung_cap_nhat_tat_ca(seq, danh_sach))
            return
        it, loai_thu_muc, source, moi_nhat = danh_sach[0]
        con_lai = danh_sach[1:]
        cancel_event = threading.Event()
        self._dang_cap_nhat_don.add(id(it))
        try:
            self._btn_update_all.configure(
                state="disabled", text=f"⏳ Đang cập nhật {it.get('display', '')}…")
        except tk.TclError:
            pass
        w = self._row_widgets.get(id(it))
        if w and w.get("update") is not None:
            try:
                w["update"].unbind("<Button-1>")
                w["update"].config(text="⏳ Đang cập nhật…", cursor="arrow",
                                    fg=theme.colors()["fg_desc"])
            except Exception:
                pass
        def _khi_xong_1_muc():
            self._dang_cap_nhat_don.discard(id(it))
            it["_co_ban_moi"] = False
            it["_ban_moi"] = None
            w2 = self._row_widgets.get(id(it))
            if w2 and w2.get("update") is not None:
                try:
                    w2["update"].config(text="Đã cài", fg=theme.colors()["fg_desc"], cursor="arrow")
                except Exception:
                    pass
            self._ap_dung_cap_nhat_tat_ca(seq, con_lai)
        self._cai_tu_chi_tiet(it, loai_thu_muc, source, moi_nhat, cancel_event,
                               on_done=_khi_xong_1_muc)
    def _cap_nhat_mot_hang(self, item):
        ban_moi = item.get("_ban_moi")
        if not ban_moi:
            return
        if id(item) in self._dang_cap_nhat_don:
            return  
        version_data = ban_moi["version_data"]
        loai_thu_muc = ban_moi["loai_thu_muc"]
        source = ban_moi["source"]
        ten_ban_moi = (version_data.get("version_number") if source == "modrinth"
                       else (version_data.get("displayName") or version_data.get("fileName")))
        def _thuc_hien():
            if perf.dang_choi():
                self.app.modal.alert("Cập nhật",
                                      "Vui lòng tắt game đang chạy trước khi cập nhật.")
                return
            self._dang_cap_nhat_don.add(id(item))
            w = self._row_widgets.get(id(item))
            if w and w.get("update") is not None:
                try:
                    w["update"].unbind("<Button-1>")
                    w["update"].config(text="⏳ Đang cập nhật…", cursor="arrow",
                                        fg=theme.colors()["fg_desc"])
                except Exception:
                    pass
            cancel_event = threading.Event()
            vnum_truoc = item.get("version_number")
            def _khi_xong():
                self._dang_cap_nhat_don.discard(id(item))
                w2 = self._row_widgets.get(id(item))
                thanh_cong = (item.get("version_reliable")
                              and str(item.get("version_number") or "") == str(ten_ban_moi or "")
                              and item.get("version_number") != vnum_truoc)
                if thanh_cong:
                    item["_co_ban_moi"] = False
                    item["_ban_moi"] = None
                    if w2 and w2.get("update") is not None:
                        try:
                            w2["update"].config(text="Đã cài",
                                                 fg=theme.colors()["fg_desc"], cursor="arrow")
                        except Exception:
                            pass
                    if w2 and w2.get("version") is not None:
                        try:
                            w2["version"].config(text=item.get("version_number") or "Không rõ")
                        except Exception:
                            pass
                else:
                    if w2 and w2.get("update") is not None:
                        try:
                            w2["update"].config(text="⬆ Cập nhật", fg="#FFB300", cursor="hand2")
                            w2["update"].unbind("<Button-1>")
                            w2["update"].bind("<Button-1>", lambda e: self._cap_nhat_mot_hang(item))
                        except Exception:
                            pass
            self._cai_tu_chi_tiet(item, loai_thu_muc, source, version_data, cancel_event,
                                   on_done=_khi_xong)
        self.app.modal.confirm(
            title="Cập nhật",
            message=f"Cập nhật '{item.get('display', '?')}' lên {ten_ban_moi or '?'}?",
            on_confirm=_thuc_hien,
            confirm_text="Cập nhật")
    def _render_table(self):
        key = self._current_sub_tab
        items = self._scan_cache.get(key, [])
        kw = self.ent_content_search.get().strip().lower()
        if kw:
            items = [it for it in items
                     if kw in it["display"].lower()
                     or kw in it.get("filename", "").lower()]
        for w in self._table_inner.winfo_children():
            w.destroy()
        self._row_widgets = {}
        c = theme.colors()
        if not items:
            cfg = next(t for t in _SUB_TABS if t[0] == key)
            empty_holder = tk.Frame(self._table_inner, bg=c["row_bg"])
            empty_holder.pack(fill="x", pady=30)
            tk.Label(empty_holder, text=f"Chưa có {cfg[1].lower()}.", font=("Arial", 10),
                     bg=c["row_bg"], fg=c["fg_desc"]).pack()
            tk.Button(empty_holder, text="+ Add Content", font=("Arial", 9, "bold"),
                      bg="#1E88E5", fg="white", relief="flat", padx=10, pady=5,
                      cursor="hand2", command=lambda: self.app._switch_view("modpack")
                      ).pack(pady=(8, 0))
            self._lam_moi_scrollregion()
            return
        la_worlds = (key == "worlds")
        for idx, item in enumerate(items):
            self._render_row(item, idx, la_worlds, key)
        if not la_worlds:
            self._bat_dau_nap_icon(key, items)
        self._lam_moi_scrollregion()
    def _lam_moi_scrollregion(self):
        self._table_canvas.update_idletasks()
        self._table_canvas.configure(scrollregion=self._table_canvas.bbox("all"))
        self._table_canvas.yview_moveto(0)
    def _render_row(self, item, idx, la_worlds, key=None):
        c = theme.colors()
        row_bg = c["row_bg"] if idx % 2 == 0 else c["bg_alt"]
        row = tk.Frame(self._table_inner, bg=row_bg)
        row.pack(fill="x")
        btn_del = tk.Label(row, text="🗑", font=("Arial", 10), bg=row_bg,
                            fg="#E53935", cursor="hand2", padx=8)
        btn_del.pack(side="right", padx=(0, 8))
        btn_del.bind("<Button-1>", lambda e, it=item: self._xoa_item(it))
        if la_worlds:
            tk.Label(row, text="—", bg=row_bg, fg=c["fg_desc"], width=8).pack(side="right", padx=4)
        else:
            toggle = _ToggleSwitch(row, value=item["enabled"], bg=row_bg,
                                    on_toggle=lambda v, it=item: self._toggle_item(it, v))
            toggle.pack(side="right", padx=(4, 10))
        co_ban_moi = item.get("_co_ban_moi") if not la_worlds else None
        if la_worlds:
            trang_thai_cap_nhat = "—"
        elif co_ban_moi is True:
            trang_thai_cap_nhat = "⬆ Cập nhật"
        elif co_ban_moi is False:
            trang_thai_cap_nhat = "Đã cài"
        else:
            trang_thai_cap_nhat = "—"
        lbl_update = tk.Label(row, text=("" if la_worlds else trang_thai_cap_nhat),
                               font=_FONT_UPDATE, bg=row_bg,
                               fg=("#FFB300" if co_ban_moi is True else c["fg_desc"]),
                               anchor="w", width=_COL_UPDATE_CHARS,
                               cursor=("hand2" if co_ban_moi is True else "arrow"))
        lbl_update.pack(side="right", padx=4)
        if co_ban_moi is True:
            lbl_update.bind("<Button-1>", lambda e, it=item: self._cap_nhat_mot_hang(it))
        lbl_filename = None
        lbl_version = None
        if not la_worlds:
            mid_holder = tk.Frame(row, bg=row_bg)
            mid_holder.pack(side="right", padx=4)
            lbl_version = tk.Label(mid_holder, text=item.get("version_number") or "Không rõ",
                     font=_FONT_VERSION, bg=row_bg, fg=c["fg_title"],
                     anchor="w", width=_COL_VERSION_CHARS)
            lbl_version.pack(fill="x", anchor="w")
            lbl_filename = tk.Label(mid_holder, text=_rut_gon_giua(item["filename"]),
                                     font=_FONT_FILENAME, bg=row_bg, fg=c["fg_desc"],
                                     anchor="w", width=_COL_VERSION_CHARS)
            lbl_filename.pack(fill="x", anchor="w")
            _RowTooltip(lbl_filename, lambda it=item: it.get("filename", ""))
        var_check = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(row, variable=var_check, bg=row_bg,
                              activebackground=row_bg, bd=0, highlightthickness=0)
        chk.pack(side="left", padx=(8, 4), pady=6)
        lbl_icon = None
        if not la_worlds:
            icon_holder = tk.Frame(row, bg=row_bg, width=_ROW_ICON_SIZE, height=_ROW_ICON_SIZE)
            icon_holder.pack(side="left", padx=(2, 6), pady=4)
            icon_holder.pack_propagate(False)
            lbl_icon = tk.Label(icon_holder, bg=c["icon_bg"], text="",
                                 font=("Arial", 12, "bold"), fg=c["fg_title"])
            lbl_icon.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._dat_icon_fallback(lbl_icon, item, key)
        name_holder = tk.Frame(row, bg=row_bg)
        name_holder.pack(side="left", fill="x", expand=True, padx=4)
        lbl_name = tk.Label(name_holder, text=item["display"], font=("Arial", 10, "bold"),
                             bg=row_bg, fg=c["fg_title"], anchor="w")
        lbl_name.pack(fill="x", anchor="w")
        lbl_author = None
        if not la_worlds:
            lbl_author = tk.Label(name_holder, text=item.get("author", "—"), font=("Arial", 9),
                                   bg=row_bg, fg=c["fg_author"], anchor="w")
            lbl_author.pack(fill="x", anchor="w")
        self._row_widgets[id(item)] = {
            "name": lbl_name, "author": lbl_author, "icon": lbl_icon,
            "filename": lbl_filename, "version": lbl_version,
            "update": lbl_update if not la_worlds else None,
        }
        if not la_worlds and key in ("mods", "rp", "sh"):
            _dblclick = lambda e, it=item, k=key: self._mo_chi_tiet_mod(it, k)
            for w in (row, icon_holder, lbl_icon, name_holder, lbl_name,
                      lbl_author, mid_holder, lbl_version, lbl_filename):
                if w is not None:
                    w.bind("<Double-Button-1>", _dblclick)
        sep = tk.Frame(self._table_inner, bg=c["row_sep"], height=1)
        sep.pack(fill="x")
        self._bind_wheel_tree(row)
    def _mo_chi_tiet_mod(self, item, key):
        if item.get("kind") != "file":
            return
        pid = item.get("project_id")
        source = item.get("source")
        if not pid or source not in ("modrinth", "curseforge"):
            return
        loai = _INDEX_LOAI_THEO_TAB.get(key, "mods")
        def _t():
            data = None
            try:
                if source == "modrinth":
                    proj = lay_project_modrinth(pid) or {}
                    data = {
                        "title": item.get("display") or proj.get("title") or pid,
                        "author": item.get("author") or "",
                        "description": proj.get("description", ""),
                        "downloads": proj.get("downloads", 0),
                        "icon_url": item.get("icon_url") or proj.get("icon_url", ""),
                        "project_id": pid,
                        "gallery": proj.get("gallery", []),
                        "body": proj.get("body", ""),
                    }
                else:
                    mods = lay_nhieu_mod_curseforge([pid])
                    data = mods[0] if mods else None
                    if not data:
                        data = {
                            "id": pid, "name": item.get("display") or pid,
                            "authors": ([{"name": item.get("author")}]
                                        if item.get("author") else []),
                            "summary": "", "downloadCount": 0,
                            "logo": {"url": item.get("icon_url", "")},
                            "links": {}, "screenshots": [],
                        }
            except Exception:
                data = None
            if data:
                self.after(0, lambda: self._hien_cua_so_chi_tiet(item, key, loai, source, data))
        threading.Thread(target=_t, daemon=True).start()
    def _hien_cua_so_chi_tiet(self, item, key, loai, source, data):
        modal = getattr(self.app, "modal", None)
        if modal is None:
            return
        self.update_idletasks()
        try:
            root = self.winfo_toplevel()
            rw, rh = root.winfo_width(), root.winfo_height()
        except Exception:
            rw, rh = 1280, 720
        width = max(680, min(960, rw - 60))
        height = max(520, min(700, rh - 60))
        cancel_holder = {"event": None, "dang_cai": False}
        def _guard():
            if not cancel_holder["dang_cai"]:
                return True
            def _xac_nhan_huy():
                ev = cancel_holder.get("event")
                if ev:
                    ev.set()
                modal.close()
            modal.confirm(
                title="Hủy cài đặt?",
                message="Đang tải/cài đặt, bạn có chắc muốn hủy?",
                on_confirm=_xac_nhan_huy,
                confirm_text="Hủy",
                cancel_text="Không",
            )
            return False
        def _build(card, close):
            try:
                installed_info = lay_trang_thai_da_cai(
                    loai, source, item.get("project_id"), ten_instance=self.ten_instance)
            except Exception:
                installed_info = None
            def _cai_dat(version_data, on_done=None, progress_cb=None):
                ev = threading.Event()
                cancel_holder["event"] = ev
                cancel_holder["dang_cai"] = True
                def _on_done_wrap():
                    cancel_holder["dang_cai"] = False
                    if on_done:
                        on_done()
                self._cai_tu_chi_tiet(item, loai, source, version_data, ev,
                                       on_done=_on_done_wrap, progress_cb=progress_cb)
            def _huy_chi_tiet():
                ev = cancel_holder.get("event")
                if ev:
                    ev.set()
            panel = ModDetailWindow(
                card, source, data, [], install_cb=_cai_dat,
                on_back=close, cancel_cb=_huy_chi_tiet,
                accent="#1E88E5", installed_info=installed_info,
                instance_ctl=None, loai=loai,
            )
            panel.pack(fill="both", expand=True)
        modal.open(_build, width=width, height=height, close_guard=_guard)
    def _lay_lbl_status_an(self):
        lbl = getattr(self, "_lbl_status_an_cache", None)
        if lbl is None or not lbl.winfo_exists():
            lbl = tk.Label(self)
            self._lbl_status_an_cache = lbl
        return lbl
    def _cai_tu_chi_tiet(self, item, loai, source, version_data, cancel_event,
                          on_done=None, progress_cb=None):
        def _xong():
            if on_done:
                self.after(0, on_done)
        if source == "modrinth":
            files = version_data.get("files") or []
            prim = next((f for f in files if f.get("primary")),
                        files[0] if files else None)
            if not prim:
                self.after(0, lambda: messagebox.showerror(
                    "Lỗi", "Không tìm thấy file tải!", parent=self))
                _xong()
                return
            url = prim.get("url")
            fname = prim.get("filename") or "file"
            version_id = version_data.get("id")
            version_number = version_data.get("version_number")
            ngay = version_data.get("date_published")
        else:
            url = version_data.get("downloadUrl")
            fname = version_data.get("fileName") or "file"
            if not url:
                self.after(0, lambda: messagebox.showerror(
                    "Lỗi", "Không tìm thấy file tải (CurseForge)!", parent=self))
                _xong()
                return
            vid = version_data.get("id")
            version_id = str(vid) if vid is not None else None
            version_number = version_data.get("displayName") or fname
            ngay = version_data.get("fileDate")
        def _t():
            try:
                thu_muc_game = config.current_config.get("thu_muc_game", "")
                tmp = os.path.join(thu_muc_game, "_instance_detail_tmp")
                os.makedirs(tmp, exist_ok=True)
                local_path = os.path.join(tmp, fname)
                def _prog(da, tong):
                    if cancel_event.is_set():
                        raise Exception("Đã hủy")
                    if progress_cb:
                        self.after(0, lambda: progress_cb(da, tong))
                tai_file(url, local_path, _prog)
                if cancel_event.is_set():
                    raise Exception("Đã hủy")
            except Exception as e:
                msg = str(e)
                if msg != "Đã hủy":
                    self.after(0, lambda: messagebox.showerror(
                        "Lỗi", f"Tải thất bại: {msg}", parent=self))
                _xong()
                return
            lbl_an = self._lay_lbl_status_an()
            def _sau_khi_cai():
                try:
                    ten_file_moi = os.path.basename(local_path)
                    luu_muc_da_cai(
                        self.ten_instance, loai, item.get("project_id"), source,
                        version_id, version_number, ten_file_moi, ngay=ngay,
                        title=item.get("display"), author=item.get("author"),
                        icon_url=item.get("icon_url"))
                    item["filename"] = ten_file_moi
                    item["version_number"] = version_number
                    item["version_reliable"] = True
                    seq = self._scan_seq
                    self.after(0, lambda: self._lam_moi_hang(
                        seq, item, {"title": False, "author": False, "version": True}))
                except Exception:
                    pass
                _xong()
            if loai in ("resourcepacks", "shaderpacks"):
                cai_rsp_shader_tu_file(
                    local_path, self.ten_instance,
                    "rsp" if loai == "resourcepacks" else "sh",
                    lbl_an, callback_xong=_sau_khi_cai)
            else:
                cai_mod_tu_file(local_path, self.ten_instance, lbl_an,
                                 callback_xong=_sau_khi_cai)
        threading.Thread(target=_t, daemon=True).start()
    def _bat_dau_nap_icon(self, key, items):
        self._icon_seq += 1
        seq_icon = self._icon_seq
        self._nap_icon_theo_lo(seq_icon, key, list(items))
    def _nap_icon_theo_lo(self, seq_icon, key, hang_doi):
        if seq_icon != self._icon_seq or self._current_sub_tab != key:
            return
        if perf.dang_choi():
            self.after(1000, lambda: self._nap_icon_theo_lo(seq_icon, key, hang_doi))
            return
        lo, con_lai = hang_doi[:_ICON_BATCH_SIZE], hang_doi[_ICON_BATCH_SIZE:]
        for item in lo:
            self._nap_icon_1_dong(item, key)
        if con_lai:
            self.after(16, lambda: self._nap_icon_theo_lo(seq_icon, key, con_lai))
    def _nap_icon_1_dong(self, item, key):
        widgets = self._row_widgets.get(id(item))
        lbl_icon = widgets.get("icon") if widgets else None
        if lbl_icon is None:
            return
        try:
            if not lbl_icon.winfo_exists():
                return
        except Exception:
            return
        duong_dan_local = duong_dan_icon_da_tai(
            self.ten_instance, item.get("source"), item.get("project_id"))
        if duong_dan_local:
            photo = self._anh_icon_tu_file(duong_dan_local, _ROW_ICON_SIZE)
            if photo is not None:
                self._ap_dung_icon(item, photo)
                return
        icon_url = item.get("icon_url")
        if icon_url:
            def _on_ready(photo, item=item, key=key):
                if photo is None:
                    self._ap_dung_icon_fallback(item, key)
                    return
                nho = self._thu_nho_photo(photo, _ROW_ICON_SIZE)
                self._ap_dung_icon(item, nho, giu_anh_goc=photo)
            _IconCache.get(lbl_icon, icon_url, _on_ready)
            return
        self._ap_dung_icon_fallback(item, key)
    def _thu_nho_photo(self, photo, size):
        if not _PIL_OK:
            return photo
        try:
            img = ImageTk.getimage(photo).convert("RGBA").resize((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return photo
    def _anh_icon_tu_file(self, path, size):
        if not path or not _PIL_OK:
            return None
        cache_key = (path, size)
        cached = self._row_icon_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._row_icon_cache[cache_key] = photo
            return photo
        except Exception:
            return None
    def _ap_dung_icon(self, item, photo, giu_anh_goc=None):
        widgets = self._row_widgets.get(id(item))
        lbl = widgets.get("icon") if widgets else None
        if lbl is None:
            return
        try:
            if not lbl.winfo_exists():
                return
            lbl.configure(image=photo, text="")
            lbl.image = photo
            if giu_anh_goc is not None:
                lbl._icon_anh_goc_ref = giu_anh_goc
        except Exception:
            pass
    def _ap_dung_icon_fallback(self, item, key):
        widgets = self._row_widgets.get(id(item))
        lbl = widgets.get("icon") if widgets else None
        if lbl is None:
            return
        self._dat_icon_fallback(lbl, item, key)
    def _dat_icon_fallback(self, lbl, item, key):
        if lbl is None:
            return
        duong_dan = duong_dan_icon_notfind(key)
        photo = self._anh_icon_tu_file(duong_dan, _ROW_ICON_SIZE)
        try:
            if not lbl.winfo_exists():
                return
            if photo is not None:
                lbl.configure(image=photo, text="")
                lbl.image = photo
            else:
                chu = (item.get("display") or "?").strip()[:1].upper() or "?"
                lbl.configure(image="", text=chu)
        except Exception:
            pass
    def _game_dang_chay(self):
        proc = getattr(self.app, "_game_process", None)
        return proc is not None and proc.poll() is None
    def _toggle_item(self, item, muon_bat):
        if self._game_dang_chay():
            self.app.modal.alert("Chú ý", "Vui lòng tắt game trước khi bật/tắt nội dung!")
            self._show_sub_tab(self._current_sub_tab)
            return
        path = item["path"]
        base = item["path"][: -len(".disabled")] if path.endswith(".disabled") else path
        dich = base if muon_bat else base + ".disabled"
        try:
            if os.path.exists(path) and path != dich:
                os.rename(path, dich)
            item["path"] = dich
            item["enabled"] = muon_bat
            item["filename"] = os.path.basename(dich)
            self._cap_nhat_nhan_so_luong()
            widgets = self._row_widgets.get(id(item))
            lbl_filename = widgets.get("filename") if widgets else None
            if lbl_filename is not None:
                try:
                    if lbl_filename.winfo_exists():
                        lbl_filename.config(text=_rut_gon_giua(item["filename"]))
                except Exception:
                    pass
        except Exception as e:
            self.app.modal.alert("Lỗi", f"Không thể đổi trạng thái:\n{e}")
            self._show_sub_tab(self._current_sub_tab)
    def _xoa_item(self, item):
        if self._game_dang_chay():
            self.app.modal.alert("Chú ý", "Vui lòng tắt game trước khi xóa nội dung!")
            return
        def _thuc_hien():
            key = self._current_sub_tab
            try:
                if item["kind"] == "dir":
                    shutil.rmtree(item["path"])
                else:
                    os.remove(item["path"])
                items = self._scan_cache.get(key)
                if items is not None and item in items:
                    items.remove(item)
            except Exception as e:
                self.app.modal.alert("Lỗi", f"Không thể xóa:\n{e}")
            self._cap_nhat_nhan_so_luong()
            self._render_table()
        self.app.modal.confirm(
            title="Xóa nội dung",
            message=f"Bạn có chắc muốn xóa '{item['display']}'?",
            on_confirm=_thuc_hien, confirm_text="Xóa")
    def _build_logs_tab(self, parent):
        c = theme.colors()
        frame = tk.Frame(parent, bg=c["bg"])
        holder = tk.Frame(frame, bg=c["bg"])
        holder.pack(fill="both", expand=True, padx=16, pady=12)
        self._txt_logs = tk.Text(holder, font=("Consolas", 9), bg="#1e1e1e",
                                  fg="#d4d4d4", wrap="word", state="disabled",
                                  relief="flat")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self._txt_logs.yview)
        self._txt_logs.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._txt_logs.pack(side="left", fill="both", expand=True)
        return frame
    def _load_logs(self):
        folder = os.path.join(thu_muc_instance(self.ten_instance), "logs")
        path = os.path.join(folder, "latest.log")
        self._txt_logs.config(state="normal")
        self._txt_logs.delete("1.0", "end")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    noi_dung = f.read()
                self._txt_logs.insert("end", noi_dung[-200_000:])
            except Exception as e:
                self._txt_logs.insert("end", f"(Không thể đọc log: {e})")
        else:
            self._txt_logs.insert("end", "Chưa có log nào cho phiên bản này.")
        self._txt_logs.config(state="disabled")
    def _build_shots_tab(self, parent):
        c = theme.colors()
        frame = tk.Frame(parent, bg=c["bg"])
        wrap = tk.Frame(frame, bg=c["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=12)
        self._shots_canvas = tk.Canvas(wrap, bg=c["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self._shots_canvas.yview)
        self._shots_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._shots_canvas.pack(side="left", fill="both", expand=True)
        self._shots_inner = tk.Frame(self._shots_canvas, bg=c["bg"])
        self._shots_inner_id = self._shots_canvas.create_window((0, 0), window=self._shots_inner, anchor="nw")
        self._shots_inner.bind("<Configure>", lambda e: self._shots_canvas.configure(
            scrollregion=self._shots_canvas.bbox("all")))
        return frame
    def _load_screenshots(self):
        for w in self._shots_inner.winfo_children():
            w.destroy()
        c = theme.colors()
        folder = os.path.join(thu_muc_instance(self.ten_instance), "screenshots")
        if not os.path.isdir(folder):
            tk.Label(self._shots_inner, text="Chưa có ảnh chụp màn hình nào.",
                     font=("Arial", 10), bg=c["bg"], fg=c["fg_desc"]).pack(pady=30)
            return
        try:
            files = sorted(
                (f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))),
                reverse=True)
        except Exception:
            files = []
        if not files:
            tk.Label(self._shots_inner, text="Chưa có ảnh chụp màn hình nào.",
                     font=("Arial", 10), bg=c["bg"], fg=c["fg_desc"]).pack(pady=30)
            return
        col = 0
        row_frame = tk.Frame(self._shots_inner, bg=c["bg"])
        row_frame.pack(fill="x")
        for i, name in enumerate(files[:60]):
            if col == 5:
                row_frame = tk.Frame(self._shots_inner, bg=c["bg"])
                row_frame.pack(fill="x")
                col = 0
            holder = tk.Frame(row_frame, bg=c["bg_alt"], width=140, height=90)
            holder.pack(side="left", padx=4, pady=4)
            holder.pack_propagate(False)
            if _PIL_OK:
                try:
                    img = Image.open(os.path.join(folder, name)).convert("RGB")
                    img.thumbnail((140, 90))
                    photo = ImageTk.PhotoImage(img)
                    self._img_refs[f"shot_{i}"] = photo
                    tk.Label(holder, image=photo, bg=c["bg_alt"]).place(relx=0.5, rely=0.5, anchor="center")
                except Exception:
                    tk.Label(holder, text=name, bg=c["bg_alt"], fg=c["fg_desc"]).place(relx=0.5, rely=0.5, anchor="center")
            else:
                tk.Label(holder, text=name, bg=c["bg_alt"], fg=c["fg_desc"]).place(relx=0.5, rely=0.5, anchor="center")
            col += 1