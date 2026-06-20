"""
modrinthmod.py
--------------
Tat ca method lien quan den Modrinth trong ModMcWindow / ModMcFrame:
  - Tab Modpack   (Modrinth)
  - Tab Mod       (Modrinth)
  - Tab Resource Pack (Modrinth)
  - Tab Shader    (Modrinth)
  - Tab Cai tu File (dung chung cho ca Modrinth lan CurseForge)

Duoc mix vao class chinh qua ke thua ModrinthModMixin.
"""

import os
import shutil
import threading

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config
from components.api_helpers import (
    lay_modrinth_popular,
    tim_kiem_modrinth,
    lay_phien_ban_modrinth,
)
from components.install_utils import (
    tai_file,
    cai_mod_tu_file,
    cai_rsp_shader_tu_file,
    cai_modpack_tu_file,
)


class ModrinthModMixin:
    """
    Mixin chua toan bo logic cho cac tab Modrinth (Modpack / Mod / RSP / Shader)
    va tab Cai tu File.

    Yeu cau class cha co cac thuoc tinh:
        self.tab_mr, self.tab_modmr, self.tab_rsp, self.tab_sh, self.tab_f
        self.ent_search, self.lbl_status,
        self._cancel_event, self._tang_tac_vu(), self._giam_tac_vu(),
        self._swap_to_detail(), self._get_inst_mc_loader(),
        TacVuBiHuy (exception class)
    """

    # ==================================================================
    # TAB: MODPACK MODRINTH
    # ==================================================================

    def _build_modpack_modrinth(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        f  = self.tab_mr
        BG = f["bg"]

        self.lv_mr = tk.Frame(f, bg=BG)
        self.lv_mr.pack(fill="both", expand=True)
        self.dv_mr = tk.Frame(f, bg=BG)
        lv = self.lv_mr

        self.fb_mr = FilterBar(lv, self._search_mr, accent_color="#1E88E5", show_category=True, bg=BG)
        self.fb_mr.pack(fill="x", padx=10, pady=(8, 4))
        self.list_mr = ContentTableWidget(lv, "modrinth", self._select_mr)
        self.list_mr.pack(fill="both", expand=True, padx=10)

        self.pg_mr = PaginationBar(lv, self._goto_mr_page, accent_color="#1E88E5", bg=BG)
        self.pg_mr.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_mr_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_mr_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Ten Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        self.ent_mr_name = tk.Entry(bp, font=("Arial", 9), width=44)
        self.ent_mr_name.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cai Modpack", font=("Arial", 9, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white",
                  width=14, pady=4, command=self._install_mr).grid(row=0, column=2, rowspan=2, padx=8)

        self._mr_data     = []
        self._mr_vers_raw = []
        self._mr_page     = 1
        self._mr_total    = 0
        self._mr_last_kw  = None

    def _load_mr_top(self, page=1):
        self._mr_page    = page
        self._mr_last_kw = None
        try:
            r, total = lay_modrinth_popular("modpack", 50, offset=(page - 1) * 50)
            self._mr_data  = r
            self._mr_total = total
            self.after(0, lambda: (
                self.list_mr.load(r),
                self.pg_mr.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Modpack (Modrinth) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi MR: {e}", fg="red"))

    def _search_mr(self, page=1):
        kw          = self.ent_search.get().strip()
        mc, ld, cat = self.fb_mr.get()
        self._mr_page    = page
        self._mr_last_kw = (kw, mc, ld, cat)
        self.lbl_status.config(text="Dang tim...", fg="#1E88E5")
        def _t():
            try:
                r, total = tim_kiem_modrinth("modpack", kw, mc, ld, cat, 50, offset=(page - 1) * 50)
                self._mr_data  = r
                self._mr_total = total
                self.after(0, lambda: (
                    self.list_mr.load(r),
                    self.pg_mr.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} modpack - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_mr_page(self, page):
        if self._mr_last_kw is None:
            threading.Thread(target=self._load_mr_top, args=(page,), daemon=True).start()
        else:
            self._search_mr(page)

    def _select_mr(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._mr_data): return
        r   = self._mr_data[idx]
        ten = r.get("title", "")
        self.ent_mr_name.delete(0, "end")
        self.ent_mr_name.insert(0, ten.replace(" ", "_")[:30])

        if install:
            def _install_from_detail(version_data):
                files = version_data.get("files", [])
                prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
                url      = prim["url"]
                fname    = prim.get("filename", "modpack.mrpack")
                ten_inst = ten.replace(" ", "_")[:30]
                self.ent_mr_name.delete(0, "end")
                self.ent_mr_name.insert(0, ten_inst)
                self.lbl_status.config(text="Dang tai...", fg="#1E88E5")
                self._tang_tac_vu()
                def _t():
                    _tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                    try:
                        os.makedirs(_tmp, exist_ok=True)
                        pz = os.path.join(_tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai modpack")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(
                                text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#1E88E5"))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai modpack")
                        def _done_va_xoa():
                            try: shutil.rmtree(_tmp)
                            except: pass
                            self._giam_tac_vu()
                            self._done()
                        cai_modpack_tu_file(pz, ten_inst, self.lbl_status, _done_va_xoa,
                                            cancel_event=self._cancel_event)
                    except TacVuBiHuy:
                        try: shutil.rmtree(_tmp)
                        except: pass
                        self._giam_tac_vu()
                        self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Modpack.", fg="#E53935"))
                    except Exception as e:
                        self._giam_tac_vu()
                        self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
                threading.Thread(target=_t, daemon=True).start()

            self._swap_to_detail(self.lv_mr, self.dv_mr, "modrinth", r,
                                  self._mr_vers_raw, install_cb=_install_from_detail,
                                  accent="#1E88E5")
            return

        self.cbo_mr_ver.set("Dang tai phien ban...")
        pid = r.get("project_id", "")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._mr_vers_raw = vs
                ds = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]
                self.after(0, lambda: (
                    self.cbo_mr_ver.config(values=ds),
                    self.cbo_mr_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chon phien ban roi nhan Cai Modpack.", fg="gray"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_mr(self):
        from components.mod_mc import TacVuBiHuy
        ten = self.ent_mr_name.get().strip()
        if not ten:
            messagebox.showwarning("Chu y", "Nhap ten Instance!", parent=self); return
        if ten in config.current_config["danh_sach_instances"]:
            messagebox.showwarning("Chu y", "Ten da ton tai!", parent=self); return
        iv = self.cbo_mr_ver.current()
        if iv < 0 or not self._mr_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        vd    = self._mr_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "modpack.mrpack")
        self.lbl_status.config(text="Dang tai...", fg="#1E88E5")

        self._tang_tac_vu()
        def _t():
            _tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
            try:
                os.makedirs(_tmp, exist_ok=True)
                pz = os.path.join(_tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai modpack")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#1E88E5"))
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai modpack")
                def _done_va_xoa():
                    try: shutil.rmtree(_tmp)
                    except: pass
                    self._giam_tac_vu()
                    self._done()
                cai_modpack_tu_file(pz, ten, self.lbl_status, _done_va_xoa, cancel_event=self._cancel_event)
            except TacVuBiHuy:
                try: shutil.rmtree(_tmp)
                except: pass
                self._giam_tac_vu()
                self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Modpack.", fg="#E53935"))
            except Exception as e:
                self._giam_tac_vu()
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    # ==================================================================
    # TAB: MOD MODRINTH
    # ==================================================================

    def _build_mod_modrinth(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        self._modmr_data     = []
        self._modmr_vers_raw = []
        self._modmr_ver_idx_map = []
        self._modmr_page     = 1
        self._modmr_total    = 0
        self._modmr_last_kw  = None
        f  = self.tab_modmr
        BG = f["bg"]

        self.lv_modmr = tk.Frame(f, bg=BG)
        self.lv_modmr.pack(fill="both", expand=True)
        self.dv_modmr = tk.Frame(f, bg=BG)
        lv = self.lv_modmr

        self.fb_modmr = FilterBar(lv, self._search_modmr, accent_color="#00897B", bg=BG)
        self.fb_modmr.pack(fill="x", padx=10, pady=(8, 4))
        self.list_modmr = ContentTableWidget(lv, "modrinth", self._select_modmr)
        self.list_modmr.pack(fill="both", expand=True, padx=10)

        self.pg_modmr = PaginationBar(lv, self._goto_modmr_page, accent_color="#00897B", bg=BG)
        self.pg_modmr.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban mod:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_modmr_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_modmr_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_modmr_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst:  self.cbo_modmr_inst.set(cur)
        elif ds_inst:       self.cbo_modmr_inst.set(ds_inst[0])
        self.cbo_modmr_inst.grid(row=1, column=1, padx=6)
        self.cbo_modmr_inst.bind("<<ComboboxSelected>>", lambda e: self._filter_modmr_ver())
        tk.Button(bp, text="Cai Mod", font=("Arial", 9, "bold"),
                  bg="#00897B", fg="white", activebackground="#00897B", activeforeground="white",
                  width=14, pady=4, command=self._install_modmr).grid(row=0, column=2, rowspan=2, padx=8)

    def _load_modmr_top(self, page=1):
        self._modmr_page    = page
        self._modmr_last_kw = None
        try:
            r, total = lay_modrinth_popular("mod", 50, offset=(page - 1) * 50)
            self._modmr_data  = r
            self._modmr_total = total
            self.after(0, lambda: (
                self.list_modmr.load(r),
                self.pg_modmr.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Mod (Modrinth) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi ModMR: {e}", fg="red"))

    def _search_modmr(self, page=1):
        kw         = self.ent_search.get().strip()
        mc, ld, _c = self.fb_modmr.get()
        self._modmr_page    = page
        self._modmr_last_kw = (kw, mc, ld)
        self.lbl_status.config(text="Dang tim Mod Modrinth...", fg="#00897B")
        def _t():
            try:
                r, total = tim_kiem_modrinth("mod", kw, mc, ld, "", 50, offset=(page - 1) * 50)
                self._modmr_data  = r
                self._modmr_total = total
                self.after(0, lambda: (
                    self.list_modmr.load(r),
                    self.pg_modmr.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} mod - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_modmr_page(self, page):
        if self._modmr_last_kw is None:
            threading.Thread(target=self._load_modmr_top, args=(page,), daemon=True).start()
        else:
            self._search_modmr(page)

    def _select_modmr(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._modmr_data): return
        r   = self._modmr_data[idx]
        pid = r.get("project_id", "")

        if install:
            def _install_from_detail(version_data):
                files = version_data.get("files", [])
                prim  = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
                url      = prim["url"]
                fname    = prim.get("filename", "mod.jar")
                ten_inst = self.cbo_modmr_inst.get().strip()
                if not ten_inst:
                    messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
                self.lbl_status.config(text="Dang tai Mod...", fg="#00897B")
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
                            self.after(0, lambda: self.lbl_status.config(text=f"Dang tai mod: {pct}%", fg="#00897B"))
                        tai_file(url, pz, prog)
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

            self._swap_to_detail(self.lv_modmr, self.dv_modmr, "modrinth", r,
                                  self._modmr_vers_raw, install_cb=_install_from_detail,
                                  accent="#00897B")
            return

        self.cbo_modmr_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._modmr_vers_raw = vs
                self.after(0, lambda: self._filter_modmr_ver())
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_modmr_ver(self):
        vs     = self._modmr_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}  [{', '.join(v.get('loaders',[]))}]"
                  for v in vs]
        ten_inst        = self.cbo_modmr_inst.get().strip()
        mcv, loader     = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if mcv:
            idxs = [
                i for i, v in enumerate(vs)
                if mcv in v.get("game_versions", [])
                and (not loader or loader == "Vanilla"
                     or loader.lower() in [l.lower() for l in v.get("loaders", [])])
            ]
        else:
            idxs = list(range(len(vs)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._modmr_ver_idx_map = idxs
            self.cbo_modmr_ver.config(values=ds)
            self.cbo_modmr_ver.set(ds[0])
            self.lbl_status.config(
                text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}"
                     + (f", {loader}" if loader and loader != "Vanilla" else "") + ")."
                if mcv else "Chon phien ban roi nhan Cai Mod.",
                fg="gray")
        else:
            self._modmr_ver_idx_map = list(range(len(vs)))
            self.cbo_modmr_ver.config(values=ds_all)
            if ds_all: self.cbo_modmr_ver.set(ds_all[0])
            else:       self.cbo_modmr_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}"
                         + (f", {loader}" if loader and loader != "Vanilla" else "")
                         + "). Hien thi tat ca - kiem tra ky truoc khi cai.",
                    fg="#E64A19")

    def _install_modmr(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_modmr_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_modmr_ver.current()
        if iv < 0 or not self._modmr_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._modmr_ver_idx_map):
            iv = self._modmr_ver_idx_map[iv]
        vd    = self._modmr_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "mod.jar")
        self.lbl_status.config(text="Dang tai Mod...", fg="#00897B")

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
                    self.after(0, lambda: self.lbl_status.config(text=f"Dang tai mod: {pct}%", fg="#00897B"))
                tai_file(url, pz, prog)
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
    # TAB: RESOURCE PACK MODRINTH
    # ==================================================================

    def _build_rsp_tab(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        self._rsp_data        = []
        self._rsp_vers_raw    = []
        self._rsp_ver_idx_map = []
        self._rsp_page        = 1
        self._rsp_total       = 0
        self._rsp_last_kw     = None
        f  = self.tab_rsp
        BG = f["bg"]

        self.lv_rsp = tk.Frame(f, bg=BG)
        self.lv_rsp.pack(fill="both", expand=True)
        self.dv_rsp = tk.Frame(f, bg=BG)
        lv = self.lv_rsp

        self.fb_rsp = FilterBar(lv, self._search_rsp, accent_color="#8E24AA", show_loader=False, bg=BG)
        self.fb_rsp.pack(fill="x", padx=10, pady=(8, 4))
        self.list_rsp = ContentTableWidget(lv, "modrinth", self._select_rsp)
        self.list_rsp.pack(fill="both", expand=True, padx=10)

        self.pg_rsp = PaginationBar(lv, self._goto_rsp_page, accent_color="#8E24AA", bg=BG)
        self.pg_rsp.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_rsp_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_rsp_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_rsp_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst: self.cbo_rsp_inst.set(cur)
        elif ds_inst:      self.cbo_rsp_inst.set(ds_inst[0])
        self.cbo_rsp_inst.grid(row=1, column=1, padx=6)
        self.cbo_rsp_inst.bind("<<ComboboxSelected>>", lambda e: self._filter_rsp_ver())
        tk.Button(bp, text="Cai RSP", font=("Arial", 9, "bold"),
                  bg="#8E24AA", fg="white", activebackground="#8E24AA", activeforeground="white",
                  width=14, pady=4, command=self._install_rsp).grid(row=0, column=2, rowspan=2, padx=8)

    def _load_rsp_top(self, page=1):
        self._rsp_page    = page
        self._rsp_last_kw = None
        try:
            r, total = lay_modrinth_popular("resourcepack", 50, offset=(page - 1) * 50)
            self._rsp_data  = r
            self._rsp_total = total
            self.after(0, lambda: (
                self.list_rsp.load(r),
                self.pg_rsp.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Resource Pack - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi RSP: {e}", fg="red"))

    def _search_rsp(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, _, _c = self.fb_rsp.get()
        self._rsp_page    = page
        self._rsp_last_kw = (kw, mc)
        self.lbl_status.config(text="Dang tim RSP...", fg="#8E24AA")
        def _t():
            try:
                r, total = tim_kiem_modrinth("resourcepack", kw, mc, "", "", 50, offset=(page - 1) * 50)
                self._rsp_data  = r
                self._rsp_total = total
                self.after(0, lambda: (
                    self.list_rsp.load(r),
                    self.pg_rsp.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} resource pack - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_rsp_page(self, page):
        if self._rsp_last_kw is None:
            threading.Thread(target=self._load_rsp_top, args=(page,), daemon=True).start()
        else:
            self._search_rsp(page)

    def _select_rsp(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._rsp_data): return
        r   = self._rsp_data[idx]
        pid = r.get("project_id", "")

        if install:
            def _install_from_detail(version_data):
                files = version_data.get("files", [])
                prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
                url      = prim["url"]
                fname    = prim.get("filename", "resourcepack.zip")
                ten_inst = self.cbo_rsp_inst.get().strip()
                if not ten_inst:
                    messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
                self.lbl_status.config(text="Dang tai RSP...", fg="#8E24AA")
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
                            self.after(0, lambda: self.lbl_status.config(text=f"Dang tai: {pct}%", fg="#8E24AA"))
                        tai_file(url, pz, prog)
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

            self._swap_to_detail(self.lv_rsp, self.dv_rsp, "modrinth", r,
                                  self._rsp_vers_raw, install_cb=_install_from_detail,
                                  accent="#8E24AA")
            return

        self.cbo_rsp_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._rsp_vers_raw = vs
                self.after(0, lambda: self._filter_rsp_ver())
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_rsp_ver(self):
        vs     = self._rsp_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]

        ten_inst = self.cbo_rsp_inst.get().strip()
        mcv, _   = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if ten_inst and mcv:
            try:
                self.fb_rsp.cbo_mc.set(mcv)
                self.fb_rsp.cbo_mc.config(state="disabled")
            except Exception:
                pass
        else:
            try:
                self.fb_rsp.cbo_mc.config(state="readonly")
            except Exception:
                pass

        idxs = [i for i, v in enumerate(vs) if mcv in v.get("game_versions", [])] if mcv \
               else list(range(len(vs)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._rsp_ver_idx_map = idxs
            self.cbo_rsp_ver.config(values=ds)
            self.cbo_rsp_ver.set(ds[0])
            self.lbl_status.config(
                text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv})." if mcv
                     else "Chon phien ban roi nhan Cai RSP.",
                fg="gray")
        else:
            self._rsp_ver_idx_map = list(range(len(vs)))
            self.cbo_rsp_ver.config(values=ds_all)
            if ds_all: self.cbo_rsp_ver.set(ds_all[0])
            else:       self.cbo_rsp_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}). Hien thi tat ca.",
                    fg="#E64A19")

    def _install_rsp(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_rsp_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_rsp_ver.current()
        if iv < 0 or not self._rsp_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._rsp_ver_idx_map):
            iv = self._rsp_ver_idx_map[iv]
        vd    = self._rsp_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "resourcepack.zip")
        self.lbl_status.config(text="Dang tai RSP...", fg="#8E24AA")

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
                    self.after(0, lambda: self.lbl_status.config(text=f"Dang tai: {pct}%", fg="#8E24AA"))
                tai_file(url, pz, prog)
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
    # TAB: SHADER MODRINTH
    # ==================================================================

    def _build_shader_tab(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar

        self._sh_data        = []
        self._sh_vers_raw    = []
        self._sh_ver_idx_map = []
        self._sh_page        = 1
        self._sh_total       = 0
        self._sh_last_kw     = None
        f  = self.tab_sh
        BG = f["bg"]

        self.lv_sh = tk.Frame(f, bg=BG)
        self.lv_sh.pack(fill="both", expand=True)
        self.dv_sh = tk.Frame(f, bg=BG)
        lv = self.lv_sh

        self.fb_sh = FilterBar(lv, self._search_sh, accent_color="#F57C00", show_loader=False, bg=BG)
        self.fb_sh.pack(fill="x", padx=10, pady=(8, 4))
        self.list_sh = ContentTableWidget(lv, "modrinth", self._select_sh)
        self.list_sh.pack(fill="both", expand=True, padx=10)

        self.pg_sh = PaginationBar(lv, self._goto_sh_page, accent_color="#F57C00", bg=BG)
        self.pg_sh.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_sh_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_sh_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_sh_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst: self.cbo_sh_inst.set(cur)
        elif ds_inst:      self.cbo_sh_inst.set(ds_inst[0])
        self.cbo_sh_inst.grid(row=1, column=1, padx=6)
        self.cbo_sh_inst.bind("<<ComboboxSelected>>", lambda e: self._filter_sh_ver())
        tk.Button(bp, text="Cai Shader", font=("Arial", 9, "bold"),
                  bg="#F57C00", fg="white", activebackground="#F57C00", activeforeground="white",
                  width=14, pady=4, command=self._install_sh).grid(row=0, column=2, rowspan=2, padx=8)

    def _load_sh_top(self, page=1):
        self._sh_page    = page
        self._sh_last_kw = None
        try:
            r, total = lay_modrinth_popular("shader", 50, offset=(page - 1) * 50)
            self._sh_data  = r
            self._sh_total = total
            self.after(0, lambda: (
                self.list_sh.load(r),
                self.pg_sh.set_total(total, 50, page),
                self.lbl_status.config(text=f"Top Shader - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi Shader: {e}", fg="red"))

    def _search_sh(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, _, _c = self.fb_sh.get()
        self._sh_page    = page
        self._sh_last_kw = (kw, mc)
        self.lbl_status.config(text="Dang tim Shader...", fg="#F57C00")
        def _t():
            try:
                r, total = tim_kiem_modrinth("shader", kw, mc, "", "", 50, offset=(page - 1) * 50)
                self._sh_data  = r
                self._sh_total = total
                self.after(0, lambda: (
                    self.list_sh.load(r),
                    self.pg_sh.set_total(total, 50, page),
                    self.lbl_status.config(text=f"{total} shader - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _goto_sh_page(self, page):
        if self._sh_last_kw is None:
            threading.Thread(target=self._load_sh_top, args=(page,), daemon=True).start()
        else:
            self._search_sh(page)

    def _select_sh(self, idx, install=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._sh_data): return
        r   = self._sh_data[idx]
        pid = r.get("project_id", "")

        if install:
            def _install_from_detail(version_data):
                files = version_data.get("files", [])
                prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
                url      = prim["url"]
                fname    = prim.get("filename", "shader.zip")
                ten_inst = self.cbo_sh_inst.get().strip()
                if not ten_inst:
                    messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
                self.lbl_status.config(text="Dang tai Shader...", fg="#F57C00")
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
                            self.after(0, lambda: self.lbl_status.config(text=f"Dang tai: {pct}%", fg="#F57C00"))
                        tai_file(url, pz, prog)
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

            self._swap_to_detail(self.lv_sh, self.dv_sh, "modrinth", r,
                                  self._sh_vers_raw, install_cb=_install_from_detail,
                                  accent="#F57C00")
            return

        self.cbo_sh_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._sh_vers_raw = vs
                self.after(0, lambda: self._filter_sh_ver())
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_sh_ver(self):
        vs     = self._sh_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]

        ten_inst = self.cbo_sh_inst.get().strip()
        mcv, _   = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if ten_inst and mcv:
            try:
                self.fb_sh.cbo_mc.set(mcv)
                self.fb_sh.cbo_mc.config(state="disabled")
            except Exception:
                pass
        else:
            try:
                self.fb_sh.cbo_mc.config(state="readonly")
            except Exception:
                pass

        idxs = [i for i, v in enumerate(vs) if mcv in v.get("game_versions", [])] if mcv \
               else list(range(len(vs)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._sh_ver_idx_map = idxs
            self.cbo_sh_ver.config(values=ds)
            self.cbo_sh_ver.set(ds[0])
            self.lbl_status.config(
                text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv})." if mcv
                     else "Chon phien ban roi nhan Cai Shader.",
                fg="gray")
        else:
            self._sh_ver_idx_map = list(range(len(vs)))
            self.cbo_sh_ver.config(values=ds_all)
            if ds_all: self.cbo_sh_ver.set(ds_all[0])
            else:       self.cbo_sh_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}). Hien thi tat ca.",
                    fg="#E64A19")

    def _install_sh(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_sh_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_sh_ver.current()
        if iv < 0 or not self._sh_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._sh_ver_idx_map):
            iv = self._sh_ver_idx_map[iv]
        vd    = self._sh_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "shader.zip")
        self.lbl_status.config(text="Dang tai Shader...", fg="#F57C00")

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
                    self.after(0, lambda: self.lbl_status.config(text=f"Dang tai: {pct}%", fg="#F57C00"))
                tai_file(url, pz, prog)
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

    # ==================================================================
    # TAB: CAI TU FILE (dung chung cho Modrinth & CurseForge)
    # ==================================================================

    def _build_file(self):
        from components.install_utils import cai_modpack_tu_file
        f = self.tab_f
        tk.Label(f, text="Cai tu file  (.mrpack / .zip / .jar)",
                 font=("Arial", 11, "bold"), fg="#37474F").pack(pady=(20, 4))
        tk.Label(f, text="Modpack: Modrinth (.mrpack)  |  CurseForge (.zip)\n"
                         "Mod: file .jar (copy thang vao thu muc mods/)\n"
                         "Resource Pack / Shader: file .zip / .jar",
                 font=("Arial", 9, "italic"), fg="gray", justify="left").pack(pady=(0, 12))

        fr = tk.Frame(f)
        fr.pack(padx=24)
        tk.Label(fr, text="File:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=6)
        self.ent_fp = tk.Entry(fr, font=("Arial", 9), width=38, state="readonly")
        self.ent_fp.grid(row=0, column=1, padx=6)
        tk.Button(fr, text="Chon file", font=("Arial", 9), bg="#607D8B", fg="white",
                  activebackground="#607D8B", activeforeground="white",
                  command=self._pick_file).grid(row=0, column=2)

        tk.Label(fr, text="Loai:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=6)
        self.cbo_file_type = ttk.Combobox(
            fr, values=["Modpack", "Mod", "Resource Pack", "Shader"],
            font=("Arial", 9), state="readonly", width=20)
        self.cbo_file_type.set("Modpack")
        self.cbo_file_type.grid(row=1, column=1, sticky="w", padx=6)

        tk.Label(fr, text="Ten / Instance:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=6)
        self.ent_fn = tk.Entry(fr, font=("Arial", 9), width=38)
        self.ent_fn.grid(row=2, column=1, padx=6)

        tk.Button(f, text="Cai dat tu File", font=("Arial", 10, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white",
                  width=22, height=2, command=self._install_file).pack(pady=16)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            parent=self, title="Chon file",
            filetypes=[("Modpack/Mod/Pack files", "*.mrpack *.zip *.jar"), ("All files", "*.*")])
        if path:
            self.ent_fp.config(state="normal")
            self.ent_fp.delete(0, "end")
            self.ent_fp.insert(0, path)
            self.ent_fp.config(state="readonly")
            self.ent_fn.delete(0, "end")
            self.ent_fn.insert(0, os.path.splitext(os.path.basename(path))[0].replace(" ", "_")[:30])
            ext = os.path.splitext(path)[1].lower()
            if ext == ".mrpack":
                self.cbo_file_type.set("Modpack")
            elif ext == ".jar":
                self.cbo_file_type.set("Mod")

    def _install_file(self):
        from components.install_utils import cai_modpack_tu_file
        path = self.ent_fp.get().strip()
        ten  = self.ent_fn.get().strip()
        loai = self.cbo_file_type.get()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Chu y", "Chon file hop le!", parent=self); return
        if not ten:
            messagebox.showwarning("Chu y", "Nhap ten!", parent=self); return
        if loai == "Modpack" and ten in config.current_config["danh_sach_instances"]:
            messagebox.showwarning("Chu y", "Ten Instance da ton tai!", parent=self); return

        self._tang_tac_vu()
        try:
            if loai == "Modpack":
                cai_modpack_tu_file(path, ten, self.lbl_status, self._done, cancel_event=self._cancel_event)
            elif loai == "Mod":
                cai_mod_tu_file(path, ten, self.lbl_status)
            else:
                map_loai = {"Resource Pack": "rsp", "Shader": "shader"}
                cai_rsp_shader_tu_file(path, ten, map_loai[loai], self.lbl_status)
        finally:
            self._giam_tac_vu()