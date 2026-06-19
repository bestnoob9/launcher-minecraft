import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import sys

import config
import core
import theme
from icon_utils import gan_icon_app as _gan_icon_app
from components.account_frame import AccountFrame
from components.instance_frame import InstanceFrame
from components.setting_window import SettingWindow
from components.mod_mc import ModMcWindow
from setup_wizard import kiem_tra_va_chay_wizard


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
            #print(f"[System] Doc RAM bang psutil: {total_mb} MB")
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
                #print(f"[System] Doc RAM bang ctypes/WinAPI: {total_mb} MB")
        except Exception as e:
            print(f"[System] ctypes that bai: {e}")

    if total_mb is None:
        try:
            import wmi
            c = wmi.WMI()
            tong = sum(int(cs.TotalPhysicalMemory) for cs in c.Win32_ComputerSystem())
            if tong > 0:
                total_mb = tong // (1024 * 1024)
                #print(f"[System] Doc RAM bang wmi: {total_mb} MB")
        except Exception as e:
            print(f"[System] wmi that bai: {e}")

    if total_mb and total_mb > 0:
        info["ram_total_mb"] = total_mb
        info["ram_total_gb"] = _lam_tron_ram_gb(total_mb)
    else:
        print("[System] lỗi à ko thấy ram, dùng tạm 8 GB.")

    config.current_config["_system_info"] = info

