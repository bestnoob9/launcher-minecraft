import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import time
import unicodedata
import json
import config
import core


def kiem_tra_ten_hop_le(ten):
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
        self._watcher_running = True
        self._watcher_thread = threading.Thread(target=self._sync_watcher, daemon=True)
        self._watcher_thread.start()

    def create_widgets(self):
        lbl_title = tk.Label(self, text="Chọn Thư mục phiên bản (Instance):", font=("Arial", 10))
        lbl_title.pack()

        frame_inner = tk.Frame(self)
        frame_inner.pack(pady=5)

        # Tạo Latest Version nếu danh sách trống
        ds_instance = list(config.current_config["danh_sach_instances"].keys())
        if not ds_instance or "Default_Instance" in ds_instance:
            config.current_config["danh_sach_instances"].pop("Default_Instance", None)
            release_versions = core.lay_danh_sach_phien_ban_chinh()
            ban_moi_nhat = release_versions[0] if release_versions else "1.21.5"
            ten_mac_dinh = "Latest Version"
            config.current_config["danh_sach_instances"][ten_mac_dinh] = {
                "version_goc": ban_moi_nhat,
                "loai_game": "Vanilla",
                "version_mod": "Vanilla"
            }
            config.current_config["current_instance"] = ten_mac_dinh
            config.luu_toan_bo_cau_hinh()
            ds_instance = list(config.current_config["danh_sach_instances"].keys())
            os.makedirs(os.path.join(self.thu_muc_instances, "Latest_Version"), exist_ok=True)

        # Tự động cập nhật version_goc cho "Latest Version" mỗi lần mở
        if "Latest Version" in config.current_config["danh_sach_instances"]:
            try:
                release_versions = core.lay_danh_sach_phien_ban_chinh()
                ban_moi_nhat = release_versions[0] if release_versions else "1.21.5"
                config.current_config["danh_sach_instances"]["Latest Version"]["version_goc"] = ban_moi_nhat
                config.luu_toan_bo_cau_hinh()
            except:
                pass
            os.makedirs(os.path.join(self.thu_muc_instances, "Latest_Version"), exist_ok=True)

        self.cbo_instance = ttk.Combobox(frame_inner, values=ds_instance, font=("Arial", 10), state="readonly", width=22)
        current_saved = config.current_config.get("current_instance", "Latest Version")
        self.cbo_instance.set(current_saved if current_saved in ds_instance else ds_instance[0])
        self.cbo_instance.grid(row=0, column=0, padx=5)
        self.cbo_instance.bind("<<ComboboxSelected>>", self.khi_chuyen_instance)

        btn_add_instance = tk.Button(
            frame_inner, text="➕ Tạo phiên bản",
            font=("Arial", 9, "bold"), bg="#4CAF50", fg="white",
            command=self.mo_cua_so_tao_instance
        )
        btn_add_instance.grid(row=0, column=1, padx=2)

        self.lbl_info = tk.Label(self, text="", font=("Arial", 9, "italic"), fg="#2E7D32")
        self.lbl_info.pack(pady=2)
        self.cap_nhat_nhan_thong_tin()

    def _get_folders_on_disk(self):
        """Trả về set tên instance (dạng display) từ các folder thực tế trên disk."""
        result = set()
        if not os.path.exists(self.thu_muc_instances):
            return result
        for name in os.listdir(self.thu_muc_instances):
            if os.path.isdir(os.path.join(self.thu_muc_instances, name)):
                result.add(name.replace("_", " "))
        return result

    def _sync_watcher(self):
        """Chạy nền, poll mỗi 2 giây, sync folder disk <-> config."""
        while self._watcher_running:
            try:
                self._dong_bo_instances()
            except Exception:
                pass
            time.sleep(2)

    def _dong_bo_instances(self):
        """So sánh disk vs config, cập nhật 2 chiều nếu có thay đổi."""
        folders_disk = self._get_folders_on_disk()
        instances_config = set(config.current_config.get("danh_sach_instances", {}).keys())

        # Folder mới trên disk nhưng chưa có trong config → thêm vào
        them_moi = folders_disk - instances_config - {"Latest Version"}
        # Instance trong config nhưng folder đã bị xóa ngoài disk → xóa khỏi config
        # (không xóa "Latest Version" dù không có folder)
        bi_xoa = instances_config - folders_disk - {"Latest Version"}

        if not them_moi and not bi_xoa:
            return  # Không có gì thay đổi

        changed = False

        for ten in them_moi:
            ten_folder = ten.replace(" ", "_")
            file_info = os.path.join(self.thu_muc_instances, ten_folder, "instance_info.json")

            # Đợi tối đa 3 giây để cai_modpack_tu_file ghi xong instance_info.json
            _waited = 0
            while not os.path.exists(file_info) and _waited < 6:
                time.sleep(0.5)
                _waited += 1

            if os.path.exists(file_info):
                try:
                    with open(file_info, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    loai_game   = data.get("loai_game", "Vanilla")
                    version_goc = data.get("version_goc", "1.21.1")
                    version_mod = data.get("version_mod", "Vanilla")
                except Exception:
                    loai_game, version_goc, version_mod = "Vanilla", "1.21.1", "Vanilla"
            else:
                # Tự đoán từ tên folder nếu không có file info
                ten_lower = ten_folder.lower()
                loai_game = "Vanilla"
                for loader in ["fabric", "neoforge", "forge", "quilt"]:
                    if loader in ten_lower:
                        loai_game = loader.capitalize() if loader != "neoforge" else "NeoForge"
                        break
                version_goc = "1.21.1"
                for v in ["1.21.1", "1.21", "1.20.1", "1.20", "1.19.4", "1.19.2",
                           "1.18.2", "1.16.5", "1.12.2", "1.8.9", "1.7.10"]:
                    if v in ten_folder:
                        version_goc = v
                        break
                version_mod = "Vanilla"
                try:
                    os.makedirs(os.path.join(self.thu_muc_instances, ten_folder), exist_ok=True)
                    with open(file_info, "w", encoding="utf-8") as f:
                        json.dump({"loai_game": loai_game, "version_goc": version_goc,
                                   "version_mod": version_mod}, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass

            config.current_config["danh_sach_instances"][ten] = {
                "version_goc": version_goc,
                "loai_game": loai_game,
                "version_mod": version_mod,
            }
            changed = True

        for ten in bi_xoa:
            del config.current_config["danh_sach_instances"][ten]
            # Nếu instance đang chọn bị xóa → reset về Latest Version
            if config.current_config.get("current_instance") == ten:
                config.current_config["current_instance"] = "Latest Version"
            changed = True

        if changed:
            config.luu_toan_bo_cau_hinh()
            self.after(0, self._lam_moi_dropdown)

    def _lam_moi_dropdown(self):
        """Cập nhật dropdown từ config, ưu tiên current_instance trong config."""
        ds_moi = list(config.current_config["danh_sach_instances"].keys())
        hien_tai = self.cbo_instance.get()
        current_in_config = config.current_config.get("current_instance", "")
        self.cbo_instance["values"] = ds_moi

        # Ưu tiên: current_instance trong config (mới nhất) > đang chọn > đầu danh sách
        if current_in_config and current_in_config in ds_moi:
            self.cbo_instance.set(current_in_config)
        elif hien_tai in ds_moi:
            self.cbo_instance.set(hien_tai)
        elif ds_moi:
            self.cbo_instance.set(ds_moi[0])
        self.cap_nhat_nhan_thong_tin()

    def get_game_path(self):
        return self.thu_muc_goc

    def destroy(self):
        self._watcher_running = False
        super().destroy()

    def get_current_instance(self):
        return self.cbo_instance.get()

    def get_instance_values(self):
        name = self.get_current_instance()
        return config.current_config["danh_sach_instances"].get(
            name, {"version_goc": "1.21.5", "loai_game": "Vanilla", "version_mod": "Vanilla"}
        )

    def cap_nhat_nhan_thong_tin(self):
        info = self.get_instance_values()
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
        win_create.geometry("420x480")
        win_create.resizable(False, False)
        win_create.grab_set()

        # 1. Nhập tên phiên bản
        tk.Label(win_create, text="Tên thư mục phiên bản (Instance):", font=("Arial", 10, "bold")).pack(pady=(15, 2))
        ent_name = tk.Entry(win_create, font=("Arial", 10), width=28)
        ent_name.pack()

        lbl_ten_loi = tk.Label(win_create, text="", font=("Arial", 8, "italic"), fg="red")
        lbl_ten_loi.pack()

        def kiem_tra_realtime(*args):
            ten_nhap = ent_name.get()
            hop_le, thong_bao = kiem_tra_ten_hop_le(ten_nhap)
            if not hop_le:
                dong_ngan = thong_bao.split("\n")[0]
                lbl_ten_loi.config(text=f"⚠ {dong_ngan}")
            else:
                lbl_ten_loi.config(text="")

        ent_name.bind("<KeyRelease>", kiem_tra_realtime)

        # 2. Chọn loại phiên bản (Release / Snapshot / Beta / Alpha)
        tk.Label(win_create, text="Loại phiên bản:", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        cbo_loai_ver = ttk.Combobox(
            win_create,
            values=["Release", "Snapshot", "Beta", "Alpha"],
            font=("Arial", 10), state="readonly", width=25
        )
        cbo_loai_ver.set("Release")
        cbo_loai_ver.pack()

        # 3. Chọn phiên bản cụ thể
        tk.Label(win_create, text="Chọn phiên bản Minecraft:", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        cbo_ver = ttk.Combobox(win_create, values=[], font=("Arial", 10), state="readonly", width=25)
        cbo_ver.pack()
        lbl_loading_ver = tk.Label(win_create, text="", font=("Arial", 8, "italic"), fg="gray")
        lbl_loading_ver.pack()

        def cap_nhat_danh_sach_ver(*args):
            loai = cbo_loai_ver.get()
            mapping = {
                "Release": "release",
                "Snapshot": "snapshot",
                "Beta": "old_beta",
                "Alpha": "old_alpha"
            }
            lbl_loading_ver.config(text="Đang tải danh sách phiên bản...")
            cbo_ver.set("")

            def load_ver():
                try:
                    ds = core.lay_danh_sach_phien_ban_theo_loai(mapping[loai])
                except:
                    ds = []
                win_create.after(0, lambda: dien_danh_sach_ver(ds))

            threading.Thread(target=load_ver, daemon=True).start()
            
        def cap_nhat_mod_loader_theo_loai():
            loai = cbo_loai_ver.get()
            if loai == "Release":
                loaders = ["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"]
            elif loai == "Snapshot":
                loaders = ["Vanilla", "Fabric", "Quilt"]
            else:  # Beta, Alpha
                loaders = ["Vanilla"]
            
            cbo_mod_type['values'] = loaders
            cbo_mod_type.set("Vanilla")
            # Ẩn mod loader detail nếu đang chọn
            lbl_mod_detail.pack_forget()
            cbo_mod_ver.pack_forget()
            lbl_loading_mod.pack_forget()
            
        def dien_danh_sach_ver(ds):
            lbl_loading_ver.config(text="")
            if ds:
                cbo_ver['values'] = ds
                cbo_ver.set(ds[0])
            else:
                cbo_ver['values'] = []
                cbo_ver.set("")
            cap_nhat_mod_loader_theo_loai() 

        # cbo_loai_ver.bind("<<ComboboxSelected>>", cap_nhat_danh_sach_ver)
        cbo_loai_ver.bind("<<ComboboxSelected>>", lambda e: [cap_nhat_danh_sach_ver(), cap_nhat_mod_loader_theo_loai()])
        cap_nhat_danh_sach_ver()  # load Release ngay khi mở

        # 4. Chọn loại Mod Loader
        tk.Label(win_create, text="Chọn Loại Game (Mod Loader):", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        cbo_mod_type = ttk.Combobox(
            win_create,
            values=["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"],
            font=("Arial", 10), state="readonly", width=25
        )
        cbo_mod_type.set("Vanilla")
        cbo_mod_type.pack()

        # 5. Chọn phiên bản Mod Loader cụ thể
        lbl_mod_detail = tk.Label(
            win_create, text="Chọn Phiên bản Mod Loader:",
            font=("Arial", 10, "bold"), fg="#2E7D32"
        )
        cbo_mod_ver = ttk.Combobox(win_create, font=("Arial", 10), state="readonly", width=35)
        lbl_loading_mod = tk.Label(win_create, text="", font=("Arial", 9, "italic"), fg="gray")

        def cap_nhat_list_mod_detail(*args):
            v_goc = cbo_ver.get()
            l_game = cbo_mod_type.get()

            if l_game == "Vanilla":
                lbl_mod_detail.pack_forget()
                cbo_mod_ver.pack_forget()
                lbl_loading_mod.pack_forget()
            else:
                lbl_mod_detail.pack(pady=(10, 2))
                cbo_mod_ver.pack()
                lbl_loading_mod.pack()
                cbo_mod_ver.set("")

                def loading_thread():
                    lbl_loading_mod.config(text=f"Đang tải danh sách {l_game}...")
                    ds = core.tai_danh_sach_mod(l_game, v_goc)
                    win_create.after(0, lambda: dien_du_lieu_mod(ds))

                threading.Thread(target=loading_thread, daemon=True).start()

        def dien_du_lieu_mod(danh_sach):
            lbl_loading_mod.config(text="")
            if danh_sach:
                danh_sach_sach = [str(x) for x in danh_sach if x and str(x).strip() != "Mới nhất"]
                if danh_sach_sach:
                    cbo_mod_ver['values'] = danh_sach_sach
                    cbo_mod_ver.set(danh_sach_sach[0])
                    lbl_loading_mod.config(text=f"Đề xuất: {danh_sach_sach[0]}")
                    return
            cbo_mod_ver['values'] = ["Mặc định"]
            cbo_mod_ver.set("Mặc định")

        cbo_ver.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)
        cbo_mod_type.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)

        # Xử lý nút Xác nhận tạo
        def xu_ly_tao():
            ten_nhap = ent_name.get().strip()

            hop_le, thong_bao = kiem_tra_ten_hop_le(ten_nhap)
            if not hop_le:
                messagebox.showerror("Lỗi tên phiên bản", thong_bao, parent=win_create)
                ent_name.focus()
                return

            if not ten_nhap:
                messagebox.showwarning("Chú ý", "Tên không được để trống!", parent=win_create)
                return

            if not cbo_ver.get():
                messagebox.showwarning("Chú ý", "Vui lòng chọn phiên bản Minecraft!", parent=win_create)
                return

            ten_thu_muc = ten_nhap.replace(" ", "_")

            if ten_nhap in config.current_config["danh_sach_instances"]:
                messagebox.showwarning("Chú ý", "Tên phiên bản này đã tồn tại!", parent=win_create)
                return

            chuoi_mod_goc = cbo_mod_ver.get()
            if chuoi_mod_goc.startswith("Mặc định"):
                chuoi_mod_goc = "Vanilla"

            config.current_config["danh_sach_instances"][ten_nhap] = {
                "version_goc": cbo_ver.get(),
                "loai_game": cbo_mod_type.get(),
                "version_mod": chuoi_mod_goc if cbo_mod_type.get() != "Vanilla" else "Vanilla"
            }
            config.current_config["current_instance"] = ten_nhap
            config.luu_toan_bo_cau_hinh()

            os.makedirs(os.path.join(self.thu_muc_instances, ten_thu_muc), exist_ok=True)

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
        btn_confirm.pack(side=tk.BOTTOM, pady=15)

