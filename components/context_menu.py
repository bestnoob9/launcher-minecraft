import tkinter as tk
import theme
class ThemedDropdownMenu:
    WIDTH_MAC_DINH = 190
    def __init__(self, owner):
        self.owner = owner
        self._popup = None
        self._armed = False
        self._exclude_widget = None
    def is_open(self):
        return self._popup is not None
    def toggle(self, items, x_root, y_root, width=WIDTH_MAC_DINH, exclude_widget=None):
        if self._popup is not None:
            self.close()
            return
        self.open_at(items, x_root, y_root, width=width, exclude_widget=exclude_widget)
    def open_at(self, items, x_root, y_root, width=WIDTH_MAC_DINH, exclude_widget=None):
        self.close()
        c = theme.colors()
        border = c.get("row_sep", "#444444")
        bg_alt = c["bg_alt"]
        hover_bg = c.get("icon_bg", bg_alt)
        self._exclude_widget = exclude_widget
        pop = tk.Toplevel(self.owner)
        self._popup = pop
        pop.overrideredirect(True)
        pop.configure(bg=border)
        pop.geometry(f"{width}x1+{x_root}+{y_root}")
        inner = tk.Frame(pop, bg=bg_alt)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        for i, (nhan, lenh, nguy_hiem) in enumerate(items):
            if nguy_hiem and i > 0:
                tk.Frame(inner, bg=border, height=1).pack(fill="x")
            fg = "#E53935" if nguy_hiem else c["fg_title"]
            row = tk.Label(inner, text=nhan, font=("Arial", 9), bg=bg_alt, fg=fg,
                            anchor="w", padx=10, pady=8, cursor="hand2")
            row.pack(fill="x")
            def _chay(_e=None, lenh=lenh):
                self.close()
                lenh()
            row.bind("<Button-1>", _chay)
            row.bind("<Enter>", lambda e, r=row: r.configure(bg=hover_bg))
            row.bind("<Leave>", lambda e, r=row: r.configure(bg=bg_alt))
        pop.update_idletasks()
        total_h = inner.winfo_reqheight() + 2
        pop.geometry(f"{width}x{total_h}+{x_root}+{y_root}")
        pop.focus_force()
        self.owner.after(1, self._arm)
    def _arm(self):
        if self._popup is None:
            return
        self.owner.bind_all("<Button-1>", self._on_click_outside, add="+")
        self._armed = True
    def _on_click_outside(self, event):
        popup = self._popup
        if popup is None:
            return
        widget = event.widget
        if self._exclude_widget is not None and widget is self._exclude_widget:
            return
        try:
            top = widget.winfo_toplevel()
        except Exception:
            top = None
        if top is popup:
            return
        self.close()
    def close(self):
        if self._armed:
            try:
                self.owner.unbind_all("<Button-1>")
            except Exception:
                pass
            self._armed = False
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None