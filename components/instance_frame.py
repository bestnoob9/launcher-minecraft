import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import unicodedata
import config
import core


def kiem_tra_ten_hop_le(ten):
    """
    Trả về (True, "") nếu tên hợp lệ.
    Trả về (False, thông_báo_lỗi) nếu tên chứa dấu hoặc ký tự không hợp lệ.
    Cho phép: chữ a-z, A-Z, 0-9, dấu gạch dưới _, dấu gạch ngang -, khoảng trắng (sẽ chuyển thành _).
    """
    chuan_hoa = unicodedata.normalize('NFD', ten)
    for c in chuan_hoa:
        if unicodedata.category(c) in ('Mn', 'Mc'):
            return False, (
                "Tên phiên bản không được chứa chữ có dấu!\n"
                "✅ Đúng: minecraft test, MyWorld_1, survival-2025\n"
                "❌ Sai: thế giới, phiên bản mới, tên_có_dấu"
            )
    for c in ten:
        if ord(c) > 127:
            return False, (
                "Tên phiên bản chỉ được dùng ký tự tiếng Anh (a-z, A-Z, 0-9, _, -)!\n"
                "✅ Đúng: minecraft test, MyWorld_1\n"
                "❌ Sai: thế giới, 我的世界"
            )
    return True, ""


