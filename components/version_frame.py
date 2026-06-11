import tkinter as tk
from tkinter import ttk
import threading
import os
import config
import core

class VersionFrame(tk.Frame):
    def __init__(self, parent, get_game_path_func, set_status_callback, on_change_callback):
        super().__init__(parent)
        self.get_game_path = get_game_path_func
        self.set_status = set_status_callback
        self.on_change_callback = on_change_callback
        self.create_widgets()

    def create_widgets(self):
        # Chọn phiên bản chính
        lbl_ver = tk.Label(self, text="Chọn phiên bản chính (Vanilla):", font=("Arial", 10))
        lbl_ver.pack()
        
        release_versions = core.lay_danh_sach_phien_ban_chinh()
        self.cbo_versions = ttk.Combobox(self, values=release_versions, font=("Arial", 10), state="readonly", width=22)
        saved_ver = config.current_config.get("version_goc", "1.21.1")
        self.cbo_versions.set(saved_ver if saved_ver in release_versions else release_versions[0])
        self.cbo_versions.pack(pady=5)
        self.cbo_versions.bind("<<ComboboxSelected>>", self.cap_nhat_tuy_chon_mod_loader)

        # Chọn Loại Mod Loader
        lbl_mod = tk.Label(self, text="Chọn Loại Game (Mod Loader):", font=("Arial", 10))
        lbl_mod.pack()
        
        self.cbo_mod_loader = ttk.Combobox(self, values=["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"], font=("Arial", 10), state="readonly", width=22)
        self.cbo_mod_loader.set(config.current_config.get("loai_game", "Vanilla"))
        self.cbo_mod_loader.pack(pady=5)
        self.cbo_mod_loader.bind("<<ComboboxSelected>>", self.cap_nhat_danh_sach_mod_version)

        # Chọn Phiên bản Mod chi tiết (Mặc định chuẩn bị sẵn cấu trúc ẩn/hiện)
        self.lbl_mod_ver = tk.Label(self, text="Chọn Phiên bản Mod Loader cụ thể:", font=("Arial", 10, "bold"), fg="#2E7D32")
        self.cbo_mod_versions = ttk.Combobox(self, font=("Arial", 10), state="readonly", width=35)

    def get_values(self):
        return {
            "version_goc": self.cbo_versions.get(),
            "loai_game": self.cbo_mod_loader.get(),
            "version_mod": self.cbo_mod_versions.get()
        }

    def cap_nhat_tuy_chon_mod_loader(self, *args):
        version_goc = self.cbo_versions.get()
        cac_lua_chon = ["Vanilla"]
        
        try:
            parts = version_goc.split('.')
            sub_ver = int(parts[1]) if len(parts) > 1 else 0
        except:
            sub_ver = 14

        if sub_ver >= 14 or int(parts[0]) >= 26:
            cac_lua_chon.extend(["Fabric", "Quilt"])
        cac_lua_chon.append("Forge")
        if sub_ver >= 20 or int(parts[0]) >= 26:
            cac_lua_chon.append("NeoForge")
            
        self.cbo_mod_loader['values'] = cac_lua_chon
        
        saved_mod_loader = config.current_config.get("loai_game", "Vanilla")
        if saved_mod_loader in cac_lua_chon:
            self.cbo_mod_loader.set(saved_mod_loader)
        else:
            self.cbo_mod_loader.set("Vanilla")
            
        self.on_change_callback()
        self.cap_nhat_danh_sach_mod_version()

    def cap_nhat_danh_sach_mod_version(self, *args):
        version_goc = self.cbo_versions.get()
        loai_game = self.cbo_mod_loader.get()
        self.on_change_callback()
        
        if loai_game == "Vanilla":
            self.lbl_mod_ver.pack_forget()
            self.cbo_mod_versions.pack_forget()
        else:
            self.lbl_mod_ver.pack(pady=(5,0))
            self.cbo_mod_versions.pack(pady=5)

            def code_chay_ngam():
                self.set_status(f"Đang tải danh sách trực tiếp từ {loai_game}...")
                ds_loader = core.tai_danh_sach_mod(loai_game, version_goc)
                
                if not ds_loader and loai_game == "Forge":
                    thu_muc_game = self.get_game_path()
                    thu_muc_versions = os.path.join(thu_muc_game, "versions")
                    if os.path.exists(thu_muc_versions):
                        for folder in os.listdir(thu_muc_versions):
                            if "forge" in folder.lower() and str(version_goc) in str(folder):
                                if folder not in ds_loader:
                                    ds_loader.append(folder)
                        ds_loader = ds_loader[::-1]
                
                if not ds_loader:
                    if loai_game == "Fabric": ds_loader = ["0.16.0", "0.15.11", "0.14.25"]
                    elif loai_game == "Quilt": ds_loader = ["0.26.3", "0.25.0", "0.24.1"]
                    elif loai_game == "Forge": ds_loader = [f"{version_goc}-forge-latest", f"{version_goc}-forge-recommended"]

                self.after(0, lambda: self.config_cbo_mod_versions(ds_loader))
                    
            threading.Thread(target=code_chay_ngam, daemon=True).start()

    def config_cbo_mod_versions(self, danh_sach):
        if danh_sach:
            self.cbo_mod_versions['values'] = danh_sach
            self.cbo_mod_versions.set(danh_sach[0])
            self.set_status("Sẵn sàng")
        else:
            self.cbo_mod_versions['values'] = ["Không tìm thấy bản phù hợp"]
            self.cbo_mod_versions.set("Không tìm thấy bản phù hợp")
            self.set_status("Không có bản Mod Loader tương thích!")