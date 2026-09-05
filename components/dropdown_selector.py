"""
DropdownSelector - "combobox" tuy chinh dung chung cho khu vuc chon Tai khoan
va chon Phien ban (Instance) o sidebar.

Khac voi ttk.Combobox mac dinh:
- Danh sach hien ra la 1 popup (Toplevel khong vien) NGAY DUOI nut chon,
  cuon len/xuong duoc (Canvas + Scrollbar) khi co nhieu muc.
- Moi dong co the co: 1 o vuong trong dat truoc ten (danh cho anh rieng
  sau nay), ten muc (tu dong cat bot + "..." neu qua dai), 1 icon "✏"
  mau accent de sua (chi bat khi truyen on_edit) va 1 nut "X" mau do o
  cuoi dong de xoa nhanh (chi bat khi truyen on_delete).
- Cuoi popup luon co 1 dong GHIM CO DINH (khong cuon theo danh sach) chua
  nut hanh dong rieng, vd "+ Thêm" hoac "+ Tạo phiên bản".
"""
import tkinter as tk
from tkinter import font as tkfont
import theme

# Sidebar cua app hoa mau theo theme sang/toi hien tai cua app (xem
# theme.sidebar_colors()). Widget nay lay mau tu do thay vi hardcode,
# de khi doi theme thi combobox cung doi mau dung.
def _sb():
    return theme.sidebar_colors()


