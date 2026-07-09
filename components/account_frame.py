import tkinter as tk
from tkinter import ttk, messagebox
import config
from icon_utils import gan_icon_app

class AccountFrame(tk.Frame):
    def __init__(self, parent, on_change_callback):
        super().__init__(parent)
        self.on_change_callback = on_change_callback
        # Đồng bộ username.json ngay khi mở app: các tài khoản đã tạo TỪ
        # TRƯỚC khi có tính năng này cũng được backfill UUID vào file,
        # không cần đợi tới lúc bấm "Vào game".
        config.dong_bo_username_json(
            config.current_config.get("thu_muc_game", ""),
            config.current_config.get("danh_sach_acc", []),
        )
        self.create_widgets()

    def create_widgets(self):
        lbl_user = tk.Label(self, text="Chọn tài khoản (Profile):", font=("Arial", 10))
        lbl_user.pack()
        
        frame_inner = tk.Frame(self)
        frame_inner.pack(pady=5)
        
        self.cbo_username = ttk.Combobox(
            frame_inner, 
            values=config.current_config["danh_sach_acc"], 
            font=("Arial", 10), 
            state="readonly", 
            width=22
        )
        self.cbo_username.set(config.current_config.get("current_account", ""))
        self.cbo_username.grid(row=0, column=0, padx=5)
        self.cbo_username.bind("<<ComboboxSelected>>", self._khi_chon_tai_khoan)
        
        self.btn_add_acc = tk.Button(frame_inner, text="➕", font=("Arial", 9), bg="#4CAF50", fg="white", width=3, command=self.them_tai_khoan)
        self.btn_add_acc.grid(row=0, column=1, padx=2)
        
        self.btn_del_acc = tk.Button(frame_inner, text="❌", font=("Arial", 9), bg="#F44336", fg="white", width=3, command=self.xoa_tai_khoan)
        self.btn_del_acc.grid(row=0, column=2, padx=2)

    def _khi_chon_tai_khoan(self, event=None):
        ten = self.cbo_username.get().strip()
        if ten:
            config.current_config["current_account"] = ten
            config.luu_toan_bo_cau_hinh()
        self.on_change_callback()

    def get_username(self):
        return self.cbo_username.get().strip()
    def get_current_account(self):
        return self.cbo_username.get().strip()

    def khoa(self, tat: bool):
        """Khóa/mở khóa toàn bộ UI tài khoản. tat=True → khóa, False → mở."""
        trang_thai_cb = "disabled" if tat else "readonly"
        trang_thai_btn = "disabled" if tat else "normal"
        self.cbo_username.configure(state=trang_thai_cb)
        self.btn_add_acc.configure(state=trang_thai_btn)
        self.btn_del_acc.configure(state=trang_thai_btn)

    def them_tai_khoan(self):
        # Nếu main.py đã wire inline panel thì dùng, không thì fallback Toplevel
        if hasattr(self, 'on_open_add_panel') and self.on_open_add_panel:
            self.on_open_add_panel()
            return
        self._them_tai_khoan_toplevel()

    def _them_tai_khoan_toplevel(self):
        win_add = tk.Toplevel(self)
        win_add.title("Thêm tài khoản")
        win_add.geometry("300x150")
        win_add.resizable(False, False)
        win_add.grab_set()
        gan_icon_app(win_add)
        
        tk.Label(win_add, text="Nhập tên tài khoản mới:", font=("Arial", 10)).pack(pady=10)
        ent_new_name = tk.Entry(win_add, font=("Arial", 11), width=20)
        ent_new_name.pack(pady=5)
        ent_new_name.focus()
        
        def xu_ly_them():
            ten_moi = ent_new_name.get().strip()
            if not ten_moi:
                messagebox.showwarning("Chú ý", "Tên không được để trống!")
                return
            if ten_moi in config.current_config["danh_sach_acc"]:
                messagebox.showwarning("Chú ý", "Tên tài khoản này đã tồn tại!")
                return
                
            config.current_config["danh_sach_acc"].append(ten_moi)
            config.current_config["current_account"] = ten_moi
            config.luu_toan_bo_cau_hinh()
            config.lay_hoac_luu_uuid(ten_moi, config.current_config.get("thu_muc_game", ""))
            
            self.cbo_username['values'] = config.current_config["danh_sach_acc"]
            self.cbo_username.set(ten_moi)
            self.on_change_callback()
            win_add.destroy()
            
        tk.Button(win_add, text="Xác nhận", font=("Arial", 10, "bold"), bg="#4CAF50", fg="white", command=xu_ly_them).pack(pady=10)

    def xoa_tai_khoan(self):
        acc_dang_chon = self.cbo_username.get()
        if not acc_dang_chon:
            return
            
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa tài khoản '{acc_dang_chon}' không?"):
            config.current_config["danh_sach_acc"].remove(acc_dang_chon)
            config.xoa_username(acc_dang_chon, config.current_config.get("thu_muc_game", ""))
            if not config.current_config["danh_sach_acc"]:
                config.current_config["current_account"] = ""
                self.cbo_username['values'] = []
                self.cbo_username.set("")
                
            else:
                config.current_config["current_account"] = config.current_config["danh_sach_acc"][0]
                self.cbo_username['values'] = config.current_config["danh_sach_acc"]
                self.cbo_username.set(config.current_config["current_account"])
            
            config.luu_toan_bo_cau_hinh()
            self.on_change_callback()
    def build_add_panel(self, parent, on_close):
        """
        Dựng form Thêm tài khoản vào 'parent' (Frame inline).
        on_close() được gọi khi người dùng hủy hoặc thêm xong.
        """
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(bar, text="➕ Thêm tài khoản", font=("Arial", 12, "bold"), fg="#4CAF50").pack(side="left")
        tk.Button(bar, text="✕ Đóng", font=("Arial", 9), bg="#E53935", fg="white",
                  relief="flat", padx=6, command=on_close).pack(side="right")

        content = tk.Frame(parent)
        content.pack(pady=20)

        tk.Label(content, text="Nhập tên tài khoản mới:", font=("Arial", 10)).pack(pady=(0, 8))
        ent_new_name = tk.Entry(content, font=("Arial", 11), width=22)
        ent_new_name.pack(pady=4)
        ent_new_name.focus_set()

        def xu_ly_them():
            ten_moi = ent_new_name.get().strip()
            if not ten_moi:
                messagebox.showwarning("Chú ý", "Tên không được để trống!")
                return
            if ten_moi in config.current_config["danh_sach_acc"]:
                messagebox.showwarning("Chú ý", "Tên tài khoản này đã tồn tại!")
                return
            config.current_config["danh_sach_acc"].append(ten_moi)
            config.current_config["current_account"] = ten_moi
            config.luu_toan_bo_cau_hinh()
            config.lay_hoac_luu_uuid(ten_moi, config.current_config.get("thu_muc_game", ""))
            self.cbo_username['values'] = config.current_config["danh_sach_acc"]
            self.cbo_username.set(ten_moi)
            self.on_change_callback()
            on_close()

        btn = tk.Button(content, text="✔ Xác nhận", font=("Arial", 10, "bold"),
                        bg="#4CAF50", fg="white", width=14, height=2, command=xu_ly_them)
        btn.pack(pady=12)
        content.bind_all("<Return>", lambda e: xu_ly_them())