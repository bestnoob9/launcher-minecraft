import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from PIL import ImageOps
import config
import theme
from components.context_menu import ThemedDropdownMenu
from components.instance_common import (
    LOADER_LETTER, LOADER_COLOR, thu_muc_instance, tim_anh_bia,
    lay_gia_tri_instance, luu_anh_bia,
)
from components.widgets import CoverPickerPanel
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False
_CARD_W = 128
_CARD_GAP = 14
_COVER_H = 128
class HomeLibraryFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._kw = ""
        self._sort_mode = "name"
        self._loader_filter = "Tất cả"
        self._img_refs = {}          
        self._card_frames = {}       
        self._card_order = []
        self._menu = ThemedDropdownMenu(self)   
        self._build_toolbar()
        self._build_grid_area()
        self.refresh()
    def _build_toolbar(self):
        c = theme.colors()
        bar = tk.Frame(self, bg=c["bg"])
        bar.pack(fill="x", padx=14, pady=(10, 6))
        self._toolbar = bar
        left = tk.Frame(bar, bg=c["bg"])
        left.pack(side="left")
        def _tool_btn(parent, text, cmd, bg="#1E88E5"):
            b = tk.Button(parent, text=text, font=("Arial", 9, "bold"),
                          bg=bg, fg="white", activebackground=bg,
                          activeforeground="white", relief="flat",
                          padx=10, pady=5, cursor="hand2", command=cmd)
            b.pack(side="left", padx=(0, 6))
            return b
        _tool_btn(left, "+ Tạo", self._tao_instance, bg="#43A047")
        _tool_btn(left, "⬇ Nhập", self._nhap_modpack, bg="#455A64")
        _tool_btn(left, "▦ Tạo nhóm", self._chua_ho_tro, bg="#37474F")
        right = tk.Frame(bar, bg=c["bg"])
        right.pack(side="right")
        self.ent_search = tk.Entry(right, font=("Arial", 9), width=20,
                                    bg=c["entry_bg"], fg=c["entry_fg"],
                                    insertbackground=c["entry_fg"],
                                    relief="solid", bd=1)
        self.ent_search.pack(side="left", padx=(0, 6), ipady=3)
        self.ent_search.insert(0, "")
        self.ent_search.bind("<KeyRelease>", self._on_search_change)
        _placeholder_hint(self.ent_search, "🔎 Tìm theo tên")
        self.cbo_sort = ttk.Combobox(
            right, values=["Tên A-Z", "Tên Z-A"],
            font=("Arial", 9), state="readonly", width=9)
        self.cbo_sort.set("Tên A-Z")
        self.cbo_sort.pack(side="left", padx=(0, 6))
        self.cbo_sort.bind("<<ComboboxSelected>>", self._on_sort_change)
        loaders = ["Tất cả", "Vanilla", "Forge", "NeoForge", "Fabric", "Quilt"]
        self.cbo_filter = ttk.Combobox(
            right, values=loaders, font=("Arial", 9),
            state="readonly", width=9)
        self.cbo_filter.set("Tất cả")
        self.cbo_filter.pack(side="left", padx=(0, 6))
        self.cbo_filter.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.btn_view_mode = tk.Button(
            right, text="▦", font=("Arial", 10, "bold"),
            bg=c["icon_bg"], fg=c["fg_title"], relief="flat",
            padx=8, pady=4, cursor="hand2", command=self._chua_ho_tro)
        self.btn_view_mode.pack(side="left")
    def _tao_instance(self):
        self.app.instance_frame.mo_cua_so_tao_instance()
    def _nhap_modpack(self):
        self.app.modal.alert(
            "Nhập modpack",
            "Hãy dùng tab '🧩 Nội dung' để cài modpack từ Modrinth/CurseForge,\n"
            "hoặc mục Import trong đó để nạp file modpack có sẵn.")
        self.app._switch_view("modpack")
    def _chua_ho_tro(self):
        self.app.modal.alert("Chưa hỗ trợ", "Tính năng này sẽ được bổ sung sau.")
    def _on_search_change(self, event=None):
        self._kw = self.ent_search.get().strip().lower()
        if self._kw == "🔎 tìm theo tên":
            self._kw = ""
        self.refresh()
    def _on_sort_change(self, event=None):
        self._sort_mode = "name_desc" if self.cbo_sort.get() == "Tên Z-A" else "name"
        self.refresh()
    def _on_filter_change(self, event=None):
        self._loader_filter = self.cbo_filter.get()
        self.refresh()
    def _build_grid_area(self):
        c = theme.colors()
        wrap = tk.Frame(self, bg=c["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._canvas = tk.Canvas(wrap, bg=c["bg"], highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=c["bg"])
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        def _on_wheel(event):
            delta = -1 if event.num == 4 else 1 if event.num == 5 else -event.delta // 120
            self._canvas.yview_scroll(delta, "units")
        self._canvas.bind_all("<MouseWheel>", _on_wheel, add="+")
        self._canvas.bind_all("<Button-4>", _on_wheel, add="+")
        self._canvas.bind_all("<Button-5>", _on_wheel, add="+")
    def _on_canvas_resize(self, event):
        self._canvas.itemconfigure(self._inner_id, width=event.width)
        self._relayout()
    def _danh_sach_loc_sap_xep(self):
        ds = list(config.current_config.get("danh_sach_instances", {}).keys())
        if self._kw:
            ds = [t for t in ds if self._kw in t.lower()]
        if self._loader_filter != "Tất cả":
            ds = [t for t in ds if lay_gia_tri_instance(t).get("loai_game") == self._loader_filter]
        ds.sort(key=lambda t: t.lower(), reverse=(self._sort_mode == "name_desc"))
        return ds
    def refresh(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._card_frames.clear()
        self._card_order.clear()
        ds = self._danh_sach_loc_sap_xep()
        c = theme.colors()
        if not ds:
            tk.Label(self._inner, text="Không tìm thấy phiên bản nào.",
                     font=("Arial", 10), bg=c["bg"], fg=c["fg_desc"]
                     ).grid(row=0, column=0, padx=20, pady=40)
            return
        for ten in ds:
            card = self._build_card(self._inner, ten)
            self._card_frames[ten] = card
            self._card_order.append(ten)
        self.update_idletasks()
        self._relayout()
        self.after_idle(self._relayout)
    def cap_nhat_cover(self, ten):
        self._img_refs.pop(ten, None)
        self.refresh()
    def _relayout(self):
        if not self._card_order:
            return
        try:
            width = self._canvas.winfo_width()
        except Exception:
            return
        col_w = _CARD_W + _CARD_GAP
        cols = max(1, width // col_w)
        for i, ten in enumerate(self._card_order):
            r, col = divmod(i, cols)
            frame = self._card_frames.get(ten)
            if frame is not None:
                frame.grid_forget()
                frame.grid(row=r, column=col, padx=(0, _CARD_GAP), pady=(0, _CARD_GAP), sticky="n")
    def _load_cover_photo(self, ten, size=(_CARD_W, _COVER_H)):
        if not _PIL_OK:
            return None
        path = tim_anh_bia(ten)
        if not path:
            return None
        try:
            img = Image.open(path).convert("RGB")
            img = ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.5))
            photo = ImageTk.PhotoImage(img)
            self._img_refs[ten] = photo
            return photo
        except Exception:
            return None
    def _build_card(self, parent, ten):
        c = theme.colors()
        info = lay_gia_tri_instance(ten)
        loai_game = info.get("loai_game", "Vanilla")
        version_goc = info.get("version_goc", "")
        dang_chon = (ten == self.app.instance_frame.get_current_instance())
        border_color = "#1E88E5" if dang_chon else c["icon_border"]
        card = tk.Frame(parent, bg=c["bg_alt"], highlightthickness=2,
                         highlightbackground=border_color, width=_CARD_W)
        card.pack_propagate(False)
        card.grid_propagate(False)
        card.configure(width=_CARD_W, height=_COVER_H + 42)
        cover_holder = tk.Frame(card, bg=c["bg_alt"], width=_CARD_W, height=_COVER_H)
        cover_holder.pack(fill="x")
        cover_holder.pack_propagate(False)
        photo = self._load_cover_photo(ten)
        if photo is not None:
            lbl_cover = tk.Label(cover_holder, image=photo, bd=0)
        else:
            mau_nen = LOADER_COLOR.get(loai_game, "#546E7A")
            lbl_cover = tk.Label(cover_holder, text=(ten[:1] or "?").upper(),
                                  font=("Arial", 26, "bold"), bg=mau_nen, fg="white")
        lbl_cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        badge_text = f"{LOADER_LETTER.get(loai_game, '?')} {version_goc}".strip()
        lbl_badge = tk.Label(cover_holder, text=badge_text,
                              font=("Arial", 8, "bold"),
                              bg="#111111", fg="#F2F2F2",
                              padx=5, pady=1, bd=0)
        lbl_badge.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)
        lbl_badge._bo_qua_theme = True
        text_holder = tk.Frame(card, bg=c["bg_alt"])
        text_holder.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        lbl_name = tk.Label(
            text_holder, text=ten, font=("Arial", 9, "bold"),
            bg=c["bg_alt"], fg=c["fg_title"], anchor="w", justify="left",
            wraplength=_CARD_W - 16)
        lbl_name.pack(fill="x", anchor="w")
        widgets_to_bind = [card, cover_holder, lbl_cover, lbl_badge, text_holder, lbl_name]
        def _on_enter(e):
            card.configure(bg=c["icon_bg"])
            text_holder.configure(bg=c["icon_bg"])
            lbl_name.configure(bg=c["icon_bg"])
        def _on_leave(e):
            card.configure(bg=c["bg_alt"])
            text_holder.configure(bg=c["bg_alt"])
            lbl_name.configure(bg=c["bg_alt"])
        def _on_click(e):
            self.app.open_instance_detail(ten)
        def _on_right_click(e):
            self._show_context_menu(e, ten)
        for w in widgets_to_bind:
            w.configure(cursor="hand2") if hasattr(w, "configure") else None
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)
            w.bind("<Button-1>", _on_click)
            w.bind("<Button-3>", _on_right_click)
        return card
    def _show_context_menu(self, event, ten):
        items = [
            ("▶ Chơi", lambda: self._choi(ten), False),
            ("📂 Mở thư mục", lambda: self._mo_thu_muc(ten), False),
            ("🛠 Sửa loader", lambda: self.app.instance_frame.sua_instance_theo_ten(ten), False),
            ("🖼 Đổi ảnh bìa", lambda: self._doi_anh_bia(ten), False),
            ("🗑 Xóa", lambda: self._xoa(ten), True),
        ]
        self._menu.open_at(items, event.x_root, event.y_root)
    def _choi(self, ten):
        self.app.instance_frame.selector.set(ten)
        self.app.instance_frame._khi_chon_selector(ten)
        self.app.bat_dau_hoac_tat_game()
    def _mo_thu_muc(self, ten):
        folder = thu_muc_instance(ten)
        if not os.path.exists(folder):
            self.app.modal.alert("Chú ý", "Thư mục instance chưa tồn tại.")
            return
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    def _xoa(self, ten):
        self.app.instance_frame.xoa_instance_theo_ten(ten)
    def _doi_anh_bia(self, ten):
        modal = getattr(self.app, "modal", None)
        if modal is None:
            return
        modal.open(lambda parent, close: self._build_panel_doi_anh_bia(parent, close, ten), width=460)
    def _build_panel_doi_anh_bia(self, parent, close, ten):
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
        anh_hien_tai = tim_anh_bia(ten)
        picker = CoverPickerPanel(content, duong_dan_ban_dau=anh_hien_tai)
        picker.pack(fill="x")
        def _luu():
            duong_dan = picker.get_duong_dan()
            if not duong_dan:
                self.app.modal.alert("Chú ý", "Vui lòng chọn 1 ảnh bìa trước khi lưu.")
                return
            ok = luu_anh_bia(ten, duong_dan)
            if not ok:
                self.app.modal.alert("Lỗi", "Không thể lưu ảnh bìa đã chọn.")
                return
            close()
            self.cap_nhat_cover(ten)
        btn_bar = tk.Frame(content, bg=colors["bg_alt"])
        btn_bar.pack(fill="x", pady=(14, 0))
        tk.Button(btn_bar, text="Hủy", font=("Arial", 10), bg=colors["bg"],
                  fg=colors["fg_title"], relief="flat", padx=14, pady=6,
                  cursor="hand2", command=close).pack(side="right", padx=(8, 0))
        tk.Button(btn_bar, text="✔ Lưu ảnh bìa", font=("Arial", 10, "bold"),
                  bg="#1E88E5", fg="white", relief="flat", padx=14, pady=6,
                  cursor="hand2", command=_luu).pack(side="right")
def _placeholder_hint(entry, text):
    c = theme.colors()
    entry.insert(0, text)
    entry.configure(fg=c["fg_desc"])
    def _on_focus_in(e):
        if entry.get() == text:
            entry.delete(0, "end")
            entry.configure(fg=c["fg_title"])
    def _on_focus_out(e):
        if not entry.get().strip():
            entry.insert(0, text)
            entry.configure(fg=c["fg_desc"])
    entry.bind("<FocusIn>", _on_focus_in)
    entry.bind("<FocusOut>", _on_focus_out)