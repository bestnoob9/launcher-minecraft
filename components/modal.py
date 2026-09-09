import tkinter as tk
import theme
try:
    from PIL import Image, ImageTk, ImageGrab
    _PIL_OK = True
except Exception:
    _PIL_OK = False
class AppModal:
    _OVERLAY_BG = "#1b1d22"
    _DIM_ALPHA = 0.45
    def __init__(self, root):
        self.root = root
        self._stack = []
        self._toasts = []
    def _chup_va_lam_toi_nen(self, w, h):
        if not _PIL_OK or w <= 0 or h <= 0:
            return None
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            snapshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            if snapshot.size != (w, h):
                snapshot = snapshot.resize((w, h))
            snapshot = snapshot.convert("RGB")
            den = Image.new("RGB", snapshot.size, (0, 0, 0))
            dim = Image.blend(snapshot, den, self._DIM_ALPHA)
            return ImageTk.PhotoImage(dim)
        except Exception:
            return None
    def is_open(self):
        return bool(self._stack)
    def open(self, build_fn, width=420, height=None, close_guard=None):
        colors = theme.colors()
        border = theme.sidebar_colors().get("border", "#c5cad3")
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        overlay_img = self._chup_va_lam_toi_nen(w, h)
        if overlay_img is not None:
            overlay = tk.Label(self.root, image=overlay_img, bd=0,
                                highlightthickness=0)
        else:
            overlay = tk.Label(self.root, bg=self._OVERLAY_BG, bd=0,
                                highlightthickness=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        card = tk.Frame(overlay, bg=colors["bg_alt"],
                         highlightthickness=1, highlightbackground=border)
        if height is not None:
            card.place(relx=0.5, rely=0.5, anchor="center",
                       width=width, height=height)
        else:
            card.place(relx=0.5, rely=0.5, anchor="center", width=width)
        def _on_overlay_click(event, overlay=overlay):
            if event.widget is overlay:
                self.request_close()
        overlay.bind("<Button-1>", _on_overlay_click)
        overlay.grab_set()
        overlay.focus_set()
        self.root.bind_all("<Escape>", lambda e: self.request_close())
        self._stack.append({
            "overlay": overlay,
            "card": card,
            "overlay_img": overlay_img,
            "close_guard": close_guard,
        })
        build_fn(card, self.request_close)
    def request_close(self):
        if not self._stack:
            return
        guard = self._stack[-1]["close_guard"]
        if guard is not None:
            try:
                allowed = guard()
            except Exception:
                allowed = True
            if not allowed:
                return
        self.close()
    def close(self):
        if not self._stack:
            return
        top = self._stack.pop()
        try:
            top["overlay"].grab_release()
        except Exception:
            pass
        try:
            top["overlay"].destroy()
        except Exception:
            pass
        if self._stack:
            duoi = self._stack[-1]
            try:
                duoi["overlay"].grab_set()
                duoi["overlay"].focus_set()
            except Exception:
                pass
            self.root.bind_all("<Escape>", lambda e: self.request_close())
        else:
            try:
                self.root.unbind_all("<Escape>")
            except Exception:
                pass
    def close_all(self):
        while self._stack:
            self.close()
    def confirm(self, title, message, on_confirm, confirm_text="Xóa",
                cancel_text="Hủy", danger=True, width=360):
        colors = theme.colors()
        def _build(card, close):
            content = tk.Frame(card, bg=colors["bg_alt"])
            content.pack(fill="both", expand=True, padx=18, pady=16)
            tk.Label(content, text=title, font=("Arial", 12, "bold"),
                     bg=colors["bg_alt"], fg=colors["fg_title"],
                     wraplength=width - 40, justify="left"
                     ).pack(anchor="w", pady=(0, 8))
            tk.Label(content, text=message, font=("Arial", 10),
                     bg=colors["bg_alt"], fg=colors["fg_desc"],
                     wraplength=width - 40, justify="left"
                     ).pack(anchor="w", pady=(0, 16))
            bar = tk.Frame(content, bg=colors["bg_alt"])
            bar.pack(fill="x")
            def _do_confirm():
                close()
                on_confirm()
            tk.Button(bar, text=cancel_text, font=("Arial", 10),
                      bg=colors["bg"], fg=colors["fg_title"], relief="flat",
                      padx=14, pady=6, command=close
                      ).pack(side="right", padx=(8, 0))
            tk.Button(bar, text=confirm_text, font=("Arial", 10, "bold"),
                      bg=("#E53935" if danger else "#1E88E5"), fg="white",
                      relief="flat", padx=14, pady=6, command=_do_confirm
                      ).pack(side="right")
        self.open(_build, width=width)
    _TOAST_DURATION_MS = 2500
    _TOAST_MARGIN = 18
    _TOAST_GAP = 8
    def toast(self, message, loai="ok"):
        colors = theme.colors()
        accent = "#43A047" if loai != "loi" else "#E53935"
        try:
            top = tk.Toplevel(self.root)
        except Exception:
            return
        try:
            top.overrideredirect(True)
            top.attributes("-topmost", True)
        except Exception:
            pass
        card = tk.Frame(top, bg=colors["bg_alt"],
                         highlightthickness=1, highlightbackground=accent)
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=colors["bg_alt"])
        inner.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(inner, text=("✓ " if loai != "loi" else "✕ ") + message,
                 font=("Arial", 10), bg=colors["bg_alt"], fg=colors["fg_title"],
                 wraplength=320, justify="left").pack(anchor="w")
        entry = {"win": top}
        self._toasts.append(entry)
        self.root.update_idletasks()
        self._layout_toasts()
        top.after(self._TOAST_DURATION_MS, lambda: self._dong_toast(entry))
        return top
    def _layout_toasts(self):
        try:
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
        except Exception:
            return
        y_cursor = ry + rh - self._TOAST_MARGIN
        for entry in reversed(self._toasts):
            win = entry["win"]
            try:
                win.update_idletasks()
                tw = win.winfo_reqwidth()
                th = win.winfo_reqheight()
                x = rx + rw - tw - self._TOAST_MARGIN
                y = y_cursor - th
                win.geometry(f"{tw}x{th}+{x}+{y}")
                y_cursor = y - self._TOAST_GAP
            except Exception:
                continue
    def _dong_toast(self, entry):
        if entry in self._toasts:
            self._toasts.remove(entry)
        try:
            entry["win"].destroy()
        except Exception:
            pass
        self._layout_toasts()
    def alert(self, title, message, ok_text="OK", width=360):
        colors = theme.colors()
        def _build(card, close):
            content = tk.Frame(card, bg=colors["bg_alt"])
            content.pack(fill="both", expand=True, padx=18, pady=16)
            tk.Label(content, text=title, font=("Arial", 12, "bold"),
                     bg=colors["bg_alt"], fg=colors["fg_title"],
                     wraplength=width - 40, justify="left"
                     ).pack(anchor="w", pady=(0, 8))
            tk.Label(content, text=message, font=("Arial", 10),
                     bg=colors["bg_alt"], fg=colors["fg_desc"],
                     wraplength=width - 40, justify="left"
                     ).pack(anchor="w", pady=(0, 16))
            bar = tk.Frame(content, bg=colors["bg_alt"])
            bar.pack(fill="x")
            tk.Button(bar, text=ok_text, font=("Arial", 10, "bold"),
                      bg="#1E88E5", fg="white", relief="flat",
                      padx=14, pady=6, command=close
                      ).pack(side="right")
        self.open(_build, width=width)