import os
import shutil
import threading
import urllib.parse

import tkinter as tk
from tkinter import ttk, messagebox

import config
from components.api_helpers import (
    lay_curseforge_popular,
    tim_kiem_curseforge,
    lay_phien_ban_curseforge,
    lay_category_curseforge,
)
from components.install_utils import (
    tai_file,
    cai_mod_tu_file,
    cai_rsp_shader_tu_file,
    cai_modpack_tu_file,
    lay_trang_thai_da_cai,
    luu_muc_da_cai,
    luu_modpack_da_cai,
    kiem_tra_ten_da_cai,
    tim_ten_file_da_cai,
)
from components.widgets import make_instance_ctl

_NO_INST = "— Chưa chọn —"

_MC_TO_CF = {
    "1.21.5": "26.3", "1.21.4": "26.2", "1.21.3": "26.1", "1.21.2": "26.1",
    "1.21.1": "26.1", "1.21":   "26.0",
    "1.20.6": "25.2", "1.20.4": "25.2", "1.20.2": "25.1", "1.20.1": "25.0",
    "1.20":   "25.0",
    "1.19.4": "24.4", "1.19.2": "24.2", "1.19.1": "24.1", "1.19": "24.0",
    "1.18.2": "23.2", "1.18.1": "23.1", "1.18": "23.0",
    "1.17.1": "22.1", "1.17": "22.0",
    "1.16.5": "21.5", "1.16.4": "21.4", "1.16.3": "21.3",
    "1.16.2": "21.2", "1.16.1": "21.1", "1.16": "21.0",
}

def _cf_build_url(version_data):
    url = version_data.get("downloadUrl", "")
    if not url:
        fid = version_data.get("id", 0)
        fn  = version_data.get("fileName", "")
        if fid and fn:
            ids = str(fid)
            url = (f"https://mediafilez.forgecdn.net/files/"
                   f"{ids[:4]}/{ids[4:].lstrip('0') or '0'}/{urllib.parse.quote(fn)}")
    return url

