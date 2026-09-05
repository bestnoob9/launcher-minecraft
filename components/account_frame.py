import tkinter as tk
from tkinter import messagebox
import config
import theme
from icon_utils import gan_icon_app
from components.dropdown_selector import DropdownSelector

class AccountFrame(tk.Frame):
    def __init__(self, parent, on_change_callback, modal=None):
        super().__init__(parent)
        self.on_change_callback = on_change_callback
        # modal: doi tuong components.modal.AppModal duoc app truyen vao (xem
        # main.py). Neu co, moi thao tac Them/Xoa tai khoan se hien thi bang
        # 1 panel giua launcher thay vi mo tk.Toplevel (cua so OS moi). Neu
        # khong co (None), giu fallback Toplevel cu de tuong thich nguoc.
        self.modal = modal
        # Cho phep gan tay tu ben ngoai (main.py) neu can override cach mo
        # panel Them tai khoan; mac dinh None se dung self.modal.
        self.on_open_add_panel = None

        config.dong_bo_username_json(
            config.current_config.get("thu_muc_game", ""),
            config.current_config.get("danh_sach_acc", []),
        )
        self.create_widgets()

    def create_widgets(self):
        lbl_user = tk.Label(self, text="Chọn tài khoản (Profile):", font=("Arial", 9), anchor="w")
        lbl_user.pack(fill="x")

        self.selector = DropdownSelector(
            self,
            on_select=self._khi_chon_tai_khoan,
            on_delete=self.xoa_tai_khoan,
            bottom_text="➕ Thêm tài khoản",
            on_bottom_click=self.them_tai_khoan,
            show_icon_box=True,
            placeholder="(Chưa có tài khoản)",
        )
        self.selector.set_items(config.current_config["danh_sach_acc"])
        self.selector.set(config.current_config.get("current_account", ""))
        self.selector.pack(fill="x", pady=(3, 5))

    def _refresh_selector(self):
        self.selector.set_items(config.current_config["danh_sach_acc"])

    def _khi_chon_tai_khoan(self, ten):
        ten = (ten or "").strip()
        if ten:
            config.current_config["current_account"] = ten
            config.luu_toan_bo_cau_hinh()
        self.on_change_callback()

    def get_username(self):
        return self.selector.get().strip()

    def get_current_account(self):
        return self.selector.get().strip()

    def khoa(self, tat: bool):
        self.selector.configure_state(not tat)

    # ------------------------------------------------------------------
    # THEM TAI KHOAN
    # ------------------------------------------------------------------
    def them_tai_khoan(self):
        if self.on_open_add_panel:
            self.on_open_add_panel()
            return
        if self.modal is not None:
            self.modal.open(self.build_add_panel, width=380)
            return
        # Fallback (khong co modal duoc truyen vao): giu Toplevel cu.
        self._them_tai_khoan_toplevel()

    def build_add_panel(self, parent, close):
        """Dung noi dung form 'Them tai khoan' ben trong 1 card cua modal
        (parent = card, close = ham dong modal). Giu nguyen logic validate +
        luu cau hinh nhu ban Toplevel cu."""
        colors = theme.colors()
        parent.configure(bg=colors["bg_alt"])

        content = tk.Frame(parent, bg=colors["bg_alt"])
        content.pack(fill="both", expand=True, padx=18, pady=16)

        bar = tk.Frame(content, bg=colors["bg_alt"])
        bar.pack(fill="x", pady=(0, 12))
        tk.Label(bar, text="➕ Thêm tài khoản", font=("Arial", 12, "bold"),
                 bg=colors["bg_alt"], fg=colors["fg_title"]).pack(side="left")
        tk.Button(bar, text="✕", font=("Arial", 9, "bold"), bg=colors["bg_alt"],
                  fg=colors["fg_desc"], relief="flat", bd=0, cursor="hand2",
                  command=close).pack(side="right")

        tk.Label(content, text="Nhập tên tài khoản mới:", font=("Arial", 10),
                 bg=colors["bg_alt"], fg=colors["fg_title"], anchor="w"
                 ).pack(fill="x", pady=(0, 6))
        ent_new_name = tk.Entry(content, font=("Arial", 11), width=24,
                                 bg=colors["entry_bg"], fg=colors["entry_fg"],
                                 insertbackground=colors["entry_fg"], relief="solid", bd=1)
        ent_new_name.pack(fill="x")
        ent_new_name.focus_set()

        lbl_loi = tk.Label(content, text="", font=("Arial", 8, "italic"),
                            bg=colors["bg_alt"], fg="#E53935", anchor="w")
        lbl_loi.pack(fill="x", pady=(4, 0))

        def xu_ly_them():
            ten_moi = ent_new_name.get().strip()
            if not ten_moi:
                lbl_loi.config(text="⚠ Tên không được để trống!")
                return
            if ten_moi in config.current_config["danh_sach_acc"]:
                lbl_loi.config(text="⚠ Tên tài khoản này đã tồn tại!")
                return

            config.current_config["danh_sach_acc"].append(ten_moi)
            config.current_config["current_account"] = ten_moi
            config.luu_toan_bo_cau_hinh()
            config.lay_hoac_luu_uuid(ten_moi, config.current_config.get("thu_muc_game", ""))

            self._refresh_selector()
            self.selector.set(ten_moi)
            self.on_change_callback()
            close()

        btn_bar = tk.Frame(content, bg=colors["bg_alt"])
        btn_bar.pack(fill="x", pady=(14, 0))
        tk.Button(btn_bar, text="Hủy", font=("Arial", 10), bg=colors["bg"],
                  fg=colors["fg_title"], relief="flat", padx=14, pady=6,
                  command=close).pack(side="right", padx=(8, 0))
        tk.Button(btn_bar, text="✔ Xác nhận", font=("Arial", 10, "bold"),
                  bg="#4CAF50", fg="white", relief="flat", padx=14, pady=6,
                  command=xu_ly_them).pack(side="right")

        ent_new_name.bind("<Return>", lambda e: xu_ly_them())

    def _them_tai_khoan_toplevel(self):
        """Fallback cu (chi dung khi khong truyen modal vao AccountFrame)."""
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

            self._refresh_selector()
            self.selector.set(ten_moi)
            self.on_change_callback()
            win_add.destroy()

        tk.Button(win_add, text="Xác nhận", font=("Arial", 10, "bold"), bg="#4CAF50", fg="white", command=xu_ly_them).pack(pady=10)

    # ------------------------------------------------------------------
    # XOA TAI KHOAN
    # ------------------------------------------------------------------
    def xoa_tai_khoan(self, ten=None):
        acc_dang_chon = ten if ten is not None else self.selector.get()
        if not acc_dang_chon:
            return

        def _thuc_hien_xoa():
            if acc_dang_chon not in config.current_config["danh_sach_acc"]:
                return
            config.current_config["danh_sach_acc"].remove(acc_dang_chon)
            config.xoa_username(acc_dang_chon, config.current_config.get("thu_muc_game", ""))

            dang_chon_bi_xoa = (acc_dang_chon == self.selector.get())

            if not config.current_config["danh_sach_acc"]:
                config.current_config["current_account"] = ""
                self._refresh_selector()
                self.selector.set("")
            else:
                self._refresh_selector()
                if dang_chon_bi_xoa:
                    config.current_config["current_account"] = config.current_config["danh_sach_acc"][0]
                    self.selector.set(config.current_config["current_account"])

            config.luu_toan_bo_cau_hinh()
            self.on_change_callback()

        if self.modal is not None:
            self.modal.confirm(
                title="Xóa tài khoản",
                message=f"Bạn có chắc muốn xóa tài khoản '{acc_dang_chon}' không?",
                on_confirm=_thuc_hien_xoa,
                confirm_text="Xóa",
            )
            return

        # Fallback (khong co modal): giu messagebox cu.
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa tài khoản '{acc_dang_chon}' không?"):
            _thuc_hien_xoa()
