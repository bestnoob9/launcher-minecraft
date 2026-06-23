"""
forgemod.py
-----------
Tat ca method lien quan den CurseForge trong ModMcWindow / ModMcFrame:
  - Tab Modpack        (CurseForge)
  - Tab Mod            (CurseForge)
  - Tab Resource Pack  (CurseForge)
  - Tab Shader         (CurseForge)

Duoc mix vao class chinh qua ke thua ForgeModMixin.
"""

import os
import shutil
import threading
import urllib.parse

import tkinter as tk
from tkinter import ttk, messagebox

import config
from components.api_helpers import (
    CURSEFORGE_API_KEY,
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
)


def _cf_build_url(version_data):
    """Tra ve download URL tu version_data CurseForge (xu ly truong hop CF an URL)."""
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
    """
    Mixin chua toan bo logic cho cac tab CurseForge (Modpack / Mod / RSP / Shader).

    Yeu cau class cha co cac thuoc tinh:
        self.tab_cf, self.tab_modcf, self.tab_rsp_cf, self.tab_sh_cf
        self.ent_search, self.lbl_status,
        self._cancel_event, self._tang_tac_vu(), self._giam_tac_vu(),
        self._swap_to_detail(), self._get_inst_mc_loader(),
        TacVuBiHuy (exception class)
    """

    def _load_categories_async(self, fb, class_id):
        """
        Tai danh sach category THAT cua CurseForge (theo class_id) trong
        thread phu, roi fill vao dropdown Category cua FilterBar 'fb' khi
        xong. Goi 1 lan ngay sau khi tao moi FilterBar cho 4 tab CurseForge
        (Modpack=4471, Mod=6, Resource Pack=12, Shader=6552).
        """
        def _t():
            try:
                cats = lay_category_curseforge(class_id)
                if cats:
                    fb.after(0, lambda: fb.set_categories(cats))
            except Exception:
                pass  # giu nguyen list rong/mac dinh neu loi - khong chan UI
        threading.Thread(target=_t, daemon=True).start()

    # ==================================================================
    # TAB: MODPACK CURSEFORGE
    # ==================================================================

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
        self.list_cf = ContentTableWidget(lv, "curseforge", self._select_cf)
        self.list_cf.pack(fill="both", expand=True, padx=10)

        self.pg_cf = PaginationBar(lv, self._goto_cf_page, accent_color="#E64A19", bg=BG)
        self.pg_cf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Ten Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        self.ent_cf_name = tk.Entry(bp, font=("Arial", 9), width=44)
        self.ent_cf_name.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cai Modpack", font=("Arial", 9, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white",
                  width=14, pady=4, command=self._install_cf).grid(row=0, column=2, rowspan=2, padx=8)

        self._cf_data    = []
        self._cf_files   = []
        self._cf_page    = 1
        self._cf_total   = 0
        self._cf_last_kw = None

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
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF: {e}", fg="red"))

    def _search_cf(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, ld, c = self.fb_cf.get()
        self._cf_page    = page
        self._cf_last_kw = (kw, mc, ld, c)
        self.lbl_status.config(text="Dang tim CF...", fg="#E64A19")
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
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_cf_page(self, page):
        if self._cf_last_kw is None:
            threading.Thread(target=self._load_cf_top, args=(page,), daemon=True).start()
        else:
            self._search_cf(page)

    def _select_cf(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._cf_data): return
        r   = self._cf_data[idx]
        ten = r.get("name", "")
        mid = r.get("id", "")
        self.ent_cf_name.delete(0, "end")
        self.ent_cf_name.insert(0, ten.replace(" ", "_")[:30])

        if install:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Loi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "modpack.zip")
                ten_inst = ten.replace(" ", "_")[:30]
                self.ent_cf_name.delete(0, "end")
                self.ent_cf_name.insert(0, ten_inst)
                self.lbl_status.config(text="Dang tai tu CurseForge...", fg="#E64A19")
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
                                text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#E64A19"))
                            # Giai doan tai file goi modpack chiem 0-10% thanh tien trinh chung
                            self.ghi_tien_do(pct // 10, f"Đang tải gói: {pct}%")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(pct // 10, 100))
                        tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai modpack")
                        def _done_va_xoa():
                            try: shutil.rmtree(tmp)
                            except: pass
                            self._done()
                            _finish()
                        def _huy_va_xoa():
                            # Goi khi cai_modpack_tu_file ket thuc do BI HUY/LOI -
                            # rieng voi _done_va_xoa (chi danh cho THANH CONG).
                            try: shutil.rmtree(tmp)
                            except: pass
                            _finish()
                        def _modpack_progress(da_mod, tong_mod):
                            # Giai doan cai tung mod chiem 10-100% thanh tien trinh chung
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
                        self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Modpack.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            self._swap_to_detail(self.lv_cf, self.dv_cf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#E64A19")
            return

        self.cbo_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text=f"Dang tai phien ban '{ten}'...", fg="#E64A19")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._cf_files = files
                ds = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                      for fi in files]
                self.after(0, lambda: (
                    self.cbo_cf_ver.config(values=ds),
                    self.cbo_cf_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chon phien ban roi nhan Cai Modpack.", fg="gray"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF ver: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_cf(self):
        from components.mod_mc import TacVuBiHuy
        ten = self.ent_cf_name.get().strip()
        if not ten:
            messagebox.showwarning("Chu y", "Nhap ten Instance!", parent=self); return
        if ten in config.current_config["danh_sach_instances"]:
            messagebox.showwarning("Chu y", "Ten da ton tai!", parent=self); return
        iv = self.cbo_cf_ver.current()
        if iv < 0 or not self._cf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        fd  = self._cf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Loi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
            return
        fname = fd.get("fileName", "modpack.zip")
        self.lbl_status.config(text="Dang tai tu CurseForge...", fg="#E64A19")

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
                        text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#E64A19"))
                tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai modpack")
                def _done_va_xoa():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self._done()
                cai_modpack_tu_file(pz, ten, self.lbl_status, _done_va_xoa, cancel_event=self._cancel_event)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Modpack.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()

    # ==================================================================
    # TAB: MOD CURSEFORGE
    # ==================================================================

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
        self.list_modcf = ContentTableWidget(lv, "curseforge", self._select_modcf)
        self.list_modcf.pack(fill="both", expand=True, padx=10)

        self.pg_modcf = PaginationBar(lv, self._goto_modcf_page, accent_color="#F9A825", bg=BG)
        self.pg_modcf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban mod:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_modcf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_modcf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_modcf_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst:  self.cbo_modcf_inst.set(cur)
        elif ds_inst:       self.cbo_modcf_inst.set(ds_inst[0])
        self.cbo_modcf_inst.grid(row=1, column=1, padx=6)
        self.cbo_modcf_inst.bind("<<ComboboxSelected>>", lambda e: self._filter_modcf_ver())
        tk.Button(bp, text="Cai Mod", font=("Arial", 9, "bold"),
                  bg="#F9A825", fg="white", activebackground="#F9A825", activeforeground="white",
                  width=14, pady=4, command=self._install_modcf).grid(row=0, column=2, rowspan=2, padx=8)

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
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi ModCF: {e}", fg="red"))

    def _search_modcf(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, ld, c = self.fb_modcf.get()
        self._modcf_page    = page
        self._modcf_last_kw = (kw, mc, ld, c)
        self.lbl_status.config(text="Dang tim Mod CurseForge...", fg="#F9A825")
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
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_modcf_page(self, page):
        if self._modcf_last_kw is None:
            threading.Thread(target=self._load_modcf_top, args=(page,), daemon=True).start()
        else:
            self._search_modcf(page)

    def _select_modcf(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._modcf_data): return
        r   = self._modcf_data[idx]
        mid = r.get("id", "")

        if install:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Loi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "mod.jar")
                ten_inst = self.cbo_modcf_inst.get().strip()
                if not ten_inst:
                    messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Dang tai Mod tu CurseForge...", fg="#F9A825")
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
                                text=f"Dang tai mod: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#F9A825"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai mod")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            self.lbl_status.after(0, lambda: self.lbl_status.config(
                                text=f"Da cai mod '{fname}' vao {ten_inst}!", fg="#2b8c54"))
                            _finish()
                        cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
                    except TacVuBiHuy:
                        try: shutil.rmtree(tmp)
                        except: pass
                        self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Mod.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            self._swap_to_detail(self.lv_modcf, self.dv_modcf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#F9A825")
            return

        self.cbo_modcf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Dang tai phien ban mod...", fg="#F9A825")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._modcf_files = files
                self.after(0, lambda: self._filter_modcf_ver())
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF ver: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_modcf_ver(self):
        files  = self._modcf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst    = self.cbo_modcf_inst.get().strip()
        mcv, loader = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if mcv:
            idxs = []
            for i, fi in enumerate(files):
                gvs = fi.get("gameVersions", [])
                gvs_lower = [g.lower() for g in gvs]
                if mcv not in gvs:
                    continue
                if loader and loader != "Vanilla" and loader.lower() not in gvs_lower:
                    continue
                idxs.append(i)
        else:
            idxs = list(range(len(files)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._modcf_ver_idx_map = idxs
            self.cbo_modcf_ver.config(values=ds)
            self.cbo_modcf_ver.set(ds[0])
            self.lbl_status.config(
                text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}"
                     + (f", {loader}" if loader and loader != "Vanilla" else "") + ")."
                if mcv else "Chon phien ban roi nhan Cai Mod.",
                fg="gray")
        else:
            self._modcf_ver_idx_map = list(range(len(files)))
            self.cbo_modcf_ver.config(values=ds_all)
            if ds_all: self.cbo_modcf_ver.set(ds_all[0])
            else:       self.cbo_modcf_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}"
                         + (f", {loader}" if loader and loader != "Vanilla" else "")
                         + "). Hien thi tat ca - kiem tra ky truoc khi cai.",
                    fg="#E64A19")

    def _install_modcf(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_modcf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_modcf_ver.current()
        if iv < 0 or not self._modcf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._modcf_ver_idx_map):
            iv = self._modcf_ver_idx_map[iv]
        fd  = self._modcf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Loi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
            return
        fname = fd.get("fileName", "mod.jar")
        self.lbl_status.config(text="Dang tai Mod tu CurseForge...", fg="#F9A825")

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
                        text=f"Dang tai mod: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#F9A825"))
                tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai mod")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai mod '{fname}' vao {ten_inst}!", fg="#2b8c54"))
                cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Mod.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()

    # ==================================================================
    # TAB: RESOURCE PACK CURSEFORGE
    # ==================================================================

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
        self.list_rsp_cf = ContentTableWidget(lv, "curseforge", self._select_rsp_cf)
        self.list_rsp_cf.pack(fill="both", expand=True, padx=10)

        self.pg_rsp_cf = PaginationBar(lv, self._goto_rsp_cf_page, accent_color="#AB47BC", bg=BG)
        self.pg_rsp_cf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_rsp_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_rsp_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_rsp_cf_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst: self.cbo_rsp_cf_inst.set(cur)
        elif ds_inst:      self.cbo_rsp_cf_inst.set(ds_inst[0])
        self.cbo_rsp_cf_inst.grid(row=1, column=1, padx=6)
        self.cbo_rsp_cf_inst.bind("<<ComboboxSelected>>", lambda e: self._filter_rsp_cf_ver())
        tk.Button(bp, text="Cai RSP", font=("Arial", 9, "bold"),
                  bg="#AB47BC", fg="white", activebackground="#AB47BC", activeforeground="white",
                  width=14, pady=4, command=self._install_rsp_cf).grid(row=0, column=2, rowspan=2, padx=8)

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
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi RSP CF: {e}", fg="red"))

    def _search_rsp_cf(self, page=1):
        kw       = self.ent_search.get().strip()
        mc, _, c = self.fb_rsp_cf.get()
        self._rsp_cf_page    = page
        self._rsp_cf_last_kw = (kw, mc, c)
        self.lbl_status.config(text="Dang tim RSP CurseForge...", fg="#AB47BC")
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
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_rsp_cf_page(self, page):
        if self._rsp_cf_last_kw is None:
            threading.Thread(target=self._load_rsp_cf_top, args=(page,), daemon=True).start()
        else:
            self._search_rsp_cf(page)

    def _select_rsp_cf(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._rsp_cf_data): return
        r   = self._rsp_cf_data[idx]
        mid = r.get("id", "")

        if install:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Loi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "resourcepack.zip")
                ten_inst = self.cbo_rsp_cf_inst.get().strip()
                if not ten_inst:
                    messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Dang tai RSP tu CurseForge...", fg="#AB47BC")
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
                                text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#AB47BC"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai RSP")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            self.lbl_status.after(0, lambda: self.lbl_status.config(
                                text=f"Da cai RSP vao {ten_inst}!", fg="#2b8c54"))
                            _finish()
                        cai_rsp_shader_tu_file(pz, ten_inst, "rsp", self.lbl_status, _done)
                    except TacVuBiHuy:
                        try: shutil.rmtree(tmp)
                        except: pass
                        self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Resource Pack.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            self._swap_to_detail(self.lv_rsp_cf, self.dv_rsp_cf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#AB47BC")
            return

        self.cbo_rsp_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Dang tai phien ban RSP...", fg="#AB47BC")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._rsp_cf_files = files
                self.after(0, lambda: self._filter_rsp_cf_ver())
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_rsp_cf_ver(self):
        files  = self._rsp_cf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst = self.cbo_rsp_cf_inst.get().strip()
        mcv, _   = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if ten_inst and mcv:
            try:
                self.fb_rsp_cf.cbo_mc.set(mcv)
                self.fb_rsp_cf.cbo_mc.config(state="disabled")
            except Exception:
                pass
        else:
            try:
                self.fb_rsp_cf.cbo_mc.config(state="readonly")
            except Exception:
                pass

        idxs = [i for i, fi in enumerate(files) if mcv in fi.get("gameVersions", [])] if mcv \
               else list(range(len(files)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._rsp_cf_ver_idx_map = idxs
            self.cbo_rsp_cf_ver.config(values=ds)
            self.cbo_rsp_cf_ver.set(ds[0])
            self.lbl_status.config(
                text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv})." if mcv
                     else "Chon phien ban roi nhan Cai RSP.",
                fg="gray")
        else:
            self._rsp_cf_ver_idx_map = list(range(len(files)))
            self.cbo_rsp_cf_ver.config(values=ds_all)
            if ds_all: self.cbo_rsp_cf_ver.set(ds_all[0])
            else:       self.cbo_rsp_cf_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}). Hien thi tat ca.",
                    fg="#E64A19")

    def _install_rsp_cf(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_rsp_cf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_rsp_cf_ver.current()
        if iv < 0 or not self._rsp_cf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._rsp_cf_ver_idx_map):
            iv = self._rsp_cf_ver_idx_map[iv]
        fd  = self._rsp_cf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Loi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
            return
        fname = fd.get("fileName", "resourcepack.zip")
        self.lbl_status.config(text="Dang tai RSP tu CurseForge...", fg="#AB47BC")

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
                        text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#AB47BC"))
                tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai RSP")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai RSP vao {ten_inst}!", fg="#2b8c54"))
                cai_rsp_shader_tu_file(pz, ten_inst, "rsp", self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Resource Pack.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()

    # ==================================================================
    # TAB: SHADER CURSEFORGE
    # ==================================================================

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
        self.list_sh_cf = ContentTableWidget(lv, "curseforge", self._select_sh_cf)
        self.list_sh_cf.pack(fill="both", expand=True, padx=10)

        self.pg_sh_cf = PaginationBar(lv, self._goto_sh_cf_page, accent_color="#FB8C00", bg=BG)
        self.pg_sh_cf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_sh_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_sh_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_sh_cf_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst: self.cbo_sh_cf_inst.set(cur)
        elif ds_inst:      self.cbo_sh_cf_inst.set(ds_inst[0])
        self.cbo_sh_cf_inst.grid(row=1, column=1, padx=6)
        self.cbo_sh_cf_inst.bind("<<ComboboxSelected>>", lambda e: self._filter_sh_cf_ver())
        tk.Button(bp, text="Cai Shader", font=("Arial", 9, "bold"),
                  bg="#FB8C00", fg="white", activebackground="#FB8C00", activeforeground="white",
                  width=14, pady=4, command=self._install_sh_cf).grid(row=0, column=2, rowspan=2, padx=8)

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
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi Shader CF: {e}", fg="red"))

    def _search_sh_cf(self, page=1):
        kw       = self.ent_search.get().strip()
        mc, _, c = self.fb_sh_cf.get()
        self._sh_cf_page    = page
        self._sh_cf_last_kw = (kw, mc, c)
        self.lbl_status.config(text="Dang tim Shader CurseForge...", fg="#FB8C00")
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
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_sh_cf_page(self, page):
        if self._sh_cf_last_kw is None:
            threading.Thread(target=self._load_sh_cf_top, args=(page,), daemon=True).start()
        else:
            self._search_sh_cf(page)

    def _select_sh_cf(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._sh_cf_data): return
        r   = self._sh_cf_data[idx]
        mid = r.get("id", "")

        if install:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                url = _cf_build_url(version_data)
                if not url:
                    messagebox.showerror("Loi",
                        "File nay khong co link tai truc tiep.\n"
                        "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
                    _finish()
                    return
                fname    = version_data.get("fileName", "shader.zip")
                ten_inst = self.cbo_sh_cf_inst.get().strip()
                if not ten_inst:
                    messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Dang tai Shader tu CurseForge...", fg="#FB8C00")
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
                                text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#FB8C00"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai Shader")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            self.lbl_status.after(0, lambda: self.lbl_status.config(
                                text=f"Da cai Shader vao {ten_inst}!", fg="#2b8c54"))
                            _finish()
                        cai_rsp_shader_tu_file(pz, ten_inst, "shader", self.lbl_status, _done)
                    except TacVuBiHuy:
                        try: shutil.rmtree(tmp)
                        except: pass
                        self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Shader.", fg="#E53935"))
                        _finish()
                    except Exception as e:
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
                        _finish()
                    finally:
                        self._giam_tac_vu()
                threading.Thread(target=_t, daemon=True).start()

            self._swap_to_detail(self.lv_sh_cf, self.dv_sh_cf, "curseforge", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#FB8C00")
            return

        self.cbo_sh_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Dang tai phien ban Shader...", fg="#FB8C00")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._sh_cf_files = files
                self.after(0, lambda: self._filter_sh_cf_ver())
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_sh_cf_ver(self):
        files  = self._sh_cf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst = self.cbo_sh_cf_inst.get().strip()
        mcv, _   = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if ten_inst and mcv:
            try:
                self.fb_sh_cf.cbo_mc.set(mcv)
                self.fb_sh_cf.cbo_mc.config(state="disabled")
            except Exception:
                pass
        else:
            try:
                self.fb_sh_cf.cbo_mc.config(state="readonly")
            except Exception:
                pass

        idxs = [i for i, fi in enumerate(files) if mcv in fi.get("gameVersions", [])] if mcv \
               else list(range(len(files)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._sh_cf_ver_idx_map = idxs
            self.cbo_sh_cf_ver.config(values=ds)
            self.cbo_sh_cf_ver.set(ds[0])
            self.lbl_status.config(
                text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv})." if mcv
                     else "Chon phien ban roi nhan Cai Shader.",
                fg="gray")
        else:
            self._sh_cf_ver_idx_map = list(range(len(files)))
            self.cbo_sh_cf_ver.config(values=ds_all)
            if ds_all: self.cbo_sh_cf_ver.set(ds_all[0])
            else:       self.cbo_sh_cf_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}). Hien thi tat ca.",
                    fg="#E64A19")

    def _install_sh_cf(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_sh_cf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_sh_cf_ver.current()
        if iv < 0 or not self._sh_cf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._sh_cf_ver_idx_map):
            iv = self._sh_cf_ver_idx_map[iv]
        fd  = self._sh_cf_files[iv]
        url = _cf_build_url(fd)
        if not url:
            messagebox.showerror("Loi",
                "File nay khong co link tai truc tiep (CF an URL).\n"
                "Tai thu cong tu curseforge.com roi dung tab 'Cai tu File'.", parent=self)
            return
        fname = fd.get("fileName", "shader.zip")
        self.lbl_status.config(text="Dang tai Shader tu CurseForge...", fg="#FB8C00")

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
                        text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#FB8C00"))
                tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai Shader")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai Shader vao {ten_inst}!", fg="#2b8c54"))
                cai_rsp_shader_tu_file(pz, ten_inst, "shader", self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Shader.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        threading.Thread(target=_t, daemon=True).start()