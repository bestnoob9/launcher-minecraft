import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import config

class SettingWindow(tk.Toplevel):
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.title("Cài đặt cấu hình")
        self.geometry("460x640")  # Chiều cao tăng để vừa thanh kéo RAM + JVM Arguments
        self.resizable(False, False)
        self.grab_set()  # Khóa màn hình chính khi đang mở setting
        
        self.on_save_callback = on_save_callback
        
        # Tạo bản đồ ánh xạ hiển thị tiếng Việt sang mã cài đặt lưu trong JSON
        self.preset_options = {
            "Tối ưu hóa toàn diện (Khuyên dùng)": "aikar_optimized",
            "Dành cho máy yếu / Ít RAM": "low_end",
            "Tải Chunk nhanh / Giảm giật hình": "chunk_loading_heavy",
            "Chơi Modpack nặng (Nhiều Mods)": "heavy_modded",
            "Siêu mượt Real-time (Shenandoah GC)": "shenandoah_ultra"
        }
        
        self.create_widgets()

    def create_widgets(self):
        # 1. CÀI ĐẶT ĐƯỜNG DẪN GAME
        lbl_path_title = tk.Label(self, text="Thư mục game (Minecraft Path):", font=("Arial", 10, "bold"))
        lbl_path_title.pack(anchor="w", padx=20, pady=(15, 2))
        
        frame_path = tk.Frame(self)
        frame_path.pack(fill="x", padx=20)
        
        self.ent_path = tk.Entry(frame_path, font=("Arial", 10), width=35)
        self.ent_path.pack(side=tk.LEFT, ipady=2, fill="x", expand=True)
        self.ent_path.insert(0, config.current_config.get("thu_muc_game", ""))
        
        btn_browse = tk.Button(frame_path, text="Chọn...", font=("Arial", 9), command=self.chon_duong_dan)
        btn_browse.pack(side=tk.LEFT, padx=5)

        # 2. CÀI ĐẶT RAM JVM — Thanh kéo đơn, giới hạn theo RAM máy
        lbl_ram_title = tk.Label(self, text="Bộ Nhớ Sử Dụng:", font=("Arial", 10, "bold"))
        lbl_ram_title.pack(anchor="w", padx=20, pady=(15, 2))

        frame_ram = tk.Frame(self)
        frame_ram.pack(fill="x", padx=20)

        # --- Đọc RAM vật lý từ _system_info (đã đọc 1 lần khi khởi động) ---
        _sys = config.current_config.get("_system_info", {})
        _total_mb = _sys.get("ram_total_mb", 0)
        _gb       = _sys.get("ram_total_gb", 0)

        # Nếu _system_info chưa được đọc (lần đầu hoặc không có psutil), tự đọc lại
        if not _total_mb or _total_mb < 1024:
            import math

            def _lam_tron_ram_gb(total_mb):
                """Lam tron sang moc GB thuong gap thay vi math.ceil don thuan."""
                cac_moc = [4, 8, 12, 16, 24, 32, 48, 64, 128]
                total_gb_thuc = total_mb / 1024
                for moc in cac_moc:
                    if total_gb_thuc <= moc * 1.05:
                        return moc
                return math.ceil(total_gb_thuc)

            _total_mb = 0

            # Phuong phap 1: psutil
            try:
                import psutil
                _total_mb = psutil.virtual_memory().total // (1024 * 1024)
            except Exception as e:
                print(f"[SettingWindow] psutil that bai: {e}")

            # Phuong phap 2: ctypes WinAPI (khong can thu vien ngoai)
            if not _total_mb:
                try:
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength",                 ctypes.c_ulong),
                            ("dwMemoryLoad",             ctypes.c_ulong),
                            ("ullTotalPhys",             ctypes.c_ulonglong),
                            ("ullAvailPhys",             ctypes.c_ulonglong),
                            ("ullTotalPageFile",         ctypes.c_ulonglong),
                            ("ullAvailPageFile",         ctypes.c_ulonglong),
                            ("ullTotalVirtual",          ctypes.c_ulonglong),
                            ("ullAvailVirtual",          ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(stat)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    if stat.ullTotalPhys > 0:
                        _total_mb = stat.ullTotalPhys // (1024 * 1024)
                except Exception as e:
                    print(f"[SettingWindow] ctypes that bai: {e}")

            if not _total_mb:
                _total_mb = 8192  # fallback cuoi cung

            _gb = _lam_tron_ram_gb(_total_mb)
            # Luu lai vao _system_info de lan sau khong phai doc lai
            config.current_config["_system_info"] = {
                "ram_total_mb": _total_mb,
                "ram_total_gb": _gb,
            }
            print(f"[SettingWindow] Doc lai RAM: {_gb} GB ({_total_mb} MB)")

        RAM_STEP   = 256
        RAM_MIN_MB = 512
        # Giới hạn tối đa = RAM thực tế - 2GB dành cho HĐH (tối thiểu 1GB)
        RAM_MAX_MB = max(1024, _total_mb - 2048)

        # --- Hàm tiện ích ---
        def parse_ram_to_mb(s):
            s = str(s).strip().upper().replace(" ", "")
            if s.endswith("GB"): return int(float(s[:-2]) * 1024)
            elif s.endswith("MB"): return int(s[:-2])
            elif s.endswith("G"): return int(float(s[:-1]) * 1024)
            elif s.endswith("M"): return int(s[:-1])
            try: return int(s)
            except: return 2048

        def mb_to_display(mb):
            if mb >= 1024 and mb % 1024 == 0:
                return f"{mb // 1024} GB"
            elif mb >= 1024:
                return f"{mb / 1024:.1f} GB"
            return f"{mb} MB"

        def mb_to_step(mb):
            return round((mb - RAM_MIN_MB) / RAM_STEP)

        def step_to_mb(step):
            return RAM_MIN_MB + int(step) * RAM_STEP

        num_steps = (RAM_MAX_MB - RAM_MIN_MB) // RAM_STEP

        # Tải giá trị đã lưu, clamp vào [min, max máy thực tế]
        saved_mb = parse_ram_to_mb(config.current_config.get("ram_max", "2GB"))
        saved_mb = max(RAM_MIN_MB, min(RAM_MAX_MB, saved_mb))

        # --- Hàng thanh kéo + ô MiB + Auto ---
        frame_slider_row = tk.Frame(frame_ram)
        frame_slider_row.pack(fill="x", pady=(4, 0))

        self.sld_ram = tk.Scale(
            frame_slider_row,
            from_=0, to=num_steps,
            orient=tk.HORIZONTAL,
            showvalue=False,
            sliderlength=16,
            troughcolor="#4A90D9",
            activebackground="#1E88E5",
            bg=self.cget("bg"),
            highlightthickness=0,
            bd=0
        )
        self.sld_ram.set(mb_to_step(saved_mb))
        self.sld_ram.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 6))

        self.var_ram_mib = tk.StringVar(value=str(saved_mb))
        self.ent_ram_mib = tk.Entry(
            frame_slider_row, textvariable=self.var_ram_mib,
            font=("Arial", 9), width=6, justify="center", relief="groove"
        )
        self.ent_ram_mib.pack(side=tk.LEFT, padx=(0, 2))
        tk.Label(frame_slider_row, text="MiB", font=("Arial", 9), fg="#555").pack(side=tk.LEFT, padx=(0, 8))

        # Checkbox Auto
        self.var_ram_auto = tk.BooleanVar(value=config.current_config.get("ram_auto", False))
        chk_auto = tk.Checkbutton(
            frame_slider_row, text="Auto",
            variable=self.var_ram_auto, font=("Arial", 9),
            command=lambda: khi_thay_doi_auto()
        )
        chk_auto.pack(side=tk.LEFT)

        # --- Đồng bộ thanh kéo <-> ô nhập ---
        def khi_keo_ram(val):
            self.var_ram_mib.set(str(step_to_mb(int(float(val)))))

        self.sld_ram.config(command=khi_keo_ram)

        def khi_nhap_mib(event=None):
            try:
                mb = int(self.var_ram_mib.get().strip())
                mb = max(RAM_MIN_MB, min(RAM_MAX_MB, mb))
                self.sld_ram.set(mb_to_step(mb))
            except ValueError:
                pass

        self.ent_ram_mib.bind("<Return>", khi_nhap_mib)
        self.ent_ram_mib.bind("<FocusOut>", khi_nhap_mib)

        def khi_thay_doi_auto():
            if self.var_ram_auto.get():
                # Auto: 50% RAM vật lý, tối thiểu 2 GB
                auto_mb = max(2048, min(RAM_MAX_MB // 2, RAM_MAX_MB))
                auto_mb = round(auto_mb / RAM_STEP) * RAM_STEP
                self.sld_ram.set(mb_to_step(auto_mb))
                self.var_ram_mib.set(str(auto_mb))
                self.sld_ram.config(state="disabled")
                self.ent_ram_mib.config(state="disabled")
            else:
                self.sld_ram.config(state="normal")
                self.ent_ram_mib.config(state="normal")

        khi_thay_doi_auto()

        # --- Nhãn mốc tick theo RAM máy thực tế ---
        # Chia đều các mốc GB từ 0 đến RAM_MAX
        canvas_ticks = tk.Canvas(frame_ram, height=14, bg=self.cget("bg"), highlightthickness=0)
        canvas_ticks.pack(fill="x", pady=(0, 4))

        def ve_tick_labels(event=None):
            canvas_ticks.delete("all")
            w = canvas_ticks.winfo_width()
            if w < 10:
                return
            # Tạo nhãn theo từng GB từ 1 GB đến RAM_MAX
            mocs = []
            gb = _gb
            step_gb = max(1, gb // 6)  # tối đa ~6 nhãn
            cur = step_gb
            while cur * 1024 <= RAM_MAX_MB:
                mocs.append(cur * 1024)
                cur += step_gb
            if not mocs or mocs[-1] < RAM_MAX_MB:
                mocs.append(RAM_MAX_MB)

            for i, mb_val in enumerate(mocs):
                pct = (mb_val - RAM_MIN_MB) / (RAM_MAX_MB - RAM_MIN_MB)
                x   = int(pct * w)
                lbl = f"{mb_val // 1024}G"
                anchor = "nw" if i == 0 else ("ne" if i == len(mocs) - 1 else "n")
                canvas_ticks.create_text(x, 2, text=lbl, anchor=anchor,
                                         font=("Arial", 7), fill="#888888")

        canvas_ticks.bind("<Configure>", ve_tick_labels)
        canvas_ticks.after(150, ve_tick_labels)

        # Lưu hàm tiện ích để dùng lại trong luu_cau_hinh
        self._mb_to_display = mb_to_display
        self._step_to_mb    = step_to_mb

        # 3. CÀI ĐẶT ĐỘ PHÂN GIẢI
        lbl_res_title = tk.Label(self, text="Độ phân giải màn hình game:", font=("Arial", 10, "bold"))
        lbl_res_title.pack(anchor="w", padx=20, pady=(15, 2))
        
        frame_res_preset = tk.Frame(self)
        frame_res_preset.pack(fill="x", padx=20, pady=2)
        tk.Label(frame_res_preset, text="Chọn nhanh:", font=("Arial", 9)).pack(side=tk.LEFT)
        
        self.cbo_res_preset = ttk.Combobox(
            frame_res_preset, 
            values=["Tự tùy chỉnh", "854x480", "1024x768", "1280x720", "1600x900", "1920x1080"], 
            width=20, 
            state="readonly"
        )
        self.cbo_res_preset.pack(side=tk.LEFT, padx=10)
        self.cbo_res_preset.bind("<<ComboboxSelected>>", self.khi_chon_preset)

        frame_res_custom = tk.Frame(self)
        frame_res_custom.pack(fill="x", padx=20, pady=5)
        
        tk.Label(frame_res_custom, text="Chiều rộng:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_width = tk.Entry(frame_res_custom, font=("Arial", 10), width=8, justify="center")
        self.ent_width.pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_res_custom, text=" x ", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        tk.Label(frame_res_custom, text="Chiều cao:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_height = tk.Entry(frame_res_custom, font=("Arial", 10), width=8, justify="center")
        self.ent_height.pack(side=tk.LEFT, padx=5)

        gia_tri_cu = str(config.current_config.get("do_phan_giai", "854x480"))
        match = re.search(r"(\d+)\s*x\s*(\d+)", gia_tri_cu)
        if match:
            rong_cu, cao_cu = match.groups()
            self.ent_width.insert(0, rong_cu)
            self.ent_height.insert(0, cao_cu)
            chuoi_so_sanh = f"{rong_cu}x{cao_cu}"
            if chuoi_so_sanh in ["854x480", "1024x768", "1280x720", "1600x900", "1920x1080"]:
                self.cbo_res_preset.set(chuoi_so_sanh)
            else:
                self.cbo_res_preset.set("Tự tùy chỉnh")
        else:
            self.ent_width.insert(0, "854")
            self.ent_height.insert(0, "480")
            self.cbo_res_preset.set("854x480")

        # =====================================================================
        # BỔ SUNG KHU VỰC 4: TÙY CHỈNH JAVA ARGUMENTS (JVM NÂNG CAO)
        # =====================================================================
        lbl_jvm_title = tk.Label(self, text="Tùy chỉnh Java Arguments (JVM):", font=("Arial", 10, "bold"))
        lbl_jvm_title.pack(anchor="w", padx=20, pady=(15, 2))

        # Dropdown chọn chế độ vận hành JVM
        frame_jvm_mode = tk.Frame(self)
        frame_jvm_mode.pack(fill="x", padx=20, pady=2)
        tk.Label(frame_jvm_mode, text="Chế độ:", font=("Arial", 9)).pack(side=tk.LEFT)
        
        self.cbo_jvm_mode = ttk.Combobox(
            frame_jvm_mode, 
            values=["Mặc định (Mojang)", "Sử dụng gói tối ưu sẵn", "Tự nhập tay (Custom)"], 
            width=25, 
            state="readonly"
        )
        self.cbo_jvm_mode.pack(side=tk.LEFT, padx=10)
        self.cbo_jvm_mode.bind("<<ComboboxSelected>>", self.khi_thay_doi_che_do_jvm)

        # Dropdown chọn gói tối ưu có sẵn (Chỉ bật khi chọn Chế độ 2)
        frame_jvm_preset = tk.Frame(self)
        frame_jvm_preset.pack(fill="x", padx=20, pady=3)
        tk.Label(frame_jvm_preset, text="Gói tối ưu:", font=("Arial", 9)).pack(side=tk.LEFT)
        
        self.cbo_jvm_presets = ttk.Combobox(frame_jvm_preset, values=list(self.preset_options.keys()), width=35, state="readonly")
        self.cbo_jvm_presets.pack(side=tk.LEFT, padx=10)

        # Ô nhập tay Arguments Custom (Chỉ bật khi chọn Chế độ 3)
        frame_jvm_custom = tk.Frame(self)
        frame_jvm_custom.pack(fill="x", padx=20, pady=3)
        tk.Label(frame_jvm_custom, text="Nhập tay:", font=("Arial", 9)).pack(side=tk.LEFT)
        
        self.ent_jvm_custom = tk.Entry(frame_jvm_custom, font=("Arial", 9), width=45)
        self.ent_jvm_custom.pack(side=tk.LEFT, padx=10, fill="x", expand=True)

        # Tải dữ liệu JVM cũ từ file config lên UI
        self.dong_bo_du_lieu_jvm_cu()
        # =====================================================================

        # NÚT LƯU CẤU HÌNH
        btn_save = tk.Button(self, text="LƯU CÀI ĐẶT", font=("Arial", 10, "bold"), bg="#2196F3", fg="white", width=15, height=2, command=self.luu_cau_hinh)
        btn_save.pack(side=tk.BOTTOM, pady=15)

    def dong_bo_du_lieu_jvm_cu(self):
        """Đọc file config hiện tại để hiển thị chính xác trạng thái JVM lên giao diện"""
        current_mode = config.current_config.get("jvm_mode", "default")
        if current_mode == "default":
            self.cbo_jvm_mode.set("Mặc định (Mojang)")
        elif current_mode == "preset":
            self.cbo_jvm_mode.set("Sử dụng gói tối ưu sẵn")
        elif current_mode == "custom":
            self.cbo_jvm_mode.set("Tự nhập tay (Custom)")

        current_preset = config.current_config.get("preset_jvm_args", "aikar_optimized")
        for vn_name, en_name in self.preset_options.items():
            if en_name == current_preset:
                self.cbo_jvm_presets.set(vn_name)
                break
        else:
            self.cbo_jvm_presets.set(list(self.preset_options.keys())[0])

        current_custom = config.current_config.get("custom_jvm_args", "")
        self.ent_jvm_custom.insert(0, current_custom)

        # Khóa/mở khóa các ô nhập dựa theo chế độ tải lên
        self.khi_thay_doi_che_do_jvm()

    def khi_thay_doi_che_do_jvm(self, event=None):
        """Tự động đóng/mở khóa các Widget nhập liệu tùy theo chế độ JVM đang chọn"""
        che_do = self.cbo_jvm_mode.get()
        if che_do == "Mặc định (Mojang)":
            self.cbo_jvm_presets.configure(state="disabled")
            self.ent_jvm_custom.configure(state="disabled")
        elif che_do == "Sử dụng gói tối ưu sẵn":
            self.cbo_jvm_presets.configure(state="readonly")
            self.ent_jvm_custom.configure(state="disabled")
        elif che_do == "Tự nhập tay (Custom)":
            self.cbo_jvm_presets.configure(state="disabled")
            self.ent_jvm_custom.configure(state="normal")

    def khi_chon_preset(self, event=None):
        preset = self.cbo_res_preset.get()
        if preset != "Tự tùy chỉnh":
            rong, cao = preset.split("x")
            self.ent_width.delete(0, tk.END)
            self.ent_width.insert(0, rong.strip())
            self.ent_height.delete(0, tk.END)
            self.ent_height.insert(0, cao.strip())

    def chon_duong_dan(self):
        thu_muc = filedialog.askdirectory(title="Chọn thư mục lưu Game")
        if thu_muc:
            self.ent_path.delete(0, tk.END)
            self.ent_path.insert(0, thu_muc)

    def luu_cau_hinh(self):
        path = self.ent_path.get().strip()
        if not path:
            messagebox.showwarning("Cảnh báo", "Đường dẫn game không được để trống!")
            return
            
        rong_input = self.ent_width.get().strip()
        cao_input = self.ent_height.get().strip()
        
        if not rong_input.isdigit() or not cao_input.isdigit():
            messagebox.showerror(
                "Lỗi nhập liệu", 
                "Kích thước màn hình phải là số nguyên dương!\nVí dụ: Rộng 1920 - Cao 1080"
            )
            return
            
        int_rong = int(rong_input)
        int_cao = int(cao_input)
        
        if int_rong < 300 or int_cao < 300:
            messagebox.showwarning("Cảnh báo", "Độ phân giải quá nhỏ có thể gây lỗi hiển thị game!")
            return
            
        res_chuan_hoa = f"{int_rong}x{int_cao}"
            
        # --- Đọc RAM từ ô nhập MiB (ưu tiên) hoặc thanh kéo ---
        try:
            max_mb = int(self.var_ram_mib.get().strip())
            if max_mb < 256:
                raise ValueError
        except ValueError:
            max_mb = self._step_to_mb(int(self.sld_ram.get()))

        ram_max_val = self._mb_to_display(max_mb)

        # Lưu trạng thái Auto
        config.current_config["ram_auto"] = self.var_ram_auto.get()

        # --- Lưu các trường cơ bản ---
        config.current_config["thu_muc_game"] = path
        config.current_config["ram_max"] = ram_max_val
        config.current_config.pop("ram_min", None)  # xoa ram_min neu con ton tai
        config.current_config["do_phan_giai"] = res_chuan_hoa
        
        # --- LƯU CÁC TRƯỜNG JVM ARGUMENTS MỚI TÍCH HỢP ---
        jvm_ui_mode = self.cbo_jvm_mode.get()
        if jvm_ui_mode == "Mặc định (Mojang)":
            config.current_config["jvm_mode"] = "default"
        elif jvm_ui_mode == "Sử dụng gói tối ưu sẵn":
            config.current_config["jvm_mode"] = "preset"
        elif jvm_ui_mode == "Tự nhập tay (Custom)":
            config.current_config["jvm_mode"] = "custom"

        ten_goi_tieng_viet = self.cbo_jvm_presets.get()
        config.current_config["preset_jvm_args"] = self.preset_options.get(ten_goi_tieng_viet, "aikar_optimized")
        config.current_config["custom_jvm_args"] = self.ent_jvm_custom.get().strip()
        
        # Đồng bộ và ghi file
        config.luu_toan_bo_cau_hinh()
        messagebox.showinfo("Thành công", f"Đã lưu toàn bộ cấu hình hệ thống!")
        self.on_save_callback()
        self.destroy()
