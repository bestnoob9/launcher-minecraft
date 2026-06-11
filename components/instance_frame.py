import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import config
import core

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
            ten_mac_dinh = "New_Version"
            
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
        
        btn_add_instance = tk.Button(frame_inner, text="➕ New Version", font=("Arial", 9, "bold"), bg="#4CAF50", fg="white", command=self.mo_cua_so_tao_instance)
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
        return config.current_config["danh_sach_instances"].get(name, {"version_goc": "1.21.1", "loai_game": "Vanilla", "version_mod": "Vanilla"})

    def cap_nhat_nhan_thong_tin(self):
        info = self.get_instance_values()
        text_hien_thi = f"Cấu hình: {info['loai_game']} | Bản: {info['version_mod'] if info['loai_game'] != 'Vanilla' else info['version_goc']}"
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
        tk.Label(win_create, text="Tên thư mục phiên bản (Instance):", font=("Arial", 10, "bold")).pack(pady=(15,2))
        ent_name = tk.Entry(win_create, font=("Arial", 10), width=28)
        ent_name.pack()
        ent_name.insert(0, "New_Version")

        # 2. Chọn phiên bản chính (Vanilla)
        tk.Label(win_create, text="Chọn phiên bản chính (Vanilla):", font=("Arial", 10, "bold")).pack(pady=(15,2))
        release_versions = core.lay_danh_sach_phien_ban_chinh()
        cbo_ver = ttk.Combobox(win_create, values=release_versions, font=("Arial", 10), state="readonly", width=25)
        
        if release_versions:
            cbo_ver.set(release_versions[0])
        else:
            cbo_ver.set("1.21.1")
        cbo_ver.pack()

        # 3. Chọn loại Mod Loader
        tk.Label(win_create, text="Chọn Loại Game (Mod Loader):", font=("Arial", 10, "bold")).pack(pady=(15,2))
        cbo_mod_type = ttk.Combobox(win_create, values=["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"], font=("Arial", 10), state="readonly", width=25)
        cbo_mod_type.set("Vanilla")
        cbo_mod_type.pack()

        # 4. Chọn bản Mod cụ thể
        lbl_mod_detail = tk.Label(win_create, text="Chọn Phiên bản Mod Loader cụ thể:", font=("Arial", 10, "bold"), fg="#2E7D32")
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
                lbl_mod_detail.pack(pady=(15,2))
                cbo_mod_ver.pack()
                lbl_loading.pack()
                
                def loading_thread():
                    lbl_loading.config(text=f"Đang tải danh sách {l_game}...")
                    ds = core.tai_danh_sach_mod(l_game, v_goc)
                    # Ép luồng đồ họa cập nhật giá trị hiện thời từ combobox chính xác
                    win_create.after(0, lambda: dien_du_lieu_mod(ds, cbo_ver.get()))
                threading.Thread(target=loading_thread, daemon=True).start()

        # --- FIX LỖI: SỬ DỤNG CHÍNH XÁC THÔNG TIN BIẾN ĐƯỢC TRUYỀN VÀO LUỒNG ---
        def dien_du_lieu_mod(danh_sach, ver_minecraft):
            lbl_loading.config(text="")
            if danh_sach:
                # Loại bỏ chuỗi "Mới nhất" để tránh gây trùng lặp thông tin hiển thị
                danh_sach_sach = [str(x) for x in danh_sach if x and str(x).strip() != "Mới nhất"]
                
                if danh_sach_sach:
                    # Gộp phiên bản Minecraft trực tiếp theo cấu trúc chuẩn
                    danh_sach_kem_mc = [f"{loader} - (Minecraft {ver_minecraft})" for loader in danh_sach_sach]
                    cbo_mod_ver['values'] = danh_sach_kem_mc
                    cbo_mod_ver.set(danh_sach_kem_mc[0])
                    return
            
            cbo_mod_ver['values'] = [f"Mặc định - (Minecraft {ver_minecraft})"]
            cbo_mod_ver.set(f"Mặc định - (Minecraft {ver_minecraft})")

        cbo_ver.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)
        cbo_mod_type.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)

        # Xử lý nút bấm Xác nhận tạo
        def xu_ly_tao():
            ten_thu_muc = ent_name.get().strip().replace(" ", "_")
            if not ten_thu_muc:
                messagebox.showwarning("Chú ý", "Tên không được để trống!")
                return
            if ten_thu_muc in config.current_config["danh_sach_instances"]:
                messagebox.showwarning("Chú ý", "Tên phiên bản này đã tồn tại!")
                return
                
            chuoi_hien_thi = cbo_mod_ver.get()
            chuoi_mod_goc = chuoi_hien_thi.split(" - (Minecraft ")[0] if " - (Minecraft " in chuoi_hien_thi else chuoi_hien_thi
            
            if chuoi_mod_goc.startswith("Mặc định"):
                chuoi_mod_goc = "Vanilla"
                
            config.current_config["danh_sach_instances"][ten_thu_muc] = {
                "version_goc": cbo_ver.get(),
                "loai_game": cbo_mod_type.get(),
                "version_mod": chuoi_mod_goc if cbo_mod_type.get() != "Vanilla" else "Vanilla"
            }
            config.current_config["current_instance"] = ten_thu_muc
            config.luu_toan_bo_cau_hinh()
            
            os.makedirs(os.path.join(self.thu_muc_instances, ten_thu_muc), exist_ok=True)
            
            self.on_change_callback()
            win_create.destroy()
            messagebox.showinfo("Thành công", f"Đã tạo phiên bản: {ten_thu_muc}")

        btn_confirm = tk.Button(win_create, text="XÁC NHẬN TẠO", font=("Arial", 10, "bold"), bg="#4CAF50", fg="white", width=18, height=2, command=xu_ly_tao)
        btn_confirm.pack(side=tk.BOTTOM, pady=25)