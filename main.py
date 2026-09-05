import tkinter as tk
from tkinter import ttk
import threading
import os
import sys
import config
import core
import theme
from icon_utils import gan_icon_app as _gan_icon_app
from components.account_frame import AccountFrame
from components.instance_frame import InstanceFrame
from setup_wizard import kiem_tra_va_chay_wizard

def _can_giua_man_hinh(win, width, height):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

def _doc_cau_hinh_may():
    import math

    def _lam_tron_ram_gb(total_mb):
        cac_moc = [4, 8, 12, 16, 24, 32, 48, 64, 128]
        total_gb_thuc = total_mb / 1024
        for moc in cac_moc:
            if total_gb_thuc <= moc * 1.05:
                return moc
        return math.ceil(total_gb_thuc)

    info = {
        "ram_total_mb": 8192,   
        "ram_total_gb": 8,
    }

    total_mb = None

    try:
        import psutil
        total_bytes = psutil.virtual_memory().total
        if total_bytes > 0:
            total_mb = total_bytes // (1024 * 1024)
    except Exception as e:
        print(f"[System] psutil that bai: {e}")

    if total_mb is None:
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength",                ctypes.c_ulong),
                    ("dwMemoryLoad",            ctypes.c_ulong),
                    ("ullTotalPhys",            ctypes.c_ulonglong),
                    ("ullAvailPhys",            ctypes.c_ulonglong),
                    ("ullTotalPageFile",        ctypes.c_ulonglong),
                    ("ullAvailPageFile",        ctypes.c_ulonglong),
                    ("ullTotalVirtual",         ctypes.c_ulonglong),
                    ("ullAvailVirtual",         ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            if stat.ullTotalPhys > 0:
                total_mb = stat.ullTotalPhys // (1024 * 1024)
        except Exception as e:
            print(f"[System] ctypes that bai: {e}")

    if total_mb is None:
        try:
            import wmi
            c = wmi.WMI()
            tong = sum(int(cs.TotalPhysicalMemory) for cs in c.Win32_ComputerSystem())
            if tong > 0:
                total_mb = tong // (1024 * 1024)
        except Exception as e:
            print(f"[System] wmi that bai: {e}")

    if total_mb and total_mb > 0:
        info["ram_total_mb"] = total_mb
        info["ram_total_gb"] = _lam_tron_ram_gb(total_mb)
    else:
        print("[System] where ram bro")

    config.current_config["_system_info"] = info

class ConsoleWindow(tk.Toplevel):
    _BG_MAIN   = "#1e1e1e"
    _BG_BAR    = "#2d2d2d"
    _BG_BTN    = "#3c3c3c"
    _FG_TEXT   = "#d4d4d4"
    _FG_COUNT  = "#888888"

    def __init__(self, parent):
        super().__init__(parent)
        # An ngay lap tuc: Toplevel tu map ra man hinh ngay khi tao, neu de
        # withdraw() o cuoi (sau khi build xong title/geometry/widget) thi
        # se bi chop 1 khung cua so rong/mac dinh truoc khi an di.
        self.withdraw()

        self.title("Console — Minecraft Log")
        self.geometry("780x420")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        _gan_icon_app(self)
        self.configure(bg=self._BG_MAIN)

        self.txt = tk.Text(self, font=("Consolas", 9),
                           bg=self._BG_MAIN, fg=self._FG_TEXT,
                           insertbackground=self._FG_TEXT,
                           selectbackground="#264f78",
                           wrap="word", state="disabled", relief="flat", bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self, bg=self._BG_BAR)
        btn_frame.pack(fill="x")

        self._btn_clear = tk.Button(btn_frame, text="Xóa log", font=("Arial", 8),
                  bg=self._BG_BTN, fg="white", activebackground="#555",
                  activeforeground="white", relief="flat", padx=8,
                  command=self.clear)
        self._btn_clear.pack(side="left", padx=4, pady=4)

        self.lbl_count = tk.Label(btn_frame, text="0 dòng", font=("Arial", 8),
                                  bg=self._BG_BAR, fg=self._FG_COUNT)
        self.lbl_count.pack(side="right", padx=8)

        self._line_count = 0
        self.bind("<Map>", self._restore_colors)

    def _restore_colors(self, event=None):
        try:
            self.configure(bg=self._BG_MAIN)
            self.txt.configure(bg=self._BG_MAIN, fg=self._FG_TEXT)
            self._btn_clear.configure(bg=self._BG_BTN, fg="white",
                                      activebackground="#555", activeforeground="white")
            self.lbl_count.configure(bg=self._BG_BAR, fg=self._FG_COUNT)
            bf = self.lbl_count.master
            if bf:
                bf.configure(bg=self._BG_BAR)
        except Exception:
            pass
    def append(self, text):
        self.txt.config(state="normal")
        self.txt.insert("end", text)
        self.txt.see("end")
        self.txt.config(state="disabled")
        self._line_count += text.count("\n")
        self.lbl_count.config(text=f"{self._line_count} dòng")

    def clear(self):
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.config(state="disabled")
        self._line_count = 0
        self.lbl_count.config(text="0 dòng")

    def show(self):
        self.deiconify()
        self.lift()

class MinecraftLauncherApp:
    """Giao dien kieu 'launcher hien dai' (lay cam hung tu SKlauncher):
    mot sidebar co dinh ben trai (tai khoan + quan ly cau hinh/instance +
    nut VAO GAME luon hien) va mot vung noi dung ben phai co the doi qua
    lai giua Trang chu / Noi dung (Mod-Modpack-Resource Pack-Shader) / Cai dat.

    Vi sidebar luon hien thi (khong bi an di khi doi tab), nut VAO GAME va
    thanh tien do tai game co the dung o bat ky dau (kien tao lai Content
    thoai mai sau nay) ma khong lam mat kha nang bam Choi.
    """

    _TAB_ACTIVE_BG   = "#1E88E5"
    _TAB_INACTIVE_BG = "#37474F"
    _TAB_FG          = "white"

    # Bang mau cho sidebar - LAY THEO theme sang/toi hien tai cua app
    # (xem theme.sidebar_colors()), khong con la 1 bang mau co dinh
    # (xanh-tim) nua: theme toi thi sidebar toi hoa hop, theme sang thi
    # sidebar sang hoa hop. Dung @property de moi noi dang dung
    # self._SB_BG/self._SB_BG_ALT/... deu tu dong lay dung mau hien tai
    # ma khong can sua tung cho.
    _SB_WIDTH     = 288

    @property
    def _SB_BG(self):
        return theme.sidebar_colors()["bg"]

    @property
    def _SB_BG_ALT(self):
        return theme.sidebar_colors()["bg_alt"]

    @property
    def _SB_BORDER(self):
        return theme.sidebar_colors()["border"]

    @property
    def _SB_TEXT(self):
        return theme.sidebar_colors()["text"]

    @property
    def _SB_TEXT_DIM(self):
        return theme.sidebar_colors()["text_dim"]

    @property
    def _SB_ACCENT(self):
        return theme.sidebar_colors()["accent"]

    @staticmethod
    def _doc_kich_thuoc_cua_so():
        import re
        raw = str(config.current_config.get("kich_thuoc_cua_so", "1280x720"))
        match = re.search(r"(\d+)\s*x\s*(\d+)", raw)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
            if w >= 800 and h >= 600:
                return w, h
        return 1280, 720

    def ap_dung_kich_thuoc_cua_so(self):
        rong_cs, cao_cs = self._doc_kich_thuoc_cua_so()
        self.root.minsize(min(800, rong_cs), min(600, cao_cs))
        # Chi doi kich thuoc, GIU NGUYEN vi tri hien tai cua cua so - ham
        # nay duoc goi lai moi khi doi tai khoan/phien ban (xem
        # khi_thay_doi_instance) VA khi luu Cai dat kich thuoc cua so, nen
        # khong the dung _can_giua_man_hinh() (ep toa do x,y ve giua man
        # hinh) o day nua, neu khong moi lan doi acc/instance cua so se bi
        # keo ve giua, mat vi tri nguoi dung da keo/dat truoc do.
        self.root.geometry(f"{rong_cs}x{cao_cs}")

    def __init__(self, root):
        self.root = root
        self.root.title("NoName MCL")

        rong_cs, cao_cs = self._doc_kich_thuoc_cua_so()
        self.root.minsize(min(800, rong_cs), min(600, cao_cs))
        self.root.resizable(True, True)
        _gan_icon_app(self.root)
        # KHONG can giua man hinh o day nua: main() da set geometry (size +
        # vi tri giua man hinh) ngay khi tao Tk(), TRUOC khi build UI, de
        # tranh phai center lai 2 lan (vua cham, vua co the gay flash/nhay
        # vi tri khi cua so hien ra). Neu goi lai o day se ep cua so ve
        # giua ngay ca khi nguoi dung da co vi tri khac (vd sau nay neu co
        # luu vi tri cua so).

        config.current_config = config.tai_toan_bo_cau_hinh()
        self._game_process = None
        self._dang_tai = False
        self._huy_tai = False

        self.console = ConsoleWindow(root)
        self._current_view = None
        self._tab_buttons  = {}
        self._view_frames  = {}
        self._progress_popup = None

        # Modal dung chung cho toan app (overlay toi + card giua man hinh),
        # thay the cho cac tk.Toplevel rieng cua Them/Xoa tai khoan va
        # Tao/Xoa/Sua chua phien ban - xem components/modal.py. Tao TRUOC
        # create_widgets() vi AccountFrame/InstanceFrame can no ngay luc
        # khoi tao.
        from components.modal import AppModal
        self.modal = AppModal(self.root)

        self.create_widgets()
        theme.apply_theme(self.root)
        self.ap_dung_theme_sidebar()   # ve lai toan bo mau sidebar dung theme
        self.root.protocol("WM_DELETE_WINDOW", self._xu_ly_thoat)

        self._switch_view("home")

    # ------------------------------------------------------------------
    # BO KHUNG CHINH: sidebar (trai) + noi dung (phai)
    # ------------------------------------------------------------------
    def create_widgets(self):
        root_split = tk.Frame(self.root)
        root_split.pack(fill="both", expand=True)

        self._sidebar = tk.Frame(root_split, width=self._SB_WIDTH, bg=self._SB_BG)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._content_wrap = tk.Frame(root_split)
        self._content_wrap.pack(side="left", fill="both", expand=True)

        self._build_sidebar(self._sidebar)
        self._build_content_area(self._content_wrap)

        self._view_frames["home"]     = self._build_home_view(self._container)
        self._view_frames["modpack"]  = self._build_modpack_view(self._container)
        self._view_frames["settings"] = self._build_settings_view(self._container)

        self._poll_modpack_progress()

    # ---------------------------- SIDEBAR ------------------------------
    def _sb_separator(self, parent):
        sep = tk.Frame(parent, bg=self._SB_BORDER, height=1)
        sep.pack(fill="x", padx=14, pady=8)
        self._sb_separators.append(sep)
        return sep

    def _sb_section_label(self, parent, text):
        lbl = tk.Label(
            parent, text=text, font=("Arial", 8, "bold"),
            bg=self._SB_BG, fg=self._SB_TEXT_DIM, anchor="w"
        )
        lbl.pack(fill="x", padx=16, pady=(0, 4))
        self._sb_section_labels.append(lbl)
        return lbl

    def _build_sidebar(self, sb):
        self._sb_separators = []
        self._sb_section_labels = []

        # ---- Header / logo app ----
        header = tk.Frame(sb, bg=self._SB_BG)
        header.pack(fill="x", padx=16, pady=(16, 10))
        self._sb_header = header
        self._sb_lbl_logo = tk.Label(header, text="🟫", font=("Arial", 18), bg=self._SB_BG,
                 fg=self._SB_ACCENT)
        self._sb_lbl_logo.pack(side="left")
        self._sb_lbl_title = tk.Label(header, text="NoName MCL", font=("Arial", 13, "bold"),
                 bg=self._SB_BG, fg=self._SB_TEXT)
        self._sb_lbl_title.pack(side="left", padx=(8, 0))

        self._sb_separator(sb)

        # ---- Khu tai khoan (Profile) ----
        self._sb_section_label(sb, "TÀI KHOẢN")
        acc_holder = tk.Frame(sb, bg=self._SB_BG)
        acc_holder.pack(fill="x", padx=10, pady=(0, 4))
        self._sb_acc_holder = acc_holder
        self.account_frame = AccountFrame(acc_holder, self.khi_thay_doi_instance, modal=self.modal)
        self.account_frame.pack(fill="x")

        self._sb_separator(sb)

        # ---- Nav: Trang chu / Noi dung / Cai dat ----
        self._sb_section_label(sb, "ĐIỀU HƯỚNG")
        nav_holder = tk.Frame(sb, bg=self._SB_BG)
        nav_holder.pack(fill="x", padx=10, pady=(0, 4))
        self._sb_nav_holder = nav_holder

        tabs = [
            ("home",     "🏠  Trang chủ"),
            ("modpack",  "🧩  Nội dung"),
            ("settings", "⚙️  Cài đặt"),
        ]
        for name, label in tabs:
            btn = tk.Button(
                nav_holder, text=label, font=("Arial", 10, "bold"),
                bg=self._SB_BG, fg=self._SB_TEXT,
                activebackground=self._SB_ACCENT, activeforeground="white",
                relief="flat", bd=0, anchor="w", padx=10, pady=8,
                command=lambda n=name: self._switch_view(n),
            )
            btn.pack(fill="x", pady=1)
            self._tab_buttons[name] = btn

        self._sb_separator(sb)

        # ---- Quan ly cau hinh (Instance) ----
        self._sb_section_label(sb, "QUẢN LÝ CẤU HÌNH")
        inst_holder = tk.Frame(sb, bg=self._SB_BG)
        inst_holder.pack(fill="x", padx=10, pady=(0, 4))
        self._instance_holder = inst_holder
        self.instance_frame = InstanceFrame(inst_holder, self.khi_thay_doi_instance, modal=self.modal)
        self.instance_frame.pack(fill="x")

        # ---- Nut tien do dang cai mod/modpack (chi hien khi co, click
        #      de xem chi tiet - hoat dong du dang o tab nao khac) ----
        self.lbl_floating_progress = tk.Label(
            sb, text="", font=("Arial", 9, "bold"),
            bg=self._SB_BG, fg=self._SB_ACCENT, anchor="w",
            wraplength=self._SB_WIDTH - 32, justify="left",
        )
        self.lbl_floating_progress.pack(fill="x", padx=16, pady=(4, 0), side="bottom")
        self.lbl_floating_progress.bind("<Button-1>", self._toggle_progress_popup)

        # ------------------ Vung day xuong day (nut CHOI) ------------------
        bottom = tk.Frame(sb, bg=self._SB_BG_ALT)
        bottom.pack(side="bottom", fill="x")
        self._sb_bottom = bottom
        self._sb_bottom_sep = tk.Frame(bottom, bg=self._SB_BORDER, height=1)
        self._sb_bottom_sep.pack(fill="x")

        self.lbl_status = tk.Label(bottom, text="Sẵn sàng", font=("Arial", 9, "italic"),
                                    bg=self._SB_BG_ALT, fg=self._SB_TEXT_DIM)
        self.lbl_status.pack(pady=(2, 2))

        self.frame_progress = tk.Frame(bottom, bg=self._SB_BG_ALT)
        self.frame_progress.pack(fill="x", padx=14, pady=(0, 2))
        self.progress_bar = ttk.Progressbar(self.frame_progress, orient="horizontal",
                                             mode="determinate")
        self.progress_bar.pack(fill="x")
        self.lbl_progress = tk.Label(bottom, text="", font=("Arial", 8),
                                      bg=self._SB_BG_ALT, fg=self._SB_TEXT_DIM)
        self.lbl_progress.pack(pady=(0, 2))
        self.frame_progress.pack_forget()
        self.lbl_progress.pack_forget()

        self.lbl_version_hint = tk.Label(
            bottom, text="", font=("Arial", 8, "bold"),
            bg=self._SB_BG_ALT, fg=self._SB_TEXT_DIM,
        )
        self.lbl_version_hint.pack(pady=(4, 0))

        self.btn_launch = tk.Button(
            bottom, text="▶ CHƠI",
            font=("Arial", 13, "bold"), bg="#1E88E5", fg="white",
            relief="flat", height=2, command=self.bat_dau_hoac_tat_game
        )
        self.btn_launch.pack(fill="x", padx=14, pady=(4, 14))

        self._cap_nhat_goi_y_phien_ban()

    def ap_dung_theme_sidebar(self):
        """Ve lai toan bo mau cua sidebar theo theme.sidebar_colors()
        hien tai. Goi ham nay moi khi nguoi dung doi theme sang/toi o
        Cai dat de sidebar cap nhat mau ngay, khong can khoi dong lai app."""
        sb, sb_alt = self._SB_BG, self._SB_BG_ALT
        border, text, text_dim, accent = (
            self._SB_BORDER, self._SB_TEXT, self._SB_TEXT_DIM, self._SB_ACCENT)

        try:
            self._sidebar.configure(bg=sb)
            self._sb_header.configure(bg=sb)
            self._sb_lbl_logo.configure(bg=sb, fg=accent)
            self._sb_lbl_title.configure(bg=sb, fg=text)

            for sep in self._sb_separators:
                sep.configure(bg=border)
            for lbl in self._sb_section_labels:
                lbl.configure(bg=sb, fg=text_dim)

            self._sb_acc_holder.configure(bg=sb)
            self._sb_nav_holder.configure(bg=sb)
            self._instance_holder.configure(bg=sb)

            for name, btn in self._tab_buttons.items():
                if name == self._current_view:
                    btn.configure(bg=accent, fg="white", activebackground=accent)
                else:
                    btn.configure(bg=sb, fg=text, activebackground=accent)

            self.lbl_floating_progress.configure(bg=sb, fg=accent)

            self._sb_bottom.configure(bg=sb_alt)
            self._sb_bottom_sep.configure(bg=border)
            self.lbl_status.configure(bg=sb_alt, fg=text_dim)
            self.frame_progress.configure(bg=sb_alt)
            self.lbl_progress.configure(bg=sb_alt, fg=text_dim)
            self.lbl_version_hint.configure(bg=sb_alt, fg=text_dim)
        except Exception:
            pass

        if hasattr(self, "account_frame") and hasattr(self.account_frame, "selector"):
            self.account_frame.selector.apply_sidebar_colors()
        if hasattr(self, "instance_frame") and hasattr(self.instance_frame, "selector"):
            self.instance_frame.selector.apply_sidebar_colors()

        self._lam_toi_mau_sidebar()

    def _lam_toi_mau_sidebar(self):
        """Ep mau nen/chu cua cac widget con (Frame/Label mac dinh) nam
        ben trong sidebar ve dung mau sidebar hien tai (theo theme), boi
        vi AccountFrame/InstanceFrame von duoc thiet ke de dat trong vung
        noi dung (theo theme sang/toi cua app), khong tu dong hop voi
        nen cua sidebar."""
        def _walk(w):
            try:
                cls = w.winfo_class()
            except Exception:
                cls = ""
            if cls == "Frame":
                try:
                    w.configure(bg=self._SB_BG)
                except Exception:
                    pass
            elif cls == "Label":
                try:
                    fg_hien_tai = str(w.cget("fg"))
                except Exception:
                    fg_hien_tai = ""
                try:
                    w.configure(bg=self._SB_BG)
                except Exception:
                    pass
                da_ep_mau_chu = getattr(w, "_sb_forced_fg", False)
                if da_ep_mau_chu or fg_hien_tai.lower() in ("black", "systembuttontext", "", "#000000"):
                    try:
                        w.configure(fg=self._SB_TEXT)
                        w._sb_forced_fg = True
                    except Exception:
                        pass
            for c in w.winfo_children():
                _walk(c)
        _walk(self.account_frame)
        _walk(self.instance_frame)

    def _cap_nhat_goi_y_phien_ban(self):
        try:
            info = self.instance_frame.get_instance_values()
            ten = self.instance_frame.get_current_instance()
            if info.get("loai_game", "Vanilla") == "Vanilla":
                phu = info.get("version_goc", "")
            else:
                phu = f"{info.get('loai_game')} {info.get('version_mod', '')}".strip()
            self.lbl_version_hint.config(text=f"{ten}  •  {phu}" if ten else "")
        except Exception:
            pass

    # --------------------------- CONTENT AREA ---------------------------
    def _build_content_area(self, parent):
        # ---- Thanh cong cu goc phai tren: Thu muc + Console (chuyen tu
        #      day sidebar len day theo yeu cau, luon hien du dang o tab nao) ----
        topbar = tk.Frame(parent)
        topbar.pack(fill="x", side="top")

        btn_console = tk.Button(
            topbar, text="🖥 Console", font=("Arial", 9, "bold"),
            bg="#455A64", fg="white", relief="flat", padx=8, pady=3,
            command=self.console.show,
        )
        btn_console.pack(side="right", padx=(0, 10), pady=8)

        self.btn_open_folder = tk.Button(
            topbar, text="📂 Thư mục", font=("Arial", 9, "bold"),
            bg="#43A047", fg="white", relief="flat", padx=8, pady=3,
            command=self.mo_thu_muc_game
        )
        self.btn_open_folder.pack(side="right", padx=(0, 6), pady=8)

        self._container = tk.Frame(parent)
        self._container.pack(fill="both", expand=True)

    def _switch_view(self, name: str):
        if self._current_view == name:
            return

        if self._current_view == "modpack":
            modpack_frame = self._view_frames.get("modpack")
            if modpack_frame and hasattr(modpack_frame, "can_switch"):
                if not modpack_frame.can_switch():
                    self.modal.alert(
                        "Đang tải/cài đặt",
                        "Đang có tác vụ tải/cài đặt đang chạy.\n"
                        "Vui lòng đợi hoàn tất hoặc hủy trước khi chuyển tab!")
                    return

        if self._current_view == "settings":
            settings_frame = self._view_frames.get("settings")
            if (settings_frame and hasattr(settings_frame, "has_unsaved_changes")
                    and settings_frame.has_unsaved_changes()):
                # modal.confirm() mo bat dong bo (khong block nhu askyesno
                # cu) nen phai hoan viec chuyen tab that su vao on_confirm.
                def _dong_y_roi_di():
                    if hasattr(settings_frame, "discard_changes"):
                        settings_frame.discard_changes()
                    self._thuc_hien_chuyen_tab(name)
                self.modal.confirm(
                    title="Thay đổi chưa được lưu",
                    message="Bạn có thay đổi trong Cài đặt chưa được lưu.\n"
                            "Bạn có chắc muốn rời đi khi chưa lưu không?",
                    on_confirm=_dong_y_roi_di,
                    confirm_text="Rời đi",
                    cancel_text="Ở lại",
                    danger=False,
                )
                return

        self._thuc_hien_chuyen_tab(name)

    def _thuc_hien_chuyen_tab(self, name: str):
        for frame in self._view_frames.values():
            frame.pack_forget()

        self._view_frames[name].pack(fill="both", expand=True)
        self._current_view = name

        for tab_name, btn in self._tab_buttons.items():
            if tab_name == name:
                btn.configure(bg=self._SB_ACCENT, fg="white")
            else:
                btn.configure(bg=self._SB_BG, fg=self._SB_TEXT)

    def _build_home_view(self, parent) -> tk.Frame:
        """Trang chu / Dashboard - chi la khu vuc noi dung minh hoa, co the
        thay bang bat cu thu gi sau nay (vd trang tin tuc, thong ke...).
        Tai khoan / Instance / Nut Choi da chuyen het sang sidebar nen o
        day khong con phu thuoc vao Home View nua."""
        frame = tk.Frame(parent)

        wrap = tk.Frame(frame)
        wrap.place(relx=0.5, rely=0.42, anchor="center")

        self._home_title = tk.Label(wrap, text="Chào mừng trở lại!",
                                     font=("Arial", 20, "bold"))
        self._home_title.pack()
        self._home_sub = tk.Label(
            wrap, text="", font=("Arial", 11), fg="gray")
        self._home_sub.pack(pady=(6, 0))

        btn_go_content = tk.Button(
            wrap, text="🧩 Xem Mod / Modpack / Resource Pack / Shader",
            font=("Arial", 10, "bold"), bg="#1E88E5", fg="white",
            relief="flat", padx=14, pady=8,
            command=lambda: self._switch_view("modpack"),
        )
        btn_go_content.pack(pady=(18, 0))

        self._cap_nhat_home_view()
        return frame

    def _cap_nhat_home_view(self):
        if not hasattr(self, "_home_sub"):
            return
        try:
            acc = self.account_frame.get_current_account() or "chưa chọn"
            inst = self.instance_frame.get_current_instance() or "chưa chọn"
            self._home_sub.config(
                text=f"Tài khoản: {acc}    |    Cấu hình đang chọn: {inst}")
        except Exception:
            pass

    def _build_modpack_view(self, parent) -> tk.Frame:
        from components.mod_mc import ModMcFrame
        frame = ModMcFrame(parent, callback_lam_moi=self._lam_moi_instance_frame)
        return frame

    def _khi_luu_setting(self):
        """Callback rieng cho SettingFrame khi nguoi dung bam Luu trong tab
        Cai dat: lam moi cac thu binh thuong (nhu khi_thay_doi_instance), roi
        MOI ap dung lai kich thuoc cua so vua luu - day la noi DUY NHAT con
        goi ap_dung_kich_thuoc_cua_so(), khong con goi khi doi account/instance
        nua (xem ghi chu trong khi_thay_doi_instance)."""
        self.khi_thay_doi_instance()
        self.ap_dung_kich_thuoc_cua_so()

    def _build_settings_view(self, parent) -> tk.Frame:
        from components.setting_window import SettingFrame
        frame = SettingFrame(parent, on_save_callback=self._khi_luu_setting, modal=self.modal)
        return frame

    def mo_thu_muc_game(self):
        import subprocess, sys
        thu_muc = config.current_config.get("thu_muc_game", "").strip()
        if not thu_muc or not os.path.exists(thu_muc):
            self.modal.alert("Chú ý", "Chưa có thư mục game hoặc thư mục không tồn tại!\nVui lòng kiểm tra lại trong Settings.")
            return
        if sys.platform == "win32":
            os.startfile(thu_muc)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", thu_muc])
        else:
            subprocess.Popen(["xdg-open", thu_muc])

    def _dinh_dang_chi_tiet_tien_do(self, label):
        import re as _re
        label = (label or "").strip()

        m = _re.match(r"^(\d+)\s*/\s*(\d+)\s*mod$", label, _re.IGNORECASE)
        if m:
            return f"{m.group(1)}/{m.group(2)} mod đang được cài"

        m = _re.match(r"^(\d+)\s*KB\s*/\s*(\d+)\s*KB$", label, _re.IGNORECASE)
        if m:
            return f"{m.group(1)}KB/{m.group(2)}KB đang được cài"

        if label:
            return f"{label} đang được cài"
        return "Đang xử lý..."

    def _toggle_progress_popup(self, event=None):
        if self._progress_popup is not None and self._progress_popup.winfo_exists():
            self._dong_progress_popup()
            return

        modpack_frame = self._view_frames.get("modpack")
        pct = getattr(modpack_frame, "_last_progress_pct", None) if modpack_frame else None
        if pct is None:
            return

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        sb = theme.sidebar_colors()
        bg_popup, border_popup = sb["bg_alt"], sb["accent"]
        fg_popup, fg_dim_popup = sb["text"], sb["text_dim"]
        popup.configure(bg=bg_popup)
        try:
            popup.attributes("-topmost", True)
        except tk.TclError:
            pass

        frame = tk.Frame(popup, bg=bg_popup, highlightbackground=border_popup,
                          highlightthickness=1, bd=0)
        frame.pack(fill="both", expand=True)

        lbl = tk.Label(
            frame, text=self._dinh_dang_chi_tiet_tien_do(
                getattr(modpack_frame, "_last_progress_label", "")),
            font=("Arial", 9, "bold"), bg=bg_popup, fg=fg_popup,
            padx=12, pady=8, justify="left")
        lbl.pack(side="left")

        btn_close = tk.Button(
            frame, text="✕", font=("Arial", 8, "bold"),
            bg=bg_popup, fg=fg_dim_popup, activebackground=sb["border"],
            activeforeground=fg_popup, relief="flat", bd=0, padx=6,
            command=self._dong_progress_popup)
        btn_close.pack(side="right", padx=(0, 6))

        self.root.update_idletasks()
        x = self.lbl_floating_progress.winfo_rootx()
        y = self.lbl_floating_progress.winfo_rooty() + self.lbl_floating_progress.winfo_height() + 4
        popup.geometry(f"+{x}+{y}")

        popup.bind("<FocusOut>", lambda e: self._dong_progress_popup())

        self._progress_popup = popup
        self._progress_popup_lbl = lbl
        popup.after(50, lambda: popup.focus_set())

    def _dong_progress_popup(self):
        if self._progress_popup is not None:
            try:
                self._progress_popup.destroy()
            except tk.TclError:
                pass
            self._progress_popup = None
            self._progress_popup_lbl = None

    def _poll_modpack_progress(self):
        try:
            if not self.root.winfo_exists():
                return
            modpack_frame = self._view_frames.get("modpack")
            pct = getattr(modpack_frame, "_last_progress_pct", None) if modpack_frame else None
            if pct is not None:
                label = getattr(modpack_frame, "_last_progress_label", "") or ""
                text = f"⬇ {pct}%"
                if label:
                    text += f" — {label}"
                self.lbl_floating_progress.config(text=text, cursor="hand2")
                if self._progress_popup is not None and self._progress_popup.winfo_exists():
                    try:
                        self._progress_popup_lbl.config(
                            text=self._dinh_dang_chi_tiet_tien_do(label))
                    except tk.TclError:
                        pass
            else:
                self.lbl_floating_progress.config(text="", cursor="")
                self._dong_progress_popup()
        except tk.TclError:
            return
        except Exception:
            pass
        try:
            self.root.after(500, self._poll_modpack_progress)
        except tk.TclError:
            pass

    def _xu_ly_thoat(self):
        import components.mod_mc as mod_mc
        if mod_mc.dang_cai_modpack():
            # modal.confirm() mo bat dong bo (khong block nhu askyesno cu)
            # nen phai hoan viec thoat that su vao on_confirm.
            self.modal.confirm(
                title="Đang tải modpack",
                message="Nếu thoát có thể bị lỗi dữ liệu. Có thoát không?",
                on_confirm=self._thuc_hien_thoat,
                confirm_text="Thoát",
                cancel_text="Ở lại",
            )
            return
        self._thuc_hien_thoat()

    def _thuc_hien_thoat(self):
        # 1. An cua so ngay lap tuc -> nguoi dung thay "da tat" tuc thi,
        #    khong phai cho destroy() don hang tram widget/anh o tab Mod.
        try:
            self.root.withdraw()
        except Exception:
            pass

        # CHU Y: KHONG tu dong terminate() self._game_process o day. Game
        # (Minecraft) duoc thiet ke chay doc lap voi launcher (xem
        # bat_dau_hoac_tat_game / _hien_lai_launcher: launcher tu an khi
        # dang choi va chi hien lai khi game tat), nen dong launcher khong
        # nen lam tat luon game dang choi cua nguoi dung. Neu ban MUON hanh
        # vi "dong launcher = tat luon game", noi minh de them lai co canh
        # bao/xac nhan rieng cho truong hop do.

        # 2. Luu cau hinh ngay (ghi file dong bo, khong doi UI)
        try:
            config.luu_toan_bo_cau_hinh()
        except Exception:
            pass

        # 3. Thoat cung, bo qua destroy() traversal cham cua Tk. An toan vi
        #    tat ca thread trong app (tai modpack, load anh, load version...)
        #    deu la daemon=True nen tu ket thuc theo process, va config vua
        #    duoc luu o buoc 2.
        try:
            self.root.quit()
        except Exception:
            pass
        os._exit(0)

    def khi_thay_doi_instance(self):
        if hasattr(self, 'instance_frame'):
            self.instance_frame.cap_nhat_nhan_thong_tin()
        # KHONG goi ap_dung_kich_thuoc_cua_so() o day: ham nay dung lam
        # callback moi khi doi tai khoan/instance (AccountFrame, InstanceFrame,
        # _lam_moi_instance_frame). Truoc day goi ca ap_dung_kich_thuoc_cua_so()
        # o day khien cua so bi ep ve dung kich thuoc da LUU trong config (vd
        # 1280x720) moi lan doi ten tai khoan hoac chon phien ban khac, du
        # nguoi dung vua tu keo to/nho cua so tay - mat het thay doi size vua
        # keo. Viec ap dung kich thuoc cua so chi can xay ra khi nguoi dung
        # thuc su bam Luu trong tab Cai dat (xem _khi_luu_setting ben duoi).
        self._cap_nhat_goi_y_phien_ban()
        self._cap_nhat_home_view()
        # Danh sach Instance vua thay doi (tao/xoa/sua chua...) - dong bo lai
        # ngay trang thai "Cai dat / Da cai dat" o tab Modpack/Mod/Resource
        # Pack/Shader (neu view do da duoc tao), khong doi den luc nguoi dung
        # tu loc/tim kiem lai moi thay dung. Truoc day, vd xoa 1 phien ban da
        # cai modpack thi tab Modpack van ghi "Da cai dat" cho toi khi loc lai.
        modpack_frame = self._view_frames.get("modpack") if hasattr(self, "_view_frames") else None
        if modpack_frame is not None and hasattr(modpack_frame, "refresh_all_installed_states"):
            try:
                modpack_frame.refresh_all_installed_states()
            except Exception:
                pass

    def mo_cua_so_setting(self):
        self._switch_view("settings")

    def mo_cua_so_modpack(self):
        self._switch_view("modpack")

    def _lam_moi_instance_frame(self):
        from components.instance_frame import InstanceFrame
        self.instance_frame.destroy()
        self.instance_frame = InstanceFrame(self._instance_holder, self.khi_thay_doi_instance, modal=self.modal)
        self.instance_frame.pack(fill="x")
        self._lam_toi_mau_sidebar()
        self._cap_nhat_goi_y_phien_ban()
        self._cap_nhat_home_view()

    def hien_thi_progress(self, hien=True):
        if hien:
            self.frame_progress.pack(fill="x", padx=14, pady=(0, 2), before=self.lbl_version_hint)
            self.lbl_progress.pack(pady=(0, 2), before=self.lbl_version_hint)
        else:
            self.frame_progress.pack_forget()
            self.lbl_progress.pack_forget()
            self.progress_bar["value"] = 0
            self.lbl_progress.config(text="")

    def cap_nhat_progress(self, phan_tram: float, mo_ta: str = ""):
        self.root.after(0, lambda: self._cap_nhat_progress_ui(phan_tram, mo_ta))

    def _cap_nhat_progress_ui(self, phan_tram, mo_ta: str):
        if phan_tram is not None:
            self.progress_bar["value"] = max(0.0, min(100.0, phan_tram))
        if mo_ta:
            self.lbl_progress.config(text=mo_ta)

    def _khoa_ui(self):
        self.account_frame.khoa(True)
        self.instance_frame.khoa(True)

    def _mo_khoa_ui(self):
        self.account_frame.khoa(False)
        self.instance_frame.khoa(False)

    def _an_launcher_khi_choi(self):
        try:
            if config.current_config.get("an_launcher_khi_choi", True):
                self.root.withdraw()
        except Exception:
            pass

    def _hien_lai_launcher(self):
        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass

    def bat_dau_hoac_tat_game(self):
        if self._dang_tai:
            self._huy_tai = True
            self.btn_launch.config(state="disabled", text="⏳ Đang hủy...")
            self.lbl_status.config(text="Đang hủy tải xuống...", fg="#E53935")
            return
        if self._game_process is not None and self._game_process.poll() is None:
            try:
                self._game_process.terminate()
            except Exception:
                pass
            self._game_process = None
            self.btn_launch.config(text="▶ CHƠI", bg="#1E88E5", state="normal")
            self.lbl_status.config(text="Đã tắt game.", fg=self._SB_TEXT_DIM)
            self._hien_lai_launcher()
            return
        self.bat_dau_chay_game()

    def bat_dau_chay_game(self):
        tai_khoan = self.account_frame.get_current_account()
        if not tai_khoan:
            self.modal.alert("Chú ý", "Vui lòng chọn hoặc thêm tài khoản trước khi chơi!")
            return

        self._dang_tai = True
        self.btn_launch.config(state="normal", text="🟥 HỦY", bg="#E53935")
        self.lbl_status.config(text="Đang chuẩn bị dữ liệu game...", fg="#1E88E5")
        self.hien_thi_progress(True)
        self._khoa_ui()

        def luong_khoi_dong():
            try:
                ten_instance = self.instance_frame.get_current_instance()
                if self._huy_tai:
                    self._dang_tai = False
                    self._huy_tai = False
                    self.root.after(0, lambda: self.btn_launch.config(text="▶ CHƠI", bg="#1E88E5", state="normal"))
                    self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg=self._SB_TEXT_DIM))
                    self.root.after(0, lambda: self.hien_thi_progress(False))
                    self.root.after(0, self._mo_khoa_ui)
                    return
                thu_muc_game = config.current_config.get("thu_muc_game")

                proc = core.chay_game_minecraft(tai_khoan, ten_instance, thu_muc_game, self.lbl_status, self.cap_nhat_progress, lambda: self._huy_tai)
                self._game_process = proc

                self._dang_tai = False
                self._huy_tai = False
                self.root.after(0, lambda: self.btn_launch.config(
                    state="normal", text="⏹ TẮT GAME", bg="#E53935"))
                self.root.after(0, lambda: self.lbl_status.config(
                    text="Minecraft đang chạy...", fg="#2E7D32"))
                self.root.after(0, lambda: self.hien_thi_progress(False))
                self.root.after(0, self._mo_khoa_ui)

                if proc:
                    self.root.after(0, self._an_launcher_khi_choi)

                    def _stream_log(p):
                        try:
                            for line in p.stdout:
                                self.root.after(0, lambda l=line: self.console.append(l))
                        except Exception:
                            pass

                    if proc.stdout:
                        threading.Thread(target=_stream_log, args=(proc,), daemon=True).start()

                    proc.wait()

                    self._game_process = None
                    self.root.after(0, lambda: self.btn_launch.config(
                        text="▶ CHƠI", bg="#1E88E5", state="normal"))
                    self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg=self._SB_TEXT_DIM))
                    self.root.after(0, self._mo_khoa_ui)
                    self.root.after(0, self._hien_lai_launcher)
                else:
                    self._game_process = None
                    self.root.after(0, lambda: self.btn_launch.config(
                        text="▶ CHƠI", bg="#1E88E5", state="normal"))
                    self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg=self._SB_TEXT_DIM))
                    self.root.after(0, self._mo_khoa_ui)

            except Exception as e:
                loi = str(e)
                self._game_process = None
                self.root.after(0, lambda: self.modal.alert("Lỗi", f"Khởi động game thất bại:\n{loi}"))
                self._dang_tai = False
                self._huy_tai = False
                self.root.after(0, lambda: self.btn_launch.config(
                    text="▶ CHƠI", bg="#1E88E5", state="normal"))
                self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg=self._SB_TEXT_DIM))
                self.root.after(0, lambda: self.hien_thi_progress(False))
                self.root.after(0, self._mo_khoa_ui)
                self.root.after(0, self._hien_lai_launcher)

        threading.Thread(target=luong_khoi_dong, daemon=True).start()

