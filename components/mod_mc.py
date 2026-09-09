import threading
import tkinter as tk
from tkinter import ttk, messagebox
import config
import theme
from icon_utils import gan_icon_app
from components import perf
from components.widgets import BG_DARK, BG_SEL, FG_TITLE, ContentTableWidget
def _tim_content_table(widget):
    if isinstance(widget, ContentTableWidget):
        return widget
    for child in widget.winfo_children():
        found = _tim_content_table(child)
        if found is not None:
            return found
    return None
from components.mod_detail_window import ModDetailWindow
from components.Mod.modrinthmod import ModrinthModMixin
from components.Mod.forgemod import ForgeModMixin
from components.install_utils import dang_cai_modpack
class TacVuBiHuy(Exception):
    pass
_SEARCH_IGNORE_KEYSYMS = {
    "Caps_Lock", "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L", "Meta_R",
    "Tab", "Escape", "Num_Lock", "Scroll_Lock", "Insert",
    "Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
    "F10", "F11", "F12",
}
class PaginationBar(tk.Frame):
    def __init__(self, parent, on_page, accent_color="#00ACC1", bg=None, **kw):
        bg = bg or (parent["bg"] if isinstance(parent, (tk.Frame, tk.Toplevel)) else "#f5f5f7")
        super().__init__(parent, bg=bg, **kw)
        self.on_page      = on_page
        self.accent_color = accent_color
        self.bg           = bg
        self.page         = 1
        self.total_pages  = 1
        self._c           = theme.colors()
    def set_total(self, total_items, page_size, current_page=1):
        self.total_pages = max(1, (total_items + page_size - 1) // page_size) if page_size else 1
        self.page = max(1, min(current_page, self.total_pages))
        self._render()
    def _btn(self, text, cmd=None, active=False):
        parent = getattr(self, "_inner", None) or self
        c = self._c
        if active:
            b = tk.Button(parent, text=text, font=("Arial", 9, "bold"),
                          bg=self.accent_color, fg="white",
                          activebackground=self.accent_color, activeforeground="white",
                          relief="flat", width=4, state="disabled")
        elif cmd is None:
            b = tk.Label(parent, text=text, font=("Arial", 9), bg=self.bg,
                         fg=c["fg_author"], width=4)
        else:
            b = tk.Button(parent, text=text, font=("Arial", 9),
                          bg=c["icon_bg"], fg=c["fg_title"],
                          activebackground=c["icon_border"], activeforeground=c["fg_title"],
                          relief="flat", width=4, command=cmd)
        b.pack(side="left", padx=4)
        return b
    def _go(self, p):
        if 1 <= p <= self.total_pages and p != self.page:
            self.page = p
            self.on_page(p)
            self._render()
    def _render(self):
        for w in self.winfo_children():
            w.destroy()
        self._c = theme.colors()
        self.bg = self._c["bg_alt"]
        try:
            self.configure(bg=self.bg)
        except tk.TclError:
            pass
        if self.total_pages <= 1:
            return
        inner = tk.Frame(self, bg=self.bg)
        inner.pack(anchor="center")
        self._inner = inner
        self._btn("<", (lambda: self._go(self.page - 1)) if self.page > 1 else None)
        tp, cur = self.total_pages, self.page
        WINDOW = 2
        pages = {1, tp, cur}
        for d in range(-WINDOW, WINDOW + 1):
            p = cur + d
            if 1 <= p <= tp:
                pages.add(p)
        pages = sorted(pages)
        last = 0
        for p in pages:
            if p - last > 1:
                self._btn("...")
            self._btn(str(p), (lambda pp=p: self._go(pp)), active=(p == cur))
            last = p
        self._btn(">", (lambda: self._go(self.page + 1)) if self.page < tp else None)
class ModMcFrame(ModrinthModMixin, ForgeModMixin, tk.Frame):
    def __init__(self, parent, callback_lam_moi=None, modal=None):
        super().__init__(parent)
        self.callback_lam_moi = callback_lam_moi
        self.modal = modal
        self._so_tac_vu_dang_chay = 0
        self._cancel_event        = threading.Event()
        self._hang_doi_cai = []
        self._tac_vu_hien_tai_id = None
        self._last_progress_pct   = None
        self._last_progress_label = ""
        self._debounce_search     = None
        self._modmr_ver_idx_map  = []
        self._modcf_ver_idx_map  = []
        self._rsp_ver_idx_map    = []
        self._sh_ver_idx_map     = []
        self._rsp_cf_ver_idx_map = []
        self._sh_cf_ver_idx_map  = []
        self._build_ui()
    def can_switch(self) -> bool:
        return True
    def _tang_tac_vu(self):
        self._so_tac_vu_dang_chay += 1
        self._cancel_event.clear()
    def _giam_tac_vu(self):
        self._so_tac_vu_dang_chay = max(0, self._so_tac_vu_dang_chay - 1)
        if self._so_tac_vu_dang_chay == 0:
            self._cancel_event.clear()
            self._last_progress_pct = None
            self._last_progress_label = ""
            self._tac_vu_hien_tai_id = None
            self.after(0, self._thu_chay_hang_doi_tiep)
    def _chay_hoac_xep_hang(self, mo_ta, ham_bat_dau, item_id=None):
        if self._dang_co_tac_vu():
            self._hang_doi_cai.append((mo_ta, ham_bat_dau, item_id))
            vi_tri = len(self._hang_doi_cai)
            self.lbl_status.config(
                text=f"⏳ Đã thêm vào hàng đợi (vị trí {vi_tri}): {mo_ta} "
                     "— đang có tác vụ khác chạy, sẽ tự động cài khi đến lượt.",
                fg="#f57c00")
            return
        self._tac_vu_hien_tai_id = item_id
        ham_bat_dau()
    def _thu_chay_hang_doi_tiep(self):
        if self._so_tac_vu_dang_chay > 0:
            return
        try:
            dang_chay_global = dang_cai_modpack()
        except Exception:
            dang_chay_global = False
        if dang_chay_global:
            return
        if not self._hang_doi_cai:
            return
        mo_ta, ham_bat_dau, item_id = self._hang_doi_cai.pop(0)
        con_lai = len(self._hang_doi_cai)
        self._tac_vu_hien_tai_id = item_id
        try:
            self.lbl_status.config(
                text=f"▶ Đang bắt đầu (hàng đợi): {mo_ta}"
                     + (f" — còn {con_lai} việc chờ." if con_lai else ""),
                fg="#00ACC1")
        except Exception:
            pass
        ham_bat_dau()
    def _huy_khoi_hang_doi(self, item_id):
        if item_id is None:
            return False
        truoc = len(self._hang_doi_cai)
        self._hang_doi_cai = [e for e in self._hang_doi_cai if e[2] != item_id]
        return len(self._hang_doi_cai) < truoc
    def ghi_tien_do(self, pct, label=""):
        self._last_progress_pct = max(0, min(100, int(pct)))
        self._last_progress_label = label
    def _huy_tac_vu(self):
        if self._so_tac_vu_dang_chay <= 0:
            return
        if messagebox.askyesno("Hủy", "Bạn có chắc muốn hủy?", parent=self):
            self._huy_tac_vu_khong_hoi()
    def _huy_tac_vu_khong_hoi(self):
        if self._so_tac_vu_dang_chay <= 0:
            return
        self._cancel_event.set()
        self.lbl_status.config(text="Đang hủy...", fg="#E53935")
    def _dang_co_tac_vu(self):
        dang_chay_local = self._so_tac_vu_dang_chay > 0
        try:
            dang_chay_global = dang_cai_modpack()
        except Exception:
            dang_chay_global = False
        return dang_chay_local or dang_chay_global
    def _swap_to_detail(self, lv_frame, dv_frame, source, data, versions,
                        install_cb, accent, installed_info=None, instance_ctl=None,
                        loai=None):
        def _back():
            self._swap_to_list(lv_frame, dv_frame)
        for w in dv_frame.winfo_children():
            w.destroy()
        panel = ModDetailWindow(dv_frame, source, data, versions,
                                install_cb=install_cb, on_back=_back,
                                cancel_cb=self._huy_tac_vu, accent=accent,
                                installed_info=installed_info,
                                instance_ctl=instance_ctl,
                                loai=loai)
        panel.pack(fill="both", expand=True)
        lv_frame.pack_forget()
        dv_frame.pack(fill="both", expand=True)
    def _swap_to_list(self, lv_frame, dv_frame):
        dv_frame.pack_forget()
        for w in dv_frame.winfo_children():
            w.destroy()
        lv_frame.pack(fill="both", expand=True)
        table = _tim_content_table(lv_frame)
        if table is not None:
            table.sync_installing_state()
    def _on_search_key(self, e):
        if e.keysym in _SEARCH_IGNORE_KEYSYMS:
            return
        self._debounce("_debounce_search", 400, self._search_current_tab)
    def _debounce(self, attr, ms, fn):
        old = getattr(self, attr, None)
        if old:
            try: self.after_cancel(old)
            except: pass
        setattr(self, attr, self.after(ms, fn))
    def _get_inst_mc_loader(self, ten_inst):
        info = config.current_config.get("danh_sach_instances", {}).get(ten_inst, {})
        return info.get("version_goc", ""), info.get("loai_game", "")
    def _apply_inst_filter_to_fb(self, ten_inst, fb):
        if not ten_inst or fb is None:
            return False
        mcv, loader = self._get_inst_mc_loader(ten_inst)
        changed = False
        try:
            if mcv:
                mc_vals = list(fb.cbo_mc.cget("values"))
                if mcv in mc_vals and fb.cbo_mc.get() != mcv:
                    fb.cbo_mc.set(mcv)
                    changed = True
            cbo_ld = getattr(fb, "cbo_loader", None)
            if loader and cbo_ld is not None:
                ld_vals = list(cbo_ld.cget("values"))
                match = next((v for v in ld_vals if v.lower() == loader.lower()), None)
                if match and cbo_ld.get() != match:
                    cbo_ld.set(match)
                    changed = True
        except Exception:
            pass
        return changed
    def refresh_all_installed_states(self):
        for ten_attr in ("list_mr", "list_cf", "list_modmr", "list_modcf",
                          "list_rsp", "list_rsp_cf", "list_sh", "list_sh_cf"):
            w = getattr(self, ten_attr, None)
            if w is not None:
                try:
                    w.refresh_installed_states()
                except Exception:
                    pass
    def _thong_bao_thanh_cong(self, message):
        if self.modal is not None:
            self.modal.toast(message, loai="ok")
            return
        messagebox.showinfo("Thành công", message, parent=self)
    def _done(self):
        if self.callback_lam_moi:
            self.callback_lam_moi()
        self.refresh_all_installed_states()
        self._thong_bao_thanh_cong(
            "Đã cài đặt thành công!\nInstance mới đã xuất hiện trong danh sách.")
    def _thong_bao_cai_xong(self, loai, ten, ten_inst):
        self.refresh_all_installed_states()
        self._thong_bao_thanh_cong(
            f"Đã cài đặt {loai} '{ten}' vào Instance '{ten_inst}' thành công!")
    def _build_ui(self):
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
        search_bar = tk.Frame(self)
        search_bar.pack(fill="x", padx=14, pady=(0, 4))
        search_bar_inner = tk.Frame(search_bar)
        search_bar_inner.pack(anchor="center")
        tk.Label(search_bar_inner, text="Tìm kiếm:", font=("Arial", 10)).pack(side="left")
        self.ent_search = tk.Entry(search_bar_inner, font=("Arial", 10), width=60)
        self.ent_search.pack(side="left", padx=6)
        self.ent_search.bind("<Return>", lambda e: self._search_current_tab())
        self.ent_search.bind("<KeyRelease>", self._on_search_key)
        tk.Button(search_bar_inner, text="Tìm", font=("Arial", 9, "bold"),
                  bg="#1E88E5", fg="white", activebackground="#1E88E5", activeforeground="white",
                  width=6, command=self._search_current_tab).pack(side="left")
        status_bar = tk.Frame(self)
        self.lbl_status = tk.Label(status_bar, text="",
                                   font=("Arial", 9, "italic"), fg="#1E88E5", anchor="w")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=4)
        BG = "#f5f5f7"
        self.tab_modrinth   = tk.Frame(self.nb, bg=BG)
        self.tab_curseforge = tk.Frame(self.nb, bg=BG)
        self.tab_f          = tk.Frame(self.nb)
        self.nb.add(self.tab_modrinth,   text="  Modrinth  ")
        self.nb.add(self.tab_curseforge, text="  CurseForge  ")
        self.nb.add(self.tab_f,          text="  Import  ")
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
        self._top_4_ham = {
            "mr": self._load_mr_top, "cf": self._load_cf_top,
            "rsp": self._load_rsp_top, "sh": self._load_sh_top,
        }
        self._top_4_da_nap = set()
        if perf.get_perf()["profile"] == "weak":
            key0 = self._current_tab_key()
            fn0 = self._top_4_ham.get(key0)
            if fn0:
                threading.Thread(target=fn0, daemon=True).start()
                self._top_4_da_nap.add(key0)
        else:
            for k, fn in self._top_4_ham.items():
                threading.Thread(target=fn, daemon=True).start()
                self._top_4_da_nap.add(k)
        self.nb.bind("<<NotebookTabChanged>>",    self._on_tab_changed)
        self.nb_mr.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.nb_cf.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        theme.apply_theme(self)
    def _current_tab_key(self):
        outer = self.nb.index(self.nb.select())
        if outer == 0:
            inner = self.nb_mr.index(self.nb_mr.select())
            return ["mr", "modmr", "rsp", "sh"][inner]
        elif outer == 1:
            inner = self.nb_cf.index(self.nb_cf.select())
            return ["cf", "modcf", "rsp_cf", "sh_cf"][inner]
        return "file"
    def _on_tab_changed(self, e):
        key = self._current_tab_key()
        lazy_map = {
            "modmr":  (self._load_modmr_top,  "_modmr_data"),
            "modcf":  (self._load_modcf_top,  "_modcf_data"),
            "rsp_cf": (self._load_rsp_cf_top, "_rsp_cf_data"),
            "sh_cf":  (self._load_sh_cf_top,  "_sh_cf_data"),
        }
        if key in lazy_map:
            fn, attr = lazy_map[key]
            if not getattr(self, attr, None):
                threading.Thread(target=fn, daemon=True).start()
        fn2 = self._top_4_ham.get(key)
        if fn2 and key not in self._top_4_da_nap:
            self._top_4_da_nap.add(key)
            threading.Thread(target=fn2, daemon=True).start()
        kw = self.ent_search.get().strip()
        if kw and key != "file":
            last_kw_map = {
                "mr":     getattr(self, "_mr_last_kw",     None),
                "cf":     getattr(self, "_cf_last_kw",     None),
                "modmr":  getattr(self, "_modmr_last_kw",  None),
                "modcf":  getattr(self, "_modcf_last_kw",  None),
                "rsp":    getattr(self, "_rsp_last_kw",    None),
                "sh":     getattr(self, "_sh_last_kw",     None),
                "rsp_cf": getattr(self, "_rsp_cf_last_kw", None),
                "sh_cf":  getattr(self, "_sh_cf_last_kw",  None),
            }
            last = last_kw_map.get(key)
            cur_kw = last[0] if last else None
            if cur_kw != kw:
                self._search_current_tab()
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