class ConsoleWindow(tk.Toplevel):
    # Màu cố định, không bị theme ghi đè
    _BG_MAIN   = "#1e1e1e"
    _BG_BAR    = "#2d2d2d"
    _BG_BTN    = "#3c3c3c"
    _FG_TEXT   = "#d4d4d4"
    _FG_COUNT  = "#888888"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Console — Minecraft Log")
        self.geometry("780x420")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        _gan_icon_app(self)

        # Đặt màu nền cửa sổ cố định
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

        # Chống theme ghi đè: khôi phục màu mỗi khi cửa sổ được hiển thị
        self.bind("<Map>", self._restore_colors)

        self.withdraw()

    def _restore_colors(self, event=None):
        """Khôi phục màu cố định sau khi theme có thể đã thay đổi."""
        try:
            self.configure(bg=self._BG_MAIN)
            self.txt.configure(bg=self._BG_MAIN, fg=self._FG_TEXT)
            self._btn_clear.configure(bg=self._BG_BTN, fg="white",
                                      activebackground="#555", activeforeground="white")
            self.lbl_count.configure(bg=self._BG_BAR, fg=self._FG_COUNT)
            # Tìm btn_frame qua parent của lbl_count
            bf = self.lbl_count.master
            if bf:
                bf.configure(bg=self._BG_BAR)
        except Exception:
            pass
    def append(self, text):
        """Thêm text vào console (thread-safe qua after)."""
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
    def __init__(self, root):
        self.root = root
        self.root.title("Bacontete MCL")
        self.root.geometry("480x520")
        self.root.minsize(480, 520)
        self.root.resizable(True, True)
        _gan_icon_app(self.root)

        config.current_config = config.tai_toan_bo_cau_hinh()
        self._game_process = None
        self._dang_tai = False
        self._huy_tai = False

        self.console = ConsoleWindow(root)
        self.create_widgets()
        theme.apply_theme(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._xu_ly_thoat)

    def create_widgets(self):
        lbl_main_title = tk.Label(self.root, text="Bacontete MCL", font=("Arial", 16, "bold"), fg="#1E88E5")
        lbl_main_title.pack(pady=(20, 15))

        self.account_frame = AccountFrame(self.root, self.khi_thay_doi_instance)
        self.account_frame.pack(pady=10)

        self.instance_frame = InstanceFrame(self.root, self.khi_thay_doi_instance)
        self.instance_frame.pack(pady=10)

        self.lbl_status = tk.Label(self.root, text="Sẵn sàng", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_status.pack(pady=(5, 2))

        self.frame_progress = tk.Frame(self.root)
        self.frame_progress.pack(fill="x", padx=40, pady=(0, 4))

        self.progress_bar = ttk.Progressbar(
            self.frame_progress,
            orient="horizontal",
            mode="determinate",
            length=400
        )
        self.progress_bar.pack(fill="x")

        self.lbl_progress = tk.Label(
            self.root, text="", font=("Arial", 8), fg="#555"
        )
        self.lbl_progress.pack(pady=(0, 2))

        self.frame_progress.pack_forget()
        self.lbl_progress.pack_forget()

        self.btn_launch = tk.Button(
            self.root,
            text="▶ VÀO GAME",
            font=("Arial", 12, "bold"),
            bg="#1E88E5",
            fg="white",
            width=18,
            height=2,
            command=self.bat_dau_hoac_tat_game
        )
        self.btn_launch.pack(pady=(10, 8))

        toolbar = tk.Frame(self.root)
        toolbar.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        left = tk.Frame(toolbar)
        left.pack(side="left")

        self.btn_open_folder = tk.Button(
            left,
            text="📂 Thư mục",
            font=("Arial", 9, "bold"),
            bg="#43A047",
            fg="white",
            padx=8, pady=3,
            command=self.mo_thu_muc_game
        )
        self.btn_open_folder.pack(side="left")

        right = tk.Frame(toolbar)
        right.pack(side="right")

        self.btn_modpack = tk.Button(
            right,
            text="🧩 Modpack",
            font=("Arial", 9, "bold"),
            bg="#5C6BC0",
            fg="white",
            padx=8, pady=3,
            command=self.mo_cua_so_modpack
        )
        self.btn_modpack.pack(side="left", padx=(0, 4))

        self.btn_console = tk.Button(
            right,
            text="🖥 Console",
            font=("Arial", 9, "bold"),
            bg="#37474F",
            fg="white",
            padx=8, pady=3,
            command=self.console.show
        )
        self.btn_console.pack(side="left", padx=(0, 4))

        self.btn_setting = tk.Button(
            right,
            text="⚙️ Settings",
            font=("Arial", 9, "bold"),
            bg="#607D8B",
            fg="white",
            padx=8, pady=3,
            command=self.mo_cua_so_setting
        )
        self.btn_setting.pack(side="left")

    def mo_thu_muc_game(self):
        import subprocess, sys
        thu_muc = config.current_config.get("thu_muc_game", "").strip()
        if not thu_muc or not os.path.exists(thu_muc):
            messagebox.showwarning("Chú ý", "Chưa có thư mục game hoặc thư mục không tồn tại!\nVui lòng kiểm tra lại trong Settings.")
            return
        if sys.platform == "win32":
            os.startfile(thu_muc)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", thu_muc])
        else:
            subprocess.Popen(["xdg-open", thu_muc])

    def _xu_ly_thoat(self):
        import components.mod_mc as mod_mc
        if mod_mc.dang_cai_modpack():
            chon = messagebox.askyesno(
                "Đang tải modpack",
                "Nếu thoát có thể bị lỗi dữ liệu.Có thoát ko?",
                icon="warning"
            )
            if not chon:
                return
        self.root.destroy()

    def khi_thay_doi_instance(self):
        if hasattr(self, 'instance_frame'):
            self.instance_frame.cap_nhat_nhan_thong_tin()

    def mo_cua_so_setting(self):
        SettingWindow(self.root, self.khi_thay_doi_instance)

    def mo_cua_so_modpack(self):
        ModMcWindow(self.root, self._lam_moi_instance_frame)

    def _lam_moi_instance_frame(self):
        from components.instance_frame import InstanceFrame
        self.instance_frame.destroy()
        self.instance_frame = InstanceFrame(self.root, self.khi_thay_doi_instance)
        self.instance_frame.pack(pady=10)
        self.instance_frame.pack_configure(after=self.account_frame)
        theme.apply_theme(self.instance_frame)

    def hien_thi_progress(self, hien=True):
        """Hien / an khu vuc thanh tien do."""
        if hien:
            self.frame_progress.pack(fill="x", padx=40, pady=(0, 2),
                                     after=self.btn_launch)
            self.lbl_progress.pack(pady=(0, 4), after=self.frame_progress)
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
            self.btn_launch.config(text="▶ VÀO GAME", bg="#1E88E5", state="normal")
            self.lbl_status.config(text="Đã tắt game.", fg="gray")
            return
        self.bat_dau_chay_game()

    def bat_dau_chay_game(self):
        tai_khoan = self.account_frame.get_current_account()
        if not tai_khoan:
            messagebox.showwarning("Chú ý", "Vui lòng chọn hoặc thêm tài khoản trước khi chơi!")
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
                    self.root.after(0, lambda: self.btn_launch.config(text="▶ VÀO GAME", bg="#1E88E5", state="normal"))
                    self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg="gray"))
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
                        text="▶ VÀO GAME", bg="#1E88E5", state="normal"))
                    self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg="gray"))
                    self.root.after(0, self._mo_khoa_ui)
                else:
                    self._game_process = None
                    self.root.after(0, lambda: self.btn_launch.config(
                        text="▶ VÀO GAME", bg="#1E88E5", state="normal"))
                    self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg="gray"))
                    self.root.after(0, self._mo_khoa_ui)

            except Exception as e:
                loi = str(e)
                self._game_process = None
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Khởi động game thất bại:\n{loi}"))
                self._dang_tai = False
                self._huy_tai = False
                self.root.after(0, lambda: self.btn_launch.config(
                    text="▶ VÀO GAME", bg="#1E88E5", state="normal"))
                self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg="gray"))
                self.root.after(0, lambda: self.hien_thi_progress(False))
                self.root.after(0, self._mo_khoa_ui)

        threading.Thread(target=luong_khoi_dong, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    theme.preload_combobox_options(root)

    _doc_cau_hinh_may()
    kiem_tra_va_chay_wizard(root)

    try:
        root.deiconify()
    except Exception:
        import sys; sys.exit(0)

    app = MinecraftLauncherApp(root)
    root.app = app
    root.mainloop()