"""
mod_mc.py
---------
Cua so chinh Content Manager (ModMcWindow).
Cac chuc nang da duoc tach ra:
  - api_helpers.py   : goi API Modrinth / CurseForge
  - install_utils.py : tai file va cai dat mod / modpack / rsp / shader
  - widgets.py       : FilterBar, ContentTableWidget, make_install_panel
"""

import os
import shutil
import threading
import urllib.parse

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config
import theme
from icon_utils import gan_icon_app

# Import tu cac module da tach
from components.api_helpers import (
    CURSEFORGE_API_KEY,
    lay_modrinth_popular,
    tim_kiem_modrinth,
    lay_phien_ban_modrinth,
    lay_curseforge_popular,
    tim_kiem_curseforge,
    lay_phien_ban_curseforge,
)
from components.install_utils import (
    tai_file,
    cai_mod_tu_file,
    cai_rsp_shader_tu_file,
    cai_modpack_tu_file,
    dang_cai_modpack,
)
from components.widgets import (
    BG_DARK, BG_SEL, FG_TITLE,
    FilterBar,
    ContentTableWidget,
)


class TacVuBiHuy(Exception):
    """Duoc nem ra khi nguoi dung nhan nut 'Huy' trong khi dang tai/cai dat."""
    pass


# =====================================================================
# PAGINATION BAR (kieu Modrinth: < 1 2 ... N >)
# =====================================================================

