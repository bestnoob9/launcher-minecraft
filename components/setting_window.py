import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import config
import theme
from icon_utils import gan_icon_app

class SettingFrame(tk.Frame):
    """
    Phiên bản nhúng inline của SettingWindow — dùng cho View Switching trong main.py.
    Kế thừa toàn bộ logic từ SettingWindow nhưng là tk.Frame thay vì tk.Toplevel.
    Nút LƯU sẽ KHÔNG đóng cửa sổ mà chỉ gọi on_save_callback.
    """
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.on_save_callback = on_save_callback
        self._init_data()
        self._build_scrollable_content()

    def _init_data(self):
        """Khởi tạo dữ liệu dùng chung (preset options, flags)."""
        self.preset_options = {
            "Tối ưu hóa toàn diện (Khuyên dùng)": "aikar_optimized",
            "Dành cho máy yếu / Ít RAM": "low_end",
            "Tải Chunk nhanh / Giảm giật hình": "chunk_loading_heavy",
            "Chơi Modpack nặng (Nhiều Mods)": "heavy_modded",
            "Siêu mượt Real-time (Shenandoah GC)": "shenandoah_ultra"
        }
        self._preset_flags = {
            "aikar_optimized": (
                "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 "
                "-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch "
                "-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M "
                "-XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 "
                "-XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 "
                "-XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 "
                "-XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 "
                "-Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true"
            ),
            "low_end": (
                "-XX:+UseSerialGC -XX:+OptimizeStringConcat -XX:+UseStringDeduplication "
                "-XX:MaxGCPauseMillis=50 -Xss512k -XX:MetaspaceSize=64m -XX:MaxMetaspaceSize=128m"
            ),
            "chunk_loading_heavy": (
                "-XX:+UseZGC -XX:+UnlockExperimentalVMOptions -XX:+ZGenerational "
                "-XX:+AlwaysPreTouch -XX:+DisableExplicitGC "
                "-XX:ConcGCThreads=4 -XX:ParallelGCThreads=4"
            ),
            "heavy_modded": (
                "-XX:+UseG1GC -XX:+UnlockExperimentalVMOptions -XX:+ParallelRefProcEnabled "
                "-XX:MaxGCPauseMillis=200 -XX:+AlwaysPreTouch -XX:G1HeapRegionSize=32M "
                "-XX:G1NewSizePercent=20 -XX:G1MaxNewSizePercent=50 -XX:G1ReservePercent=15 "
                "-XX:InitiatingHeapOccupancyPercent=20 -XX:G1MixedGCLiveThresholdPercent=85 "
                "-XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=512m"
            ),
            "shenandoah_ultra": (
                "-XX:+UseShenandoahGC -XX:+UnlockExperimentalVMOptions "
                "-XX:ShenandoahGCMode=iu -XX:+AlwaysPreTouch -XX:+DisableExplicitGC "
                "-XX:+UseTransparentHugePages -XX:ConcGCThreads=4"
            ),
        }

    def _build_scrollable_content(self):
        """Tạo canvas + scrollbar để cuộn nội dung settings."""
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Frame nội dung thực bên trong canvas
        self._inner = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        def _on_inner_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)

        self._inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Build widget vào self._inner (đóng vai trò như "self" trong SettingWindow)
        self._build_widgets(self._inner)
        theme.apply_theme(self._inner)

        # ── Theo dõi thay đổi chưa lưu (dirty tracking) ─────────────
        # Đặt SAU khi build + apply_theme xong, để các thao tác insert()
        # giá trị ban đầu ở trên không bị tính nhầm là "người dùng đã sửa".
        self._is_dirty = False
        self._setup_dirty_tracking()

    def _build_widgets(self, p):
        """Build toàn bộ widgets settings vào frame p (thay vì self như trong Toplevel)."""
        import math

        # ── 1. Đường dẫn game ──────────────────────────────────────────
        tk.Label(p, text="Thư mục game (Minecraft Path):", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_path = tk.Frame(p)
        frame_path.pack(fill="x", padx=20)
        self.ent_path = tk.Entry(frame_path, font=("Arial", 10), width=35)
        self.ent_path.pack(side=tk.LEFT, ipady=2, fill="x", expand=True)
        self.ent_path.insert(0, config.current_config.get("thu_muc_game", ""))
        tk.Button(frame_path, text="Chọn...", font=("Arial", 9), command=self.chon_duong_dan).pack(side=tk.LEFT, padx=5)

        # ── 1b. Giao diện sáng/tối ────────────────────────────────────
        tk.Label(p, text="Giao diện:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_theme = tk.Frame(p)
        frame_theme.pack(fill="x", padx=20)
        self.var_theme = tk.StringVar(value=theme.get_theme_name())
        tk.Radiobutton(frame_theme, text="☀ Sáng", font=("Arial", 9), variable=self.var_theme, value="light", command=self._khi_doi_theme).pack(side=tk.LEFT, padx=(0, 12))
        tk.Radiobutton(frame_theme, text="🌙 Tối", font=("Arial", 9), variable=self.var_theme, value="dark", command=self._khi_doi_theme).pack(side=tk.LEFT)

        # ── 1c. Kích thước cửa sổ launcher ──────────────────────────────
        tk.Label(p, text="Kích thước cửa sổ launcher:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_size_preset = tk.Frame(p)
        frame_size_preset.pack(fill="x", padx=20, pady=2)
        tk.Label(frame_size_preset, text="Chọn nhanh:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.cbo_size_preset = ttk.Combobox(
            frame_size_preset,
            values=["Tự tùy chỉnh", "1024x600", "1280x720", "1366x768", "1440x900", "1600x900", "1920x1080"],
            width=20, state="readonly"
        )
        self.cbo_size_preset.pack(side=tk.LEFT, padx=10)
        self.cbo_size_preset.bind("<<ComboboxSelected>>", self.khi_chon_preset_cua_so)

        frame_size_custom = tk.Frame(p)
        frame_size_custom.pack(fill="x", padx=20, pady=5)
        tk.Label(frame_size_custom, text="Chiều rộng:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_cs_width = tk.Entry(frame_size_custom, font=("Arial", 10), width=8, justify="center")
        self.ent_cs_width.pack(side=tk.LEFT, padx=5)
        tk.Label(frame_size_custom, text=" x ", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(frame_size_custom, text="Chiều cao:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_cs_height = tk.Entry(frame_size_custom, font=("Arial", 10), width=8, justify="center")
        self.ent_cs_height.pack(side=tk.LEFT, padx=5)

        _cs_presets = ["1024x600", "1280x720", "1366x768", "1440x900", "1600x900", "1920x1080"]
        cs_cu = str(config.current_config.get("kich_thuoc_cua_so", "1280x720"))
        cs_match = re.search(r"(\d+)\s*x\s*(\d+)", cs_cu)
        if cs_match:
            cs_rong, cs_cao = cs_match.groups()
            self.ent_cs_width.insert(0, cs_rong)
            self.ent_cs_height.insert(0, cs_cao)
            cs_chuoi = f"{cs_rong}x{cs_cao}"
            self.cbo_size_preset.set(cs_chuoi if cs_chuoi in _cs_presets else "Tự tùy chỉnh")
        else:
            self.ent_cs_width.insert(0, "1280")
            self.ent_cs_height.insert(0, "720")
            self.cbo_size_preset.set("1280x720")

        # ── 1d. Ẩn launcher khi vào game ─────────────────────────────
        tk.Label(p, text="Khi vào game:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_an_launcher = tk.Frame(p)
        frame_an_launcher.pack(fill="x", padx=20)
        self.var_an_launcher = tk.IntVar(value=1 if config.current_config.get("an_launcher_khi_choi", True) else 0)
        tk.Radiobutton(frame_an_launcher, text="Ẩn launcher", font=("Arial", 9),
                       variable=self.var_an_launcher, value=1).pack(side=tk.LEFT, padx=(0, 12))
        tk.Radiobutton(frame_an_launcher, text="Không ẩn", font=("Arial", 9),
                       variable=self.var_an_launcher, value=0).pack(side=tk.LEFT)

        # ── 2. RAM ────────────────────────────────────────────────────
        tk.Label(p, text="Bộ Nhớ Sử Dụng:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_ram = tk.Frame(p)
        frame_ram.pack(fill="x", padx=20)

        _sys = config.current_config.get("_system_info", {})
        _total_mb = _sys.get("ram_total_mb", 0)
        _gb = _sys.get("ram_total_gb", 0)

        if not _total_mb or _total_mb < 1024:
            def _lam_tron(total_mb):
                cac_moc = [4, 8, 12, 16, 24, 32, 48, 64, 128]
                total_gb_thuc = total_mb / 1024
                for moc in cac_moc:
                    if total_gb_thuc <= moc * 1.05:
                        return moc
                return math.ceil(total_gb_thuc)
            _total_mb = 0
            try:
                import psutil
                _total_mb = psutil.virtual_memory().total // (1024 * 1024)
            except Exception:
                pass
            if not _total_mb:
                try:
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(stat)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    if stat.ullTotalPhys > 0:
                        _total_mb = stat.ullTotalPhys // (1024 * 1024)
                except Exception:
                    pass
            if not _total_mb:
                _total_mb = 8192
            _gb = _lam_tron(_total_mb)
            config.current_config["_system_info"] = {"ram_total_mb": _total_mb, "ram_total_gb": _gb}

        RAM_STEP = 256
        RAM_MIN_MB = 512
        RAM_MAX_MB = max(1024, int(_total_mb))

        def parse_ram_to_mb(s):
            s = str(s).strip().upper().replace(" ", "")
            if s.endswith("GB"): return int(float(s[:-2]) * 1024)
            elif s.endswith("MB"): return int(s[:-2])
            elif s.endswith("G"): return int(float(s[:-1]) * 1024)
            elif s.endswith("M"): return int(s[:-1])
            try: return int(s)
            except: return 2048

        def mb_to_display(mb):
            # Luon tra ve so nguyen MB hoac GB - KHONG bao gio sinh so thap phan
            # (vi du "3.5 GB") vi core.py / JVM khong parse duoc dang nay.
            if mb >= 1024 and mb % 1024 == 0: return f"{mb // 1024} GB"
            return f"{mb} MB"

        def mb_to_step(mb): return round((mb - RAM_MIN_MB) / RAM_STEP)
        def step_to_mb(step): return RAM_MIN_MB + int(step) * RAM_STEP

        num_steps = (RAM_MAX_MB - RAM_MIN_MB) // RAM_STEP
        saved_mb = parse_ram_to_mb(config.current_config.get("ram_max", "2GB"))
        saved_mb = max(RAM_MIN_MB, min(RAM_MAX_MB, saved_mb))

        frame_slider_row = tk.Frame(frame_ram)
        frame_slider_row.pack(fill="x", pady=(4, 0))

        self.sld_ram = tk.Scale(frame_slider_row, from_=0, to=num_steps, orient=tk.HORIZONTAL,
                                showvalue=False, sliderlength=16, troughcolor="#4A90D9",
                                activebackground="#1E88E5", highlightthickness=0, bd=0)
        self.sld_ram.set(mb_to_step(saved_mb))
        self.sld_ram.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 6))

        self.var_ram_mib = tk.StringVar(value=str(saved_mb))
        self.ent_ram_mib = tk.Entry(frame_slider_row, textvariable=self.var_ram_mib, font=("Arial", 9), width=6, justify="center", relief="groove")
        self.ent_ram_mib.pack(side=tk.LEFT, padx=(0, 2))
        tk.Label(frame_slider_row, text="MiB", font=("Arial", 9), fg="#555").pack(side=tk.LEFT, padx=(0, 8))

        self.var_ram_auto = tk.BooleanVar(value=config.current_config.get("ram_auto", False))
        tk.Checkbutton(frame_slider_row, text="Auto", variable=self.var_ram_auto, font=("Arial", 9),
                       command=lambda: khi_thay_doi_auto()).pack(side=tk.LEFT)

        def _dong_bo_arguments_neu_dang_preset():
            """RAM thay doi (keo thanh truot / nhap tay MiB / bat Auto) co the
            anh huong truc tiep den -Xmx/-Xms trong o Arguments khi dang o che
            do 'Su dung goi toi uu san'. Truoc day o Arguments chi duoc cap
            nhat khi doi dropdown preset, khien thanh truot va Arguments hien
            sai lech nhau cho den khi nguoi dung vo tinh trigger 1 su kien
            khac. Goi lai ham nay moi khi RAM doi de luon dong bo ngay."""
            try:
                if self.cbo_jvm_mode.get() == "Sử dụng gói tối ưu sẵn":
                    self._khi_chon_preset_jvm()
            except Exception:
                pass

        def khi_keo_ram(val):
            self.var_ram_mib.set(str(step_to_mb(int(float(val)))))
            _dong_bo_arguments_neu_dang_preset()
        self.sld_ram.config(command=khi_keo_ram)

        def khi_nhap_mib(event=None):
            try:
                mb = int(self.var_ram_mib.get().strip())
                mb = max(RAM_MIN_MB, min(RAM_MAX_MB, mb))
                self.sld_ram.set(mb_to_step(mb))
            except ValueError:
                pass
            _dong_bo_arguments_neu_dang_preset()
        self.ent_ram_mib.bind("<Return>", khi_nhap_mib)
        self.ent_ram_mib.bind("<FocusOut>", khi_nhap_mib)

        def khi_thay_doi_auto():
            if self.var_ram_auto.get():
                auto_mb = max(2048, min(RAM_MAX_MB // 2, RAM_MAX_MB))
                auto_mb = round(auto_mb / RAM_STEP) * RAM_STEP
                self.sld_ram.set(mb_to_step(auto_mb))
                self.var_ram_mib.set(str(auto_mb))
                self.sld_ram.config(state="disabled")
                self.ent_ram_mib.config(state="disabled")
            else:
                self.sld_ram.config(state="normal")
                self.ent_ram_mib.config(state="normal")
            _dong_bo_arguments_neu_dang_preset()
        khi_thay_doi_auto()

        self._mb_to_display = mb_to_display
        self._step_to_mb = step_to_mb

        # ── 3. Độ phân giải ────────────────────────────────────────────
        tk.Label(p, text="Độ phân giải màn hình game:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_res_preset = tk.Frame(p)
        frame_res_preset.pack(fill="x", padx=20, pady=2)
        tk.Label(frame_res_preset, text="Chọn nhanh:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.cbo_res_preset = ttk.Combobox(frame_res_preset, values=["Tự tùy chỉnh", "854x480", "1024x768", "1280x720", "1600x900", "1920x1080"], width=20, state="readonly")
        self.cbo_res_preset.pack(side=tk.LEFT, padx=10)
        self.cbo_res_preset.bind("<<ComboboxSelected>>", self.khi_chon_preset)

        frame_res_custom = tk.Frame(p)
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
            self.cbo_res_preset.set(chuoi_so_sanh if chuoi_so_sanh in ["854x480","1024x768","1280x720","1600x900","1920x1080"] else "Tự tùy chỉnh")
        else:
            self.ent_width.insert(0, "854")
            self.ent_height.insert(0, "480")
            self.cbo_res_preset.set("854x480")

        # ── 4. JVM Arguments ──────────────────────────────────────────
        tk.Label(p, text="Tùy chỉnh Java Arguments (JVM):", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))

        frame_jvm_mode = tk.Frame(p)
        frame_jvm_mode.pack(fill="x", padx=20, pady=2)
        tk.Label(frame_jvm_mode, text="Chế độ:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.cbo_jvm_mode = ttk.Combobox(frame_jvm_mode, values=["Mặc định (Mojang)", "Sử dụng gói tối ưu sẵn", "Tự nhập tay (Custom)"], width=25, state="readonly")
        self.cbo_jvm_mode.pack(side=tk.LEFT, padx=10)
        self.cbo_jvm_mode.bind("<<ComboboxSelected>>", self.khi_thay_doi_che_do_jvm)

        frame_jvm_preset = tk.Frame(p)
        frame_jvm_preset.pack(fill="x", padx=20, pady=3)
        tk.Label(frame_jvm_preset, text="Gói tối ưu:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.cbo_jvm_presets = ttk.Combobox(frame_jvm_preset, values=list(self.preset_options.keys()), width=35, state="readonly")
        self.cbo_jvm_presets.pack(side=tk.LEFT, padx=10)
        self.cbo_jvm_presets.bind("<<ComboboxSelected>>", self._khi_chon_preset_jvm)

        frame_jvm_custom = tk.Frame(p)
        frame_jvm_custom.pack(fill="x", padx=20, pady=3)
        tk.Label(frame_jvm_custom, text="Arguments:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_jvm_custom = tk.Entry(frame_jvm_custom, font=("Arial", 9), width=45)
        self.ent_jvm_custom.pack(side=tk.LEFT, padx=10, fill="x", expand=True)
        self.dong_bo_du_lieu_jvm_cu()

        # ── 5. Java Path ──────────────────────────────────────────────
        tk.Label(p, text="Đường dẫn Java (Java Path):", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 2))
        frame_java = tk.Frame(p)
        frame_java.pack(fill="x", padx=20)
        self.ent_java_path = tk.Entry(frame_java, font=("Arial", 9), width=33)
        self.ent_java_path.pack(side=tk.LEFT, ipady=2, fill="x", expand=True)
        self.ent_java_path.insert(0, config.current_config.get("java_path", ""))
        tk.Button(frame_java, text="Chọn...", font=("Arial", 9), command=self._chon_java_path).pack(side=tk.LEFT, padx=(5, 0))
        tk.Label(p, text="Để trống = dùng Java mặc định của hệ thống", font=("Arial", 8), fg="#888").pack(anchor="w", padx=20)

        # ── Nút LƯU ───────────────────────────────────────────────────
        tk.Button(p, text="💾  LƯU CÀI ĐẶT", font=("Arial", 10, "bold"),
                  bg="#2196F3", fg="white", width=18, height=2,
                  command=self.luu_cau_hinh).pack(pady=(20, 15))

    # ── Theo dõi thay đổi chưa lưu ─────────────────────────────────────

    def _setup_dirty_tracking(self):
        """Gắn sự kiện lên tất cả widget nhập liệu để phát hiện khi người
        dùng thay đổi bất kỳ giá trị nào mà chưa bấm LƯU."""

        def _mark_dirty(*_args):
            self._is_dirty = True

        # Các biến tk.Variable (Radiobutton / Checkbutton / thanh trượt RAM)
        for var in (self.var_theme, self.var_an_launcher,
                    self.var_ram_auto, self.var_ram_mib):
            try:
                var.trace_add("write", _mark_dirty)
            except Exception:
                pass

        # Các ô Entry nhập tay
        for ent in (self.ent_path, self.ent_cs_width, self.ent_cs_height,
                    self.ent_width, self.ent_height, self.ent_jvm_custom,
                    self.ent_java_path):
            try:
                ent.bind("<KeyRelease>", _mark_dirty, add="+")
            except Exception:
                pass

        # Các Combobox (chọn preset kích thước, độ phân giải, chế độ JVM...)
        for cbo in (self.cbo_size_preset, self.cbo_res_preset,
                    self.cbo_jvm_mode, self.cbo_jvm_presets):
            try:
                cbo.bind("<<ComboboxSelected>>", _mark_dirty, add="+")
            except Exception:
                pass

        # Thanh trượt RAM (kéo bằng chuột)
        try:
            self.sld_ram.bind("<ButtonRelease-1>", _mark_dirty, add="+")
        except Exception:
            pass

    def has_unsaved_changes(self) -> bool:
        """True nếu người dùng đã thay đổi ít nhất 1 giá trị nhưng chưa
        bấm LƯU CÀI ĐẶT."""
        return getattr(self, "_is_dirty", False)

    def confirm_discard_changes(self) -> bool:
        """
        Gọi hàm này TRƯỚC khi cho phép chuyển sang tab/view khác (ở
        main.py, trong handler bấm nút chuyển tab).

        Trả về:
          - True  -> được phép rời đi (không có gì thay đổi, hoặc người
                     dùng đã xác nhận bỏ qua thay đổi).
          - False -> KHÔNG được rời đi, người dùng chọn ở lại để lưu.
        """
        if not self.has_unsaved_changes():
            return True

        dong_y_roi_di = messagebox.askyesno(
            "Thay đổi chưa được lưu",
            "Bạn có thay đổi trong Cài đặt chưa được lưu.\n"
            "Bạn có chắc muốn rời đi khi chưa lưu không?"
        )
        if dong_y_roi_di:
            # Người dùng chấp nhận bỏ thay đổi -> tắt cờ để lần sau
            # không bị hỏi lại vì cùng một thay đổi cũ.
            self._is_dirty = False
        return dong_y_roi_di

    # ── Các method logic giống SettingWindow (copy nguyên) ────────────

    def _lay_ram_hien_tai(self) -> str:
        try:
            mb = int(self.var_ram_mib.get().strip())
            mb = max(512, mb)
        except Exception:
            mb = 2048
        if mb >= 1024 and mb % 1024 == 0:
            return f"{mb // 1024}G"
        return f"{mb}M"

    def _xay_dung_args_preset(self, preset_key: str) -> str:
        xmx = self._lay_ram_hien_tai()
        mb = int(self.var_ram_mib.get().strip()) if self.var_ram_mib.get().strip().isdigit() else 2048
        xms_mb = max(512, mb // 2)
        xms = f"{xms_mb // 1024}G" if xms_mb >= 1024 and xms_mb % 1024 == 0 else f"{xms_mb}M"
        gc_flags = self._preset_flags.get(preset_key, "")
        return f"-Xmx{xmx} -Xms{xms} {gc_flags}".strip()

    def _khi_chon_preset_jvm(self, event=None):
        ten_vn = self.cbo_jvm_presets.get()
        preset_key = self.preset_options.get(ten_vn, "aikar_optimized")
        args = self._xay_dung_args_preset(preset_key)
        self.ent_jvm_custom.configure(state="normal")
        self.ent_jvm_custom.delete(0, tk.END)
        self.ent_jvm_custom.insert(0, args)
        self.ent_jvm_custom.configure(state="readonly")

    def dong_bo_du_lieu_jvm_cu(self):
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

        if current_mode == "preset":
            args = self._xay_dung_args_preset(current_preset)
            self.ent_jvm_custom.insert(0, args)
        else:
            self.ent_jvm_custom.insert(0, config.current_config.get("custom_jvm_args", ""))
        self.khi_thay_doi_che_do_jvm()

    def khi_thay_doi_che_do_jvm(self, event=None):
        che_do = self.cbo_jvm_mode.get()
        if che_do == "Mặc định (Mojang)":
            self.cbo_jvm_presets.configure(state="disabled")
            self.ent_jvm_custom.configure(state="normal")
            self.ent_jvm_custom.delete(0, tk.END)
            self.ent_jvm_custom.configure(state="disabled")
        elif che_do == "Sử dụng gói tối ưu sẵn":
            self.cbo_jvm_presets.configure(state="readonly")
            ten_vn = self.cbo_jvm_presets.get()
            preset_key = self.preset_options.get(ten_vn, "aikar_optimized")
            args = self._xay_dung_args_preset(preset_key)
            self.ent_jvm_custom.configure(state="normal")
            self.ent_jvm_custom.delete(0, tk.END)
            self.ent_jvm_custom.insert(0, args)
            self.ent_jvm_custom.configure(state="readonly")
        elif che_do == "Tự nhập tay (Custom)":
            self.cbo_jvm_presets.configure(state="disabled")
            cur = self.ent_jvm_custom.get()
            self.ent_jvm_custom.configure(state="normal")
            is_preset = any(f.split()[0] in cur for f in self._preset_flags.values() if f)
            if is_preset:
                self.ent_jvm_custom.delete(0, tk.END)

    def khi_chon_preset(self, event=None):
        preset = self.cbo_res_preset.get()
        if preset != "Tự tùy chỉnh":
            rong, cao = preset.split("x")
            self.ent_width.delete(0, tk.END)
            self.ent_width.insert(0, rong.strip())
            self.ent_height.delete(0, tk.END)
            self.ent_height.insert(0, cao.strip())

    def khi_chon_preset_cua_so(self, event=None):
        preset = self.cbo_size_preset.get()
        if preset != "Tự tùy chỉnh":
            rong, cao = preset.split("x")
            self.ent_cs_width.delete(0, tk.END)
            self.ent_cs_width.insert(0, rong.strip())
            self.ent_cs_height.delete(0, tk.END)
            self.ent_cs_height.insert(0, cao.strip())

    def _khi_doi_theme(self):
        theme.set_theme(self.var_theme.get())
        config.luu_toan_bo_cau_hinh()
        try:
            root = self.winfo_toplevel()
            theme.apply_theme_to_all_toplevels(root)
            theme.apply_theme(root)
        except Exception:
            pass

    def chon_duong_dan(self):
        from tkinter import filedialog
        thu_muc = filedialog.askdirectory(title="Chọn thư mục lưu Game")
        if thu_muc:
            self.ent_path.delete(0, tk.END)
            self.ent_path.insert(0, thu_muc)

    def _chon_java_path(self):
        import sys
        from tkinter import filedialog
        if sys.platform == "win32":
            file_types = [("Java Executable", "java.exe javaw.exe"), ("All files", "*.*")]
        else:
            file_types = [("Java Executable", "java"), ("All files", "*.*")]
        java_file = filedialog.askopenfilename(title="Chọn file java.exe hoặc javaw.exe", filetypes=file_types)
        if java_file:
            self.ent_java_path.delete(0, tk.END)
            self.ent_java_path.insert(0, java_file)

    def luu_cau_hinh(self):
        from tkinter import messagebox
        path = self.ent_path.get().strip()
        if not path:
            messagebox.showwarning("Cảnh báo", "Đường dẫn game không được để trống!")
            return

        rong_input = self.ent_width.get().strip()
        cao_input = self.ent_height.get().strip()
        if not rong_input.isdigit() or not cao_input.isdigit():
            messagebox.showerror("Lỗi nhập liệu", "Kích thước màn hình phải là số nguyên dương!\nVí dụ: Rộng 1920 - Cao 1080")
            return
        int_rong, int_cao = int(rong_input), int(cao_input)
        if int_rong < 300 or int_cao < 300:
            messagebox.showwarning("Cảnh báo", "Độ phân giải quá nhỏ có thể gây lỗi hiển thị game!")
            return
        res_chuan_hoa = f"{int_rong}x{int_cao}"

        cs_rong_input = self.ent_cs_width.get().strip()
        cs_cao_input = self.ent_cs_height.get().strip()
        if not cs_rong_input.isdigit() or not cs_cao_input.isdigit():
            messagebox.showerror("Lỗi nhập liệu", "Kích thước cửa sổ launcher phải là số nguyên dương!\nVí dụ: Rộng 1280 - Cao 720")
            return
        cs_int_rong, cs_int_cao = int(cs_rong_input), int(cs_cao_input)
        if cs_int_rong < 800 or cs_int_cao < 600:
            messagebox.showwarning("Cảnh báo", "Kích thước cửa sổ launcher tối thiểu là 800 x 600!")
            return
        cs_chuan_hoa = f"{cs_int_rong}x{cs_int_cao}"

        try:
            max_mb = int(self.var_ram_mib.get().strip())
            if max_mb < 256:
                raise ValueError
        except ValueError:
            max_mb = self._step_to_mb(int(self.sld_ram.get()))

        ram_max_val = self._mb_to_display(max_mb)
        config.current_config["ram_auto"] = self.var_ram_auto.get()
        config.current_config["thu_muc_game"] = path
        config.current_config["theme"] = self.var_theme.get()
        config.current_config["ram_max"] = ram_max_val
        config.current_config.pop("ram_min", None)
        config.current_config["do_phan_giai"] = res_chuan_hoa
        config.current_config["kich_thuoc_cua_so"] = cs_chuan_hoa
        config.current_config["an_launcher_khi_choi"] = bool(self.var_an_launcher.get())
        config.current_config["java_path"] = self.ent_java_path.get().strip()

        jvm_ui_mode = self.cbo_jvm_mode.get()
        if jvm_ui_mode == "Mặc định (Mojang)":
            config.current_config["jvm_mode"] = "default"
        elif jvm_ui_mode == "Sử dụng gói tối ưu sẵn":
            config.current_config["jvm_mode"] = "preset"
        elif jvm_ui_mode == "Tự nhập tay (Custom)":
            config.current_config["jvm_mode"] = "custom"

        ten_goi_tieng_viet = self.cbo_jvm_presets.get()
        config.current_config["preset_jvm_args"] = self.preset_options.get(ten_goi_tieng_viet, "aikar_optimized")

        self.ent_jvm_custom.configure(state="normal")
        config.current_config["custom_jvm_args"] = self.ent_jvm_custom.get().strip()
        self.ent_jvm_custom.configure(state="readonly" if jvm_ui_mode == "Sử dụng gói tối ưu sẵn" else "normal")

        config.luu_toan_bo_cau_hinh()
        self._is_dirty = False  # đã lưu xong -> không còn thay đổi "treo"
        messagebox.showinfo("Thành công", "Đã lưu toàn bộ cấu hình hệ thống!")
        if self.on_save_callback:
            self.on_save_callback()


class SettingWindow(tk.Toplevel):
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.title("Cài đặt cấu hình")
        self.geometry("460x640")  # Chiều cao tăng để vừa thanh kéo RAM + JVM Arguments
        self.resizable(False, False)
        #self.grab_set()  # Khóa màn hình chính khi đang mở setting
        gan_icon_app(self)
        
        self.on_save_callback = on_save_callback
        
        # Tạo bản đồ ánh xạ hiển thị tiếng Việt sang mã cài đặt lưu trong JSON
        self.preset_options = {
            "Tối ưu hóa toàn diện (Khuyên dùng)": "aikar_optimized",
            "Dành cho máy yếu / Ít RAM": "low_end",
            "Tải Chunk nhanh / Giảm giật hình": "chunk_loading_heavy",
            "Chơi Modpack nặng (Nhiều Mods)": "heavy_modded",
            "Siêu mượt Real-time (Shenandoah GC)": "shenandoah_ultra"
        }

        # GC flags của từng preset (KHÔNG có -Xmx/-Xms — sẽ inject từ thanh kéo RAM)
        self._preset_flags = {
            "aikar_optimized": (
                "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 "
                "-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch "
                "-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M "
                "-XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 "
                "-XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 "
                "-XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 "
                "-XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 "
                "-Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true"
            ),
            "low_end": (
                "-XX:+UseSerialGC -XX:+OptimizeStringConcat -XX:+UseStringDeduplication "
                "-XX:MaxGCPauseMillis=50 -Xss512k -XX:MetaspaceSize=64m -XX:MaxMetaspaceSize=128m"
            ),
            "chunk_loading_heavy": (
                "-XX:+UseZGC -XX:+UnlockExperimentalVMOptions -XX:+ZGenerational "
                "-XX:+AlwaysPreTouch -XX:+DisableExplicitGC "
                "-XX:ConcGCThreads=4 -XX:ParallelGCThreads=4"
            ),
            "heavy_modded": (
                "-XX:+UseG1GC -XX:+UnlockExperimentalVMOptions -XX:+ParallelRefProcEnabled "
                "-XX:MaxGCPauseMillis=200 -XX:+AlwaysPreTouch -XX:G1HeapRegionSize=32M "
                "-XX:G1NewSizePercent=20 -XX:G1MaxNewSizePercent=50 -XX:G1ReservePercent=15 "
                "-XX:InitiatingHeapOccupancyPercent=20 -XX:G1MixedGCLiveThresholdPercent=85 "
                "-XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=512m"
            ),
            "shenandoah_ultra": (
                "-XX:+UseShenandoahGC -XX:+UnlockExperimentalVMOptions "
                "-XX:ShenandoahGCMode=iu -XX:+AlwaysPreTouch -XX:+DisableExplicitGC "
                "-XX:+UseTransparentHugePages -XX:ConcGCThreads=4"
            ),
        }
        
        self.create_widgets()
        theme.apply_theme(self)

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

        # 1b. GIAO DIỆN SÁNG / TỐI
        lbl_theme_title = tk.Label(self, text="Giao diện:", font=("Arial", 10, "bold"))
        lbl_theme_title.pack(anchor="w", padx=20, pady=(15, 2))

        frame_theme = tk.Frame(self)
        frame_theme.pack(fill="x", padx=20)

        self.var_theme = tk.StringVar(value=theme.get_theme_name())
        tk.Radiobutton(
            frame_theme, text="☀ Sáng", font=("Arial", 9),
            variable=self.var_theme, value="light",
            command=self._khi_doi_theme,
        ).pack(side=tk.LEFT, padx=(0, 12))
        tk.Radiobutton(
            frame_theme, text="🌙 Tối", font=("Arial", 9),
            variable=self.var_theme, value="dark",
            command=self._khi_doi_theme,
        ).pack(side=tk.LEFT)

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
        #RAM_MAX_MB = max(1024, int(_total_mb * 0.95))
        RAM_MAX_MB = max(1024, int(_total_mb))

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
            # Luon tra ve so nguyen MB hoac GB - KHONG bao gio sinh so thap phan
            # (vi du "3.5 GB") vi core.py / JVM khong parse duoc dang nay.
            if mb >= 1024 and mb % 1024 == 0:
                return f"{mb // 1024} GB"
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
        def _dong_bo_arguments_neu_dang_preset():
            """RAM thay doi co the anh huong -Xmx/-Xms trong o Arguments khi
            dang o che do 'Su dung goi toi uu san'. Goi lai moi khi RAM doi
            de Arguments luon dong bo ngay, khong phai doi su kien khac."""
            try:
                if self.cbo_jvm_mode.get() == "Sử dụng gói tối ưu sẵn":
                    self._khi_chon_preset_jvm()
            except Exception:
                pass

        def khi_keo_ram(val):
            self.var_ram_mib.set(str(step_to_mb(int(float(val)))))
            _dong_bo_arguments_neu_dang_preset()

        self.sld_ram.config(command=khi_keo_ram)

        def khi_nhap_mib(event=None):
            try:
                mb = int(self.var_ram_mib.get().strip())
                mb = max(RAM_MIN_MB, min(RAM_MAX_MB, mb))
                self.sld_ram.set(mb_to_step(mb))
            except ValueError:
                pass
            _dong_bo_arguments_neu_dang_preset()

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
            _dong_bo_arguments_neu_dang_preset()

        khi_thay_doi_auto()
        """
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
        canvas_ticks.after(150, ve_tick_labels) """

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
        # Khi chọn preset → tự điền args vào ô bên dưới
        self.cbo_jvm_presets.bind("<<ComboboxSelected>>", self._khi_chon_preset_jvm)

        # Ô hiển thị JVM Arguments thực tế sẽ truyền vào launcher
        # - Chế độ preset: tự điền (readonly, màu xám)
        # - Chế độ custom:  người dùng nhập tay (normal)
        # - Chế độ default: trống + disabled
        frame_jvm_custom = tk.Frame(self)
        frame_jvm_custom.pack(fill="x", padx=20, pady=3)
        tk.Label(frame_jvm_custom, text="Arguments:", font=("Arial", 9)).pack(side=tk.LEFT)

        self.ent_jvm_custom = tk.Entry(frame_jvm_custom, font=("Arial", 9), width=45)
        self.ent_jvm_custom.pack(side=tk.LEFT, padx=10, fill="x", expand=True)

        # Tải dữ liệu JVM cũ từ file config lên UI
        self.dong_bo_du_lieu_jvm_cu()
        # =====================================================================

        # =====================================================================
        # KHU VỰC 5: JAVA PATH
        # =====================================================================
        lbl_java_title = tk.Label(self, text="Đường dẫn Java (Java Path):", font=("Arial", 10, "bold"))
        lbl_java_title.pack(anchor="w", padx=20, pady=(15, 2))

        frame_java = tk.Frame(self)
        frame_java.pack(fill="x", padx=20)

        self.ent_java_path = tk.Entry(frame_java, font=("Arial", 9), width=33)
        self.ent_java_path.pack(side=tk.LEFT, ipady=2, fill="x", expand=True)
        self.ent_java_path.insert(0, config.current_config.get("java_path", ""))

        btn_browse_java = tk.Button(
            frame_java, text="Chọn...", font=("Arial", 9),
            command=self._chon_java_path
        )
        btn_browse_java.pack(side=tk.LEFT, padx=(5, 0))

        lbl_java_hint = tk.Label(
            self,
            text="Để trống = dùng Java mặc định của hệ thống",
            font=("Arial", 8), fg="#888"
        )
        lbl_java_hint.pack(anchor="w", padx=20)
        # =====================================================================

        # NÚT LƯU CẤU HÌNH
        btn_save = tk.Button(self, text="LƯU CÀI ĐẶT", font=("Arial", 10, "bold"), bg="#2196F3", fg="white", width=15, height=2, command=self.luu_cau_hinh)
        btn_save.pack(side=tk.BOTTOM, pady=15)

    def _lay_ram_hien_tai(self) -> str:
        """Lấy RAM hiện tại từ ô MiB trên UI, trả về dạng JVM string (vd: '4G', '2048M')."""
        try:
            mb = int(self.var_ram_mib.get().strip())
            mb = max(512, mb)
        except Exception:
            mb = 2048
        if mb >= 1024 and mb % 1024 == 0:
            return f"{mb // 1024}G"
        return f"{mb}M"

    def _xay_dung_args_preset(self, preset_key: str) -> str:
        """Ghép -Xmx/-Xms (từ thanh kéo RAM) + GC flags của preset thành 1 chuỗi."""
        xmx = self._lay_ram_hien_tai()
        mb  = int(self.var_ram_mib.get().strip()) if self.var_ram_mib.get().strip().isdigit() else 2048
        xms_mb = max(512, mb // 2)
        xms = f"{xms_mb // 1024}G" if xms_mb >= 1024 and xms_mb % 1024 == 0 else f"{xms_mb}M"
        gc_flags = self._preset_flags.get(preset_key, "")
        return f"-Xmx{xmx} -Xms{xms} {gc_flags}".strip()

    def _khi_chon_preset_jvm(self, event=None):
        """Khi người dùng chọn preset → điền args thực tế vào ô Arguments."""
        ten_vn = self.cbo_jvm_presets.get()
        preset_key = self.preset_options.get(ten_vn, "aikar_optimized")
        args = self._xay_dung_args_preset(preset_key)
        self.ent_jvm_custom.configure(state="normal")
        self.ent_jvm_custom.delete(0, tk.END)
        self.ent_jvm_custom.insert(0, args)
        self.ent_jvm_custom.configure(state="readonly")

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

        # Điền ô Arguments theo chế độ đã lưu
        if current_mode == "preset":
            # Điền args preset (với RAM hiện tại) vào ô để thấy rõ
            args = self._xay_dung_args_preset(current_preset)
            self.ent_jvm_custom.insert(0, args)
        else:
            current_custom = config.current_config.get("custom_jvm_args", "")
            self.ent_jvm_custom.insert(0, current_custom)

        # Khóa/mở khóa các ô nhập dựa theo chế độ tải lên
        self.khi_thay_doi_che_do_jvm()

    def khi_thay_doi_che_do_jvm(self, event=None):
        """Tự động đóng/mở khóa các Widget nhập liệu tùy theo chế độ JVM đang chọn"""
        che_do = self.cbo_jvm_mode.get()
        if che_do == "Mặc định (Mojang)":
            self.cbo_jvm_presets.configure(state="disabled")
            self.ent_jvm_custom.configure(state="normal")
            self.ent_jvm_custom.delete(0, tk.END)
            self.ent_jvm_custom.configure(state="disabled")
        elif che_do == "Sử dụng gói tối ưu sẵn":
            self.cbo_jvm_presets.configure(state="readonly")
            # Điền ngay args của preset đang chọn (readonly — xem được nhưng không sửa)
            ten_vn = self.cbo_jvm_presets.get()
            preset_key = self.preset_options.get(ten_vn, "aikar_optimized")
            args = self._xay_dung_args_preset(preset_key)
            self.ent_jvm_custom.configure(state="normal")
            self.ent_jvm_custom.delete(0, tk.END)
            self.ent_jvm_custom.insert(0, args)
            self.ent_jvm_custom.configure(state="readonly")
        elif che_do == "Tự nhập tay (Custom)":
            self.cbo_jvm_presets.configure(state="disabled")
            # Xóa args preset nếu đang có, để người dùng nhập tay
            cur = self.ent_jvm_custom.get()
            self.ent_jvm_custom.configure(state="normal")
            # Nếu ô đang chứa args từ preset thì xóa để nhập mới
            is_preset = any(
                f.split()[0] in cur
                for f in self._preset_flags.values()
                if f
            )
            if is_preset:
                self.ent_jvm_custom.delete(0, tk.END)

    def khi_chon_preset(self, event=None):
        preset = self.cbo_res_preset.get()
        if preset != "Tự tùy chỉnh":
            rong, cao = preset.split("x")
            self.ent_width.delete(0, tk.END)
            self.ent_width.insert(0, rong.strip())
            self.ent_height.delete(0, tk.END)
            self.ent_height.insert(0, cao.strip())

    def khi_chon_preset_cua_so(self, event=None):
        preset = self.cbo_size_preset.get()
        if preset != "Tự tùy chỉnh":
            rong, cao = preset.split("x")
            self.ent_cs_width.delete(0, tk.END)
            self.ent_cs_width.insert(0, rong.strip())
            self.ent_cs_height.delete(0, tk.END)
            self.ent_cs_height.insert(0, cao.strip())

    def _khi_doi_theme(self):
        theme.set_theme(self.var_theme.get())
        config.luu_toan_bo_cau_hinh()
        try:
            root = self.master
            theme.apply_theme_to_all_toplevels(root)
            theme.apply_theme(self)
        except Exception:
            pass

    def chon_duong_dan(self):
        thu_muc = filedialog.askdirectory(title="Chọn thư mục lưu Game")
        if thu_muc:
            self.ent_path.delete(0, tk.END)
            self.ent_path.insert(0, thu_muc)

    def _chon_java_path(self):
        """Mở hộp thoại chọn file java / java.exe / javaw.exe"""
        import sys
        if sys.platform == "win32":
            file_types = [("Java Executable", "java.exe javaw.exe"), ("All files", "*.*")]
        else:
            file_types = [("Java Executable", "java"), ("All files", "*.*")]
        java_file = filedialog.askopenfilename(
            title="Chọn file java.exe hoặc javaw.exe",
            filetypes=file_types
        )
        if java_file:
            self.ent_java_path.delete(0, tk.END)
            self.ent_java_path.insert(0, java_file)

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
        config.current_config["theme"] = self.var_theme.get()
        config.current_config["ram_max"] = ram_max_val
        config.current_config.pop("ram_min", None)  # xoa ram_min neu con ton tai
        config.current_config["do_phan_giai"] = res_chuan_hoa
        config.current_config["java_path"] = self.ent_java_path.get().strip()
        
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

        # Luôn lưu nội dung ô Arguments vào custom_jvm_args
        # (dù là preset hay nhập tay — launcher chỉ cần đọc key này)
        self.ent_jvm_custom.configure(state="normal")
        config.current_config["custom_jvm_args"] = self.ent_jvm_custom.get().strip()
        self.ent_jvm_custom.configure(state="readonly" if jvm_ui_mode == "Sử dụng gói tối ưu sẵn" else "normal")
        
        # Đồng bộ và ghi file
        config.luu_toan_bo_cau_hinh()
        messagebox.showinfo("Thành công", f"Đã lưu toàn bộ cấu hình hệ thống!")
        self.on_save_callback()
        self.destroy()