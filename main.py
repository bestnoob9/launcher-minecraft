import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os

import config
import core
from components.account_frame import AccountFrame
from components.instance_frame import InstanceFrame
from components.setting_window import SettingWindow
from components.mod_mc import ModMcWindow
from setup_wizard import kiem_tra_va_chay_wizard   # <-- import wizard


def _doc_cau_hinh_may():
    """
    Doc dung luong RAM vat ly mot lan khi khoi dong.
    Luu vao config.current_config["_system_info"] de cac module khac dung.
    Khong luu xuong file (chi luu trong bo nho phien lam viec).
    Thu tu uu tien: psutil -> ctypes (Windows) -> wmi (Windows) -> fallback.
    """
    import math

    def _lam_tron_ram_gb(total_mb):
        """Lam tron MB sang GB theo cac moc thuong gap: 4/8/12/16/24/32/48/64/128."""
        cac_moc = [4, 8, 12, 16, 24, 32, 48, 64, 128]
        total_gb_thuc = total_mb / 1024
        for moc in cac_moc:
            # Neu nam trong khoang 85% cua moc do thi lam tron len
            if total_gb_thuc <= moc * 1.05:
                return moc
        return math.ceil(total_gb_thuc)

    info = {
        "ram_total_mb": 8192,   # fallback cuoi cung
        "ram_total_gb": 8,
    }

    total_mb = None

    # --- Phuong phap 1: psutil (da nen tang) ---
    try:
        import psutil
        total_bytes = psutil.virtual_memory().total
        if total_bytes > 0:
            total_mb = total_bytes // (1024 * 1024)
            #print(f"[System] Doc RAM bang psutil: {total_mb} MB")
    except Exception as e:
        print(f"[System] psutil that bai: {e}")

    # --- Phuong phap 2: ctypes Windows (GlobalMemoryStatusEx) ---
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
                print(f"[System] Doc RAM bang ctypes/WinAPI: {total_mb} MB")
        except Exception as e:
            print(f"[System] ctypes that bai: {e}")

    # --- Phuong phap 3: wmi (Windows) ---
    if total_mb is None:
        try:
            import wmi
            c = wmi.WMI()
            tong = sum(int(cs.TotalPhysicalMemory) for cs in c.Win32_ComputerSystem())
            if tong > 0:
                total_mb = tong // (1024 * 1024)
                print(f"[System] Doc RAM bang wmi: {total_mb} MB")
        except Exception as e:
            print(f"[System] wmi that bai: {e}")

    # --- Ap dung ket qua ---
    if total_mb and total_mb > 0:
        info["ram_total_mb"] = total_mb
        info["ram_total_gb"] = _lam_tron_ram_gb(total_mb)
    else:
        print("[System] Khong doc duoc RAM thuc te, dung fallback 8 GB.")

    config.current_config["_system_info"] = info
    #print(f"[System] RAM phat hien: {info['ram_total_gb']} GB ({info['ram_total_mb']} MB)")