class PaginationBar(tk.Frame):
    """
    Thanh chuyen trang dang: <  1  2  ...  N  >
    on_page(page) duoc goi voi page bat dau tu 1.
    """
    def __init__(self, parent, on_page, accent_color="#1E88E5", bg=None, **kw):
        bg = bg or (parent["bg"] if isinstance(parent, (tk.Frame, tk.Toplevel)) else "#f5f5f7")
        super().__init__(parent, bg=bg, **kw)
        self.on_page      = on_page
        self.accent_color = accent_color
        self.bg           = bg
        self.page         = 1
        self.total_pages  = 1

    def set_total(self, total_items, page_size, current_page=1):
        self.total_pages = max(1, (total_items + page_size - 1) // page_size) if page_size else 1
        self.page = max(1, min(current_page, self.total_pages))
        self._render()

    def _btn(self, text, cmd=None, active=False):
        if active:
            b = tk.Button(self, text=text, font=("Arial", 9, "bold"),
                           bg=self.accent_color, fg="white",
                           activebackground=self.accent_color, activeforeground="white",
                           relief="flat", width=3, state="disabled")
        elif cmd is None:
            b = tk.Label(self, text=text, font=("Arial", 9), bg=self.bg, fg="#888", width=3)
        else:
            b = tk.Button(self, text=text, font=("Arial", 9), bg="#e1e4ea", fg="#1a1a1a",
                           activebackground="#cfd3da", relief="flat", width=3, command=cmd)
        b.pack(side="left", padx=2)
        return b

    def _go(self, p):
        if 1 <= p <= self.total_pages and p != self.page:
            self.page = p
            self.on_page(p)
            self._render()

    def _render(self):
        for w in self.winfo_children():
            w.destroy()

        if self.total_pages <= 1:
            return

        self._btn("<", (lambda: self._go(self.page - 1)) if self.page > 1 else None)

        tp, cur = self.total_pages, self.page
        # Danh sach so trang can hien: 1, cur-1, cur, cur+1, tp (+ "...")
        pages = sorted(set([1, tp, cur]))
        last  = 0
        for p in pages:
            if p - last > 1:
                self._btn("...")
            self._btn(str(p), (lambda pp=p: self._go(pp)), active=(p == cur))
            last = p

        self._btn(">", (lambda: self._go(self.page + 1)) if self.page < tp else None)


# =====================================================================
# CUA SO CHINH
# =====================================================================

class ModMcWindow(tk.Toplevel):
    def __init__(self, parent, callback_lam_moi=None):
        super().__init__(parent)
        self.title("Content Manager")
        self.geometry("860x660")
        self.resizable(True, True)
        self.minsize(760, 500)
        # self.grab_set()  # Đã bỏ để main vẫn dùng được khi mở Modpack
        self.callback_lam_moi = callback_lam_moi
        gan_icon_app(self)

        # So tac vu tai/cai dat dang chay (mod, modpack, resource pack, shader, ...)
        # > 0 nghia la dang co tac vu chay nen -> khong cho dong cua so nay.
        self._so_tac_vu_dang_chay = 0
        # Co bao "huy" - khi nguoi dung nhan nut Huy, cac vong lap tai file se
        # kiem tra co nay va nem TacVuBiHuy de dung lai som.
        self._cancel_event = threading.Event()
        self.protocol("WM_DELETE_WINDOW", self._xu_ly_dong_cua_so)

        # Debounce ID cho o tim kiem chung
        self._debounce_search = None

        # Map tu vi tri hien thi (sau khi loc) -> vi tri thuc trong data goc
        self._modmr_ver_idx_map = []
        self._modcf_ver_idx_map = []

        self._build_ui()

    # ------------------------------------------------------------------
    # CHAN DONG CUA SO KHI DANG TAI / CAI DAT
    # ------------------------------------------------------------------

    def _tang_tac_vu(self):
        """Goi truoc khi bat dau mot tac vu tai/cai dat (mod, modpack, rsp, shader, ...)."""
        self._so_tac_vu_dang_chay += 1
        self._cancel_event.clear()
        self.after(0, lambda: self.btn_huy.config(state="normal"))

    def _giam_tac_vu(self):
        """Goi khi mot tac vu tai/cai dat ket thuc (thanh cong hoac loi)."""
        self._so_tac_vu_dang_chay = max(0, self._so_tac_vu_dang_chay - 1)
        if self._so_tac_vu_dang_chay == 0:
            self._cancel_event.clear()
            self.after(0, lambda: self.btn_huy.config(state="disabled"))

    def _huy_tac_vu(self):
        """Nguoi dung nhan nut 'Huy' - bao cho tac vu dang chay dung lai."""
        if self._so_tac_vu_dang_chay <= 0:
            return
        if messagebox.askyesno(
            "Hủy",
            "Bạn có chắc muốn hủy?",
            parent=self
        ):
            self._cancel_event.set()
            self.lbl_status.config(text="Đang hủy...", fg="#E53935")

    def _dang_co_tac_vu(self):
        dang_chay_local = self._so_tac_vu_dang_chay > 0
        try:
            dang_chay_global = dang_cai_modpack()
        except Exception:
            dang_chay_global = False
        return dang_chay_local or dang_chay_global

    def _xu_ly_dong_cua_so(self):
        """Chan nut X khi dang tai/cai Mod, Modpack, Resource Pack hoac Shader."""
        if self._dang_co_tac_vu():
            messagebox.showwarning(
                "Đang cài đặt",
                "Đang tải/cài đặt Mod, Modpack, Resource Pack hoặc Shader.\n"
                "Vui lòng đợi đến khi hoàn tất hoặc hủy để đóng cửa sổ này!",
                parent=self
            )
            return
        self.destroy()

    # ------------------------------------------------------------------
    # BUILD UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        tk.Label(self, text="Content Manager  —  Modpack / Mod / Resource Pack / Shader",
                 font=("Arial", 13, "bold"), fg="#1E88E5").pack(pady=(10, 4))

        style = ttk.Style(self)
        try:
            style.theme_use(style.theme_use())
        except Exception:
            pass
        style.configure("Modpack.Treeview",
                        background=BG_DARK, fieldbackground=BG_DARK,
                        foreground=FG_TITLE, rowheight=24, borderwidth=0)
        style.configure("Modpack.Treeview.Heading",
                        background="#e1e4ea", foreground="#1a1a1a",
                        font=("Arial", 9, "bold"))
        style.map("Modpack.Treeview",
                  background=[("selected", BG_SEL)],
                  foreground=[("selected", "#1a1a1a")])

        # --------------------------------------------------------------
        # O TIM KIEM CHUNG (dung cho ca Modpack / Mod / Resource Pack / Shader)
        # --------------------------------------------------------------
        search_bar = tk.Frame(self)
        search_bar.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(search_bar, text="Tìm kiếm:", font=("Arial", 10)).pack(side="left")
        self.ent_search = tk.Entry(search_bar, font=("Arial", 10), width=34)
        self.ent_search.pack(side="left", padx=6)
        self.ent_search.bind("<Return>", lambda e: self._search_current_tab())
        self.ent_search.bind("<KeyRelease>",
                              lambda e: self._debounce("_debounce_search", 400, self._search_current_tab))
        tk.Button(search_bar, text="Tim", font=("Arial", 9, "bold"),
                  bg="#1E88E5", fg="white", activebackground="#1E88E5", activeforeground="white",
                  width=6, command=self._search_current_tab).pack(side="left")
        tk.Button(search_bar, text="Top", font=("Arial", 9), bg="#607D8B", fg="white",
                  activebackground="#607D8B", activeforeground="white",
                  command=self._top_current_tab).pack(side="left", padx=4)
        #tk.Label(search_bar, text="(ap dung cho tat ca: Modpack / Mod / Resource Pack / Shader)",
                 #font=("Arial", 8, "italic"), fg="gray").pack(side="left", padx=8)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=4)

        BG = "#f5f5f7"

        # --- 3 tab cap 1: Modrinth / CurseForge / Cai tu File ---
        self.tab_modrinth   = tk.Frame(self.nb, bg=BG)
        self.tab_curseforge = tk.Frame(self.nb, bg=BG)
        self.tab_f          = tk.Frame(self.nb)

        self.nb.add(self.tab_modrinth,   text="  Modrinth  ")
        self.nb.add(self.tab_curseforge, text="  CurseForge  ")
        self.nb.add(self.tab_f,          text="  Cai tu File  ")

        # --- Sub-notebook trong tab Modrinth: Modpack / Mod / Resource Pack / Shader ---
        self.nb_mr = ttk.Notebook(self.tab_modrinth)
        self.nb_mr.pack(fill="both", expand=True)

        self.tab_mr    = tk.Frame(self.nb_mr, bg=BG)
        self.tab_modmr = tk.Frame(self.nb_mr, bg=BG)
        self.tab_rsp   = tk.Frame(self.nb_mr, bg=BG)
        self.tab_sh    = tk.Frame(self.nb_mr, bg=BG)

        self.nb_mr.add(self.tab_mr,    text="  Modpack  ")
        self.nb_mr.add(self.tab_modmr, text="  Mod  ")
        self.nb_mr.add(self.tab_rsp,   text="  Resource Pack  ")
        self.nb_mr.add(self.tab_sh,    text="  Shader  ")

        # --- Sub-notebook trong tab CurseForge: Modpack / Mod / Resource Pack / Shader ---
        self.nb_cf = ttk.Notebook(self.tab_curseforge)
        self.nb_cf.pack(fill="both", expand=True)

        self.tab_cf     = tk.Frame(self.nb_cf, bg=BG)
        self.tab_modcf  = tk.Frame(self.nb_cf, bg=BG)
        self.tab_rsp_cf = tk.Frame(self.nb_cf, bg=BG)
        self.tab_sh_cf  = tk.Frame(self.nb_cf, bg=BG)

        self.nb_cf.add(self.tab_cf,     text="  Modpack  ")
        self.nb_cf.add(self.tab_modcf,  text="  Mod  ")
        self.nb_cf.add(self.tab_rsp_cf, text="  Resource Pack  ")
        self.nb_cf.add(self.tab_sh_cf,  text="  Shader  ")

        self._build_modpack_modrinth()
        self._build_modpack_curseforge()
        self._build_mod_modrinth()
        self._build_mod_curseforge()
        self._build_rsp_tab()
        self._build_shader_tab()
        self._build_rsp_cf_tab()
        self._build_shader_cf_tab()
        self._build_file()

        status_bar = tk.Frame(self)
        status_bar.pack(fill="x", padx=14, pady=(2, 6))

        self.lbl_status = tk.Label(status_bar, text="Dang tai...",
                                   font=("Arial", 9, "italic"), fg="#1E88E5", anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)

        self.btn_huy = tk.Button(status_bar, text="Huy", font=("Arial", 9, "bold"),
                                  bg="#E53935", fg="white",
                                  activebackground="#E53935", activeforeground="white",
                                  width=8, state="disabled", command=self._huy_tac_vu)
        self.btn_huy.pack(side="right", padx=(8, 0))

        threading.Thread(target=self._load_mr_top,  daemon=True).start()
        threading.Thread(target=self._load_cf_top,  daemon=True).start()
        threading.Thread(target=self._load_rsp_top, daemon=True).start()
        threading.Thread(target=self._load_sh_top,  daemon=True).start()
        # Mod tabs: load lazy khi user click
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.nb_mr.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.nb_cf.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        theme.apply_theme(self)

    # ------------------------------------------------------------------
    # XAC DINH TAB CON (mr/cf/modmr/modcf/rsp/sh/file) DANG DUOC CHON
    # ------------------------------------------------------------------

    def _current_tab_key(self):
        outer = self.nb.index(self.nb.select())
        if outer == 0:      # Modrinth
            inner = self.nb_mr.index(self.nb_mr.select())
            return ["mr", "modmr", "rsp", "sh"][inner]
        elif outer == 1:    # CurseForge
            inner = self.nb_cf.index(self.nb_cf.select())
            return ["cf", "modcf", "rsp_cf", "sh_cf"][inner]
        return "file"

    def _on_tab_changed(self, e):
        key = self._current_tab_key()

        if key == "modmr" and not self._modmr_data:
            threading.Thread(target=self._load_modmr_top, daemon=True).start()
        elif key == "modcf" and not self._modcf_data:
            threading.Thread(target=self._load_modcf_top, daemon=True).start()
        elif key == "rsp_cf" and not self._rsp_cf_data:
            threading.Thread(target=self._load_rsp_cf_top, daemon=True).start()
        elif key == "sh_cf" and not self._sh_cf_data:
            threading.Thread(target=self._load_sh_cf_top, daemon=True).start()

        # Ap dung tu khoa cua o tim kiem chung cho tab vua chuyen toi
        kw = self.ent_search.get().strip()
        if kw and key != "file":
            last_kw_map = {
                "mr":     self._mr_last_kw,
                "cf":     self._cf_last_kw,
                "modmr":  self._modmr_last_kw,
                "modcf":  self._modcf_last_kw,
                "rsp":    self._rsp_last_kw,
                "sh":     self._sh_last_kw,
                "rsp_cf": self._rsp_cf_last_kw,
                "sh_cf":  self._sh_cf_last_kw,
            }
            last = last_kw_map.get(key)
            cur_kw = last[0] if last else None
            if cur_kw != kw:
                self._search_current_tab()

    # ------------------------------------------------------------------
    # O TIM KIEM CHUNG: dieu huong toi tab dang chon
    # ------------------------------------------------------------------

    def _search_current_tab(self, page=1):
        key = self._current_tab_key()
        fn = {
            "mr":     self._search_mr,
            "cf":     self._search_cf,
            "modmr":  self._search_modmr,
            "modcf":  self._search_modcf,
            "rsp":    self._search_rsp,
            "sh":     self._search_sh,
            "rsp_cf": self._search_rsp_cf,
            "sh_cf":  self._search_sh_cf,
        }.get(key)
        if fn:
            fn(page)

    def _top_current_tab(self):
        key = self._current_tab_key()
        fn = {
            "mr":     self._load_mr_top,
            "cf":     self._load_cf_top,
            "modmr":  self._load_modmr_top,
            "modcf":  self._load_modcf_top,
            "rsp":    self._load_rsp_top,
            "sh":     self._load_sh_top,
            "rsp_cf": self._load_rsp_cf_top,
            "sh_cf":  self._load_sh_cf_top,
        }.get(key)
        if fn:
            threading.Thread(target=fn, daemon=True).start()

    # ------------------------------------------------------------------
    # HELPER: debounced search
    # ------------------------------------------------------------------

    def _debounce(self, attr, ms, fn):
        old = getattr(self, attr, None)
        if old:
            try: self.after_cancel(old)
            except: pass
        setattr(self, attr, self.after(ms, fn))

    def _get_inst_mc_loader(self, ten_inst):
        """Tra ve (mc_version, loader) cua mot instance, vd ('1.21.1', 'Fabric')."""
        info = config.current_config.get("danh_sach_instances", {}).get(ten_inst, {})
        return info.get("version_goc", ""), info.get("loai_game", "")

    # ------------------------------------------------------------------
    # TAB: MODPACK MODRINTH
    # ------------------------------------------------------------------

    def _build_modpack_modrinth(self):
        f  = self.tab_mr
        BG = f["bg"]

        self.fb_mr = FilterBar(f, self._search_mr, accent_color="#1E88E5", show_category=True, bg=BG)
        self.fb_mr.pack(fill="x", padx=10, pady=(8, 4))
        self.list_mr = ContentTableWidget(f, "modrinth", self._select_mr)
        self.list_mr.pack(fill="both", expand=True, padx=10)

        self.pg_mr = PaginationBar(f, self._goto_mr_page, accent_color="#1E88E5", bg=BG)
        self.pg_mr.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phiên bản:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_mr_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_mr_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Tên Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        self.ent_mr_name = tk.Entry(bp, font=("Arial", 9), width=44)
        self.ent_mr_name.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cài Modpack", font=("Arial", 9, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white",
                  width=14, pady=4, command=self._install_mr).grid(row=0, column=2, rowspan=2, padx=8)

        self._mr_data     = []
        self._mr_vers_raw = []
        self._mr_page     = 1
        self._mr_total    = 0
        self._mr_last_kw  = ("", "", "", "")  # (kw, mc, ld, cat); ("","","","") => top

    def _load_mr_top(self, page=1):
        self._mr_page    = page
        self._mr_last_kw = None  # None => top
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
        self.lbl_status.config(text="Đang tìm...", fg="#1E88E5")
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
        if idx >= len(self._mr_data): return
        r   = self._mr_data[idx]
        ten = r.get("title", "")
        self.ent_mr_name.delete(0, "end")
        self.ent_mr_name.insert(0, ten.replace(" ", "_")[:30])
        self.cbo_mr_ver.set("Đang tải phiên bản...")
        pid = r.get("project_id", "")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._mr_vers_raw = vs
                ds = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]
                self.after(0, lambda: (
                    self.cbo_mr_ver.config(values=ds),
                    self.cbo_mr_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chọn phiên bản rồi nhấn cài Modpack.", fg="gray"),
                ))
                if install: self.after(200, self._install_mr)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_mr(self):
        ten = self.ent_mr_name.get().strip()
        if not ten:
            messagebox.showwarning("Chú ý", "Nhập tên Instance!", parent=self); return
        if ten in config.current_config["danh_sach_instances"]:
            messagebox.showwarning("Chú ý", "Tên đã tồn tại!", parent=self); return
        iv = self.cbo_mr_ver.current()
        if iv < 0 or not self._mr_vers_raw:
            messagebox.showwarning("Chú ý", "Chọn phiên bản!", parent=self); return
        vd    = self._mr_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Lỗi", "Không tìm thấy file tải!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "modpack.mrpack")
        self.lbl_status.config(text="Dang tai...", fg="#1E88E5")

        self._tang_tac_vu()
        def _t():
            _tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
            try:
                os.makedirs(_tmp, exist_ok=True)
                pz  = os.path.join(_tmp, fname)
                def prog(da, tong):
                    if self._cancel_event.is_set():
                        raise TacVuBiHuy("Đã hủy tải modpack")
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Đang tải: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#1E88E5"))
                tai_file(url, pz, prog)
                if self._cancel_event.is_set():
                    raise TacVuBiHuy("Đã hủy cài modpack")
                def _done_va_xoa():
                    try: shutil.rmtree(_tmp)
                    except: pass
                    self._giam_tac_vu()   # ← chuyển vào đây
                    self._done()
                cai_modpack_tu_file(pz, ten, self.lbl_status, _done_va_xoa, cancel_event=self._cancel_event)
                # KHÔNG finally ở đây — _giam_tac_vu đã nằm trong callback
            except TacVuBiHuy:
                try: shutil.rmtree(_tmp)
                except: pass
                self._giam_tac_vu()   # ← hủy sớm thì giảm ở đây
                self.after(0, lambda: self.lbl_status.config(text="Da huy cai dat Modpack.", fg="#E53935"))
            except Exception as e:
                self._giam_tac_vu()   # ← lỗi thì giảm ở đây
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # TAB: MODPACK CURSEFORGE
    # ------------------------------------------------------------------

    def _build_modpack_curseforge(self):
        f  = self.tab_cf
        BG = f["bg"]

        self.fb_cf = FilterBar(f, self._search_cf, accent_color="#E64A19", show_category=True, bg=BG)
        self.fb_cf.pack(fill="x", padx=10, pady=(8, 4))
        self.list_cf = ContentTableWidget(f, "curseforge", self._select_cf)
        self.list_cf.pack(fill="both", expand=True, padx=10)

        self.pg_cf = PaginationBar(f, self._goto_cf_page, accent_color="#E64A19", bg=BG)
        self.pg_cf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phiên bản:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Tên Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        self.ent_cf_name = tk.Entry(bp, font=("Arial", 9), width=44)
        self.ent_cf_name.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cài Modpack", font=("Arial", 9, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white",
                  width=14, pady=4, command=self._install_cf).grid(row=0, column=2, rowspan=2, padx=8)

        self._cf_data  = []
        self._cf_files = []
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
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Lỗi CF: {e}", fg="red"))

    def _search_cf(self, page=1):
        kw         = self.ent_search.get().strip()
        mc, ld, _c = self.fb_cf.get()
        self._cf_page    = page
        self._cf_last_kw = (kw, mc, ld)
        self.lbl_status.config(text="Dang tim CF...", fg="#E64A19")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, ld, limit=50, class_id=4471, offset=(page - 1) * 50)
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
        if idx >= len(self._cf_data): return
        r   = self._cf_data[idx]
        ten = r.get("name", "")
        mid = r.get("id", "")
        self.ent_cf_name.delete(0, "end")
        self.ent_cf_name.insert(0, ten.replace(" ", "_")[:30])
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
                if install: self.after(200, self._install_cf)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF ver: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_cf(self):
        ten = self.ent_cf_name.get().strip()
        if not ten:
            messagebox.showwarning("Chu y", "Nhap ten Instance!", parent=self); return
        if ten in config.current_config["danh_sach_instances"]:
            messagebox.showwarning("Chu y", "Ten da ton tai!", parent=self); return
        iv = self.cbo_cf_ver.current()
        if iv < 0 or not self._cf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        fd  = self._cf_files[iv]
        url = fd.get("downloadUrl", "")
        if not url:
            fid = fd.get("id", 0)
            fn  = fd.get("fileName", "")
            if fid and fn:
                ids = str(fid)
                url = f"https://mediafilez.forgecdn.net/files/{ids[:4]}/{ids[4:].lstrip('0') or '0'}/{urllib.parse.quote(fn)}"
            else:
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: MOD MODRINTH
    # ------------------------------------------------------------------

    def _build_mod_modrinth(self):
        self._modmr_data     = []
        self._modmr_vers_raw = []
        self._modmr_page     = 1
        self._modmr_total    = 0
        self._modmr_last_kw  = None
        f  = self.tab_modmr
        BG = f["bg"]

        self.fb_modmr = FilterBar(f, self._search_modmr, accent_color="#00897B", bg=BG)
        self.fb_modmr.pack(fill="x", padx=10, pady=(8, 4))
        self.list_modmr = ContentTableWidget(f, "modrinth", self._select_modmr)
        self.list_modmr.pack(fill="both", expand=True, padx=10)

        self.pg_modmr = PaginationBar(f, self._goto_modmr_page, accent_color="#00897B", bg=BG)
        self.pg_modmr.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
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
        if idx >= len(self._modmr_data): return
        r   = self._modmr_data[idx]
        pid = r.get("project_id", "")
        self.cbo_modmr_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._modmr_vers_raw = vs
                self.after(0, lambda: (
                    self._filter_modmr_ver(),
                ))
                if install: self.after(200, self._install_modmr)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_modmr_ver(self):
        """Loc combobox phien ban mod theo MC version / loader cua Instance dang chon."""
        vs = self._modmr_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}  [{', '.join(v.get('loaders',[]))}]"
                  for v in vs]

        ten_inst = self.cbo_modmr_inst.get().strip()
        mcv, loader = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        if mcv:
            idxs = [
                i for i, v in enumerate(vs)
                if mcv in v.get("game_versions", [])
                and (
                    not loader or loader == "Vanilla"
                    or loader.lower() in [l.lower() for l in v.get("loaders", [])]
                )
            ]
        else:
            idxs = list(range(len(vs)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._modmr_ver_idx_map = idxs
            self.cbo_modmr_ver.config(values=ds)
            self.cbo_modmr_ver.set(ds[0])
            if mcv:
                self.lbl_status.config(
                    text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}"
                         + (f", {loader}" if loader and loader != "Vanilla" else "") + ").",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chon phien ban roi nhan Cai Mod.", fg="gray")
        else:
            self._modmr_ver_idx_map = list(range(len(vs)))
            self.cbo_modmr_ver.config(values=ds_all)
            if ds_all:
                self.cbo_modmr_ver.set(ds_all[0])
            else:
                self.cbo_modmr_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}"
                         + (f", {loader}" if loader and loader != "Vanilla" else "")
                         + "). Hien thi tat ca - kiem tra ky truoc khi cai.",
                    fg="#E64A19")

    def _install_modmr(self):
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: MOD CURSEFORGE
    # ------------------------------------------------------------------

    def _build_mod_curseforge(self):
        self._modcf_data  = []
        self._modcf_files = []
        self._modcf_page    = 1
        self._modcf_total   = 0
        self._modcf_last_kw = None
        f  = self.tab_modcf
        BG = f["bg"]

        self.fb_modcf = FilterBar(f, self._search_modcf, accent_color="#F9A825", bg=BG)
        self.fb_modcf.pack(fill="x", padx=10, pady=(8, 4))
        self.list_modcf = ContentTableWidget(f, "curseforge", self._select_modcf)
        self.list_modcf.pack(fill="both", expand=True, padx=10)

        self.pg_modcf = PaginationBar(f, self._goto_modcf_page, accent_color="#F9A825", bg=BG)
        self.pg_modcf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
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
        kw         = self.ent_search.get().strip()
        mc, ld, _c = self.fb_modcf.get()
        self._modcf_page    = page
        self._modcf_last_kw = (kw, mc, ld)
        self.lbl_status.config(text="Dang tim Mod CurseForge...", fg="#F9A825")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, ld, limit=50, class_id=6, offset=(page - 1) * 50)
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
        if idx >= len(self._modcf_data): return
        r   = self._modcf_data[idx]
        mid = r.get("id", "")
        self.cbo_modcf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Dang tai phien ban mod...", fg="#F9A825")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._modcf_files = files
                self.after(0, lambda: (
                    self._filter_modcf_ver(),
                ))
                if install: self.after(200, self._install_modcf)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF ver: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_modcf_ver(self):
        """Loc combobox phien ban mod (CurseForge) theo MC version / loader cua Instance dang chon."""
        files = self._modcf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst = self.cbo_modcf_inst.get().strip()
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
            if mcv:
                self.lbl_status.config(
                    text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}"
                         + (f", {loader}" if loader and loader != "Vanilla" else "") + ").",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chon phien ban roi nhan Cai Mod.", fg="gray")
        else:
            self._modcf_ver_idx_map = list(range(len(files)))
            self.cbo_modcf_ver.config(values=ds_all)
            if ds_all:
                self.cbo_modcf_ver.set(ds_all[0])
            else:
                self.cbo_modcf_ver.set("")
            if mcv:
                self.lbl_status.config(
                    text=f"Khong co phien ban khop voi {ten_inst} (MC {mcv}"
                         + (f", {loader}" if loader and loader != "Vanilla" else "")
                         + "). Hien thi tat ca - kiem tra ky truoc khi cai.",
                    fg="#E64A19")

    def _install_modcf(self):
        ten_inst = self.cbo_modcf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_modcf_ver.current()
        if iv < 0 or not self._modcf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._modcf_ver_idx_map):
            iv = self._modcf_ver_idx_map[iv]
        fd  = self._modcf_files[iv]
        url = fd.get("downloadUrl", "")
        if not url:
            fid = fd.get("id", 0)
            fn  = fd.get("fileName", "")
            if fid and fn:
                ids = str(fid)
                url = f"https://mediafilez.forgecdn.net/files/{ids[:4]}/{ids[4:].lstrip('0') or '0'}/{urllib.parse.quote(fn)}"
            else:
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: RESOURCE PACK
    # ------------------------------------------------------------------

    def _build_rsp_tab(self):
        self._rsp_data     = []
        self._rsp_vers_raw = []
        self._rsp_ver_idx_map = []
        self._rsp_page     = 1
        self._rsp_total    = 0
        self._rsp_last_kw  = None
        f  = self.tab_rsp
        BG = f["bg"]

        self.fb_rsp = FilterBar(f, self._search_rsp, accent_color="#8E24AA", show_loader=False, bg=BG)
        self.fb_rsp.pack(fill="x", padx=10, pady=(8, 4))
        self.list_rsp = ContentTableWidget(f, "modrinth", self._select_rsp)
        self.list_rsp.pack(fill="both", expand=True, padx=10)

        self.pg_rsp = PaginationBar(f, self._goto_rsp_page, accent_color="#8E24AA", bg=BG)
        self.pg_rsp.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
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
        if idx >= len(self._rsp_data): return
        r   = self._rsp_data[idx]
        pid = r.get("project_id", "")
        self.cbo_rsp_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._rsp_vers_raw = vs
                self.after(0, lambda: self._filter_rsp_ver())
                if install: self.after(200, self._install_rsp)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_rsp_ver(self):
        """Loc combobox phien ban RSP theo MC version cua Instance dang chon. Neu chon instance thi khoa cbo MC version."""
        vs = self._rsp_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]

        ten_inst = self.cbo_rsp_inst.get().strip()
        mcv, _ = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        # Khi da chon instance, khoa combobox phien ban MC o FilterBar
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

        if mcv:
            idxs = [i for i, v in enumerate(vs) if mcv in v.get("game_versions", [])]
        else:
            idxs = list(range(len(vs)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._rsp_ver_idx_map = idxs
            self.cbo_rsp_ver.config(values=ds)
            self.cbo_rsp_ver.set(ds[0])
            if mcv:
                self.lbl_status.config(
                    text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}).",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chon phien ban roi nhan Cai RSP.", fg="gray")
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: SHADERS
    # ------------------------------------------------------------------

    def _build_shader_tab(self):
        self._sh_data     = []
        self._sh_vers_raw = []
        self._sh_ver_idx_map = []
        self._sh_page     = 1
        self._sh_total    = 0
        self._sh_last_kw  = None
        f  = self.tab_sh
        BG = f["bg"]

        self.fb_sh = FilterBar(f, self._search_sh, accent_color="#F57C00", show_loader=False, bg=BG)
        self.fb_sh.pack(fill="x", padx=10, pady=(8, 4))
        self.list_sh = ContentTableWidget(f, "modrinth", self._select_sh)
        self.list_sh.pack(fill="both", expand=True, padx=10)

        self.pg_sh = PaginationBar(f, self._goto_sh_page, accent_color="#F57C00", bg=BG)
        self.pg_sh.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
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
        if idx >= len(self._sh_data): return
        r   = self._sh_data[idx]
        pid = r.get("project_id", "")
        self.cbo_sh_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._sh_vers_raw = vs
                self.after(0, lambda: self._filter_sh_ver())
                if install: self.after(200, self._install_sh)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_sh_ver(self):
        """Loc combobox phien ban Shader theo MC version cua Instance dang chon. Neu chon instance thi khoa cbo MC version."""
        vs = self._sh_vers_raw
        ds_all = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]

        ten_inst = self.cbo_sh_inst.get().strip()
        mcv, _ = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

        # Khi da chon instance, khoa combobox phien ban MC o FilterBar
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

        if mcv:
            idxs = [i for i, v in enumerate(vs) if mcv in v.get("game_versions", [])]
        else:
            idxs = list(range(len(vs)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._sh_ver_idx_map = idxs
            self.cbo_sh_ver.config(values=ds)
            self.cbo_sh_ver.set(ds[0])
            if mcv:
                self.lbl_status.config(
                    text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}).",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chon phien ban roi nhan Cai Shader.", fg="gray")
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: RESOURCE PACK (CURSEFORGE)
    # ------------------------------------------------------------------

    def _build_rsp_cf_tab(self):
        self._rsp_cf_data     = []
        self._rsp_cf_files    = []
        self._rsp_cf_ver_idx_map = []
        self._rsp_cf_page     = 1
        self._rsp_cf_total    = 0
        self._rsp_cf_last_kw  = None
        f  = self.tab_rsp_cf
        BG = f["bg"]

        self.fb_rsp_cf = FilterBar(f, self._search_rsp_cf, accent_color="#AB47BC", show_loader=False, bg=BG)
        self.fb_rsp_cf.pack(fill="x", padx=10, pady=(8, 4))
        self.list_rsp_cf = ContentTableWidget(f, "curseforge", self._select_rsp_cf)
        self.list_rsp_cf.pack(fill="both", expand=True, padx=10)

        self.pg_rsp_cf = PaginationBar(f, self._goto_rsp_cf_page, accent_color="#AB47BC", bg=BG)
        self.pg_rsp_cf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
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
        kw        = self.ent_search.get().strip()
        mc, _, _c = self.fb_rsp_cf.get()
        self._rsp_cf_page    = page
        self._rsp_cf_last_kw = (kw, mc)
        self.lbl_status.config(text="Dang tim RSP CurseForge...", fg="#AB47BC")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, "", limit=50, class_id=12, offset=(page - 1) * 50)
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
        if idx >= len(self._rsp_cf_data): return
        r   = self._rsp_cf_data[idx]
        mid = r.get("id", "")
        self.cbo_rsp_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Dang tai phien ban RSP...", fg="#AB47BC")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._rsp_cf_files = files
                self.after(0, lambda: self._filter_rsp_cf_ver())
                if install: self.after(200, self._install_rsp_cf)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_rsp_cf_ver(self):
        """Loc combobox phien ban RSP (CurseForge) theo MC version cua Instance dang chon. Neu chon instance thi khoa cbo MC version."""
        files = self._rsp_cf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst = self.cbo_rsp_cf_inst.get().strip()
        mcv, _ = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

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

        if mcv:
            idxs = [i for i, fi in enumerate(files) if mcv in fi.get("gameVersions", [])]
        else:
            idxs = list(range(len(files)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._rsp_cf_ver_idx_map = idxs
            self.cbo_rsp_cf_ver.config(values=ds)
            self.cbo_rsp_cf_ver.set(ds[0])
            if mcv:
                self.lbl_status.config(
                    text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}).",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chon phien ban roi nhan Cai RSP.", fg="gray")
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
        ten_inst = self.cbo_rsp_cf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_rsp_cf_ver.current()
        if iv < 0 or not self._rsp_cf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._rsp_cf_ver_idx_map):
            iv = self._rsp_cf_ver_idx_map[iv]
        fd  = self._rsp_cf_files[iv]
        url = fd.get("downloadUrl", "")
        if not url:
            fid = fd.get("id", 0)
            fn  = fd.get("fileName", "")
            if fid and fn:
                ids = str(fid)
                url = f"https://mediafilez.forgecdn.net/files/{ids[:4]}/{ids[4:].lstrip('0') or '0'}/{urllib.parse.quote(fn)}"
            else:
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: SHADER (CURSEFORGE)
    # ------------------------------------------------------------------

    def _build_shader_cf_tab(self):
        self._sh_cf_data     = []
        self._sh_cf_files    = []
        self._sh_cf_ver_idx_map = []
        self._sh_cf_page     = 1
        self._sh_cf_total    = 0
        self._sh_cf_last_kw  = None
        f  = self.tab_sh_cf
        BG = f["bg"]

        self.fb_sh_cf = FilterBar(f, self._search_sh_cf, accent_color="#FB8C00", show_loader=False, bg=BG)
        self.fb_sh_cf.pack(fill="x", padx=10, pady=(8, 4))
        self.list_sh_cf = ContentTableWidget(f, "curseforge", self._select_sh_cf)
        self.list_sh_cf.pack(fill="both", expand=True, padx=10)

        self.pg_sh_cf = PaginationBar(f, self._goto_sh_cf_page, accent_color="#FB8C00", bg=BG)
        self.pg_sh_cf.pack(fill="x", padx=10, pady=(2, 0))

        bp = tk.Frame(f, bg=BG)
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
        kw        = self.ent_search.get().strip()
        mc, _, _c = self.fb_sh_cf.get()
        self._sh_cf_page    = page
        self._sh_cf_last_kw = (kw, mc)
        self.lbl_status.config(text="Dang tim Shader CurseForge...", fg="#FB8C00")
        def _t():
            try:
                r, total = tim_kiem_curseforge(kw, mc, "", limit=50, class_id=6552, offset=(page - 1) * 50)
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
        if idx >= len(self._sh_cf_data): return
        r   = self._sh_cf_data[idx]
        mid = r.get("id", "")
        self.cbo_sh_cf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text="Dang tai phien ban Shader...", fg="#FB8C00")
        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._sh_cf_files = files
                self.after(0, lambda: self._filter_sh_cf_ver())
                if install: self.after(200, self._install_sh_cf)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _filter_sh_cf_ver(self):
        """Loc combobox phien ban Shader (CurseForge) theo MC version cua Instance dang chon. Neu chon instance thi khoa cbo MC version."""
        files = self._sh_cf_files
        ds_all = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                  for fi in files]

        ten_inst = self.cbo_sh_cf_inst.get().strip()
        mcv, _ = self._get_inst_mc_loader(ten_inst) if ten_inst else ("", "")

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

        if mcv:
            idxs = [i for i, fi in enumerate(files) if mcv in fi.get("gameVersions", [])]
        else:
            idxs = list(range(len(files)))

        if idxs:
            ds = [ds_all[i] for i in idxs]
            self._sh_cf_ver_idx_map = idxs
            self.cbo_sh_cf_ver.config(values=ds)
            self.cbo_sh_cf_ver.set(ds[0])
            if mcv:
                self.lbl_status.config(
                    text=f"Da loc {len(ds)} phien ban phu hop voi {ten_inst} (MC {mcv}).",
                    fg="gray")
            else:
                self.lbl_status.config(text="Chon phien ban roi nhan Cai Shader.", fg="gray")
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
        ten_inst = self.cbo_sh_cf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_sh_cf_ver.current()
        if iv < 0 or not self._sh_cf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        if iv < len(self._sh_cf_ver_idx_map):
            iv = self._sh_cf_ver_idx_map[iv]
        fd  = self._sh_cf_files[iv]
        url = fd.get("downloadUrl", "")
        if not url:
            fid = fd.get("id", 0)
            fn  = fd.get("fileName", "")
            if fid and fn:
                ids = str(fid)
                url = f"https://mediafilez.forgecdn.net/files/{ids[:4]}/{ids[4:].lstrip('0') or '0'}/{urllib.parse.quote(fn)}"
            else:
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
                pz  = os.path.join(tmp, fname)
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

    # ------------------------------------------------------------------
    # TAB: CAI TU FILE
    # ------------------------------------------------------------------

    def _build_file(self):
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
        path = self.ent_fp.get().strip()
        ten  = self.ent_fn.get().strip()
        loai = self.cbo_file_type.get()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Chu y", "Chon file hop le!", parent=self); return
        if not ten:
            messagebox.showwarning("Chu y", "Nhap ten!", parent=self); return

        if loai == "Modpack":
            if ten in config.current_config["danh_sach_instances"]:
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

    # ------------------------------------------------------------------
    # CALLBACK CHUNG
    # ------------------------------------------------------------------

    def _done(self):
        if self.callback_lam_moi:
            self.callback_lam_moi()
        messagebox.showinfo("Thanh cong",
            "Da cai dat thanh cong!\nInstance moi da xuat hien trong danh sach.", parent=self)