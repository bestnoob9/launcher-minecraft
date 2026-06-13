import tkinter as tk
from tkinter import ttk, messagebox
import config

class AccountFrame(tk.Frame):
    def __init__(self, parent, on_change_callback):
        super().__init__(parent)
        self.on_change_callback = on_change_callback
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
        win_add = tk.Toplevel(self)
        win_add.title("Thêm tài khoản")
        win_add.geometry("300x150")
        win_add.resizable(False, False)
        win_add.grab_set()
        
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