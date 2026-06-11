import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os

# Import các module hệ thống của bạn
import config
import core
from components.account_frame import AccountFrame
from components.instance_frame import InstanceFrame
from components.setting_window import SettingWindow  # Module cài đặt mới gộp RAM, Resolution, Path

class MinecraftLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft Professional Instance Launcher")
        self.root.geometry("480x520")
        self.root.resizable(False, False)

        # Nạp cấu hình hệ thống từ file JSON
        config.tai_toan_bo_cau_hinh()

        self.create_widgets()

    def create_widgets(self):
        # 1. TIÊU ĐỀ LAUNCHER
        lbl_main_title = tk.Label(self.root, text="MINECRAFT LAUNCHER", font=("Arial", 16, "bold"), fg="#1E88E5")
        lbl_main_title.pack(pady=(20, 15))

        # 2. COMPONENT CHỌN TÀI KHOẢN (ACCOUNT)
        self.account_frame = AccountFrame(self.root, self.khi_thay_doi_instance)
        self.account_frame.pack(pady=10)

        # 3. COMPONENT CHỌN PHIÊN BẢN (INSTANCE)
        # Truyền self.khi_thay_doi_instance làm callback để đồng bộ giao diện khi chuyển Instance
        self.instance_frame = InstanceFrame(self.root, self.khi_thay_doi_instance)
        self.instance_frame.pack(pady=10)

        # 4. NÚT XÓA INSTANCE ĐANG CHỌN (Giữ nguyên tính năng của bạn)
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

        # 5. TRẠNG THÁI HỆ THỐNG
        self.lbl_status = tk.Label(self.root, text="Sẵn sàng", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_status.pack(pady=5)

        # 6. NÚT VÀO GAME (TO, RÕ RÀNG Ở CHÍNH GIỮA DƯỚI)
        self.btn_launch = tk.Button(
            self.root, 
            text="VÀO GAME", 
            font=("Arial", 12, "bold"), 
            bg="#1E88E5", 
            fg="white", 
            width=18, 
            height=2, 
            command=self.bat_dau_chay_game
        )
        self.btn_launch.pack(pady=(10, 20))

        # 7. NÚT SETTING (⚙️ SETTINGS CHUYỂN XUỐNG GÓC PHẢI BÊN DƯỚI)
        # Sử dụng .place() để ghim chặt vào góc phải dưới bất kể bố cục pack() ở trên thế nào
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

    def khi_thay_doi_instance(self):
        """Hàm callback tự động chạy khi người dùng đổi tên Instance hoặc lưu Setting mới"""
        if hasattr(self, 'instance_frame'):
            self.instance_frame.cap_nhat_nhan_thong_tin()

    def mo_cua_so_setting(self):
        """Mở pop-up gộp chung chỉnh RAM, Độ phân giải, Đường dẫn game"""
        SettingWindow(self.root, self.khi_thay_doi_instance)

    def xoa_instance_hien_tai(self):
        """Xử lý xóa Instance đang chọn khỏi cấu hình và ổ đĩa"""
        ten_instance = self.instance_frame.get_current_instance()
        
        if ten_instance == "New_Version":
            messagebox.showwarning("Chú ý", "Không thể xóa phiên bản mặc định hệ thống!")
            return
            
        xac_nhan = messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa hoàn toàn phiên bản '{ten_instance}'?")
        if xac_nhan:
            # 1. Xóa trong file cấu hình JSON
            if ten_instance in config.current_config["danh_sach_instances"]:
                del config.current_config["danh_sach_instances"][ten_instance]
            
            config.current_config["current_instance"] = "New_Version"
            config.luu_toan_bo_cau_hinh()
            
            # 2. Xóa thư mục vật lý tương ứng (nếu muốn dọn sạch ổ đĩa)
            duong_dan_folder = os.path.join(self.instance_frame.thu_muc_instances, ten_instance)
            if os.path.exists(duong_dan_folder):
                try:
                    import shutil
                    shutil.rmtree(duong_dan_folder)
                except Exception as e:
                    print(f"Không thể xóa thư mục vật lý: {e}")

            # 3. Làm mới lại thanh chọn Combobox ngoài màn hình chính
            messagebox.showinfo("Thành công", f"Đã xóa phiên bản: {ten_instance}")
            
            # Khởi động lại frame chọn instance để nạp lại danh sách sạch
            self.instance_frame.destroy()
            self.instance_frame = InstanceFrame(self.root, self.khi_thay_doi_instance)
            # Chèn lại vào đúng vị trí cũ (sau thanh account và trước nút xóa)
            self.instance_frame.pack(pady=10)
            self.instance_frame.pack_configure(after=self.account_frame)

    def bat_dau_chay_game(self):
        """Kích hoạt luồng chạy ngầm để khởi động Minecraft không bị đơ giao diện"""
        tai_khoan = self.account_frame.get_current_account()
        if not tai_khoan:
            messagebox.showwarning("Chú ý", "Vui lòng chọn hoặc thêm tài khoản trước khi chơi!")
            return

        self.btn_launch.config(state="disabled", text="ĐANG CHẠY...")
        self.lbl_status.config(text="Đang chuẩn bị dữ liệu game...", fg="#1E88E5")
        
        def luong_khoi_dong():
            try:
                # Lấy dữ liệu cấu hình instance và các thông số cài đặt RAM từ config
                thong_tin_instance = self.instance_frame.get_instance_values()
                thu_muc_game = config.current_config.get("thu_muc_game")
                ten_instance = self.instance_frame.get_current_instance()
                
                # Gọi hàm chạy game bên file core.py của bạn
                core.chay_game_minecraft(tai_khoan, ten_instance, thong_tin_instance, thu_muc_game, self.lbl_status)
                
                self.root.after(0, lambda: self.lbl_status.config(text="Game đã khởi động thành công!", fg="#2E7D32"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Khởi động game thất bại:\n{str(e)}"))
            finally:
                self.root.after(0, lambda: self.btn_launch.config(state="normal", text="VÀO GAME"))
                self.root.after(0, lambda: self.lbl_status.config(text="Sẵn sàng", fg="gray"))

        threading.Thread(target=luong_khoi_dong, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = MinecraftLauncherApp(root)
    root.mainloop()