class DropdownSelector(tk.Frame):
    MAX_VISIBLE_ROWS = 6
    ROW_H = 34

    def __init__(self, parent, on_select=None, on_delete=None, on_edit=None,
                 bottom_text="+ Thêm", on_bottom_click=None,
                 show_icon_box=True, placeholder="(Trống)",
                 bg=None, fg=None, accent=None,
                 border=None, danger="#E53935",
                 hover_bg=None, popup_bg=None, **kw):
        sb = _sb()
        bg       = bg or sb["bg"]
        fg       = fg or sb["text"]
        accent   = accent or sb["accent"]
        border   = border or sb["border"]
        hover_bg = hover_bg or sb["border"]
        popup_bg = popup_bg or sb["bg_alt"]
        super().__init__(parent, bg=bg, **kw)
        self._on_select       = on_select
        self._on_delete       = on_delete
        self._on_edit         = on_edit
        self._bottom_text     = bottom_text
        self._on_bottom_click = on_bottom_click
        self._show_icon_box   = show_icon_box
        self._placeholder     = placeholder
        self._bg, self._fg    = bg, fg
        self._accent          = accent
        self._border          = border
        self._danger          = danger
        self._hover_bg        = hover_bg
        self._popup_bg        = popup_bg

        self._items   = []
        self._current = ""
        self._popup   = None
        self._enabled = True
        self._root_bind_id = None
        self._wheel_bound  = False
        self._focus_bind_id = None
        self._focus_bind_widget = None

        self._font = tkfont.Font(family="Arial", size=10)

        self.configure(highlightthickness=1, highlightbackground=border, bd=0)
        self._btn = tk.Frame(self, bg=bg, cursor="hand2")
        self._btn.pack(fill="x")

        self._lbl_value = tk.Label(
            self._btn, text=placeholder, font=("Arial", 10),
            bg=bg, fg=fg, anchor="w", padx=8, pady=6, cursor="hand2")
        self._lbl_value.pack(side="left", fill="x", expand=True)

        self._lbl_arrow = tk.Label(
            self._btn, text="▾", font=("Arial", 9), bg=bg, fg=fg,
            padx=8, cursor="hand2")
        self._lbl_arrow.pack(side="right")

        for w in (self._btn, self._lbl_value, self._lbl_arrow):
            w.bind("<Button-1>", self._toggle_popup)

    # ------------------------------------------------------------------
    def apply_sidebar_colors(self):
        """Cap nhat lai toan bo mau cua combobox theo theme.sidebar_colors()
        hien tai. Goi ham nay tu ap_dung_theme_sidebar() trong main.py moi
        khi nguoi dung doi theme sang/toi de combobox doi mau ngay, khong
        can khoi dong lai app. Popup (Toplevel) khong can sua vi no duoc
        tao lai tu dau moi lan mo, se tu dong dung mau moi."""
        sb = _sb()
        self._bg       = sb["bg"]
        self._fg       = sb["text"]
        self._accent   = sb["accent"]
        self._border   = sb["border"]
        self._hover_bg = sb["border"]
        self._popup_bg = sb["bg_alt"]

        self.configure(bg=self._bg, highlightbackground=self._border)
        self._btn.configure(bg=self._bg)
        self._lbl_value.configure(
            bg=self._bg, fg=self._fg if self._enabled else "#9aa0a6")
        self._lbl_arrow.configure(bg=self._bg, fg=self._fg)

    def set_items(self, items):
        """items: list[str]"""
        self._items = list(items)

    def set(self, value):
        self._current = value or ""
        self._refresh_label()

    def get(self):
        return self._current

    def configure_state(self, enabled: bool):
        self._enabled = enabled
        cur = "hand2" if enabled else "arrow"
        for w in (self._btn, self._lbl_value, self._lbl_arrow):
            w.configure(cursor=cur)
        self._lbl_value.configure(fg=self._fg if enabled else "#9aa0a6")
        if not enabled:
            self._close_popup()

    # ------------------------------------------------------------------
    def _truncate(self, name, max_chars=22):
        if len(name) > max_chars:
            return name[:max_chars - 3].rstrip() + "..."
        return name

    def _refresh_label(self):
        text = self._truncate(self._current) if self._current else self._placeholder
        self._lbl_value.configure(text=text)

    # ------------------------------------------------------------------ popup
    def _toggle_popup(self, event=None):
        if not self._enabled:
            return
        if self._popup is not None:
            self._close_popup()
        else:
            self._open_popup()

    def _close_popup(self, event=None):
        self._unbind_focus_close()
        if self._root_bind_id is not None:
            try:
                self.unbind_all("<Button-1>")
            except Exception:
                pass
            self._root_bind_id = None
        self._wheel_bound = False
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None

    def _open_popup(self):
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        width = max(self.winfo_width(), 180)

        pop = tk.Toplevel(self)
        self._popup = pop
        pop.overrideredirect(True)
        # KHONG dung "-topmost": neu bat, popup se noi len tren MOI cua so
        # khac tren toan he thong (kem ca khi Alt+Tab sang app khac), vi
        # overrideredirect window khong tu an theo focus nhu topmost binh
        # thuong. Thay vao do ta tu dong dong popup khi cua so chinh mat
        # focus (xem _bind_focus_close ben duoi).
        pop.configure(bg=self._border)
        pop.geometry(f"{width}x1+{x}+{y}")

        outer = tk.Frame(pop, bg=self._border)
        outer.pack(fill="both", expand=True, padx=1, pady=1)
        inner = tk.Frame(outer, bg=self._popup_bg)
        inner.pack(fill="both", expand=True)

        n_rows = len(self._items) if self._items else 1
        list_h = min(n_rows, self.MAX_VISIBLE_ROWS) * self.ROW_H
        need_scroll = len(self._items) > self.MAX_VISIBLE_ROWS

        list_area = tk.Frame(inner, bg=self._popup_bg)
        list_area.pack(fill="x")

        if not self._items:
            tk.Label(list_area, text="(Chưa có mục nào)", font=("Arial", 9, "italic"),
                     fg="#9aa0a6", bg=self._popup_bg, anchor="w", padx=10, pady=8
                     ).pack(fill="x")
            list_h = self.ROW_H
        elif need_scroll:
            canvas = tk.Canvas(list_area, bg=self._popup_bg, height=list_h,
                                highlightthickness=0, bd=0)
            vsb = tk.Scrollbar(list_area, orient="vertical", command=canvas.yview)
            rows_frame = tk.Frame(canvas, bg=self._popup_bg)
            canvas.configure(yscrollcommand=vsb.set)
            canvas.create_window((0, 0), window=rows_frame, anchor="nw", width=width - 18)
            canvas.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            def _on_wheel(e):
                delta = -1 if getattr(e, "delta", 0) > 0 else 1
                canvas.yview_scroll(delta * 2, "units")
                return "break"
            canvas.bind("<MouseWheel>", _on_wheel)
            rows_frame.bind("<MouseWheel>", _on_wheel)
            canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-2, "units") or "break")
            canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(2, "units") or "break")
            self._wheel_bound = True
            rows_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

            for name in self._items:
                self._build_row(rows_frame, name, width - 18)
        else:
            for name in self._items:
                self._build_row(list_area, name, width)

        tk.Frame(inner, bg=self._border, height=1).pack(fill="x")

        bottom = tk.Frame(inner, bg=self._popup_bg)
        bottom.pack(fill="x")
        btn_bottom = tk.Label(
            bottom, text=self._bottom_text, font=("Arial", 10, "bold"),
            fg=self._accent, bg=self._popup_bg, anchor="w",
            padx=10, pady=8, cursor="hand2")
        btn_bottom.pack(fill="x")

        def _on_bottom(_e=None):
            self._close_popup()
            if self._on_bottom_click:
                self._on_bottom_click()
        btn_bottom.bind("<Button-1>", _on_bottom)
        btn_bottom.bind("<Enter>", lambda e: btn_bottom.configure(bg=self._hover_bg))
        btn_bottom.bind("<Leave>", lambda e: btn_bottom.configure(bg=self._popup_bg))

        total_h = list_h + 1 + self.ROW_H
        pop.geometry(f"{width}x{total_h}+{x}+{y}")

        pop.focus_force()
        # tre 1 nhip su kien de tranh chinh cai click vua mo popup lai bi
        # bat luon boi bind_all va dong popup ngay lap tuc.
        self._root_bind_id = True
        self.after(1, self._arm_outside_click)
        self._bind_focus_close()

    def _bind_focus_close(self):
        """Tu dong dong popup khi cua so chinh cua app mat focus (vd
        nguoi dung Alt+Tab sang app khac), vi popup la overrideredirect
        Toplevel nen se khong tu an theo he thong nhu 1 cua so binh
        thuong."""
        root = self.winfo_toplevel()
        self._focus_bind_widget = root
        self._focus_bind_id = root.bind(
            "<FocusOut>", self._on_root_focus_out, add="+")

    def _unbind_focus_close(self):
        if getattr(self, "_focus_bind_id", None) is not None:
            try:
                self._focus_bind_widget.unbind("<FocusOut>", self._focus_bind_id)
            except Exception:
                pass
            self._focus_bind_id = None
            self._focus_bind_widget = None

    def _on_root_focus_out(self, event=None):
        # Sau khi mat focus, kiem tra lai (tre 1 nhip) xem focus co that su
        # roi khoi ca app (vd sang ung dung khac) hay chi chuyen noi bo
        # sang chinh popup / 1 widget khac trong app (khong nen dong).
        self.after(50, self._check_focus_still_in_app)

    def _check_focus_still_in_app(self):
        if self._popup is None:
            return
        try:
            focus_widget = self.winfo_toplevel().focus_get()
        except Exception:
            focus_widget = None
        if focus_widget is None:
            self._close_popup()

    def _arm_outside_click(self):
        if self._popup is None:
            return
        self.bind_all("<Button-1>", self._maybe_close_outside, add="+")

    def _maybe_close_outside(self, event):
        if self._popup is None:
            return
        widget = event.widget
        try:
            top = widget.winfo_toplevel()
        except Exception:
            top = None
        if top is not self._popup and widget is not self._btn \
                and widget is not self._lbl_value and widget is not self._lbl_arrow:
            self._close_popup()

    def _build_row(self, parent, name, width):
        row = tk.Frame(parent, bg=self._popup_bg, height=self.ROW_H)
        row.pack(fill="x")
        row.pack_propagate(False)

        if self._show_icon_box:
            icon_box = tk.Frame(row, bg=self._popup_bg, width=20, height=20,
                                 highlightthickness=1, highlightbackground=self._border)
            icon_box.pack(side="left", padx=(8, 6), pady=7)
            icon_box.pack_propagate(False)

        is_current = (name == self._current)
        lbl = tk.Label(
            row, text=self._truncate(name), font=("Arial", 10,
                                                    "bold" if is_current else "normal"),
            fg=(self._accent if is_current else self._fg), bg=self._popup_bg,
            anchor="w", cursor="hand2")
        lbl.pack(side="left", fill="both", expand=True)

        widgets_for_hover = [row, lbl]

        if self._on_delete:
            btn_x = tk.Label(row, text="✕", font=("Arial", 10, "bold"),
                              fg=self._danger, bg=self._popup_bg, cursor="hand2",
                              padx=8)
            btn_x.pack(side="right")
            widgets_for_hover.append(btn_x)

            def _do_delete(_e=None, n=name):
                self._close_popup()
                self._on_delete(n)
            btn_x.bind("<Button-1>", _do_delete)

            def _x_enter(e): btn_x.configure(fg="white", bg=self._danger)
            def _x_leave(e): btn_x.configure(fg=self._danger, bg=self._popup_bg)
            btn_x.bind("<Enter>", _x_enter)
            btn_x.bind("<Leave>", _x_leave)

        if self._on_edit:
            # Pack SAU nut xoa de nam ben TRAI no (pack side="right" xep tu
            # phai vao, nut pack sau se nam gan giua hon), tao thu tu tu
            # trai qua phai la: ten ... [✏ sua] [✕ xoa].
            btn_edit = tk.Label(row, text="✏", font=("Arial", 10, "bold"),
                                 fg=self._accent, bg=self._popup_bg, cursor="hand2",
                                 padx=8)
            btn_edit.pack(side="right")
            widgets_for_hover.append(btn_edit)

            def _do_edit(_e=None, n=name):
                self._close_popup()
                self._on_edit(n)
            btn_edit.bind("<Button-1>", _do_edit)

            def _edit_enter(e): btn_edit.configure(fg="white", bg=self._accent)
            def _edit_leave(e): btn_edit.configure(fg=self._accent, bg=self._popup_bg)
            btn_edit.bind("<Enter>", _edit_enter)
            btn_edit.bind("<Leave>", _edit_leave)

        def _select(_e=None, n=name):
            self._close_popup()
            self.set(n)
            if self._on_select:
                self._on_select(n)

        def _row_enter(e):
            for w in widgets_for_hover:
                try:
                    w.configure(bg=self._hover_bg)
                except Exception:
                    pass

        def _row_leave(e):
            for w in widgets_for_hover:
                try:
                    w.configure(bg=self._popup_bg)
                except Exception:
                    pass

        for w in (row, lbl):
            w.bind("<Button-1>", _select)
            w.bind("<Enter>", _row_enter)
            w.bind("<Leave>", _row_leave)
        if self._show_icon_box:
            icon_box.bind("<Button-1>", _select)