class ConsoleWindow(tk.Toplevel):
    """Cửa sổ hiển thị stdout/stderr từ Minecraft process."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Console — Minecraft Log")
        self.geometry("780x420")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)  # Ẩn thay vì đóng hẳn

        self.txt = tk.Text(self, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                           wrap="word", state="disabled", relief="flat", bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self, bg="#2d2d2d")
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="Xóa log", font=("Arial", 8),
                  bg="#3c3c3c", fg="white", relief="flat", padx=8,
                  command=self.clear).pack(side="left", padx=4, pady=4)
        self.lbl_count = tk.Label(btn_frame, text="0 dòng", font=("Arial", 8),
                                  bg="#2d2d2d", fg="#888")
        self.lbl_count.pack(side="right", padx=8)

        self._line_count = 0
        self.withdraw()  # Ẩn lúc đầu

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
        self.root.title("Minecraft Launcher")
        self.root.geometry("480x520")
        self.root.resizable(False, False)

        config.current_config = config.tai_toan_bo_cau_hinh()
        self._game_process = None
        self._dang_tai = False
        self._huy_tai = False

        self.console = ConsoleWindow(root)
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._xu_ly_thoat)

    def create_widgets(self):
        lbl_main_title = tk.Label(self.root, text="MINECRAFT LAUNCHER", font=("Arial", 16, "bold"), fg="#1E88E5")
        lbl_main_title.pack(pady=(20, 15))

        self.account_frame = AccountFrame(self.root, self.khi_thay_doi_instance)
        self.account_frame.pack(pady=10)

        self.instance_frame = InstanceFrame(self.root, self.khi_thay_doi_instance)
        self.instance_frame.pack(pady=10)

        self.btn_delete_instance = tk.Button(
            self.root,
            text="❌ Xóa phiên bản đang chọn",
            font=("Arial", 10, "bold"),
            bg="#E53935",
            fg="white",
            pady=3,
            command=self.xoa_instance_hien_tai
        )
        self.btn_delete_instance.pack(pady=10)

        self.lbl_status = tk.Label(self.root, text="Sẵn sàng", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_status.pack(pady=(5, 2))

        # --- Thanh tiến độ tải xuống ---
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

        # Ẩn thanh tiến độ ban đầu
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
        self.btn_launch.pack(pady=(10, 20))

        self.btn_console = tk.Button(
            self.root,
            text="🖥 Console",
            font=("Arial", 9, "bold"),
            bg="#37474F",
            fg="white",
            padx=8,
            pady=3,
            command=self.console.show
        )
        self.btn_console.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-40)

        self.btn_setting = tk.Button(
            self.root,
            text="⚙️ Settings",
            font=("Arial", 9, "bold"),
            bg="#607D8B",
            fg="white",
            padx=8,
            pady=3,
            command=self.mo_cua_so_setting
        )
        self.btn_setting.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.btn_modpack = tk.Button(
            self.root,
            text="🧩 Modpack",
            font=("Arial", 9, "bold"),
            bg="#5C6BC0",
            fg="white",
            padx=8,
            pady=3,
            command=self.mo_cua_so_modpack
        )
        self.btn_modpack.place(relx=1.0, rely=1.0, anchor="se", x=-95, y=-10)

        self.btn_open_folder = tk.Button(
            self.root,
            text="📂 Thư mục game",
            font=("Arial", 9, "bold"),
            bg="#43A047",
            fg="white",
            padx=8,
            pady=3,
            command=self.mo_thu_muc_game
        )
        self.btn_open_folder.place(relx=0.0, rely=1.0, anchor="sw", x=10, y=-10)

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
                "Dang tai modpack",
                "Modpack dang duoc cai dat!Neu thoat bay gio, du lieu co the bi hong.Ban co chac muon thoat khong?",
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

    def xoa_instance_hien_tai(self):
        ten_instance = self.instance_frame.get_current_instance()

        if ten_instance == "Latest Version":
            messagebox.showwarning("Chú ý", "Không thể xóa phiên bản mặc định hệ thống!")
            return

        xac_nhan = messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa hoàn toàn phiên bản '{ten_instance}'?")
        if xac_nhan:
            if ten_instance in config.current_config["danh_sach_instances"]:
                del config.current_config["danh_sach_instances"][ten_instance]

            config.current_config["current_instance"] = "Latest Version"
            config.luu_toan_bo_cau_hinh()

            ten_folder = ten_instance.replace(" ", "_")
            duong_dan_folder = os.path.join(self.instance_frame.thu_muc_instances, ten_folder)
            if os.path.exists(duong_dan_folder):
                try:
                    import shutil
                    shutil.rmtree(duong_dan_folder)
                except Exception as e:
                    print(f"Không thể xóa thư mục vật lý: {e}")

            messagebox.showinfo("Thành công", f"Đã xóa phiên bản: {ten_instance}")

            self.instance_frame.destroy()
            self.instance_frame = InstanceFrame(self.root, self.khi_thay_doi_instance)
            self.instance_frame.pack(pady=10)
            self.instance_frame.pack_configure(after=self.account_frame)

    def hien_thi_progress(self, hien=True):
        """Hien / an khu vuc thanh tien do."""
        if hien:
            # Hien thanh progress sau btn_launch
            self.frame_progress.pack(fill="x", padx=40, pady=(0, 2),
                                     after=self.btn_launch)
            self.lbl_progress.pack(pady=(0, 4), after=self.frame_progress)
        else:
            self.frame_progress.pack_forget()
            self.lbl_progress.pack_forget()
            self.progress_bar["value"] = 0
            self.lbl_progress.config(text="")

    def cap_nhat_progress(self, phan_tram: float, mo_ta: str = ""):
        """
        Callback truyen vao core.chay_game_minecraft de cap nhat tien do.
        phan_tram: 0.0 -> 100.0
        mo_ta    : chuoi hien thi ben duoi thanh (ten file dang tai, ...)
        """
        self.root.after(0, lambda: self._cap_nhat_progress_ui(phan_tram, mo_ta))

    def _cap_nhat_progress_ui(self, phan_tram, mo_ta: str):
        # phan_tram=None nghia la chi cap nhat text, khong doi thanh keo
        if phan_tram is not None:
            self.progress_bar["value"] = max(0.0, min(100.0, phan_tram))
        if mo_ta:
            self.lbl_progress.config(text=mo_ta)

    def _khoa_ui(self):
        """Khóa toàn bộ UI khi game đang tải/chạy."""
        # Khóa chọn tài khoản
        self.account_frame.khoa(True)
        # Khóa chọn/thêm/xóa/đổi tên phiên bản
        self.instance_frame.khoa(True)
        self.btn_delete_instance.config(state="disabled")

    def _mo_khoa_ui(self):
        """Mở khóa toàn bộ UI khi game dừng."""
        self.account_frame.khoa(False)
        self.instance_frame.khoa(False)
        self.btn_delete_instance.config(state="normal")

    def bat_dau_hoac_tat_game(self):
        # Dang tai -> huy tai
        if self._dang_tai:
            self._huy_tai = True
            self.btn_launch.config(state="disabled", text="⏳ Đang hủy...")
            self.lbl_status.config(text="Đang hủy tải xuống...", fg="#E53935")
            return
        # Dang chay game -> tat game
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

                if proc:
                    # Stream stdout/stderr vào console
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

    _doc_cau_hinh_may()       # Đọc RAM/CPU/GPU thực tế trước khi mở bất kỳ cửa sổ nào
    kiem_tra_va_chay_wizard(root)

    try:
        root.deiconify()
    except Exception:
        # root bị hủy (người dùng tắt wizard) — thoát bình thường
        import sys; sys.exit(0)

    app = MinecraftLauncherApp(root)
    root.app = app
    root.mainloop()