class ForgeModMixin:

    def _load_categories_async(self, fb, class_id):
        def _t():
            try:
                cats = lay_category_curseforge(class_id)
                if cats:
                    fb.after(0, lambda: fb.set_categories(cats))
            except Exception:
                pass
        threading.Thread(target=_t, daemon=True).start()

    def _build_modpack_curseforge(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        f  = self.tab_cf
        BG = f["bg"]

        self.lv_cf = tk.Frame(f, bg=BG)
        self.lv_cf.pack(fill="both", expand=True)
        self.dv_cf = tk.Frame(f, bg=BG)
        lv = self.lv_cf

        self.fb_cf = FilterBar(lv, self._search_cf, accent_color="#E64A19", show_category=True, bg=BG)
        self.fb_cf.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_async(self.fb_cf, 4471)
        self.list_cf = ContentTableWidget(lv, "curseforge", self._select_cf,
                                          is_installed_cb=self._is_cf_installed)
        self.list_cf.pack(fill="both", expand=True, padx=10)

        self.pg_cf = PaginationBar(lv, self._goto_cf_page, accent_color="#E64A19", bg=BG)
        self.pg_cf.pack(fill="x", padx=10, pady=(2, 8))

        self._cf_data        = []
        self._cf_files       = []
        self._cf_ver_idx_map = []
        self._cf_page        = 1
        self._cf_total       = 0
        self._cf_last_kw     = None

    def _load_cf_top(self, page=1):
        self._cf_page    = page
        self._cf_last_kw = None
        try:
            r, total = lay_curseforge_popular(class_id=4471, limit=50, offset=(page - 1) * 50)
            self._cf_data  = r
            self._cf_total = total
            self.after(0, lambda: (
                self.list_cf.load(r),
                self.pg_cf.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Modpack (CurseForge) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi CF: {e}", fg="red"))

    def _search_cf(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, ld, c = self.fb_cf.get()
        self._cf_page    = page
        self._cf_last_kw = (kw, mc, ld, c)
        self.lbl_status.config(text="Đang tìm CF...", fg="#E64A19")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, ld, limit=50, class_id=4471,
                                                offset=(page - 1) * 50, category_id=c)
                self._cf_data  = r
                self._cf_total = total
                self.after(0, lambda: (
                    self.list_cf.load(r),
                    self.pg_cf.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} modpack - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi CF: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_cf_page(self, page):
        if self._cf_last_kw is None:
            threading.Thread(target=self._load_cf_top, args=(page,), daemon=True).start()
        else:
            self._search_cf(page)

    def _select_cf(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._cf_data): return
        r   = self._cf_data[idx]
        ten = r.get("name", "")
        mid = r.get("id", "")

        def _install_from_detail(version_data, on_done=None, progress_cb=None):
            def _finish():
                if on_done:
                    self.after(0, on_done)
            url = _cf_build_url(version_data)
            if not url:
                messagebox.showerror("Lỗi",
                    "File nay khong co link tai truc tiep.\n"
                    "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
                _finish()
                return
            fname    = version_data.get("fileName", "modpack.zip")

            _da_cai  = lay_trang_thai_da_cai("modpack", "curseforge", mid)
            ten_inst = _da_cai["ten_instance"] if _da_cai else ten[:30]
            self.lbl_status.config(text="Đang tải từ CurseForge...", fg="#E64A19")
            self._tang_tac_vu()
            def _t():
                try:
                    tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                    os.makedirs(tmp, exist_ok=True)
                    pz = os.path.join(tmp, fname)
                    def prog(da, tong):
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy tai modpack")
                        pct = int(da / tong * 100)
                        self.after(0, lambda: self.lbl_status.config(
                            text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#E64A19"))

                        self.ghi_tien_do(pct // 10, f"Đang tải gói: {pct}%")
                        if progress_cb:
                            self.after(0, lambda: progress_cb(pct // 10, 100))
                    tai_file(url, pz, prog)
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy cai modpack")
                    def _done_va_xoa():
                        try: shutil.rmtree(tmp)
                        except: pass
                        luu_modpack_da_cai(ten_inst, "curseforge", mid,
                                           version_data.get("id"),
                                           version_data.get("displayName", version_data.get("fileName", "")),
                                           ngay=version_data.get("fileDate"))

                        self._giam_tac_vu()
                        self._done()
                        _finish()
                    def _huy_va_xoa():

                        try: shutil.rmtree(tmp)
                        except: pass
                        self._giam_tac_vu()
                        _finish()
                    def _modpack_progress(da_mod, tong_mod):

                        if tong_mod:
                            self.ghi_tien_do(10 + int(da_mod / tong_mod * 90),
                                              f"{da_mod}/{tong_mod} mod")
                        if progress_cb and tong_mod:
                            progress_cb(10 + int(da_mod / tong_mod * 90), 100,
                                        label_text=f"{da_mod}/{tong_mod} mod")
                    cai_modpack_tu_file(pz, ten_inst, self.lbl_status, _done_va_xoa,
                                        cancel_event=self._cancel_event,
                                        progress_cb=_modpack_progress if progress_cb else None,
                                        callback_huy=_huy_va_xoa)
                except TacVuBiHuy:
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Modpack.", fg="#E53935"))
                    self._giam_tac_vu()
                    _finish()
                except Exception as e:
                    self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
                    self._giam_tac_vu()
                    _finish()
            threading.Thread(target=_t, daemon=True).start()

        if view:
            self._swap_to_detail(self.lv_cf, self.dv_cf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#E64A19", installed_info=lay_trang_thai_da_cai(
                                      "modpack", "curseforge", mid),
                                  loai="modpack")
            return

        if install:

            self._tang_tac_vu()
            self.lbl_status.config(text=f"Đang tải phiên bản '{ten}'...", fg="#E64A19")
            def _t():
                try:
                    files = lay_phien_ban_curseforge(mid)
                    def _apply():
                        self._giam_tac_vu()
                        try:
                            fb_mc, _, _ = self.fb_cf.get()
                        except Exception:
                            fb_mc = ""
                        if fb_mc and fb_mc != "Tất cả":
                            cf_ver = _MC_TO_CF.get(fb_mc, fb_mc)
                            idxs = [i for i, fi in enumerate(files)
                                    if cf_ver in fi.get("gameVersions", [])
                                    or fb_mc in fi.get("gameVersions", [])]
                        else:
                            idxs = []
                        best = files[idxs[0]] if idxs else (files[0] if files else None)
                        if not best:
                            messagebox.showwarning("Chú ý", "Không tìm thấy phiên bản phù hợp!", parent=self)
                            return
                        _install_from_detail(best)
                    self.after(0, _apply)
                except Exception as e:
                    def _err(e=e):
                        self._giam_tac_vu()
                        self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                        messagebox.showerror("Lỗi",
                            f"Không tải được danh sách phiên bản Modpack từ CurseForge.\n{e}",
                            parent=self)
                    self.after(0, _err)
            threading.Thread(target=_t, daemon=True).start()
            return

    def _build_mod_curseforge(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        self._modcf_data        = []
        self._modcf_files       = []
        self._modcf_ver_idx_map = []
        self._modcf_page        = 1
        self._modcf_total       = 0
        self._modcf_last_kw     = None
        f  = self.tab_modcf
        BG = f["bg"]

        self.lv_modcf = tk.Frame(f, bg=BG)
        self.lv_modcf.pack(fill="both", expand=True)
        self.dv_modcf = tk.Frame(f, bg=BG)
        lv = self.lv_modcf

        self.fb_modcf = FilterBar(lv, self._search_modcf, accent_color="#F9A825", show_category=True, bg=BG)
        self.fb_modcf.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_async(self.fb_modcf, 6)

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bp, text="Phiên bản mod:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_modcf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_modcf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cài vào Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=2)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_modcf_inst = ttk.Combobox(bp, values=[_NO_INST] + ds_inst, font=("Arial", 9), width=42, height=5)
        self.cbo_modcf_inst.set(_NO_INST)
        self.cbo_modcf_inst.grid(row=1, column=1, padx=6)
        self.cbo_modcf_inst.bind("<<ComboboxSelected>>", lambda e: self._on_modcf_inst_change())
        self.cbo_modcf_inst.bind("<ButtonPress>", lambda e: self._sync_inst_cbo(self.cbo_modcf_inst))
        tk.Button(bp, text="Cài Mod", font=("Arial", 9, "bold"),
                  bg="#F9A825", fg="white", activebackground="#F9A825", activeforeground="white",
                  width=14, pady=4, command=self._install_modcf).grid(row=0, column=2, rowspan=2, padx=8)

        self.list_modcf = ContentTableWidget(lv, "curseforge", self._select_modcf,
                                             is_installed_cb=self._is_modcf_installed)
        self.list_modcf.pack(fill="both", expand=True, padx=10)

        self.pg_modcf = PaginationBar(lv, self._goto_modcf_page, accent_color="#F9A825", bg=BG)
        self.pg_modcf.pack(fill="x", padx=10, pady=(2, 0))

    def _load_modcf_top(self, page=1):
        self._modcf_page    = page
        self._modcf_last_kw = None
        try:
            r, total = lay_curseforge_popular(class_id=6, limit=50, offset=(page - 1) * 50)
            self._modcf_data  = r
            self._modcf_total = total
            self.after(0, lambda: (
                self.list_modcf.load(r),
                self.pg_modcf.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Mod (CurseForge) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi ModCF: {e}", fg="red"))

    def _search_modcf(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, ld, c = self.fb_modcf.get()
        self._modcf_page    = page
        self._modcf_last_kw = (kw, mc, ld, c)
        self.lbl_status.config(text="Đang tìm Mod CurseForge...", fg="#F9A825")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, ld, limit=50, class_id=6,
                                                offset=(page - 1) * 50, category_id=c)
                self._modcf_data  = r
                self._modcf_total = total
                self.after(0, lambda: (
                    self.list_modcf.load(r),
                    self.pg_modcf.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} mod - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi CF: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_modcf_page(self, page):
        if self._modcf_last_kw is None:
            threading.Thread(target=self._load_modcf_top, args=(page,), daemon=True).start()
        else:
            self._search_modcf(page)

    def _lay_installed_info_day_du(self, loai, source, pid, ten_inst, ten_hien_thi):
        """Lay thong tin 'da cai' day du cho ModDetailWindow: uu tien tra index
        (chinh xac ve version), neu khong co thi thu quet ten file trong thu muc
        Instance (bat mod cai thu cong, khong qua launcher nen khong co index)."""
        info = lay_trang_thai_da_cai(loai, source, pid, ten_instance=ten_inst)
        if info:
            return info
        if not ten_inst:
            return None
        ten_file = tim_ten_file_da_cai(ten_inst, loai, ten_hien_thi)
        if not ten_file:
            return None
        return {"ten_instance": ten_inst, "source": source, "version_id": None,
                "version_number": None, "filename": ten_file, "ngay": None}

    def _is_modcf_installed(self, d):
        mid = d.get("id", "")
        ten_inst = self.cbo_modcf_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            return False
        if lay_trang_thai_da_cai("mods", "curseforge", mid, ten_instance=ten_inst):
            return True
        # Du phong: quet ten file trong thu muc mods/ - bat duoc ca mod nguoi
        # dung tu tay bo vao, khong cai qua launcher nen khong co trong index.
        return kiem_tra_ten_da_cai(ten_inst, "mods", d.get("name", ""))

    def _is_cf_installed(self, d):
        # Modpack: khong phu thuoc Instance dang chon (cai modpack se tao Instance moi).
        mid = d.get("id", "")
        return bool(lay_trang_thai_da_cai("modpack", "curseforge", mid))

    def _is_rsp_cf_installed(self, d):
        mid = d.get("id", "")
        ten_inst = self.cbo_rsp_cf_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            return False
        if lay_trang_thai_da_cai("resourcepacks", "curseforge", mid, ten_instance=ten_inst):
            return True
        return kiem_tra_ten_da_cai(ten_inst, "resourcepacks", d.get("name", ""))

    def _is_sh_cf_installed(self, d):
        mid = d.get("id", "")
        ten_inst = self.cbo_sh_cf_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            return False
        if lay_trang_thai_da_cai("shaderpacks", "curseforge", mid, ten_instance=ten_inst):
            return True
        return kiem_tra_ten_da_cai(ten_inst, "shaderpacks", d.get("name", ""))

    def _select_modcf(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._modcf_data): return
        r   = self._modcf_data[idx]
        mid = r.get("id", "")

        if view:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Lỗi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "mod.jar")
                ten_inst = self.cbo_modcf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
                if not ten_inst:
                    messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                    _finish()
                    return
                _, loader = self._get_inst_mc_loader(ten_inst)
                if loader and loader.lower() == "vanilla":
                    messagebox.showwarning("Không thể cài Mod",
                        f"Instance '{ten_inst}' dùng Vanilla (không có mod loader).\n"
                        "Hãy chọn instance dùng Fabric, Forge, Quilt hoặc NeoForge.", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Đang tải Mod từ CurseForge...", fg="#F9A825")
                self._tang_tac_vu()
                def _t():
                    try:
                        tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                        os.makedirs(tmp, exist_ok=True)
                        pz = os.path.join(tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai mod")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(
                                text=f"Đang tải mod: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#F9A825"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai mod")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            luu_muc_da_cai(ten_inst, "mods", mid, "curseforge",
                                           version_data.get("id"),
                                           version_data.get("displayName", version_data.get("fileName", "")),
                                           fname, ngay=version_data.get("fileDate"))
                            self.lbl_status.after(0, lambda: self.lbl_status.config(
                                text=f"Đã cài mod '{fname}' vào {ten_inst}!", fg="#2b8c54"))
                            self.after(0, lambda: self._thong_bao_cai_xong("Mod", fname, ten_inst))
                            _finish()
                        cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
                    except TacVuBiHuy:
                        try: shutil.rmtree(tmp)
                        except: pass
                        self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Mod.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            ten_inst_hien_tai = self.cbo_modcf_inst.get().strip()
            ten_inst_hien_tai = "" if ten_inst_hien_tai == _NO_INST else ten_inst_hien_tai
            self._swap_to_detail(self.lv_modcf, self.dv_modcf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#F9A825", installed_info=self._lay_installed_info_day_du(
                                      "mods", "curseforge", mid, ten_inst_hien_tai, r.get("name", "")),
                                  instance_ctl=make_instance_ctl(self.cbo_modcf_inst, _NO_INST),
                                  loai="mods")
            return

        if install:
            ten_inst_check = self.cbo_modcf_inst.get().strip()
            ten_inst_check = "" if ten_inst_check == _NO_INST else ten_inst_check
            if not ten_inst_check:
                messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                return
            self._tang_tac_vu()
        self.cbo_modcf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Đang tải phiên bản mod...", fg="#F9A825")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._modcf_files = files
                def _apply():
                    self._filter_modcf_ver()
                    if install:
                        started = self._install_modcf()
                        if not started:
                            self._giam_tac_vu()
                self.after(0, _apply)
            except Exception as e:
                def _err(e=e):
                    if install:
                        self._giam_tac_vu()
                    self.lbl_status.config(text=f"Lỗi CF ver: {e}", fg="red")
                    messagebox.showerror("Lỗi",
                        f"Không tải được danh sách phiên bản mod từ CurseForge.\n{e}",
                        parent=self)
                self.after(0, _err)
        threading.Thread(target=_t, daemon=True).start()

    def _on_modcf_inst_change(self):
        """Khi doi Instance trong tab Mod (CurseForge): dong bo bo loc MC/Loader theo
        Instance, roi tai lai (search lai) danh sach Mod dang duyet theo bo loc do."""
        ten_inst = self.cbo_modcf_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        da_doi_bo_loc = self._apply_inst_filter_to_fb(ten_inst, self.fb_modcf) if ten_inst else False
        self._filter_modcf_ver()
        self.list_modcf.refresh_installed_states()
        if da_doi_bo_loc:
            self._search_modcf()

    def _filter_modcf_ver(self):
        files  = self._modcf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst = self.cbo_modcf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        mcv, loader = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        self._apply_inst_filter_to_fb(ten_inst, self.fb_modcf)

        try:
            fb_mc, fb_ld, _ = self.fb_modcf.get()
        except Exception:
            fb_mc, fb_ld = mcv, loader

        use_mc = fb_mc or mcv
        use_ld = fb_ld or loader

        if use_mc:
            cf_ver = _MC_TO_CF.get(use_mc, use_mc)
            idxs = []
            for i, fi in enumerate(files):
                gvs = fi.get("gameVersions", [])
                gvs_lower = [g.lower() for g in gvs]
                if cf_ver not in gvs and use_mc not in gvs:
                    continue
                if use_ld and use_ld not in ("Tất cả", "Vanilla") and use_ld.lower() not in gvs_lower:
                    continue
                idxs.append(i)
        else:
            idxs = list(range(len(files)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._modcf_ver_idx_map = idxs
            self.cbo_modcf_ver.config(values=ds)
            self.cbo_modcf_ver.set(ds[0])
            if ten_inst and use_mc:
                self.lbl_status.config(
                    text=f"Đã lọc {len(ds)} phiên bản phù hợp với {ten_inst} (MC {use_mc}"
                         + (f", {use_ld}" if use_ld and use_ld not in ("Tất cả", "Vanilla") else "") + ").",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chọn phiên bản rồi nhấn Cài Mod.", fg="gray")
        else:
            self._modcf_ver_idx_map = list(range(len(files)))
            self.cbo_modcf_ver.config(values=ds_all)
            if ds_all: self.cbo_modcf_ver.set(ds_all[0])
            else:       self.cbo_modcf_ver.set("")

    def _install_modcf(self):
        """Bắt đầu tải + cài mod đã chọn ở combobox phiên bản.
        Trả về True nếu thực sự khởi động được luồng tải (đã _tang_tac_vu),
        False nếu bị chặn bởi validate (chưa chọn instance/loader sai/thiếu version/thiếu url)."""
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_modcf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self); return False
        _, loader = self._get_inst_mc_loader(ten_inst)
        if loader and loader.lower() == "vanilla":
            messagebox.showwarning("Không thể cài Mod",
                f"Instance '{ten_inst}' dùng Vanilla (không có mod loader).\n"
                "Hãy chọn instance dùng Fabric, Forge, Quilt hoặc NeoForge.", parent=self)
            return False
        iv = self.cbo_modcf_ver.current()
        if iv < 0 or not self._modcf_files:
            messagebox.showwarning("Chú ý",
                "Không tìm thấy phiên bản Mod phù hợp với Instance đã chọn (hoặc chưa chọn phiên bản).",
                parent=self)
            return False
        if iv < len(self._modcf_ver_idx_map):
            iv = self._modcf_ver_idx_map[iv]
        fd  = self._modcf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Lỗi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
            return False
        fname = fd.get("fileName", "mod.jar")
        self.lbl_status.config(text="Đang tải Mod từ CurseForge...", fg="#F9A825")

        self._tang_tac_vu()
        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz = os.path.join(tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai mod")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Đang tải mod: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#F9A825"))
                    self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai mod")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    luu_muc_da_cai(ten_inst, "mods", fd.get("modId", ""), "curseforge",
                                   fd.get("id"), fd.get("displayName", fd.get("fileName", "")),
                                   fname, ngay=fd.get("fileDate"))
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Đã cài mod '{fname}' vào {ten_inst}!", fg="#2b8c54"))
                    self.after(0, lambda: self._thong_bao_cai_xong("Mod", fname, ten_inst))
                cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Mod.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()
        return True

    def _build_rsp_cf_tab(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        self._rsp_cf_data        = []
        self._rsp_cf_files       = []
        self._rsp_cf_ver_idx_map = []
        self._rsp_cf_page        = 1
        self._rsp_cf_total       = 0
        self._rsp_cf_last_kw     = None
        f  = self.tab_rsp_cf
        BG = f["bg"]

        self.lv_rsp_cf = tk.Frame(f, bg=BG)
        self.lv_rsp_cf.pack(fill="both", expand=True)
        self.dv_rsp_cf = tk.Frame(f, bg=BG)
        lv = self.lv_rsp_cf

        self.fb_rsp_cf = FilterBar(lv, self._search_rsp_cf, accent_color="#AB47BC", show_loader=False, show_category=True, bg=BG)
        self.fb_rsp_cf.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_async(self.fb_rsp_cf, 12)

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bp, text="Phiên bản:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_rsp_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_rsp_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cài vào Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=2)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_rsp_cf_inst = ttk.Combobox(bp, values=[_NO_INST] + ds_inst, font=("Arial", 9), width=42, height=5)
        self.cbo_rsp_cf_inst.set(_NO_INST)
        self.cbo_rsp_cf_inst.grid(row=1, column=1, padx=6)

        self.cbo_rsp_cf_inst.bind("<ButtonPress>", lambda e: self._sync_inst_cbo(self.cbo_rsp_cf_inst))
        tk.Button(bp, text="Cài RSP", font=("Arial", 9, "bold"),
                  bg="#AB47BC", fg="white", activebackground="#AB47BC", activeforeground="white",
                  width=14, pady=4, command=self._install_rsp_cf).grid(row=0, column=2, rowspan=2, padx=8)

        self.list_rsp_cf = ContentTableWidget(lv, "curseforge", self._select_rsp_cf,
                                              is_installed_cb=self._is_rsp_cf_installed)
        self.list_rsp_cf.pack(fill="both", expand=True, padx=10)
        self.cbo_rsp_cf_inst.bind("<<ComboboxSelected>>", lambda e: (
            self.list_rsp_cf.refresh_installed_states()), add="+")

        self.pg_rsp_cf = PaginationBar(lv, self._goto_rsp_cf_page, accent_color="#AB47BC", bg=BG)
        self.pg_rsp_cf.pack(fill="x", padx=10, pady=(2, 0))

    def _load_rsp_cf_top(self, page=1):
        self._rsp_cf_page    = page
        self._rsp_cf_last_kw = None
        try:
            r, total = lay_curseforge_popular(class_id=12, limit=50, offset=(page - 1) * 50)
            self._rsp_cf_data  = r
            self._rsp_cf_total = total
            self.after(0, lambda: (
                self.list_rsp_cf.load(r),
                self.pg_rsp_cf.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Resource Pack (CurseForge) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi RSP CF: {e}", fg="red"))

    def _search_rsp_cf(self, page=1):
        kw       = self.ent_search.get().strip()
        mc, _, c = self.fb_rsp_cf.get()
        self._rsp_cf_page    = page
        self._rsp_cf_last_kw = (kw, mc, c)
        self.lbl_status.config(text="Đang tìm RSP CurseForge...", fg="#AB47BC")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, "", limit=50, class_id=12,
                                                offset=(page - 1) * 50, category_id=c)
                self._rsp_cf_data  = r
                self._rsp_cf_total = total
                self.after(0, lambda: (
                    self.list_rsp_cf.load(r),
                    self.pg_rsp_cf.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} resource pack - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_rsp_cf_page(self, page):
        if self._rsp_cf_last_kw is None:
            threading.Thread(target=self._load_rsp_cf_top, args=(page,), daemon=True).start()
        else:
            self._search_rsp_cf(page)

    def _select_rsp_cf(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._rsp_cf_data): return
        r   = self._rsp_cf_data[idx]
        mid = r.get("id", "")

        if view:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Lỗi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "resourcepack.zip")
                ten_inst = self.cbo_rsp_cf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
                if not ten_inst:
                    messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Đang tải RSP từ CurseForge...", fg="#AB47BC")
                self._tang_tac_vu()
                def _t():
                    try:
                        tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                        os.makedirs(tmp, exist_ok=True)
                        pz = os.path.join(tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai RSP")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(
                                text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#AB47BC"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai RSP")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            luu_muc_da_cai(ten_inst, "resourcepacks", mid, "curseforge",
                                           version_data.get("id"),
                                           version_data.get("displayName", version_data.get("fileName", "")),
                                           fname, ngay=version_data.get("fileDate"))
                            self.lbl_status.after(0, lambda: self.lbl_status.config(
                                text=f"Đã cài RSP vào {ten_inst}!", fg="#2b8c54"))
                            self.after(0, lambda: self._thong_bao_cai_xong("Resource Pack", fname, ten_inst))
                            _finish()
                        cai_rsp_shader_tu_file(pz, ten_inst, "rsp", self.lbl_status, _done)
                    except TacVuBiHuy:
                        try: shutil.rmtree(tmp)
                        except: pass
                        self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Resource Pack.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            ten_inst_hien_tai = self.cbo_rsp_cf_inst.get().strip()
            ten_inst_hien_tai = "" if ten_inst_hien_tai == _NO_INST else ten_inst_hien_tai
            self._swap_to_detail(self.lv_rsp_cf, self.dv_rsp_cf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#AB47BC", installed_info=self._lay_installed_info_day_du(
                                      "resourcepacks", "curseforge", mid, ten_inst_hien_tai, r.get("name", "")),
                                  instance_ctl=make_instance_ctl(self.cbo_rsp_cf_inst, _NO_INST),
                                  loai="resourcepacks")
            return

        if install:
            ten_inst_check = self.cbo_rsp_cf_inst.get().strip()
            ten_inst_check = "" if ten_inst_check == _NO_INST else ten_inst_check
            if not ten_inst_check:
                messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                return
            self._tang_tac_vu()
        self.cbo_rsp_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Đang tải phiên bản RSP...", fg="#AB47BC")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._rsp_cf_files = files
                def _apply():
                    self._filter_rsp_cf_ver()
                    if install:
                        started = self._install_rsp_cf()
                        if not started:
                            self._giam_tac_vu()
                self.after(0, _apply)
            except Exception as e:
                def _err(e=e):
                    if install:
                        self._giam_tac_vu()
                    self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                    messagebox.showerror("Lỗi",
                        f"Không tải được danh sách phiên bản Resource Pack từ CurseForge.\n{e}",
                        parent=self)
                self.after(0, _err)
        threading.Thread(target=_t, daemon=True).start()

    def _filter_rsp_cf_ver(self):
        files  = self._rsp_cf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]
        self._rsp_cf_ver_idx_map = list(range(len(files)))
        self.cbo_rsp_cf_ver.config(values=ds_all)
        if ds_all:
            self.cbo_rsp_cf_ver.set(ds_all[0])
            self.lbl_status.config(text="Chon phien ban roi nhan Cài RSP.", fg="gray")
        else:
            self.cbo_rsp_cf_ver.set("")

    def _install_rsp_cf(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_rsp_cf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self); return False
        iv = self.cbo_rsp_cf_ver.current()
        if iv < 0 or not self._rsp_cf_files:
            messagebox.showwarning("Chú ý",
                "Không tìm thấy phiên bản Resource Pack phù hợp (hoặc chưa chọn phiên bản).",
                parent=self)
            return False
        if iv < len(self._rsp_cf_ver_idx_map):
            iv = self._rsp_cf_ver_idx_map[iv]
        fd  = self._rsp_cf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Lỗi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
            return False
        fname = fd.get("fileName", "resourcepack.zip")
        self.lbl_status.config(text="Đang tải RSP từ CurseForge...", fg="#AB47BC")

        self._tang_tac_vu()
        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz = os.path.join(tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai RSP")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#AB47BC"))
                    self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai RSP")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    luu_muc_da_cai(ten_inst, "resourcepacks", fd.get("modId", ""), "curseforge",
                                   fd.get("id"), fd.get("displayName", fd.get("fileName", "")),
                                   fname, ngay=fd.get("fileDate"))
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Đã cài RSP vào {ten_inst}!", fg="#2b8c54"))
                    self.after(0, lambda: self._thong_bao_cai_xong("Resource Pack", fname, ten_inst))
                cai_rsp_shader_tu_file(pz, ten_inst, "rsp", self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Resource Pack.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()
        return True

    def _build_shader_cf_tab(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        self._sh_cf_data        = []
        self._sh_cf_files       = []
        self._sh_cf_ver_idx_map = []
        self._sh_cf_page        = 1
        self._sh_cf_total       = 0
        self._sh_cf_last_kw     = None
        f  = self.tab_sh_cf
        BG = f["bg"]

        self.lv_sh_cf = tk.Frame(f, bg=BG)
        self.lv_sh_cf.pack(fill="both", expand=True)
        self.dv_sh_cf = tk.Frame(f, bg=BG)
        lv = self.lv_sh_cf

        self.fb_sh_cf = FilterBar(lv, self._search_sh_cf, accent_color="#FB8C00", show_loader=False, show_category=True, bg=BG)
        self.fb_sh_cf.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_async(self.fb_sh_cf, 6552)

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bp, text="Phiên bản:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_sh_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_sh_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cài vào Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=2)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_sh_cf_inst = ttk.Combobox(bp, values=[_NO_INST] + ds_inst, font=("Arial", 9), width=42, height=5)
        self.cbo_sh_cf_inst.set(_NO_INST)
        self.cbo_sh_cf_inst.grid(row=1, column=1, padx=6)

        self.cbo_sh_cf_inst.bind("<ButtonPress>", lambda e: self._sync_inst_cbo(self.cbo_sh_cf_inst))
        tk.Button(bp, text="Cài Shader", font=("Arial", 9, "bold"),
                  bg="#FB8C00", fg="white", activebackground="#FB8C00", activeforeground="white",
                  width=14, pady=4, command=self._install_sh_cf).grid(row=0, column=2, rowspan=2, padx=8)

        self.list_sh_cf = ContentTableWidget(lv, "curseforge", self._select_sh_cf,
                                             is_installed_cb=self._is_sh_cf_installed)
        self.list_sh_cf.pack(fill="both", expand=True, padx=10)
        self.cbo_sh_cf_inst.bind("<<ComboboxSelected>>", lambda e: (
            self.list_sh_cf.refresh_installed_states()), add="+")

        self.pg_sh_cf = PaginationBar(lv, self._goto_sh_cf_page, accent_color="#FB8C00", bg=BG)
        self.pg_sh_cf.pack(fill="x", padx=10, pady=(2, 0))

    def _load_sh_cf_top(self, page=1):
        self._sh_cf_page    = page
        self._sh_cf_last_kw = None
        try:
            r, total = lay_curseforge_popular(class_id=6552, limit=50, offset=(page - 1) * 50)
            self._sh_cf_data  = r
            self._sh_cf_total = total
            self.after(0, lambda: (
                self.list_sh_cf.load(r),
                self.pg_sh_cf.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Shader (CurseForge) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi Shader CF: {e}", fg="red"))

    def _search_sh_cf(self, page=1):
        kw       = self.ent_search.get().strip()
        mc, _, c = self.fb_sh_cf.get()
        self._sh_cf_page    = page
        self._sh_cf_last_kw = (kw, mc, c)
        self.lbl_status.config(text="Đang tìm Shader CurseForge...", fg="#FB8C00")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, "", limit=50, class_id=6552,
                                                offset=(page - 1) * 50, category_id=c)
                self._sh_cf_data  = r
                self._sh_cf_total = total
                self.after(0, lambda: (
                    self.list_sh_cf.load(r),
                    self.pg_sh_cf.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} shader - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_sh_cf_page(self, page):
        if self._sh_cf_last_kw is None:
            threading.Thread(target=self._load_sh_cf_top, args=(page,), daemon=True).start()
        else:
            self._search_sh_cf(page)

    def _select_sh_cf(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._sh_cf_data): return
        r   = self._sh_cf_data[idx]
        mid = r.get("id", "")

        if view:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Lỗi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "shader.zip")
                ten_inst = self.cbo_sh_cf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
                if not ten_inst:
                    messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Đang tải Shader từ CurseForge...", fg="#FB8C00")
                self._tang_tac_vu()
                def _t():
                    try:
                        tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                        os.makedirs(tmp, exist_ok=True)
                        pz = os.path.join(tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai Shader")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(
                                text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#FB8C00"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai Shader")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            luu_muc_da_cai(ten_inst, "shaderpacks", mid, "curseforge",
                                           version_data.get("id"),
                                           version_data.get("displayName", version_data.get("fileName", "")),
                                           fname, ngay=version_data.get("fileDate"))
                            self.lbl_status.after(0, lambda: self.lbl_status.config(
                                text=f"Đã cài Shader vào {ten_inst}!", fg="#2b8c54"))
                            self.after(0, lambda: self._thong_bao_cai_xong("Shader", fname, ten_inst))
                            _finish()
                        cai_rsp_shader_tu_file(pz, ten_inst, "shader", self.lbl_status, _done)
                    except TacVuBiHuy:
                        try: shutil.rmtree(tmp)
                        except: pass
                        self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Shader.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            ten_inst_hien_tai = self.cbo_sh_cf_inst.get().strip()
            ten_inst_hien_tai = "" if ten_inst_hien_tai == _NO_INST else ten_inst_hien_tai
            self._swap_to_detail(self.lv_sh_cf, self.dv_sh_cf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#FB8C00", installed_info=self._lay_installed_info_day_du(
                                      "shaderpacks", "curseforge", mid, ten_inst_hien_tai, r.get("name", "")),
                                  instance_ctl=make_instance_ctl(self.cbo_sh_cf_inst, _NO_INST),
                                  loai="shaderpacks")
            return

        if install:
            ten_inst_check = self.cbo_sh_cf_inst.get().strip()
            ten_inst_check = "" if ten_inst_check == _NO_INST else ten_inst_check
            if not ten_inst_check:
                messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                return
            self._tang_tac_vu()
        self.cbo_sh_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Đang tải phiên bản Shader...", fg="#FB8C00")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._sh_cf_files = files
                def _apply():
                    self._filter_sh_cf_ver()
                    if install:
                        started = self._install_sh_cf()
                        if not started:
                            self._giam_tac_vu()
                self.after(0, _apply)
            except Exception as e:
                def _err(e=e):
                    if install:
                        self._giam_tac_vu()
                    self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                    messagebox.showerror("Lỗi",
                        f"Không tải được danh sách phiên bản Shader từ CurseForge.\n{e}",
                        parent=self)
                self.after(0, _err)
        threading.Thread(target=_t, daemon=True).start()

    def _filter_sh_cf_ver(self):
        files  = self._sh_cf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]
        self._sh_cf_ver_idx_map = list(range(len(files)))
        self.cbo_sh_cf_ver.config(values=ds_all)
        if ds_all:
            self.cbo_sh_cf_ver.set(ds_all[0])
            self.lbl_status.config(text="Chon phien ban roi nhan Cài Shader.", fg="gray")
        else:
            self.cbo_sh_cf_ver.set("")

    def _install_sh_cf(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_sh_cf_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self); return False
        iv = self.cbo_sh_cf_ver.current()
        if iv < 0 or not self._sh_cf_files:
            messagebox.showwarning("Chú ý",
                "Không tìm thấy phiên bản Shader phù hợp (hoặc chưa chọn phiên bản).",
                parent=self)
            return False
        if iv < len(self._sh_cf_ver_idx_map):
            iv = self._sh_cf_ver_idx_map[iv]
        fd  = self._sh_cf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Lỗi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tải thủ công từ curseforge.com rồi dùng tab 'Cài từ File'.", parent=self)
            return False
        fname = fd.get("fileName", "shader.zip")
        self.lbl_status.config(text="Đang tải Shader từ CurseForge...", fg="#FB8C00")

        self._tang_tac_vu()
        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz = os.path.join(tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai Shader")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#FB8C00"))
                    self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai Shader")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    luu_muc_da_cai(ten_inst, "shaderpacks", fd.get("modId", ""), "curseforge",
                                   fd.get("id"), fd.get("displayName", fd.get("fileName", "")),
                                   fname, ngay=fd.get("fileDate"))
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Đã cài Shader vào {ten_inst}!", fg="#2b8c54"))
                    self.after(0, lambda: self._thong_bao_cai_xong("Shader", fname, ten_inst))
                cai_rsp_shader_tu_file(pz, ten_inst, "shader", self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Shader.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()
        return True
