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
    lay_version_modrinth_theo_id,
    lay_project_modrinth,
    lay_category_modrinth,
)
from components.install_utils import (
    tai_file,
    _tai_file_don_gian,
    cai_mod_tu_file,
    cai_rsp_shader_tu_file,
    cai_modpack_tu_file,
    ten_folder_an_toan,
    lay_trang_thai_da_cai,
    luu_muc_da_cai,
    luu_modpack_da_cai,
    kiem_tra_ten_da_cai,
    tim_ten_file_da_cai,
    cai_anh_bia_modpack_modrinth_nen,
)
from components.widgets import make_instance_ctl
_NO_INST = "— Chưa chọn —"
_LOAI_THU_MUC_THEO_PROJECT_TYPE = {
    "mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks",
}
def _cau_bao_xong(cau_goc, so_ok, so_loi):
    text = cau_goc
    if so_ok:
        text += f" + {so_ok} dependency"
    text += "!"
    if so_loi:
        text += f" ({so_loi} dependency lỗi, xem log)"
    return text
class ModrinthModMixin:
    def _nap_lai_content_instance_dang_mo(self, ten_inst, loai_thu_muc):
        app = getattr(self, "app", None)
        if app is None:
            return
        def _goi():
            detail = getattr(app, "instance_detail", None)
            if detail is not None:
                detail.nap_lai_tab(loai_thu_muc, ten_instance=ten_inst)
        try:
            self.after(0, _goi)
        except Exception:
            pass
    def _cai_required_deps_modrinth(self, ten_inst, version_data, khi_xong=None):
        deps = [d for d in (version_data.get("dependencies") or [])
                if d.get("dependency_type") == "required"]
        if not deps or not ten_inst:
            if khi_xong:
                khi_xong(0, 0)
            return
        def _t():
            visited = set()
            loai_anh_huong = set()   
            so_ok, so_loi = self._cai_required_deps_modrinth_worker(
                ten_inst, deps, visited, loai_anh_huong)
            if so_ok:
                self.after(0, self.refresh_all_installed_states)
                for loai in loai_anh_huong:
                    self._nap_lai_content_instance_dang_mo(ten_inst, loai)
            if khi_xong:
                self.after(0, lambda: khi_xong(so_ok, so_loi))
        threading.Thread(target=_t, daemon=True).start()
    def _cai_required_deps_modrinth_worker(self, ten_inst, deps, visited, loai_anh_huong=None):
        if loai_anh_huong is None:
            loai_anh_huong = set()
        mc_ver, loader = self._get_inst_mc_loader(ten_inst)
        mc_ver_l = (mc_ver or "").strip().lower()
        loader_l = (loader or "").strip().lower()
        so_ok = 0
        so_loi = 0
        for dep in deps:
            dep_pid = dep.get("project_id")
            dep_vid = dep.get("version_id")
            khoa = dep_pid or dep_vid
            ten_dep_log = str(dep_pid or dep_vid or "?")
            if not khoa or khoa in visited:
                continue
            visited.add(khoa)
            try:
                proj = None
                if dep_vid:
                    dep_version = lay_version_modrinth_theo_id(dep_vid)
                else:
                    try:
                        proj = lay_project_modrinth(dep_pid)
                    except Exception:
                        proj = None
                    ptype_dep = (proj or {}).get("project_type", "mod")
                    can_loc_loader = ptype_dep not in ("resourcepack", "shader")
                    vs = lay_phien_ban_modrinth(dep_pid)
                    phu_hop = [
                        v for v in vs
                        if (not mc_ver_l or mc_ver_l in
                            [str(g).strip().lower() for g in v.get("game_versions", [])])
                        and (not can_loc_loader or not loader_l or loader_l in
                             [str(l).strip().lower() for l in v.get("loaders", [])])
                    ]
                    if not phu_hop:
                        msg = (f"Không tìm thấy dependency phù hợp cho "
                               f"{mc_ver or '?'} / {loader or '?'} (project {dep_pid})")
                        print(f"[RequiredDeps] {msg}")
                        self.after(0, lambda m=msg: self.lbl_status.config(text=m, fg="#E9A23B"))
                        continue
                    dep_version = phu_hop[0]
                if not dep_version:
                    continue
                dep_pid_thuc = dep_version.get("project_id") or dep_pid
                ten_hien_thi = dep_pid_thuc
                ptype = "mod"
                try:
                    if proj is None or proj.get("id") != dep_pid_thuc:
                        proj = lay_project_modrinth(dep_pid_thuc)
                    if proj:
                        ptype = proj.get("project_type", "mod")
                        ten_hien_thi = proj.get("title") or dep_pid_thuc
                except Exception:
                    pass
                loai_thu_muc = _LOAI_THU_MUC_THEO_PROJECT_TYPE.get(ptype, "mods")
                ten_dep_log = ten_hien_thi
                if lay_trang_thai_da_cai(loai_thu_muc, "modrinth", dep_pid_thuc, ten_instance=ten_inst):
                    continue
                files = dep_version.get("files", [])
                prim = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
                if not prim or not prim.get("url"):
                    raise Exception("Không tìm thấy file tải trong phiên bản dependency")
                fname = prim.get("filename") or f"{dep_pid_thuc}.jar"
                self.after(0, lambda t=ten_hien_thi: self.lbl_status.config(
                    text=f"Đang cài dependency: {t}…", fg="#00ACC1"))
                thu_muc_dest = os.path.join(
                    config.current_config.get("thu_muc_game", ""), "Instances",
                    ten_folder_an_toan(ten_inst), loai_thu_muc)
                os.makedirs(thu_muc_dest, exist_ok=True)
                _tai_file_don_gian(prim["url"], os.path.join(thu_muc_dest, fname))
                luu_muc_da_cai(ten_inst, loai_thu_muc, dep_pid_thuc, "modrinth",
                                dep_version.get("id"), dep_version.get("version_number"),
                                fname, ngay=dep_version.get("date_published"),
                                title=(proj.get("title") if proj else None),
                                icon_url=(proj.get("icon_url") if proj else None))
                so_ok += 1
                loai_anh_huong.add(loai_thu_muc)
                deps_con = [d for d in (dep_version.get("dependencies") or [])
                            if d.get("dependency_type") == "required"]
                if deps_con:
                    ok_con, loi_con = self._cai_required_deps_modrinth_worker(
                        ten_inst, deps_con, visited, loai_anh_huong)
                    so_ok += ok_con
                    so_loi += loi_con
            except Exception as e:
                so_loi += 1
                print(f"[RequiredDeps] Lỗi cài dependency '{ten_dep_log}': {e}")
                self.after(0, lambda t=ten_dep_log, err=e: self.lbl_status.config(
                    text=f"Lỗi cài dependency {t}: {err}", fg="#E53935"))
                continue
        return so_ok, so_loi
    def _load_categories_mr_async(self, fb, project_type):
        def _t():
            try:
                cats = lay_category_modrinth(project_type)
                if cats:
                    fb.after(0, lambda: fb.set_categories(cats))
            except Exception:
                pass
        threading.Thread(target=_t, daemon=True).start()
    def _build_modpack_modrinth(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar
        f  = self.tab_mr
        BG = f["bg"]
        self.lv_mr = tk.Frame(f, bg=BG)
        self.lv_mr.pack(fill="both", expand=True)
        self.dv_mr = tk.Frame(f, bg=BG)
        lv = self.lv_mr
        self.fb_mr = FilterBar(lv, self._search_mr, accent_color="#00ACC1",
                               show_category=True, multi_category=True, bg=BG)
        self.fb_mr.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_mr_async(self.fb_mr, "modpack")
        self.list_mr = ContentTableWidget(lv, "modrinth", self._select_mr,
                                          is_installed_cb=self._is_mr_installed)
        self.list_mr.pack(fill="both", expand=True, padx=10)
        self.pg_mr = PaginationBar(lv, self._goto_mr_page, accent_color="#00ACC1", bg=BG)
        self.pg_mr.pack(fill="x", padx=10, pady=(2, 8))
        self._mr_data        = []
        self._mr_vers_raw    = []
        self._mr_ver_idx_map = []
        self._mr_page        = 1
        self._mr_total       = 0
        self._mr_last_kw     = None
    def _load_mr_top(self, page=1):
        self._mr_page    = page
        self._mr_last_kw = None
        try:
            r, total = lay_modrinth_popular("modpack", 25, offset=(page - 1) * 25)
            self._mr_data  = r
            self._mr_total = total
            self.after(0, lambda: (
                self.list_mr.load(r),
                self.pg_mr.set_total(total, 25, page),
                self.lbl_status.config(text=f"Top Modpack (Modrinth) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi MR: {e}", fg="red"))
    def _search_mr(self, page=1):
        kw          = self.ent_search.get().strip()
        mc, ld, cat = self.fb_mr.get()
        self._mr_page    = page
        self._mr_last_kw = (kw, mc, ld, cat)
        self.lbl_status.config(text="Đang tìm...", fg="#00ACC1")
        def _t():
            try:
                r, total = tim_kiem_modrinth("modpack", kw, mc, ld, cat, 25, offset=(page - 1) * 25)
                self._mr_data  = r
                self._mr_total = total
                self.after(0, lambda: (
                    self.list_mr.load(r),
                    self.pg_mr.set_total(total, 25, page),
                    self.lbl_status.config(text=f"{total} modpack - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _goto_mr_page(self, page):
        if self._mr_last_kw is None:
            threading.Thread(target=self._load_mr_top, args=(page,), daemon=True).start()
        else:
            self._search_mr(page)
    def _select_mr(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._mr_data): return
        r   = self._mr_data[idx]
        ten = r.get("title", "")
        pid = r.get("project_id", r.get("slug", ""))
        def _install_from_detail(version_data, on_done=None, progress_cb=None):
            def _finish():
                if on_done:
                    self.after(0, on_done)
            files = version_data.get("files", [])
            prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
            if not prim:
                messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self)
                _finish()
                return
            url      = prim["url"]
            fname    = prim.get("filename", "modpack.mrpack")
            _da_cai  = lay_trang_thai_da_cai("modpack", "modrinth", pid)
            ten_inst = _da_cai["ten_instance"] if _da_cai else ten[:30]
            self.lbl_status.config(text="Đang tải...", fg="#00ACC1")
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
                            text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#00ACC1"))
                        self.ghi_tien_do(pct // 10, f"Đang tải gói: {pct}%")
                        if progress_cb:
                            self.after(0, lambda: progress_cb(pct // 10, 100))
                    tai_file(url, pz, prog)
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy cai modpack")
                    def _done_va_xoa():
                        try: shutil.rmtree(_tmp)
                        except: pass
                        luu_modpack_da_cai(ten_inst, "modrinth", pid,
                                           version_data.get("id"),
                                           version_data.get("version_number"),
                                           ngay=version_data.get("date_published"))
                        cai_anh_bia_modpack_modrinth_nen(ten_inst, pid, r)
                        self._giam_tac_vu()
                        self._done()
                        _finish()
                    def _huy_va_xoa():
                        try: shutil.rmtree(_tmp)
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
                                        progress_cb=_modpack_progress,
                                        callback_huy=_huy_va_xoa)
                except TacVuBiHuy:
                    try: shutil.rmtree(_tmp)
                    except: pass
                    self._giam_tac_vu()
                    self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Modpack.", fg="#E53935"))
                    _finish()
                except Exception as e:
                    self._giam_tac_vu()
                    self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
                    _finish()
            def _bat_dau():
                self._tang_tac_vu()
                threading.Thread(target=_t, daemon=True).start()
            self._chay_hoac_xep_hang(f"Modpack: {fname}", _bat_dau,
                                      item_id=("modpack", "modrinth", pid))
        if view:
            installed_info = lay_trang_thai_da_cai("modpack", "modrinth", pid)
            self._swap_to_detail(self.lv_mr, self.dv_mr, "modrinth", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#00ACC1", installed_info=installed_info,
                                  loai="modpack")
            return
        if install:
            self.lbl_status.config(text=f"Đang tải phiên bản '{ten}'...", fg="#00ACC1")
            def _t():
                try:
                    vs = lay_phien_ban_modrinth(pid)
                    def _apply():
                        self._giam_tac_vu()
                        try:
                            fb_mc, _, _ = self.fb_mr.get()
                        except Exception:
                            fb_mc = ""
                        if fb_mc and fb_mc != "Tất cả":
                            idxs = [i for i, v in enumerate(vs) if fb_mc in v.get("game_versions", [])]
                        else:
                            idxs = []
                        best = vs[idxs[0]] if idxs else (vs[0] if vs else None)
                        if not best:
                            messagebox.showwarning("Chú ý", "Không tìm thấy phiên bản phù hợp!", parent=self)
                            return
                        _install_from_detail(best)
                    self.after(0, _apply)
                except Exception as e:
                    def _err(e=e):
                        self._giam_tac_vu()
                        self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                    self.after(0, _err)
            def _bat_dau():
                self._tang_tac_vu()
                threading.Thread(target=_t, daemon=True).start()
            self._chay_hoac_xep_hang(f"Modpack: {ten}", _bat_dau,
                                      item_id=("modpack", "modrinth", pid))
            return
    def _build_mod_modrinth(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar
        self._modmr_data     = []
        self._modmr_cur      = None   
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
        self.fb_modmr = FilterBar(lv, self._search_modmr, accent_color="#00ACC1",
                                  show_category=True, multi_category=True, bg=BG)
        self.fb_modmr.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_mr_async(self.fb_modmr, "mod")
        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bp, text="Phiên bản mod:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_modmr_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_modmr_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cài vào Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=2)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_modmr_inst = ttk.Combobox(bp, values=[_NO_INST] + ds_inst, font=("Arial", 9), width=42, height=5)
        self.cbo_modmr_inst.set(_NO_INST)
        self.cbo_modmr_inst.grid(row=1, column=1, padx=6)
        self.cbo_modmr_inst.bind("<<ComboboxSelected>>", lambda e: self._on_modmr_inst_change())
        self.cbo_modmr_inst.bind("<ButtonPress>", lambda e: self._sync_inst_cbo(self.cbo_modmr_inst))
        tk.Button(bp, text="Cài Mod", font=("Arial", 9, "bold"),
                  bg="#00ACC1", fg="white", activebackground="#00ACC1", activeforeground="white",
                  width=14, pady=4, command=self._install_modmr).grid(row=0, column=2, rowspan=2, padx=8)
        self.list_modmr = ContentTableWidget(lv, "modrinth", self._select_modmr,
                                             is_installed_cb=self._is_modmr_installed)
        self.list_modmr.pack(fill="both", expand=True, padx=10)
        self.pg_modmr = PaginationBar(lv, self._goto_modmr_page, accent_color="#00ACC1", bg=BG)
        self.pg_modmr.pack(fill="x", padx=10, pady=(2, 0))
    def _load_modmr_top(self, page=1):
        self._modmr_page    = page
        self._modmr_last_kw = None
        try:
            r, total = lay_modrinth_popular("mod", 25, offset=(page - 1) * 25)
            self._modmr_data  = r
            self._modmr_total = total
            self.after(0, lambda: (
                self.list_modmr.load(r),
                self.pg_modmr.set_total(total, 25, page),
                self.lbl_status.config(text=f"Top Mod (Modrinth) - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi ModMR: {e}", fg="red"))
    def _search_modmr(self, page=1):
        kw        = self.ent_search.get().strip()
        mc, ld, c = self.fb_modmr.get()
        self._modmr_page    = page
        self._modmr_last_kw = (kw, mc, ld, c)
        self.lbl_status.config(text="Đang tìm Mod Modrinth...", fg="#00ACC1")
        def _t():
            try:
                r, total = tim_kiem_modrinth("mod", kw, mc, ld, c, 25, offset=(page - 1) * 25)
                self._modmr_data  = r
                self._modmr_total = total
                self.after(0, lambda: (
                    self.list_modmr.load(r),
                    self.pg_modmr.set_total(total, 25, page),
                    self.lbl_status.config(text=f"{total} mod - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _goto_modmr_page(self, page):
        if self._modmr_last_kw is None:
            threading.Thread(target=self._load_modmr_top, args=(page,), daemon=True).start()
        else:
            self._search_modmr(page)
    def _lay_installed_info_day_du(self, loai, source, pid, ten_inst, ten_hien_thi):
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
    def _is_modmr_installed(self, d):
        pid = d.get("project_id", "")
        ten_inst = self.cbo_modmr_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            return False
        if lay_trang_thai_da_cai("mods", "modrinth", pid, ten_instance=ten_inst):
            return True
        return kiem_tra_ten_da_cai(ten_inst, "mods", d.get("title", ""))
    def _is_mr_installed(self, d):
        pid = d.get("project_id", d.get("slug", ""))
        return bool(lay_trang_thai_da_cai("modpack", "modrinth", pid))
    def _is_rsp_installed(self, d):
        pid = d.get("project_id", "")
        ten_inst = self.cbo_rsp_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            return False
        if lay_trang_thai_da_cai("resourcepacks", "modrinth", pid, ten_instance=ten_inst):
            return True
        return kiem_tra_ten_da_cai(ten_inst, "resourcepacks", d.get("title", ""))
    def _is_sh_installed(self, d):
        pid = d.get("project_id", "")
        ten_inst = self.cbo_sh_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            return False
        if lay_trang_thai_da_cai("shaderpacks", "modrinth", pid, ten_instance=ten_inst):
            return True
        return kiem_tra_ten_da_cai(ten_inst, "shaderpacks", d.get("title", ""))
    def _select_modmr(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._modmr_data): return
        r   = self._modmr_data[idx]
        pid = r.get("project_id", "")
        self._modmr_cur = r
        if view:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                files = version_data.get("files", [])
                prim  = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self)
                    _finish()
                    return
                url      = prim["url"]
                fname    = prim.get("filename", "mod.jar")
                ten_inst = self.cbo_modmr_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
                if not ten_inst:
                    messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                    _finish()
                    return
                mcv_chk, loader = self._get_inst_mc_loader(ten_inst)
                if loader and loader.lower() == "vanilla":
                    messagebox.showwarning("Không thể cài Mod",
                        f"Instance '{ten_inst}' dùng Vanilla (không có mod loader).\n"
                        "Hãy chọn instance dùng Fabric, Forge, Quilt hoặc NeoForge.", parent=self)
                    _finish()
                    return
                if mcv_chk and mcv_chk not in version_data.get("game_versions", []):
                    messagebox.showerror("Lỗi",
                        f"Phiên bản mod này không hỗ trợ Minecraft {mcv_chk} "
                        f"(yêu cầu của Instance '{ten_inst}'). Không thể cài.", parent=self)
                    _finish()
                    return
                if loader and loader.lower() not in [l.lower() for l in version_data.get("loaders", [])]:
                    messagebox.showerror("Lỗi",
                        f"Phiên bản mod này không hỗ trợ Loader '{loader}' "
                        f"(yêu cầu của Instance '{ten_inst}'). Không thể cài.", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Đang tải Mod...", fg="#00ACC1")
                def _t():
                    try:
                        tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                        os.makedirs(tmp, exist_ok=True)
                        pz = os.path.join(tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai mod")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(text=f"Đang tải mod: {pct}%", fg="#00ACC1"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai mod")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            luu_muc_da_cai(ten_inst, "mods", pid, "modrinth",
                                           version_data.get("id"),
                                           version_data.get("version_number"),
                                           fname, ngay=version_data.get("date_published"),
                                           title=r.get("title"), author=r.get("author"),
                                           icon_url=r.get("icon_url"))
                            self._nap_lai_content_instance_dang_mo(ten_inst, "mods")
                            def _bao_xong(so_ok, so_loi):
                                self.lbl_status.config(
                                    text=_cau_bao_xong(
                                        f"Đã cài mod '{fname}' vào {ten_inst}", so_ok, so_loi),
                                    fg="#2b8c54")
                                self._thong_bao_cai_xong("Mod", fname, ten_inst)
                                _finish()
                            self._cai_required_deps_modrinth(ten_inst, version_data, khi_xong=_bao_xong)
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
                def _bat_dau():
                    self._tang_tac_vu()
                    threading.Thread(target=_t, daemon=True).start()
                self._chay_hoac_xep_hang(f"Mod: {fname}", _bat_dau,
                                          item_id=("mods", "modrinth", pid))
            ten_inst_hien_tai = self.cbo_modmr_inst.get().strip()
            ten_inst_hien_tai = "" if ten_inst_hien_tai == _NO_INST else ten_inst_hien_tai
            self._swap_to_detail(self.lv_modmr, self.dv_modmr, "modrinth", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#00ACC1", installed_info=self._lay_installed_info_day_du(
                                      "mods", "modrinth", pid, ten_inst_hien_tai, r.get("title", "")),
                                  instance_ctl=make_instance_ctl(self.cbo_modmr_inst, _NO_INST),
                                  loai="mods")
            return
        if install:
            self.cbo_modmr_ver.set("Dang tai phien ban...")
            def _t():
                try:
                    vs = lay_phien_ban_modrinth(pid)
                    self._modmr_vers_raw = vs
                    def _apply():
                        self._filter_modmr_ver()
                        self._giam_tac_vu()
                        self._install_modmr()
                    self.after(0, _apply)
                except Exception as e:
                    def _err(e=e):
                        self._giam_tac_vu()
                        self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                    self.after(0, _err)
            def _bat_dau():
                self._tang_tac_vu()
                threading.Thread(target=_t, daemon=True).start()
            self._chay_hoac_xep_hang(f"Mod: {r.get('title', pid)}", _bat_dau,
                                      item_id=("mods", "modrinth", pid))
            return
        self.cbo_modmr_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._modmr_vers_raw = vs
                def _apply():
                    self._filter_modmr_ver()
                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _sync_inst_cbo(self, cbo):
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        cur_val = cbo.get()
        cbo.config(values=[_NO_INST] + ds_inst)
        if cur_val not in ds_inst and cur_val != _NO_INST:
            cur = config.current_config.get("current_instance", "")
            cbo.set(cur if cur in ds_inst else _NO_INST)
    def _on_modmr_inst_change(self):
        ten_inst = self.cbo_modmr_inst.get().strip()
        ten_inst = "" if ten_inst == _NO_INST else ten_inst
        da_doi_bo_loc = self._apply_inst_filter_to_fb(ten_inst, self.fb_modmr) if ten_inst else False
        self._filter_modmr_ver()
        self.list_modmr.refresh_installed_states()
        if da_doi_bo_loc:
            self._search_modmr()
    def _filter_modmr_ver(self):
        vs     = self._modmr_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}  [{', '.join(v.get('loaders',[]))}]"
                  for v in vs]
        ten_inst = self.cbo_modmr_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        mcv, loader = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")
        self._apply_inst_filter_to_fb(ten_inst, self.fb_modmr)
        try:
            fb_mc, fb_ld, _ = self.fb_modmr.get()
        except Exception:
            fb_mc, fb_ld = mcv, loader
        if ten_inst:
            use_mc = mcv or fb_mc
            use_ld = loader or fb_ld
            bo_qua_loc_loader = False
        else:
            use_mc = fb_mc or mcv
            use_ld = fb_ld or loader
            bo_qua_loc_loader = (not use_ld) or use_ld in ("Tất cả", "Vanilla")
        if use_mc:
            idxs = [
                i for i, v in enumerate(vs)
                if use_mc in v.get("game_versions", [])
                and (bo_qua_loc_loader
                     or use_ld.lower() in [l.lower() for l in v.get("loaders", [])])
            ]
        else:
            idxs = list(range(len(vs)))
        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._modmr_ver_idx_map = idxs
            self.cbo_modmr_ver.config(values=ds)
            self.cbo_modmr_ver.set(ds[0])
            if ten_inst and use_mc:
                self.lbl_status.config(
                    text=f"Đã lọc {len(ds)} phiên bản phù hợp với {ten_inst} (MC {use_mc}"
                         + (f", {use_ld}" if use_ld and use_ld not in ("Tất cả", "Vanilla") else "") + ").",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chọn phiên bản rồi nhấn Cài Mod.", fg="gray")
        elif ten_inst and use_mc:
            self._modmr_ver_idx_map = []
            self.cbo_modmr_ver.config(values=[])
            self.cbo_modmr_ver.set("")
            self.lbl_status.config(
                text=f"Lỗi: Mod này không có phiên bản nào tương thích với Instance "
                     f"'{ten_inst}' (MC {use_mc}"
                     + (f", {use_ld}" if use_ld and use_ld not in ("Tất cả", "Vanilla") else "")
                     + "). Không thể cài.",
                fg="red")
        else:
            self._modmr_ver_idx_map = list(range(len(vs)))
            self.cbo_modmr_ver.config(values=ds_all)
            if ds_all: self.cbo_modmr_ver.set(ds_all[0])
            else:       self.cbo_modmr_ver.set("")
    def _install_modmr(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_modmr_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self); return
        _, loader = self._get_inst_mc_loader(ten_inst)
        if loader and loader.lower() == "vanilla":
            messagebox.showwarning("Không thể cài Mod",
                f"Instance '{ten_inst}' dùng Vanilla (không có mod loader).\n"
                "Hãy chọn instance dùng Fabric, Forge, Quilt hoặc NeoForge.", parent=self)
            return
        if not self._modmr_ver_idx_map:
            messagebox.showerror("Lỗi",
                f"Mod này không có phiên bản nào tương thích với Instance '{ten_inst}'.\n"
                "Không thể cài.", parent=self)
            return
        iv = self.cbo_modmr_ver.current()
        if iv < 0 or not self._modmr_vers_raw:
            messagebox.showwarning("Chú ý", "Chọn phiên bản!", parent=self); return
        if iv < len(self._modmr_ver_idx_map):
            iv = self._modmr_ver_idx_map[iv]
        vd    = self._modmr_vers_raw[iv]
        mcv_chk, loader_chk = self._get_inst_mc_loader(ten_inst)
        if mcv_chk and mcv_chk not in vd.get("game_versions", []):
            messagebox.showerror("Lỗi",
                f"Phiên bản mod này không hỗ trợ Minecraft {mcv_chk} "
                f"(yêu cầu của Instance '{ten_inst}'). Không thể cài.", parent=self)
            return
        if loader_chk and loader_chk.lower() not in [l.lower() for l in vd.get("loaders", [])]:
            messagebox.showerror("Lỗi",
                f"Phiên bản mod này không hỗ trợ Loader '{loader_chk}' "
                f"(yêu cầu của Instance '{ten_inst}'). Không thể cài.", parent=self)
            return
        files = vd.get("files", [])
        prim  = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "mod.jar")
        self.lbl_status.config(text="Đang tải Mod...", fg="#00ACC1")
        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz = os.path.join(tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai mod")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(text=f"Đang tải mod: {pct}%", fg="#00ACC1"))
                    self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai mod")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    _cur = self._modmr_cur or {}
                    luu_muc_da_cai(ten_inst, "mods", vd.get("project_id", ""), "modrinth",
                                   vd.get("id"), vd.get("version_number"),
                                   fname, ngay=vd.get("date_published"),
                                   title=_cur.get("title"), author=_cur.get("author"),
                                   icon_url=_cur.get("icon_url"))
                    self._nap_lai_content_instance_dang_mo(ten_inst, "mods")
                    def _bao_xong(so_ok, so_loi):
                        self.lbl_status.config(
                            text=_cau_bao_xong(
                                f"Đã cài mod '{fname}' vào {ten_inst}", so_ok, so_loi),
                            fg="#2b8c54")
                        self._thong_bao_cai_xong("Mod", fname, ten_inst)
                    self._cai_required_deps_modrinth(ten_inst, vd, khi_xong=_bao_xong)
                cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Mod.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        def _bat_dau():
            self._tang_tac_vu()
            threading.Thread(target=_t, daemon=True).start()
        self._chay_hoac_xep_hang(f"Mod: {fname}", _bat_dau,
                                  item_id=("mods", "modrinth", vd.get("project_id", "")))
    def _build_rsp_tab(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar
        self._rsp_data        = []
        self._rsp_cur         = None
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
        self.fb_rsp = FilterBar(lv, self._search_rsp, accent_color="#00ACC1",
                                show_loader=False, show_category=True, multi_category=True, bg=BG)
        self.fb_rsp.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_mr_async(self.fb_rsp, "resourcepack")
        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bp, text="Phiên bản:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_rsp_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_rsp_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cài vào Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=2)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_rsp_inst = ttk.Combobox(bp, values=[_NO_INST] + ds_inst, font=("Arial", 9), width=42, height=5)
        self.cbo_rsp_inst.set(_NO_INST)
        self.cbo_rsp_inst.grid(row=1, column=1, padx=6)
        self.cbo_rsp_inst.bind("<ButtonPress>", lambda e: self._sync_inst_cbo(self.cbo_rsp_inst))
        tk.Button(bp, text="Cài RSP", font=("Arial", 9, "bold"),
                  bg="#00ACC1", fg="white", activebackground="#00ACC1", activeforeground="white",
                  width=14, pady=4, command=self._install_rsp).grid(row=0, column=2, rowspan=2, padx=8)
        self.list_rsp = ContentTableWidget(lv, "modrinth", self._select_rsp,
                                           is_installed_cb=self._is_rsp_installed)
        self.list_rsp.pack(fill="both", expand=True, padx=10)
        self.cbo_rsp_inst.bind("<<ComboboxSelected>>", lambda e: (
            self.list_rsp.refresh_installed_states()), add="+")
        self.pg_rsp = PaginationBar(lv, self._goto_rsp_page, accent_color="#00ACC1", bg=BG)
        self.pg_rsp.pack(fill="x", padx=10, pady=(2, 0))
    def _load_rsp_top(self, page=1):
        self._rsp_page    = page
        self._rsp_last_kw = None
        try:
            r, total = lay_modrinth_popular("resourcepack", 25, offset=(page - 1) * 25)
            self._rsp_data  = r
            self._rsp_total = total
            self.after(0, lambda: (
                self.list_rsp.load(r),
                self.pg_rsp.set_total(total, 25, page),
                self.lbl_status.config(text=f"Top Resource Pack - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi RSP: {e}", fg="red"))
    def _search_rsp(self, page=1):
        kw       = self.ent_search.get().strip()
        mc, _, c = self.fb_rsp.get()
        self._rsp_page    = page
        self._rsp_last_kw = (kw, mc, c)
        self.lbl_status.config(text="Đang tìm RSP...", fg="#00ACC1")
        def _t():
            try:
                r, total = tim_kiem_modrinth("resourcepack", kw, mc, "", c, 25, offset=(page - 1) * 25)
                self._rsp_data  = r
                self._rsp_total = total
                self.after(0, lambda: (
                    self.list_rsp.load(r),
                    self.pg_rsp.set_total(total, 25, page),
                    self.lbl_status.config(text=f"{total} resource pack - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _goto_rsp_page(self, page):
        if self._rsp_last_kw is None:
            threading.Thread(target=self._load_rsp_top, args=(page,), daemon=True).start()
        else:
            self._search_rsp(page)
    def _select_rsp(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._rsp_data): return
        r   = self._rsp_data[idx]
        pid = r.get("project_id", "")
        self._rsp_cur = r
        if view:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                files = version_data.get("files", [])
                prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self)
                    _finish()
                    return
                url      = prim["url"]
                fname    = prim.get("filename", "resourcepack.zip")
                ten_inst = self.cbo_rsp_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
                if not ten_inst:
                    messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Đang tải RSP...", fg="#00ACC1")
                def _t():
                    try:
                        tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                        os.makedirs(tmp, exist_ok=True)
                        pz = os.path.join(tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai RSP")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(text=f"Đang tải: {pct}%", fg="#00ACC1"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai RSP")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            luu_muc_da_cai(ten_inst, "resourcepacks", pid, "modrinth",
                                           version_data.get("id"), version_data.get("version_number"),
                                           fname, ngay=version_data.get("date_published"),
                                           title=r.get("title"), author=r.get("author"),
                                           icon_url=r.get("icon_url"))
                            self._nap_lai_content_instance_dang_mo(ten_inst, "resourcepacks")
                            def _bao_xong(so_ok, so_loi):
                                self.lbl_status.config(
                                    text=_cau_bao_xong(f"Đã cài RSP vào {ten_inst}", so_ok, so_loi),
                                    fg="#2b8c54")
                                self._thong_bao_cai_xong("Resource Pack", fname, ten_inst)
                                _finish()
                            self._cai_required_deps_modrinth(ten_inst, version_data, khi_xong=_bao_xong)
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
                def _bat_dau():
                    self._tang_tac_vu()
                    threading.Thread(target=_t, daemon=True).start()
                self._chay_hoac_xep_hang(f"Resource Pack: {fname}", _bat_dau,
                                          item_id=("resourcepacks", "modrinth", pid))
            ten_inst_hien_tai = self.cbo_rsp_inst.get().strip()
            ten_inst_hien_tai = "" if ten_inst_hien_tai == _NO_INST else ten_inst_hien_tai
            self._swap_to_detail(self.lv_rsp, self.dv_rsp, "modrinth", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#00ACC1", installed_info=self._lay_installed_info_day_du(
                                      "resourcepacks", "modrinth", pid, ten_inst_hien_tai, r.get("title", "")),
                                  instance_ctl=make_instance_ctl(self.cbo_rsp_inst, _NO_INST),
                                  loai="resourcepacks")
            return
        if install:
            self.cbo_rsp_ver.set("Dang tai phien ban...")
            def _t():
                try:
                    vs = lay_phien_ban_modrinth(pid)
                    self._rsp_vers_raw = vs
                    def _apply():
                        self._filter_rsp_ver()
                        self._giam_tac_vu()
                        self._install_rsp()
                    self.after(0, _apply)
                except Exception as e:
                    def _err(e=e):
                        self._giam_tac_vu()
                        self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                    self.after(0, _err)
            def _bat_dau():
                self._tang_tac_vu()
                threading.Thread(target=_t, daemon=True).start()
            self._chay_hoac_xep_hang(f"Resource Pack: {r.get('title', pid)}", _bat_dau,
                                      item_id=("resourcepacks", "modrinth", pid))
            return
        self.cbo_rsp_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._rsp_vers_raw = vs
                self.after(0, self._filter_rsp_ver)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _filter_rsp_ver(self):
        vs     = self._rsp_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]
        self._rsp_ver_idx_map = list(range(len(vs)))
        self.cbo_rsp_ver.config(values=ds_all)
        if ds_all:
            self.cbo_rsp_ver.set(ds_all[0])
            self.lbl_status.config(text="Chon phien ban roi nhan Cài RSP.", fg="gray")
        else:
            self.cbo_rsp_ver.set("")
    def _install_rsp(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_rsp_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self); return
        iv = self.cbo_rsp_ver.current()
        if iv < 0 or not self._rsp_vers_raw:
            messagebox.showwarning("Chú ý", "Chọn phiên bản!", parent=self); return
        if iv < len(self._rsp_ver_idx_map):
            iv = self._rsp_ver_idx_map[iv]
        vd    = self._rsp_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "resourcepack.zip")
        self.lbl_status.config(text="Đang tải RSP...", fg="#00ACC1")
        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz = os.path.join(tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai RSP")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(text=f"Đang tải: {pct}%", fg="#00ACC1"))
                    self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai RSP")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    _cur = self._rsp_cur or {}
                    luu_muc_da_cai(ten_inst, "resourcepacks", vd.get("project_id", ""),
                                   "modrinth", vd.get("id"), vd.get("version_number"),
                                   fname, ngay=vd.get("date_published"),
                                   title=_cur.get("title"), author=_cur.get("author"),
                                   icon_url=_cur.get("icon_url"))
                    self._nap_lai_content_instance_dang_mo(ten_inst, "resourcepacks")
                    def _bao_xong(so_ok, so_loi):
                        self.lbl_status.config(
                            text=_cau_bao_xong(f"Đã cài RSP vào {ten_inst}", so_ok, so_loi),
                            fg="#2b8c54")
                        self._thong_bao_cai_xong("Resource Pack", fname, ten_inst)
                    self._cai_required_deps_modrinth(ten_inst, vd, khi_xong=_bao_xong)
                cai_rsp_shader_tu_file(pz, ten_inst, "rsp", self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Resource Pack.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        def _bat_dau():
            self._tang_tac_vu()
            threading.Thread(target=_t, daemon=True).start()
        self._chay_hoac_xep_hang(f"Resource Pack: {fname}", _bat_dau,
                                  item_id=("resourcepacks", "modrinth", vd.get("project_id", "")))
    def _build_shader_tab(self):
        from components.widgets import FilterBar, ContentTableWidget
        from components.mod_mc import PaginationBar
        self._sh_data        = []
        self._sh_cur         = None
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
        self.fb_sh = FilterBar(lv, self._search_sh, accent_color="#00ACC1",
                               show_loader=False, show_category=True, multi_category=True, bg=BG)
        self.fb_sh.pack(fill="x", padx=10, pady=(8, 4))
        self._load_categories_mr_async(self.fb_sh, "shader")
        bp = tk.Frame(lv, bg=BG)
        bp.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bp, text="Phiên bản:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_sh_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_sh_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cài vào Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=2)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_sh_inst = ttk.Combobox(bp, values=[_NO_INST] + ds_inst, font=("Arial", 9), width=42, height=5)
        self.cbo_sh_inst.set(_NO_INST)
        self.cbo_sh_inst.grid(row=1, column=1, padx=6)
        self.cbo_sh_inst.bind("<ButtonPress>", lambda e: self._sync_inst_cbo(self.cbo_sh_inst))
        tk.Button(bp, text="Cài Shader", font=("Arial", 9, "bold"),
                  bg="#00ACC1", fg="white", activebackground="#00ACC1", activeforeground="white",
                  width=14, pady=4, command=self._install_sh).grid(row=0, column=2, rowspan=2, padx=8)
        self.list_sh = ContentTableWidget(lv, "modrinth", self._select_sh,
                                          is_installed_cb=self._is_sh_installed)
        self.list_sh.pack(fill="both", expand=True, padx=10)
        self.cbo_sh_inst.bind("<<ComboboxSelected>>", lambda e: (
            self.list_sh.refresh_installed_states()), add="+")
        self.pg_sh = PaginationBar(lv, self._goto_sh_page, accent_color="#00ACC1", bg=BG)
        self.pg_sh.pack(fill="x", padx=10, pady=(2, 0))
    def _load_sh_top(self, page=1):
        self._sh_page    = page
        self._sh_last_kw = None
        try:
            r, total = lay_modrinth_popular("shader", 25, offset=(page - 1) * 25)
            self._sh_data  = r
            self._sh_total = total
            self.after(0, lambda: (
                self.list_sh.load(r),
                self.pg_sh.set_total(total, 25, page),
                self.lbl_status.config(text=f"Top Shader - trang {page}", fg="#2b8c54"),
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi Shader: {e}", fg="red"))
    def _search_sh(self, page=1):
        kw       = self.ent_search.get().strip()
        mc, _, c = self.fb_sh.get()
        self._sh_page    = page
        self._sh_last_kw = (kw, mc, c)
        self.lbl_status.config(text="Đang tìm Shader...", fg="#00ACC1")
        def _t():
            try:
                r, total = tim_kiem_modrinth("shader", kw, mc, "", c, 25, offset=(page - 1) * 25)
                self._sh_data  = r
                self._sh_total = total
                self.after(0, lambda: (
                    self.list_sh.load(r),
                    self.pg_sh.set_total(total, 25, page),
                    self.lbl_status.config(text=f"{total} shader - trang {page}", fg="#2b8c54"),
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _goto_sh_page(self, page):
        if self._sh_last_kw is None:
            threading.Thread(target=self._load_sh_top, args=(page,), daemon=True).start()
        else:
            self._search_sh(page)
    def _select_sh(self, idx, install=False, view=False):
        from components.mod_mc import TacVuBiHuy
        if idx >= len(self._sh_data): return
        r   = self._sh_data[idx]
        pid = r.get("project_id", "")
        self._sh_cur = r
        if view:
            def _install_from_detail(version_data, on_done=None, progress_cb=None):
                def _finish():
                    if on_done:
                        self.after(0, on_done)
                files = version_data.get("files", [])
                prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
                if not prim:
                    messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self)
                    _finish()
                    return
                url      = prim["url"]
                fname    = prim.get("filename", "shader.zip")
                ten_inst = self.cbo_sh_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
                if not ten_inst:
                    messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self)
                    _finish()
                    return
                self.lbl_status.config(text="Đang tải Shader...", fg="#00ACC1")
                def _t():
                    try:
                        tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                        os.makedirs(tmp, exist_ok=True)
                        pz = os.path.join(tmp, fname)
                        def prog(da, tong):
                            if self._cancel_event.is_set():
                                raise TacVuBiHuy("Da huy tai Shader")
                            pct = int(da / tong * 100)
                            self.after(0, lambda: self.lbl_status.config(text=f"Đang tải: {pct}%", fg="#00ACC1"))
                            self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                            if progress_cb:
                                self.after(0, lambda: progress_cb(da, tong))
                        tai_file(url, pz, prog)
                        if self._cancel_event.is_set():
                            raise TacVuBiHuy("Da huy cai Shader")
                        def _done():
                            try: shutil.rmtree(tmp)
                            except: pass
                            luu_muc_da_cai(ten_inst, "shaderpacks", pid, "modrinth",
                                           version_data.get("id"), version_data.get("version_number"),
                                           fname, ngay=version_data.get("date_published"),
                                           title=r.get("title"), author=r.get("author"),
                                           icon_url=r.get("icon_url"))
                            self._nap_lai_content_instance_dang_mo(ten_inst, "shaderpacks")
                            def _bao_xong(so_ok, so_loi):
                                self.lbl_status.config(
                                    text=_cau_bao_xong(f"Đã cài Shader vào {ten_inst}", so_ok, so_loi),
                                    fg="#2b8c54")
                                self._thong_bao_cai_xong("Shader", fname, ten_inst)
                                _finish()
                            self._cai_required_deps_modrinth(ten_inst, version_data, khi_xong=_bao_xong)
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
                def _bat_dau():
                    self._tang_tac_vu()
                    threading.Thread(target=_t, daemon=True).start()
                self._chay_hoac_xep_hang(f"Shader: {fname}", _bat_dau,
                                          item_id=("shaderpacks", "modrinth", pid))
            ten_inst_hien_tai = self.cbo_sh_inst.get().strip()
            ten_inst_hien_tai = "" if ten_inst_hien_tai == _NO_INST else ten_inst_hien_tai
            self._swap_to_detail(self.lv_sh, self.dv_sh, "modrinth", r,
                                  [], install_cb=_install_from_detail,
                                  accent="#00ACC1", installed_info=self._lay_installed_info_day_du(
                                      "shaderpacks", "modrinth", pid, ten_inst_hien_tai, r.get("title", "")),
                                  instance_ctl=make_instance_ctl(self.cbo_sh_inst, _NO_INST),
                                  loai="shaderpacks")
            return
        if install:
            self.cbo_sh_ver.set("Dang tai phien ban...")
            def _t():
                try:
                    vs = lay_phien_ban_modrinth(pid)
                    self._sh_vers_raw = vs
                    def _apply():
                        self._filter_sh_ver()
                        self._giam_tac_vu()
                        self._install_sh()
                    self.after(0, _apply)
                except Exception as e:
                    def _err(e=e):
                        self._giam_tac_vu()
                        self.lbl_status.config(text=f"Lỗi: {e}", fg="red")
                    self.after(0, _err)
            def _bat_dau():
                self._tang_tac_vu()
                threading.Thread(target=_t, daemon=True).start()
            self._chay_hoac_xep_hang(f"Shader: {r.get('title', pid)}", _bat_dau,
                                      item_id=("shaderpacks", "modrinth", pid))
            return
        self.cbo_sh_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._sh_vers_raw = vs
                self.after(0, self._filter_sh_ver)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()
    def _filter_sh_ver(self):
        vs     = self._sh_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]
        self._sh_ver_idx_map = list(range(len(vs)))
        self.cbo_sh_ver.config(values=ds_all)
        if ds_all:
            self.cbo_sh_ver.set(ds_all[0])
            self.lbl_status.config(text="Chon phien ban roi nhan Cài Shader.", fg="gray")
        else:
            self.cbo_sh_ver.set("")
    def _install_sh(self):
        from components.mod_mc import TacVuBiHuy
        ten_inst = self.cbo_sh_inst.get().strip(); ten_inst = "" if ten_inst == _NO_INST else ten_inst
        if not ten_inst:
            messagebox.showwarning("Chú ý", "Chọn Instance để cài vào!", parent=self); return
        iv = self.cbo_sh_ver.current()
        if iv < 0 or not self._sh_vers_raw:
            messagebox.showwarning("Chú ý", "Chọn phiên bản!", parent=self); return
        if iv < len(self._sh_ver_idx_map):
            iv = self._sh_ver_idx_map[iv]
        vd    = self._sh_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "shader.zip")
        self.lbl_status.config(text="Đang tải Shader...", fg="#00ACC1")
        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz = os.path.join(tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Da huy tai Shader")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(text=f"Đang tải: {pct}%", fg="#00ACC1"))
                    self.ghi_tien_do(pct, f"{da//1024}KB/{tong//1024}KB")
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Da huy cai Shader")
                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    _cur = self._sh_cur or {}
                    luu_muc_da_cai(ten_inst, "shaderpacks", vd.get("project_id", ""),
                                   "modrinth", vd.get("id"), vd.get("version_number"),
                                   fname, ngay=vd.get("date_published"),
                                   title=_cur.get("title"), author=_cur.get("author"),
                                   icon_url=_cur.get("icon_url"))
                    self._nap_lai_content_instance_dang_mo(ten_inst, "shaderpacks")
                    def _bao_xong(so_ok, so_loi):
                        self.lbl_status.config(
                            text=_cau_bao_xong(f"Đã cài Shader vào {ten_inst}", so_ok, so_loi),
                            fg="#2b8c54")
                        self._thong_bao_cai_xong("Shader", fname, ten_inst)
                    self._cai_required_deps_modrinth(ten_inst, vd, khi_xong=_bao_xong)
                cai_rsp_shader_tu_file(pz, ten_inst, "shader", self.lbl_status, _done)
            except TacVuBiHuy:
                try: shutil.rmtree(tmp)
                except: pass
                self.after(0, lambda: self.lbl_status.config(text="Đã hủy cài đặt Shader.", fg="#E53935"))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi: {e}", fg="red"))
            finally:
                self._giam_tac_vu()
        def _bat_dau():
            self._tang_tac_vu()
            threading.Thread(target=_t, daemon=True).start()
        self._chay_hoac_xep_hang(f"Shader: {fname}", _bat_dau,
                                  item_id=("shaderpacks", "modrinth", vd.get("project_id", "")))
    def _build_file(self):
        from components.install_utils import cai_modpack_tu_file
        f = self.tab_f
        tk.Label(f, text="Cài Modpack từ file  (.mrpack / .zip)",
                 font=("Arial", 11, "bold"), fg="#37474F").pack(pady=(20, 4))
        tk.Label(f, text="Modrinth (.mrpack)  |  CurseForge (.zip)",
                 font=("Arial", 9, "italic"), fg="gray", justify="left").pack(pady=(0, 12))
        fr = tk.Frame(f)
        fr.pack(padx=24)
        tk.Label(fr, text="File:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=6)
        self.ent_fp = tk.Entry(fr, font=("Arial", 9), width=38, state="readonly")
        self.ent_fp.grid(row=0, column=1, padx=6)
        tk.Button(fr, text="Chọn file", font=("Arial", 9), bg="#607D8B", fg="white",
                  activebackground="#607D8B", activeforeground="white",
                  command=self._pick_file).grid(row=0, column=2)
        tk.Label(fr, text="Tên / Instance:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=6)
        self.ent_fn = tk.Entry(fr, font=("Arial", 9), width=38)
        self.ent_fn.grid(row=1, column=1, padx=6)
        tk.Button(f, text="Cài đặt từ File", font=("Arial", 10, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white",
                  width=22, height=2, command=self._install_file).pack(pady=16)
    def _pick_file(self):
        path = filedialog.askopenfilename(
            parent=self, title="Chọn file Modpack",
            filetypes=[("Modpack files", "*.mrpack *.zip"), ("All files", "*.*")])
        if path:
            self.ent_fp.config(state="normal")
            self.ent_fp.delete(0, "end")
            self.ent_fp.insert(0, path)
            self.ent_fp.config(state="readonly")
            self.ent_fn.delete(0, "end")
            self.ent_fn.insert(0, os.path.splitext(os.path.basename(path))[0][:30])
    def _install_file(self):
        from components.install_utils import cai_modpack_tu_file
        path = self.ent_fp.get().strip()
        ten  = self.ent_fn.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Chú ý", "Chọn file hợp lệ!", parent=self); return
        if not ten:
            messagebox.showwarning("Chú ý", "Nhập tên!", parent=self); return
        if ten in config.current_config["danh_sach_instances"]:
            messagebox.showwarning("Chú ý", "Tên Instance đã tồn tại!", parent=self); return
        def _done_va_xoa():
            self._giam_tac_vu()
            self._done()
        def _huy_va_xoa():
            self._giam_tac_vu()
        def _modpack_progress(da_mod, tong_mod):
            if tong_mod:
                self.ghi_tien_do(int(da_mod / tong_mod * 100),
                                  f"{da_mod}/{tong_mod} mod")
        def _bat_dau():
            self._tang_tac_vu()
            try:
                cai_modpack_tu_file(path, ten, self.lbl_status, _done_va_xoa,
                                    cancel_event=self._cancel_event,
                                    progress_cb=_modpack_progress,
                                    callback_huy=_huy_va_xoa)
            except Exception:
                self._giam_tac_vu()
                raise
        self._chay_hoac_xep_hang(f"Modpack (từ file): {ten}", _bat_dau)