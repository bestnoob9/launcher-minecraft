"""
components/modal.py

Modal "trong launcher" dung chung cho AccountFrame / InstanceFrame (va cac
noi khac neu can sau nay), thay the cho viec tao tk.Toplevel rieng (cua so
OS moi). Y tuong giong panel "Tao ho so" cua CurseForge: 1 lop phu toi
(overlay) trai kin cua so goc, o giua co 1 "card" chua form.

Tkinter khong ho tro alpha/trong suot that cho 1 widget con nam trong cung
1 cua so (chi Toplevel moi dung duoc wm_attributes alpha). De co hieu ung
"dim" (mo, thay lo mo noi dung phia sau) thay vi 1 mang mau dac, lop phu
duoc gia lap bang cach: chup lai dung vung man hinh cua cua so goc ngay
truoc khi mo modal (PIL.ImageGrab), lam toi anh do bang Image.blend voi
mau den, roi hien thi anh da lam toi do lam nen cho overlay. Ket qua nhin
giong hieu ung dim cua cac app hien dai (CurseForge, Discord...).

Neu khong co Pillow, hoac chup man hinh that bai (vd moi truong khong ho
tro ImageGrab nhu 1 so may Linux/X11 khong dung), tu dong fallback ve mau
dac _OVERLAY_BG nhu truoc - dam bao modal luon mo duoc, chi la khong co
hieu ung dim.

Ho tro xep chong (stack) nhieu lop modal: goi open()/confirm()/alert() khi
dang co 1 modal khac mo san se KHONG dong modal do di, ma xep 1 lop moi
len tren (dim toi hon do lop duoi cung bi che). Dong lop tren cung se lo
lai lop duoi (grab + Escape duoc gan lai cho lop duoi). Nho vay 1 form dang
mo (vd panel "Sua chua") van co the tu mo them 1 alert/confirm nho de canh
bao nguoi dung ma khong bi mat trang thai / dong nham form dang mo.

Cach dung:
    self.modal = AppModal(self.root)
    ...
    self.modal.open(build_fn, width=420)          # form thuong, card om theo noi dung
    self.modal.confirm("Tieu de", "Mo ta...", on_confirm=xoa_gi_do)
    self.modal.alert("Tieu de", "Thong bao...")   # chi 1 nut OK de dong

build_fn(card, close) se duoc goi de dung noi dung form:
    - card: 1 tk.Frame de add widget vao (da co mau theo theme)
    - close: goi ham nay khi muon dong modal (vd sau khi Xac nhan/Huy xong)
"""
import tkinter as tk
import theme

try:
    from PIL import Image, ImageTk, ImageGrab
    _PIL_OK = True
except Exception:
    _PIL_OK = False