def main():
    """Diem khoi dong chinh cua launcher.

    Tach thanh ham rieng (thay vi de thang trong khoi __main__) de cac entry
    point khac (vi du run_app.py) co the import va goi lai duoc, thay vi phai
    exec nguyen file main.py.
    """
    root = tk.Tk()
    root.withdraw()
    # An hoan toan (alpha 0) truoc khi build UI: mot so may/Windows van ve
    # 1 khung mac dinh trong khoanh khac deiconify() du withdraw() dung,
    # alpha 0 dam bao khong co gi hien ra cho toi khi ta chu dong set lai
    # alpha = 1 (sau khi UI da san sang).
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass

    # Doc + set size/vi tri giua man hinh NGAY, TRUOC khi build bat ky
    # widget nao. Lam som nhu vay thi khi deiconify(), cua so hien ra da
    # dung kich thuoc + vi tri tu dau, khong phai center/resize lai lan
    # nua (tranh flash size mac dinh nho roi nhay ve dung cho).
    rong_cs, cao_cs = MinecraftLauncherApp._doc_kich_thuoc_cua_so()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x, y = (sw - rong_cs) // 2, (sh - cao_cs) // 2
    root.geometry(f"{rong_cs}x{cao_cs}+{x}+{y}")
    root.minsize(min(800, rong_cs), min(600, cao_cs))

    theme.preload_combobox_options(root)

    _doc_cau_hinh_may()
    kiem_tra_va_chay_wizard(root)

    thu_muc = config.current_config.get("thu_muc_game", "").strip()
    if thu_muc:
        config.cap_nhat_duong_dan_config(thu_muc)

    try:
        app = MinecraftLauncherApp(root)
        root.app = app

        # Cua so van dang withdraw()+alpha 0 trong luc MinecraftLauncherApp
        # build xong UI. Chi hien ra (alpha 1 + deiconify) SAU KHI da xong,
        # de tranh flash 1 cua so rong/mac dinh truoc khi UI ve xong.
        root.update_idletasks()
        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass
        root.deiconify()
        root.lift()
        root.focus_force()
    except Exception:
        import sys; sys.exit(0)

    root.mainloop()


if __name__ == "__main__":
    main()
