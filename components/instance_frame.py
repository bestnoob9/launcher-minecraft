import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import time
import unicodedata
import json
import config
import core
import theme
from icon_utils import gan_icon_app
from components.install_utils import (
    ten_folder_an_toan, instance_dang_duoc_cai,
    _dang_ky_dang_cai, _huy_dang_ky_dang_cai,
)
from components.dropdown_selector import DropdownSelector

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
    def __init__(self, parent, on_change_callback, modal=None):
        super().__init__(parent)
        self.on_change_callback = on_change_callback
        # modal: doi tuong components.modal.AppModal do app truyen vao (xem
        # main.py). Co no thi Tao/Xoa/Sua chua phien ban se hien qua 1 panel
        # giua launcher thay vi tk.Toplevel. Neu None, dung fallback cu.
        self.modal = modal
        self.on_open_create_panel = None
        self.thu_muc_goc = config.current_config["thu_muc_game"]
        self.thu_muc_instances = os.path.join(self.thu_muc_goc, "Instances")
        os.makedirs(self.thu_muc_instances, exist_ok=True)
        self.create_widgets()
        self._watcher_running = True
        self._watcher_thread = threading.Thread(target=self._sync_watcher, daemon=True)
        self._watcher_thread.start()

    def create_widgets(self):
        lbl_title = tk.Label(self, text="Chọn Thư mục phiên bản (Instance):", font=("Arial", 9), anchor="w")
        lbl_title.pack(fill="x")

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

        if "Latest Version" in config.current_config["danh_sach_instances"]:
            try:
                release_versions = core.lay_danh_sach_phien_ban_chinh()
                ban_moi_nhat = release_versions[0] if release_versions else "1.21.5"
                data_latest = config.current_config["danh_sach_instances"]["Latest Version"]
                if ban_moi_nhat != data_latest.get("version_goc", ""):
                    data_latest["version_goc"] = ban_moi_nhat
                    config.luu_toan_bo_cau_hinh()
            except Exception as e:
                print(f"[LatestVersion] Không thể cập nhật phiên bản: {e}")

        self.selector = DropdownSelector(
            self,
            on_select=self._khi_chon_selector,
            on_delete=self.xoa_instance_theo_ten,
            on_edit=self.sua_instance_theo_ten,
            bottom_text="➕ Tạo phiên bản",
            on_bottom_click=self.mo_cua_so_tao_instance,
            show_icon_box=True,
            placeholder="(Chưa có phiên bản)",
        )
        self.selector.set_items(ds_instance)
        current_saved = config.current_config.get("current_instance", "Latest Version")
        self.selector.set(current_saved if current_saved in ds_instance else ds_instance[0])
        self.selector.pack(fill="x", pady=(3, 5))

    def _get_folders_on_disk(self):
        result = set()
        if not os.path.exists(self.thu_muc_instances):
            return result
        for name in os.listdir(self.thu_muc_instances):
            if os.path.isdir(os.path.join(self.thu_muc_instances, name)):
                result.add(name)
        return result

    def _sync_watcher(self):
        while self._watcher_running:
            try:
                self._dong_bo_instances()
            except Exception:
                pass
            time.sleep(2)

    def _dong_bo_instances(self):
        folders_disk = self._get_folders_on_disk()
        instances_config = set(config.current_config.get("danh_sach_instances", {}).keys())

        _SPECIAL_INSTANCES = {"Latest Version", "Latest_Version"}
        them_moi = folders_disk - instances_config - _SPECIAL_INSTANCES

        bi_xoa = instances_config - folders_disk - _SPECIAL_INSTANCES

        # Bo qua cac ten dang duoc mod_mc/install_utils cai dat modpack: folder
        # cua chung da ton tai tren dia (moi tao) truoc khi instance_info.json
        # duoc ghi that su (chi ghi luc cai XONG), nen neu khong bo qua o day,
        # watcher se "doan mo" loai loader/phien ban (thuong sai, vd Vanilla)
        # va them nham vao config ngay giua luc dang tai file.
        them_moi = {t for t in them_moi if not instance_dang_duoc_cai(t)}
        bi_xoa   = {t for t in bi_xoa if not instance_dang_duoc_cai(t)}

        if not them_moi and not bi_xoa:
            return

        changed = False

        for ten in them_moi:
            ten_folder = ten_folder_an_toan(ten)
            file_info = os.path.join(self.thu_muc_instances, ten_folder, "instance_info.json")

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

                    if loai_game == "Forge" and version_mod not in ("Vanilla", "") \
                            and not version_mod.startswith(version_goc):
                        version_mod = f"{version_goc}-{version_mod}"
                        data["version_mod"] = version_mod
                        try:
                            with open(file_info, "w", encoding="utf-8") as fw:
                                json.dump(data, fw, indent=4, ensure_ascii=False)
                        except Exception:
                            pass
                except Exception:
                    loai_game, version_goc, version_mod = "Vanilla", "1.21.1", "Vanilla"
            else:

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

            if config.current_config.get("current_instance") == ten:
                config.current_config["current_instance"] = "Latest Version"
            changed = True

        if changed:
            config.luu_toan_bo_cau_hinh()
            self.after(0, self._lam_moi_dropdown)
            # Danh sach Instance thay doi tu watcher nen (vd nguoi dung xoa
            # thu muc Instance thu cong ngoai app) - dong bo luon cac tab
            # Modpack/Mod dang mo (neu co), giong nhu khi bam nut Xoa trong UI.
            self.after(0, self.on_change_callback)

    def _lam_moi_dropdown(self):
        ds_moi = list(config.current_config["danh_sach_instances"].keys())
        hien_tai = self.selector.get()
        current_in_config = config.current_config.get("current_instance", "")
        self.selector.set_items(ds_moi)

        if current_in_config and current_in_config in ds_moi:
            self.selector.set(current_in_config)
        elif hien_tai in ds_moi:
            self.selector.set(hien_tai)
        elif ds_moi:
            self.selector.set(ds_moi[0])

    def khoa(self, tat: bool):
        self.selector.configure_state(not tat)

    # ------------------------------------------------------------------
    # XOA INSTANCE
    # ------------------------------------------------------------------
    def xoa_instance_theo_ten(self, ten=None):
        """Xoa 1 phien ban theo ten duoc truyen vao (dung cho icon "X" tren
        tung dong trong dropdown - co the KHONG phai phien ban dang duoc
        chon). Neu khong truyen ten, mac dinh xoa phien ban dang chon hien
        tai (giu tuong thich nguoc voi cach goi cu)."""
        ten_instance = ten if ten is not None else self.get_current_instance()
        if not ten_instance:
            return
        if ten_instance == "Latest Version":
            thong_bao = "Không thể xóa phiên bản mặc định hệ thống!"
            if self.modal is not None:
                self.modal.alert("Chú ý", thong_bao)
            else:
                messagebox.showwarning("Chú ý", thong_bao)
            return

        def _thuc_hien_xoa():
            if ten_instance in config.current_config["danh_sach_instances"]:
                del config.current_config["danh_sach_instances"][ten_instance]
            dang_chon_bi_xoa = (ten_instance == self.get_current_instance())
            if dang_chon_bi_xoa:
                config.current_config["current_instance"] = "Latest Version"
            config.luu_toan_bo_cau_hinh()
            ten_folder = ten_folder_an_toan(ten_instance)
            duong_dan_folder = os.path.join(self.thu_muc_instances, ten_folder)
            if os.path.exists(duong_dan_folder):
                try:
                    import shutil
                    shutil.rmtree(duong_dan_folder)
                except Exception as e:
                    print(f"Không thể xóa thư mục vật lý: {e}")
            self._lam_moi_dropdown()
            self.on_change_callback()

        if self.modal is not None:
            self.modal.confirm(
                title="Xóa phiên bản",
                message=f"Bạn có chắc chắn muốn xóa hoàn toàn phiên bản '{ten_instance}'?",
                on_confirm=_thuc_hien_xoa,
                confirm_text="Xóa",
            )
            return

        # Fallback (khong co modal): giu messagebox cu.
        xac_nhan = messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa hoàn toàn phiên bản '{ten_instance}'?")
        if not xac_nhan:
            return
        _thuc_hien_xoa()
        messagebox.showinfo("Thành công", f"Đã xóa phiên bản: {ten_instance}")

    # Giu ten cu de tuong thich, phong khi co cho khac dang goi truc tiep.
    def _xoa_instance_hien_tai(self):
        self.xoa_instance_theo_ten(None)

    # ------------------------------------------------------------------
    # SUA CHUA MOD LOADER
    # ------------------------------------------------------------------
    def sua_instance_theo_ten(self, ten=None):
        """Mo panel 'Sua chua Mod Loader' cho phien ban duoc truyen vao
        (dung cho icon "✏" tren tung dong trong dropdown). Neu dong duoc
        bam KHONG phai phien ban dang chon, chuyen selector sang dong do
        truoc (cap nhat current_instance) roi moi mo panel sua chua."""
        ten_instance = ten if ten is not None else self.get_current_instance()
        if not ten_instance:
            return
        if ten_instance != self.get_current_instance():
            self.selector.set(ten_instance)
            self._khi_chon_selector(ten_instance)
        self._mo_panel_sua_chua()

    def _mo_panel_sua_chua(self):
        """Mo panel 'Sua chua phien ban' - CHI cho phep doi phien ban cua Mod
        Loader (vd Forge 47.2.0 -> 47.3.7), giu nguyen phien ban Minecraft goc
        va toan bo mod/dữ lieu da cai. Dung khi loader bi loi/thieu file ma
        khong muon tao lai instance tu dau."""
        ten_instance = self.get_current_instance()
        if not ten_instance:
            return

        info = self.get_instance_values()
        loai_game = info.get("loai_game", "Vanilla")
        version_goc = info.get("version_goc", "")
        version_mod_hien_tai = info.get("version_mod", "")

        if loai_game == "Vanilla":
            thong_bao = ("Phiên bản này đang dùng Vanilla (không có Mod "
                         "Loader) nên không có phiên bản Loader nào để sửa chữa.")
            if self.modal is not None:
                self.modal.alert("Không cần sửa chữa", thong_bao)
            else:
                # Fallback (khong co modal): giu messagebox cu.
                messagebox.showinfo("Không cần sửa chữa", thong_bao)
            return

        theme.preload_combobox_options(self)

        if self.modal is None:
            self._toplevel_sua_chua(ten_instance, loai_game, version_goc, version_mod_hien_tai)
            return

        # ctx la 1 "hop" trang thai dung chung giua build_fn (chay ben
        # trong card) va close_guard (chay khi nguoi dung co gang dong
        # modal) - can thiet vi 2 ham nay duoc tao/goi o cac thoi diem khac
        # nhau nen khong the dung closure thuong cho 1 bien duy nhat.
        ctx = {"dang_sua": False, "cancel_event": threading.Event()}

        def _guard():
            if not ctx["dang_sua"]:
                return True
            # Dang sua chua: khong the dong sync nhu askyesno cu duoc nua vi
            # modal.confirm() mo bat dong bo (khong block). Chan dong ngay
            # (return False) va tu mo 1 confirm long ben tren panel sua
            # chua; neu nguoi dung xac nhan huy thi tu goi self.modal.close()
            # de dong luon panel sua chua phia duoi.
            def _xac_nhan_huy():
                ctx["cancel_event"].set()
                self.modal.close()
            self.modal.confirm(
                title="Hủy sửa chữa?",
                message="Đang sửa chữa Mod Loader, bạn có chắc muốn hủy?",
                on_confirm=_xac_nhan_huy,
                confirm_text="Hủy sửa chữa",
                cancel_text="Không",
            )
            return False

        self.modal.open(
            lambda card, close: self._build_repair_panel(
                card, close, ten_instance, loai_game, version_goc,
                version_mod_hien_tai, ctx),
            width=440, close_guard=_guard,
        )

    def _build_repair_panel(self, card, close, ten_instance, loai_game,
                             version_goc, version_mod_hien_tai, ctx):
        colors = theme.colors()
        card.configure(bg=colors["bg_alt"])
        content = tk.Frame(card, bg=colors["bg_alt"])
        content.pack(fill="both", expand=True, padx=18, pady=16)

        tk.Label(content, text="🛠 Sửa chữa Mod Loader", font=("Arial", 12, "bold"),
                 bg=colors["bg_alt"], fg="#FF9800").pack(anchor="w")
        tk.Label(content, text=f"Phiên bản: {ten_instance}", font=("Arial", 10, "bold"),
                 bg=colors["bg_alt"], fg=colors["fg_title"]).pack(anchor="w", pady=(6, 0))
        tk.Label(content, text=f"Loại Loader: {loai_game}  |  Minecraft: {version_goc}",
                 font=("Arial", 9), bg=colors["bg_alt"], fg=colors["fg_desc"]
                 ).pack(anchor="w", pady=(2, 0))
        tk.Label(content, text=f"Phiên bản Loader hiện tại: {version_mod_hien_tai}",
                 font=("Arial", 9, "italic"), bg=colors["bg_alt"], fg="#2E7D32"
                 ).pack(anchor="w", pady=(2, 10))
        tk.Label(content, text="⚠ Chỉ thay đổi phiên bản Mod Loader. Mod, resource pack,\n"
                                "save,... của phiên bản này sẽ được giữ nguyên.",
                 font=("Arial", 8), bg=colors["bg_alt"], fg=colors["fg_desc"],
                 justify="left").pack(anchor="w", pady=(0, 8))

        tk.Label(content, text="Chọn phiên bản Mod Loader mới:", font=("Arial", 10, "bold"),
                 bg=colors["bg_alt"], fg=colors["fg_title"]).pack(anchor="w", pady=(0, 2))
        cbo_mod_ver = ttk.Combobox(content, font=("Arial", 10), state="readonly", width=32)
        cbo_mod_ver.pack(fill="x")
        lbl_loading = tk.Label(content, text="Đang tải danh sách phiên bản...",
                                font=("Arial", 8, "italic"), bg=colors["bg_alt"], fg="gray")
        lbl_loading.pack(anchor="w", pady=(2, 8))

        def _con_ton_tai():
            try:
                return bool(card.winfo_exists())
            except Exception:
                return False

        def _tai_ds():
            try:
                ds = core.tai_danh_sach_mod(loai_game, version_goc)
            except Exception:
                ds = []
            self.after(0, lambda: _dien(ds))

        def _dien(ds):
            if not _con_ton_tai():
                return
            ds_sach = [str(x) for x in ds if x and str(x).strip() != "Mới nhất"] if ds else []
            if ds_sach:
                cbo_mod_ver['values'] = ds_sach
                cbo_mod_ver.set(version_mod_hien_tai if version_mod_hien_tai in ds_sach else ds_sach[0])
                lbl_loading.config(text=f"Mới nhất: {ds_sach[0]}")
            else:
                gia_tri = [version_mod_hien_tai] if version_mod_hien_tai else []
                cbo_mod_ver['values'] = gia_tri
                cbo_mod_ver.set(version_mod_hien_tai)
                lbl_loading.config(text="Không tải được danh sách phiên bản Loader.")

        threading.Thread(target=_tai_ds, daemon=True).start()

        lbl_status = tk.Label(content, text="", font=("Arial", 9), bg=colors["bg_alt"], fg="#1E88E5")
        lbl_status.pack(anchor="w", pady=(4, 2))
        pb_var = tk.DoubleVar(value=0)
        pb = ttk.Progressbar(content, orient="horizontal", mode="determinate",
                              variable=pb_var, maximum=100)
        pb.pack(fill="x", pady=(0, 10))

        def _bat_dau_sua():
            phien_ban_moi = cbo_mod_ver.get().strip()
            if not phien_ban_moi:
                self.modal.alert("Chú ý", "Vui lòng chọn phiên bản Mod Loader!")
                return
            if phien_ban_moi == version_mod_hien_tai:
                # Truoc day dung messagebox.askyesno (dong, cho ket qua ngay).
                # modal.confirm() mo bat dong bo nen phai tach phan "thuc su
                # bat dau sua" ra ham rieng (_tien_hanh_sua) de goi lai trong
                # on_confirm khi nguoi dung xac nhan.
                self.modal.confirm(
                    title="Xác nhận",
                    message="Phiên bản Loader đang chọn giống phiên bản hiện tại.\n"
                            "Vẫn muốn cài đặt lại (sửa chữa) không?",
                    on_confirm=lambda: _tien_hanh_sua(phien_ban_moi),
                    confirm_text="Cài lại",
                    cancel_text="Hủy",
                    danger=False,
                )
                return
            _tien_hanh_sua(phien_ban_moi)

        def _tien_hanh_sua(phien_ban_moi):
            ctx["dang_sua"] = True
            btn_confirm.configure(state="disabled")
            cbo_mod_ver.configure(state="disabled")
            self.khoa(True)

            ten_folder = ten_folder_an_toan(ten_instance)
            _dang_ky_dang_cai(ten_instance, ten_folder)

            def _bao_tien_do(pct, msg):
                def _cap():
                    if not _con_ton_tai():
                        return
                    try:
                        if pct is not None:
                            pb_var.set(pct)
                        if msg:
                            lbl_status.config(text=msg, fg="#1E88E5")
                    except tk.TclError:
                        pass
                self.after(0, _cap)

            def _worker():
                loi = None
                try:
                    core.cai_dat_va_lay_lenh_chay(
                        loai_game, version_goc, phien_ban_moi,
                        self.thu_muc_goc, ten_folder, {},
                        callback_progress=_bao_tien_do,
                        should_cancel=lambda: ctx["cancel_event"].is_set()
                    )
                except InterruptedError:
                    loi = "__HUY__"
                except Exception as e:
                    loi = str(e)
                self.after(0, lambda: _xong(loi))

            def _xong(loi):
                _huy_dang_ky_dang_cai(ten_instance, ten_folder)
                ctx["dang_sua"] = False
                self.khoa(False)

                if not _con_ton_tai():
                    # Modal da bi dong giua chung (vd nguoi dung xac nhan
                    # huy) - khong dong bo lai UI cua panel nua, nhung neu
                    # thanh cong van luu ket qua cai dat vao config.
                    if loi and loi != "__HUY__":
                        pass
                    return

                if loi == "__HUY__":
                    lbl_status.config(text="Đã hủy sửa chữa.", fg="#E53935")
                    btn_confirm.configure(state="normal")
                    cbo_mod_ver.configure(state="readonly")
                    return
                if loi:
                    lbl_status.config(text=f"Lỗi: {loi}", fg="#E53935")
                    btn_confirm.configure(state="normal")
                    cbo_mod_ver.configure(state="readonly")
                    self.modal.alert("Sửa chữa thất bại", f"Không thể sửa chữa Mod Loader:\n{loi}")
                    return

                config.current_config["danh_sach_instances"][ten_instance]["version_mod"] = phien_ban_moi
                config.luu_toan_bo_cau_hinh()
                try:
                    file_info = os.path.join(self.thu_muc_instances, ten_folder, "instance_info.json")
                    data_ghi = {"loai_game": loai_game, "version_goc": version_goc,
                                "version_mod": phien_ban_moi}
                    with open(file_info, "w", encoding="utf-8") as f:
                        json.dump(data_ghi, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass

                self.cap_nhat_nhan_thong_tin()
                self.on_change_callback()
                lbl_status.config(text="Sửa chữa thành công!", fg="#2E7D32")
                close()

            threading.Thread(target=_worker, daemon=True).start()

        btn_bar = tk.Frame(content, bg=colors["bg_alt"])
        btn_bar.pack(fill="x", pady=(4, 0))
        tk.Button(btn_bar, text="Đóng", font=("Arial", 10), bg=colors["bg"],
                  fg=colors["fg_title"], relief="flat", padx=14, pady=6,
                  command=close).pack(side="right", padx=(8, 0))
        btn_confirm = tk.Button(
            btn_bar, text="🛠 Bắt đầu sửa chữa", font=("Arial", 10, "bold"),
            bg="#FF9800", fg="white", relief="flat", padx=14, pady=8,
            command=_bat_dau_sua)
        btn_confirm.pack(side="right")

    def _toplevel_sua_chua(self, ten_instance, loai_game, version_goc, version_mod_hien_tai):
        """Fallback cu bang Toplevel (chi dung khi khong truyen modal vao InstanceFrame)."""
        win = tk.Toplevel(self)
        win.title(f"Sửa chữa Mod Loader — {ten_instance}")
        win.geometry("440x340")
        win.resizable(False, False)
        win.grab_set()
        gan_icon_app(win)

        tk.Label(win, text=f"🛠 Sửa chữa Mod Loader", font=("Arial", 12, "bold"),
                 fg="#FF9800").pack(pady=(15, 2))
        tk.Label(win, text=f"Phiên bản: {ten_instance}", font=("Arial", 10, "bold")).pack()
        tk.Label(win, text=f"Loại Loader: {loai_game}  |  Minecraft: {version_goc}",
                 font=("Arial", 9), fg="#607D8B").pack(pady=(2, 0))
        tk.Label(win, text=f"Phiên bản Loader hiện tại: {version_mod_hien_tai}",
                 font=("Arial", 9, "italic"), fg="#2E7D32").pack(pady=(2, 10))
        tk.Label(win, text="⚠ Chỉ thay đổi phiên bản Mod Loader. Mod, resource pack,\n"
                            "save,... của phiên bản này sẽ được giữ nguyên.",
                 font=("Arial", 8), fg="#9E9E9E", justify="center").pack(pady=(0, 8))

        tk.Label(win, text="Chọn phiên bản Mod Loader mới:", font=("Arial", 10, "bold")).pack(pady=(0, 2))
        cbo_mod_ver = ttk.Combobox(win, font=("Arial", 10), state="readonly", width=32)
        cbo_mod_ver.pack()
        lbl_loading = tk.Label(win, text="Đang tải danh sách phiên bản...",
                                font=("Arial", 8, "italic"), fg="gray")
        lbl_loading.pack(pady=(2, 8))

        def _tai_ds():
            try:
                ds = core.tai_danh_sach_mod(loai_game, version_goc)
            except Exception:
                ds = []
            win.after(0, lambda: _dien(ds))

        def _dien(ds):
            ds_sach = [str(x) for x in ds if x and str(x).strip() != "Mới nhất"] if ds else []
            if ds_sach:
                cbo_mod_ver['values'] = ds_sach
                cbo_mod_ver.set(version_mod_hien_tai if version_mod_hien_tai in ds_sach else ds_sach[0])
                lbl_loading.config(text=f"Mới nhất: {ds_sach[0]}")
            else:
                gia_tri = [version_mod_hien_tai] if version_mod_hien_tai else []
                cbo_mod_ver['values'] = gia_tri
                cbo_mod_ver.set(version_mod_hien_tai)
                lbl_loading.config(text="Không tải được danh sách phiên bản Loader.")

        threading.Thread(target=_tai_ds, daemon=True).start()

        lbl_status = tk.Label(win, text="", font=("Arial", 9), fg="#1E88E5")
        lbl_status.pack(pady=(4, 2))
        pb_var = tk.DoubleVar(value=0)
        pb = ttk.Progressbar(win, orient="horizontal", mode="determinate",
                              variable=pb_var, maximum=100)
        pb.pack(fill="x", padx=24, pady=(0, 10))

        cancel_event = threading.Event()
        trang_thai = {"dang_sua": False}

        def _dong_cua_so():
            if trang_thai["dang_sua"]:
                if not messagebox.askyesno(
                        "Hủy sửa chữa?",
                        "Đang sửa chữa Mod Loader, bạn có chắc muốn hủy?", parent=win):
                    return
                cancel_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _dong_cua_so)

        def _bat_dau_sua():
            phien_ban_moi = cbo_mod_ver.get().strip()
            if not phien_ban_moi:
                messagebox.showwarning("Chú ý", "Vui lòng chọn phiên bản Mod Loader!", parent=win)
                return
            if phien_ban_moi == version_mod_hien_tai:
                if not messagebox.askyesno(
                        "Xác nhận",
                        "Phiên bản Loader đang chọn giống phiên bản hiện tại.\n"
                        "Vẫn muốn cài đặt lại (sửa chữa) không?", parent=win):
                    return

            trang_thai["dang_sua"] = True
            btn_confirm.configure(state="disabled")
            cbo_mod_ver.configure(state="disabled")
            self.khoa(True)

            ten_folder = ten_folder_an_toan(ten_instance)
            _dang_ky_dang_cai(ten_instance, ten_folder)

            def _bao_tien_do(pct, msg):
                def _cap():
                    try:
                        if pct is not None:
                            pb_var.set(pct)
                        if msg:
                            lbl_status.config(text=msg, fg="#1E88E5")
                    except tk.TclError:
                        pass
                try:
                    win.after(0, _cap)
                except Exception:
                    pass

            def _worker():
                loi = None
                try:
                    core.cai_dat_va_lay_lenh_chay(
                        loai_game, version_goc, phien_ban_moi,
                        self.thu_muc_goc, ten_folder, {},
                        callback_progress=_bao_tien_do,
                        should_cancel=lambda: cancel_event.is_set()
                    )
                except InterruptedError:
                    loi = "__HUY__"
                except Exception as e:
                    loi = str(e)
                try:
                    win.after(0, lambda: _xong(loi))
                except Exception:
                    pass

            def _xong(loi):
                _huy_dang_ky_dang_cai(ten_instance, ten_folder)
                trang_thai["dang_sua"] = False
                self.khoa(False)

                if loi == "__HUY__":
                    lbl_status.config(text="Đã hủy sửa chữa.", fg="#E53935")
                    btn_confirm.configure(state="normal")
                    cbo_mod_ver.configure(state="readonly")
                    return
                if loi:
                    lbl_status.config(text=f"Lỗi: {loi}", fg="#E53935")
                    btn_confirm.configure(state="normal")
                    cbo_mod_ver.configure(state="readonly")
                    messagebox.showerror(
                        "Sửa chữa thất bại",
                        f"Không thể sửa chữa Mod Loader:\n{loi}", parent=win)
                    return

                config.current_config["danh_sach_instances"][ten_instance]["version_mod"] = phien_ban_moi
                config.luu_toan_bo_cau_hinh()
                try:
                    file_info = os.path.join(self.thu_muc_instances, ten_folder, "instance_info.json")
                    data_ghi = {"loai_game": loai_game, "version_goc": version_goc,
                                "version_mod": phien_ban_moi}
                    with open(file_info, "w", encoding="utf-8") as f:
                        json.dump(data_ghi, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass

                self.cap_nhat_nhan_thong_tin()
                self.on_change_callback()
                lbl_status.config(text="Sửa chữa thành công!", fg="#2E7D32")
                messagebox.showinfo(
                    "Thành công",
                    f"Đã sửa chữa Mod Loader cho '{ten_instance}'\n"
                    f"sang phiên bản: {phien_ban_moi}", parent=win)
                win.destroy()

            threading.Thread(target=_worker, daemon=True).start()

        btn_confirm = tk.Button(
            win, text="🛠 Bắt đầu sửa chữa", font=("Arial", 10, "bold"),
            bg="#FF9800", fg="white", width=22, height=2,
            command=_bat_dau_sua)
        btn_confirm.pack(pady=(4, 14))

        theme.apply_theme(win)

    def get_game_path(self):
        return self.thu_muc_goc

    def destroy(self):
        self._watcher_running = False
        super().destroy()

    def get_current_instance(self):
        return self.selector.get()

    def get_instance_values(self):
        name = self.get_current_instance()
        return config.current_config["danh_sach_instances"].get(
            name, {"version_goc": "1.21.5", "loai_game": "Vanilla", "version_mod": "Vanilla"}
        )

    def cap_nhat_nhan_thong_tin(self):
        # Da bo nhan chu nho "Loại loader / Phiên bản..." theo yeu cau
        # thiet ke moi (khong con self.lbl_info); giu lai ham nay (khong
        # lam gi) de cac cho khac trong file goi no khong bi loi.
        pass

    def _khi_chon_selector(self, ten):
        if ten:
            config.current_config["current_instance"] = ten
            config.luu_toan_bo_cau_hinh()
        self.on_change_callback()

    def khi_chuyen_instance(self, event=None):
        ten = self.selector.get()
        self._khi_chon_selector(ten)

    # ------------------------------------------------------------------
    # TAO INSTANCE
    # ------------------------------------------------------------------
    def mo_cua_so_tao_instance(self):
        if self.on_open_create_panel:
            self.on_open_create_panel()
            return
        if self.modal is not None:
            theme.preload_combobox_options(self)
            self.modal.open(self.build_create_panel, width=460)
            return
        self._mo_toplevel_tao_instance()

    def build_create_panel(self, parent, close):
        """Dung form 'Tao phien ban moi' ben trong 1 card cua modal (parent
        = card, close = ham dong modal). Giu nguyen toan bo logic (load
        danh sach version bat dong bo, kiem tra ten hop le, luu config...)."""
        colors = theme.colors()
        parent.configure(bg=colors["bg_alt"])
        content = tk.Frame(parent, bg=colors["bg_alt"])
        content.pack(fill="both", expand=True, padx=18, pady=16)

        bar = tk.Frame(content, bg=colors["bg_alt"])
        bar.pack(fill="x", pady=(0, 10))
        tk.Label(bar, text="➕ Tạo phiên bản mới", font=("Arial", 12, "bold"),
                 bg=colors["bg_alt"], fg=colors["fg_title"]).pack(side="left")
        tk.Button(bar, text="✕", font=("Arial", 9, "bold"), bg=colors["bg_alt"],
                  fg=colors["fg_desc"], relief="flat", bd=0, cursor="hand2",
                  command=close).pack(side="right")

        def _label(text, **kw):
            return tk.Label(content, text=text, font=("Arial", 10, "bold"),
                             bg=colors["bg_alt"], fg=colors["fg_title"], anchor="w", **kw)

        _label("Tên thư mục phiên bản (Instance):").pack(fill="x", pady=(4, 2))
        ent_name = tk.Entry(content, font=("Arial", 10), bg=colors["entry_bg"],
                             fg=colors["entry_fg"], insertbackground=colors["entry_fg"],
                             relief="solid", bd=1)
        ent_name.pack(fill="x")
        ent_name.focus_set()

        lbl_ten_loi = tk.Label(content, text="", font=("Arial", 8, "italic"),
                                bg=colors["bg_alt"], fg="red", anchor="w", justify="left")
        lbl_ten_loi.pack(fill="x")

        def kiem_tra_realtime(*args):
            hop_le, thong_bao = kiem_tra_ten_hop_le(ent_name.get())
            lbl_ten_loi.config(text=f"⚠ {thong_bao.splitlines()[0]}" if not hop_le else "")

        ent_name.bind("<KeyRelease>", kiem_tra_realtime)

        _label("Loại phiên bản:").pack(fill="x", pady=(8, 2))
        cbo_loai_ver = ttk.Combobox(content, values=["Release", "Snapshot", "Beta", "Alpha"],
                                     font=("Arial", 10), state="readonly")
        cbo_loai_ver.set("Release")
        cbo_loai_ver.pack(fill="x")

        _label("Chọn phiên bản Minecraft:").pack(fill="x", pady=(8, 2))
        cbo_ver = ttk.Combobox(content, values=[], font=("Arial", 10), state="readonly")
        cbo_ver.pack(fill="x")
        lbl_loading_ver = tk.Label(content, text="", font=("Arial", 8, "italic"),
                                    bg=colors["bg_alt"], fg="gray", anchor="w")
        lbl_loading_ver.pack(fill="x")

        _label("Chọn Loại Game (Mod Loader):").pack(fill="x", pady=(8, 2))
        cbo_mod_type = ttk.Combobox(content, values=["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"],
                                     font=("Arial", 10), state="readonly")
        cbo_mod_type.set("Vanilla")
        cbo_mod_type.pack(fill="x")

        lbl_mod_detail = tk.Label(content, text="Chọn Phiên bản Mod Loader:",
                                   font=("Arial", 10, "bold"), bg=colors["bg_alt"], fg="#2E7D32", anchor="w")
        cbo_mod_ver = ttk.Combobox(content, font=("Arial", 10), state="readonly")
        lbl_loading_mod = tk.Label(content, text="", font=("Arial", 9, "italic"),
                                    bg=colors["bg_alt"], fg="gray", anchor="w")

        def _con_ton_tai():
            try:
                return bool(content.winfo_exists())
            except Exception:
                return False

        def cap_nhat_mod_loader_theo_loai():
            loai = cbo_loai_ver.get()
            loaders = {
                "Release": ["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"],
                "Snapshot": ["Vanilla", "Fabric", "Quilt"],
            }.get(loai, ["Vanilla"])
            cbo_mod_type['values'] = loaders
            cbo_mod_type.set("Vanilla")
            lbl_mod_detail.pack_forget()
            cbo_mod_ver.pack_forget()
            lbl_loading_mod.pack_forget()

        def dien_danh_sach_ver(ds):
            if not _con_ton_tai():
                return
            lbl_loading_ver.config(text="")
            cbo_ver['values'] = ds
            cbo_ver.set(ds[0] if ds else "")
            cap_nhat_mod_loader_theo_loai()

        def cap_nhat_danh_sach_ver(*args):
            mapping = {"Release": "release", "Snapshot": "snapshot", "Beta": "old_beta", "Alpha": "old_alpha"}
            lbl_loading_ver.config(text="Đang tải...")
            cbo_ver.set("")
            loai_dang_chon = cbo_loai_ver.get()

            def _load():
                try:
                    ds = core.lay_danh_sach_phien_ban_theo_loai(mapping[loai_dang_chon])
                except Exception:
                    ds = []
                self.after(0, lambda: dien_danh_sach_ver(ds))
            threading.Thread(target=_load, daemon=True).start()

        def _dien_mod(ds):
            if not _con_ton_tai():
                return
            lbl_loading_mod.config(text="")
            ds_sach = [str(x) for x in ds if x and str(x).strip() != "Mới nhất"] if ds else []
            if ds_sach:
                cbo_mod_ver['values'] = ds_sach
                cbo_mod_ver.set(ds_sach[0])
                lbl_loading_mod.config(text=f"Đề xuất: {ds_sach[0]}")
            else:
                cbo_mod_ver['values'] = ["Mặc định"]
                cbo_mod_ver.set("Mặc định")

        def cap_nhat_list_mod_detail(*args):
            l_game = cbo_mod_type.get()
            if l_game == "Vanilla":
                lbl_mod_detail.pack_forget()
                cbo_mod_ver.pack_forget()
                lbl_loading_mod.pack_forget()
                return
            lbl_mod_detail.pack(fill="x", pady=(8, 2))
            cbo_mod_ver.pack(fill="x")
            lbl_loading_mod.pack(fill="x")
            cbo_mod_ver.set("")
            v_goc = cbo_ver.get()

            def _load():
                self.after(0, lambda: lbl_loading_mod.config(text=f"Đang tải {l_game}...") if _con_ton_tai() else None)
                ds = core.tai_danh_sach_mod(l_game, v_goc)
                self.after(0, lambda: _dien_mod(ds))
            threading.Thread(target=_load, daemon=True).start()

        cbo_loai_ver.bind("<<ComboboxSelected>>", lambda e: [cap_nhat_danh_sach_ver(), cap_nhat_mod_loader_theo_loai()])
        cbo_ver.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)
        cbo_mod_type.bind("<<ComboboxSelected>>", cap_nhat_list_mod_detail)
        cap_nhat_danh_sach_ver()

        def xu_ly_tao():
            ten_nhap = ent_name.get().strip()
            hop_le, thong_bao = kiem_tra_ten_hop_le(ten_nhap)
            if not hop_le:
                self.modal.alert("Lỗi tên phiên bản", thong_bao)
                return
            if not ten_nhap:
                self.modal.alert("Chú ý", "Tên không được để trống!")
                return
            if not cbo_ver.get():
                self.modal.alert("Chú ý", "Vui lòng chọn phiên bản Minecraft!")
                return
            if ten_nhap in config.current_config["danh_sach_instances"]:
                self.modal.alert("Chú ý", "Tên phiên bản này đã tồn tại!")
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

            ten_thu_muc = ten_folder_an_toan(ten_nhap)
            os.makedirs(os.path.join(self.thu_muc_instances, ten_thu_muc), exist_ok=True)

            ds_moi = list(config.current_config["danh_sach_instances"].keys())
            self.selector.set_items(ds_moi)
            self.selector.set(ten_nhap)
            self.cap_nhat_nhan_thong_tin()
            self.on_change_callback()
            close()

        btn_bar = tk.Frame(content, bg=colors["bg_alt"])
        btn_bar.pack(fill="x", pady=(16, 0))
        tk.Button(btn_bar, text="Hủy", font=("Arial", 10), bg=colors["bg"],
                  fg=colors["fg_title"], relief="flat", padx=14, pady=8,
                  command=close).pack(side="right", padx=(8, 0))
        tk.Button(btn_bar, text="✔ XÁC NHẬN TẠO", font=("Arial", 10, "bold"),
                  bg="#4CAF50", fg="white", relief="flat", padx=14, pady=8,
                  command=xu_ly_tao).pack(side="right")

    def _mo_toplevel_tao_instance(self):
        """Fallback cu (chi dung khi khong truyen modal vao InstanceFrame)."""
        theme.preload_combobox_options(self)
        win_create = tk.Toplevel(self)
        win_create.title("Tạo phiên bản mới")
        win_create.geometry("420x480")
        win_create.resizable(False, False)
        win_create.grab_set()
        gan_icon_app(win_create)
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

        tk.Label(win_create, text="Loại phiên bản:", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        cbo_loai_ver = ttk.Combobox(
            win_create,
            values=["Release", "Snapshot", "Beta", "Alpha"],
            font=("Arial", 10), state="readonly", width=25
        )
        cbo_loai_ver.set("Release")
        cbo_loai_ver.pack()

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
            else:
                loaders = ["Vanilla"]

            cbo_mod_type['values'] = loaders
            cbo_mod_type.set("Vanilla")

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

        cbo_loai_ver.bind("<<ComboboxSelected>>", lambda e: [cap_nhat_danh_sach_ver(), cap_nhat_mod_loader_theo_loai()])
        cap_nhat_danh_sach_ver()

        tk.Label(win_create, text="Chọn Loại Game (Mod Loader):", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        cbo_mod_type = ttk.Combobox(
            win_create,
            values=["Vanilla", "Fabric", "Forge", "Quilt", "NeoForge"],
            font=("Arial", 10), state="readonly", width=25
        )
        cbo_mod_type.set("Vanilla")
        cbo_mod_type.pack()

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

            ten_thu_muc = ten_folder_an_toan(ten_nhap)

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
            self.selector.set_items(ds_moi)
            self.selector.set(ten_nhap)
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

        theme.apply_theme(win_create)