class AppModal:
    # Mau lop phu dung khi khong dim duoc (khong co Pillow / chup man hinh
    # loi) - fallback dac, khong doi theo theme sang/toi.
    _OVERLAY_BG = "#1b1d22"

    # Do toi cua lop phu dim: 0 = giu nguyen anh chup (khong toi chut nao),
    # 1 = den tuyet doi. 0.45 la muc vua du de thay "khoa" ma van thay
    # duoc lo mo layout phia sau.
    _DIM_ALPHA = 0.45

    def __init__(self, root):
        self.root = root
        # Danh sach cac lop modal dang mo, tu duoi len tren. Moi phan tu:
        # {"overlay", "card", "overlay_img", "close_guard"}. Lop cuoi cung
        # (self._stack[-1]) la lop dang hien/nhan input.
        self._stack = []

    # ------------------------------------------------------------------
    def _chup_va_lam_toi_nen(self, w, h):
        """Chup dung vung man hinh cua cua so goc (w x h, toa do man hinh
        hien tai cua self.root) roi lam toi bang blend voi mau den. Tra ve
        ImageTk.PhotoImage neu thanh cong, None neu that bai (se fallback
        ve mau dac o noi goi)."""
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

    # ------------------------------------------------------------------
    def is_open(self):
        return bool(self._stack)

    def open(self, build_fn, width=420, height=None, close_guard=None):
        """Mo them 1 lop modal len tren cung. Neu dang co modal (hoac nhieu
        lop modal) mo san, chung KHONG bi dong - lop moi se xep chong len
        tren (xem docstring dau file). Dong lop nay se tu dong lo lai lop
        ngay duoi no (neu co).

        close_guard (khong bat buoc): ham tra ve True/False, duoc goi moi
        khi nguoi dung co gang dong modal (Escape / click nen / nut close
        trong form). Tra ve False de chan dong (vd dang chay 1 tac vu nen
        khong the huy giua chung, hoac muon tu mo 1 confirm/alert long ben
        trong roi tu quyet dinh khi nao dong that - xem _guard trong
        instance_frame.py de biet vi du).

        Card luon om theo noi dung do build_fn pack vao (khong Canvas,
        khong Scrollbar): neu height khong truyen vao thi chieu cao card
        tu dong theo widget ben trong; neu truyen vao thi ep chieu cao co
        dinh nhu cu."""
        colors = theme.colors()
        border = theme.sidebar_colors().get("border", "#c5cad3")

        # Chup + lam toi trang thai cua so hien tai (da bao gom moi lop
        # modal dang mo san, neu co) truoc khi phu them lop overlay moi -
        # lop cang cao trong stack se cang toi do bi dim chong len nhau.
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        overlay_img = self._chup_va_lam_toi_nen(w, h)

        if overlay_img is not None:
            # Dim that: Label hien anh da lam toi lam nen, thay lo mo duoc
            # layout phia sau thay vi 1 mang mau dac.
            overlay = tk.Label(self.root, image=overlay_img, bd=0,
                                highlightthickness=0)
        else:
            # Fallback: khong co Pillow hoac chup man hinh that bai -> dung
            # mau dac nhu truoc, van dam bao modal mo duoc binh thuong.
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

        # Click vao nen overlay (khong phai vao card/con cua no) -> dong.
        def _on_overlay_click(event, overlay=overlay):
            if event.widget is overlay:
                self.request_close()
        overlay.bind("<Button-1>", _on_overlay_click)

        # grab_set tren overlay: overlay + con chau (card + form) la nhanh
        # duy nhat con nhan duoc input, moi thu phia sau (ke ca lop modal
        # duoi, neu co) bi khoa.
        overlay.grab_set()
        overlay.focus_set()

        # Dung bind_all (thay vi bind rieng tren overlay) de Escape van bat
        # duoc du widget dang focus la 1 Entry/Combobox nam sau trong card.
        # Luon tro ve request_close() cua LOP TREN CUNG hien tai.
        self.root.bind_all("<Escape>", lambda e: self.request_close())

        self._stack.append({
            "overlay": overlay,
            "card": card,
            "overlay_img": overlay_img,
            "close_guard": close_guard,
        })

        build_fn(card, self.request_close)

    def request_close(self):
        """Duoc dung cho moi duong dong modal (Escape, click nen, nut Huy/X
        trong form): kiem tra close_guard cua LOP TREN CUNG (neu co) truoc
        khi dong that su lop do."""
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
        """Dong ngay lop tren cung, bo qua close_guard. Neu con lop duoi
        trong stack, no se duoc "lo" lai (gan grab + Escape lai cho no);
        neu khong con lop nao, go bind Escape luon."""
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
        """Dong toan bo cac lop modal dang mo (tu tren xuong duoi), bo qua
        moi close_guard. Dung khi can dam bao sach hoan toan (vd truoc khi
        thoat app hoac chuyen man hinh lon)."""
        while self._stack:
            self.close()

    # ------------------------------------------------------------------
    def confirm(self, title, message, on_confirm, confirm_text="Xóa",
                cancel_text="Hủy", danger=True, width=360):
        """Modal xac nhan nho gon (thay cho messagebox.askyesno) - dung cho
        cac thao tac pha huy nhu xoa tai khoan / xoa phien ban."""
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

    # ------------------------------------------------------------------
    def alert(self, title, message, ok_text="OK", width=360):
        """Modal thong bao don gian (thay cho messagebox.showinfo/showwarning
        khi khong can hoi Co/Khong) - chi 1 nut de dong. Dung cho cac thong
        bao nhu 'khong the thuc hien X' ma van muon giu trong launcher thay
        vi bat 1 cua so OS rieng."""
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