class InstanceFrame(tk.Frame):
    def __init__(self, parent, on_change_callback):
        super().__init__(parent)
        self.on_change_callback = on_change_callback
        self.thu_muc_goc = config.current_config["thu_muc_game"]
        self.thu_muc_instances = os.path.join(self.thu_muc_goc, "Instances")
        os.makedirs(self.thu_muc_instances, exist_ok=True)
        self.create_widgets()

    def create_widgets(self):
        lbl_title = tk.Label(self, text="Chọn Thư mục phiên bản (Instance):", font=("Arial", 10))
        lbl_title.pack()

        frame_inner = tk.Frame(self)
        frame_inner.pack(pady=5)

        # Tạo thiết lập New_Version chạy bản mới nhất khi chạy launcher lần đầu tiên
        ds_instance = list(config.current_config["danh_sach_instances"].keys())
        if not ds_instance or "Default_Instance" in ds_instance:
            config.current_config["danh_sach_instances"].pop("Default_Instance", None)

            release_versions = core.lay_danh_sach_phien_ban_chinh()
            ban_moi_nhat = release_versions[0] if release_versions else "1.21.1"
            ten_mac_dinh = "Latest Version"

            config.current_config["danh_sach_instances"][ten_mac_dinh] = {
                "version_goc": ban_moi_nhat,
                "loai_game": "Vanilla",
                "version_mod": "Vanilla"
            }
            config.current_config["current_instance"] = ten_mac_dinh
            config.luu_toan_bo_cau_hinh()

            ds_instance = list(config.current_config["danh_sach_instances"].keys())
            os.makedirs(os.path.join(self.thu_muc_instances, ten_mac_dinh), exist_ok=True)

        self.cbo_instance = ttk.Combobox(frame_inner, values=ds_instance, font=("Arial", 10), state="readonly", width=22)
        current_saved = config.current_config.get("current_instance", "New_Version")
        self.cbo_instance.set(current_saved if current_saved in ds_instance else ds_instance[0])
        self.cbo_instance.grid(row=0, column=0, padx=5)
        self.cbo_instance.bind("<<ComboboxSelected>>", self.khi_chuyen_instance)

        # YÊU CẦU 3: Đổi "New Version" → "Latest Version"
        btn_add_instance = tk.Button(
            frame_inner, text="➕ Tạo phiên bản",
            font=("Arial", 9, "bold"), bg="#4CAF50", fg="white",
            command=self.mo_cua_so_tao_instance
        )
        btn_add_instance.grid(row=0, column=1, padx=2)

        self.lbl_info = tk.Label(self, text="", font=("Arial", 9, "italic"), fg="#2E7D32")
        self.lbl_info.pack(pady=2)
        self.cap_nhat_nhan_thong_tin()

    def get_game_path(self):
        return self.thu_muc_goc

    def get_current_instance(self):
        return self.cbo_instance.get()

    def get_instance_values(self):
        name = self.get_current_instance()
        return config.current_config["danh_sach_instances"].get(
            name, {"version_goc": "1.21.1", "loai_game": "Vanilla", "version_mod": "Vanilla"}
        )

    def cap_nhat_nhan_thong_tin(self):
        info = self.get_instance_values()
        # YÊU CẦU 4: Chỉnh lại chữ nhãn cấu hình
        if info['loai_game'] == 'Vanilla':
            text_hien_thi = (
                f"Loại loader: Vanilla  |  "
                f"Phiên bản Minecraft: {info['version_goc']}"
            )
        else:
            text_hien_thi = (
                f"Loại loader: {info['loai_game']}  |  "
                f"Phiên bản Minecraft: {info['version_goc']}  |  "
                f"Phiên bản loader: {info['version_mod']}"
            )
        self.lbl_info.config(text=text_hien_thi)

    def khi_chuyen_instance(self, event=None):
        self.cap_nhat_nhan_thong_tin()
        self.on_change_callback()

    # --- CỬA SỔ POP-UP TẠO PHIÊN BẢN MỚI ---
    def mo_cua_so_tao_instance(self):
        win_create = tk.Toplevel(self)
        win_create.title("Tạo phiên bản mới")
        win_create.geometry("420x420")
        win_create.resizable(False, False)
        win_create.grab_set()

        # 1. Nhập tên thư mục phiên bản
        tk.Label(win_create, text="Tên thư mục phiên bản (Instance):", font=("Arial", 10, "bold")).pack(pady=(15, 2))
        ent_name = tk.Entry(win_create, font=("Arial", 10), width=28)
        ent_name.pack()
        ent_name.insert(0, "")

        # Nhãn báo lỗi tên — hiển thị ngay bên dưới ô nhập
        lbl_ten_loi = tk.Label(win_create, text="", font=("Arial", 8, "italic"), fg="red")
        lbl_ten_loi.pack()

        # YÊU CẦU 1 & 2: Kiểm tra tên realtime khi người dùng gõ
        def kiem_tra_realtime(*args):
            ten_nhap = ent_name.get()
            hop_le, thong_bao = kiem_tra_ten_hop_le(ten_nhap)
            if not hop_le:
                # Chỉ hiện 1 dòng ngắn gọn ngay dưới ô nhập, không popup
                dong_ngan = thong_bao.split("\n")[0]
                lbl_ten_loi.config(text=f"⚠ {dong_ngan}")
            else:
                lbl_ten_loi.config(text="")

        ent_name.bind("<KeyRelease>", kiem_tra_realtime)

        # 2. Chọn phiên bản chính (Vanilla)
        tk.Label(win_create, text="Loại phiên bản:", font=("Arial", 10, "bold")).pack(pady=(15, 2))
        release_versions = core.lay_danh_sach_phien_ban_chinh()
        cbo_ver = ttk.Combobox(win_create, values=release_versions, font=("Arial", 10), state="readonly", width=25)

        if release_versions:
            cbo_ver.set(release_versions[0])
        else:
            cbo_ver.set("1.21.1")
        cbo_ver.pack()

        # 3. Chọn loại Mod Loader
        tk.Label(win_create, text="Chọn Loại Game (Mod Loader):", font=("Arial", 10, "bold")).pack(pady=(15, 2))
        cbo_mod_type = ttk.Combobox(
            win_create,
            values=["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"],
            font=("Arial", 10), state="readonly", width=25
        )
        cbo_mod_type.set("Vanilla")
        cbo_mod_type.pack()

        # 4. Chọn bản Mod cụ thể
        lbl_mod_detail = tk.Label(
            win_create, text="Chọn Phiên bản Mod Loader cụ thể:",
            font=("Arial", 10, "bold"), fg="#2E7D32"
        )
        cbo_mod_ver = ttk.Combobox(win_create, font=("Arial", 10), state="readonly", width=38)
        lbl_loading = tk.Label(win_create, text="", font=("Arial", 9, "italic"), fg="gray")

        def cap_nhat_list_mod_detail(*args):
            v_goc = cbo_ver.get()
            l_game = cbo_mod_type.get()

            if l_game == "Vanilla":
                lbl_mod_detail.pack_forget()
                cbo_mod_ver.pack_forget()
                lbl_loading.pack_forget()
            else:
                lbl_mod_detail.pack(pady=(15, 2))
                cbo_mod_ver.pack()
                lbl_loading.pack()
                cbo_mod_ver.set("")

                def loading_thread():
                    lbl_loading.config(text=f"Đang tải danh sách {l_game}...")
                    ds = core.tai_danh_sach_mod(l_game, v_goc)
                    win_create.after(0, lambda: dien_du_lieu_mod(ds, cbo_ver.get()))

                threading.Thread(target=loading_thread, daemon=True).start()

        def dien_du_lieu_mod(danh_sach, ver_minecraft):
            lbl_loading.config(text="")
            if danh_sach:
                danh_sach_sach = [str(x) for x in danh_sach if x and str(x).strip() != "Mới nhất"]
                if danh_sach_sach:
                    cbo_mod_ver['values'] = danh_sach_sach
                    cbo_mod_ver.set(danh_sach_sach[0])
                    lbl_loading.config(text=f"Đề xuất: {danh_sach_sach[0]}")
                    return

            cbo_mod_ver['values'] = ["Mặc định"]
            cbo_mod_ver.set("Mặc định")

        cbo_ver.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)
        cbo_mod_type.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)

        # Xử lý nút bấm Xác nhận tạo
        def xu_ly_tao():
            ten_nhap = ent_name.get().strip()

            # YÊU CẦU 1: Kiểm tra ký tự có dấu / không hợp lệ trước khi xử lý
            hop_le, thong_bao = kiem_tra_ten_hop_le(ten_nhap)
            if not hop_le:
                messagebox.showerror("Lỗi tên phiên bản", thong_bao, parent=win_create)
                ent_name.focus()
                return

            if not ten_nhap:
                messagebox.showwarning("Chú ý", "Tên không được để trống!", parent=win_create)
                return

            # YÊU CẦU 2: Khoảng trắng → dấu gạch dưới, tên vẫn chạy bình thường
            ten_thu_muc = ten_nhap.replace(" ", "_")

            # ten_nhap: tên hiển thị (giữ khoảng trắng, VD: "minecraft a")
            # ten_thu_muc: tên thư mục vật lý (dùng _, VD: "minecraft_a")
            if ten_nhap in config.current_config["danh_sach_instances"]:
                messagebox.showwarning("Chú ý", "Tên phiên bản này đã tồn tại!", parent=win_create)
                return

            chuoi_hien_thi = cbo_mod_ver.get()
            chuoi_mod_goc = chuoi_mod_goc = chuoi_hien_thi
            if chuoi_mod_goc.startswith("Mặc định"):
                chuoi_mod_goc = "Vanilla"

            # Lưu config với tên gốc có khoảng trắng (hiển thị đẹp trong combobox)
            config.current_config["danh_sach_instances"][ten_nhap] = {
                "version_goc": cbo_ver.get(),
                "loai_game": cbo_mod_type.get(),
                "version_mod": chuoi_mod_goc if cbo_mod_type.get() != "Vanilla" else "Vanilla"
            }
            config.current_config["current_instance"] = ten_nhap
            config.luu_toan_bo_cau_hinh()

            # Thư mục vật lý dùng tên có _ (tránh lỗi đường dẫn)
            os.makedirs(os.path.join(self.thu_muc_instances, ten_thu_muc), exist_ok=True)

            # Làm mới combobox ngoài màn hình chính
            ds_moi = list(config.current_config["danh_sach_instances"].keys())
            self.cbo_instance['values'] = ds_moi
            self.cbo_instance.set(ten_nhap)
            self.cap_nhat_nhan_thong_tin()

            self.on_change_callback()
            win_create.destroy()
            messagebox.showinfo("Thành công", f"Đã tạo phiên bản: {ten_nhap}")

        btn_confirm = tk.Button(
            win_create, text="XÁC NHẬN TẠO",
            font=("Arial", 10, "bold"), bg="#4CAF50", fg="white",
            width=18, height=2, command=xu_ly_tao
        )
        btn_confirm.pack(side=tk.BOTTOM, pady=25)
