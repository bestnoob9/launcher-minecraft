import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import config

class SettingWindow(tk.Toplevel):
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.title("Cài đặt cấu hình")
        self.geometry("450x520")  # Tăng chiều cao để vừa khít phần JVM Arguments mới
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

        # 2. CÀI ĐẶT RAM JVM
        lbl_ram_title = tk.Label(self, text="Cài đặt bộ nhớ RAM (JVM):", font=("Arial", 10, "bold"))
        lbl_ram_title.pack(anchor="w", padx=20, pady=(15, 2))
        
        frame_ram = tk.Frame(self)
        frame_ram.pack(fill="x", padx=20)
        
        tk.Label(frame_ram, text="Tối thiểu (Min):", font=("Arial", 9)).grid(row=0, column=0, sticky="w", pady=5)
        self.cbo_ram_min = ttk.Combobox(frame_ram, values=["512MB", "1GB", "2GB", "4GB", "8GB"], width=12, state="readonly")
        self.cbo_ram_min.set(config.current_config.get("ram_min", "1GB"))
        self.cbo_ram_min.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(frame_ram, text="Tối đa (Max):", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=5)
        self.cbo_ram_max = ttk.Combobox(frame_ram, values=["2GB", "4GB", "6GB", "8GB", "12GB", "16GB"], width=12, state="readonly")
        self.cbo_ram_max.set(config.current_config.get("ram_max", "4GB"))
        self.cbo_ram_max.grid(row=1, column=1, padx=10, pady=5)

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
            
        # --- Lưu các trường cơ bản cũ ---
        config.current_config["thu_muc_game"] = path
        config.current_config["ram_min"] = self.cbo_ram_min.get()
        config.current_config["ram_max"] = self.cbo_ram_max.get()
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