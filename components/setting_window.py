import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import config

class SettingWindow(tk.Toplevel):
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.title("Cài đặt cấu hình")
        self.geometry("450x380")
        self.resizable(False, False)
        self.grab_set()  # Khóa màn hình chính khi đang mở setting
        
        self.on_save_callback = on_save_callback
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

        # 3. CÀI ĐẶT ĐỘ PHÂN GIẢI (HÀM TÁCH SỐ THUẦN TÚY)
        lbl_res_title = tk.Label(self, text="Độ phân giải màn hình game:", font=("Arial", 10, "bold"))
        lbl_res_title.pack(anchor="w", padx=20, pady=(15, 2))
        
        # Ô chọn nhanh tỉ lệ có sẵn
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

        # 2 Ô nhập Rộng x Cao độc lập
        frame_res_custom = tk.Frame(self)
        frame_res_custom.pack(fill="x", padx=20, pady=5)
        
        tk.Label(frame_res_custom, text="Chiều rộng:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_width = tk.Entry(frame_res_custom, font=("Arial", 10), width=8, justify="center")
        self.ent_width.pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_res_custom, text=" x ", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        tk.Label(frame_res_custom, text="Chiều cao:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.ent_height = tk.Entry(frame_res_custom, font=("Arial", 10), width=8, justify="center")
        self.ent_height.pack(side=tk.LEFT, padx=5)

        # --- FIX LỖI ĐỌC CHỮ: Dùng Regex ép lấy số thuần túy từ file cấu hình ---
        gia_tri_cu = str(config.current_config.get("do_phan_giai", "854x480"))
        
        # Tìm mọi cụm số dạng SốxSố, bỏ qua hết các chữ rác như "Mặc định"
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

        # NÚT LƯU CẤU HÌNH
        btn_save = tk.Button(self, text="LƯU CÀI ĐẶT", font=("Arial", 10, "bold"), bg="#2196F3", fg="white", width=15, height=2, command=self.luu_cau_hinh)
        btn_save.pack(side=tk.BOTTOM, pady=20)

    def khi_chon_preset(self, event=None):
        """Tự động điền số sạch vào 2 ô nhập khi chọn tỉ lệ thông dụng"""
        preset = self.cbo_res_preset.get()
        if preset != "Tự tùy chỉnh":
            # Preset bây giờ chỉ có dạng số thuần túy "1920x1080", split sẽ cực kỳ an toàn
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
        
        # Kiểm tra chống gõ chữ bừa bãi vào 2 ô nhập
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
            
        # Lưu vào file JSON dạng chuỗi số sạch 100%: "854x480"
        res_chuan_hoa = f"{int_rong}x{int_cao}"
            
        config.current_config["thu_muc_game"] = path
        config.current_config["ram_min"] = self.cbo_ram_min.get()
        config.current_config["ram_max"] = self.cbo_ram_max.get()
        config.current_config["do_phan_giai"] = res_chuan_hoa
        
        config.luu_toan_bo_cau_hinh()
        messagebox.showinfo("Thành công", f"Đã lưu cấu hình!\nĐộ phân giải áp dụng: {res_chuan_hoa}")
        self.on_save_callback()
        self.destroy()