
import threading

import tkinter as tk
from tkinter import ttk, messagebox

import config
import theme
from icon_utils import gan_icon_app

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

# Cac phim khong lam thay doi noi dung o Tim kiem (Caps Lock, Shift, phim mui ten...).
# Nhan nha nhung phim nay khong duoc kich hoat tim kiem lai.
_SEARCH_IGNORE_KEYSYMS = {
    "Caps_Lock", "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L", "Meta_R",
    "Tab", "Escape", "Num_Lock", "Scroll_Lock", "Insert",
    "Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
    "F10", "F11", "F12",
}

class PaginationBar(tk.Frame):

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
        pages = sorted(set([1, tp, cur]))
        last  = 0
        for p in pages:
            if p - last > 1:
                self._btn("...")
            self._btn(str(p), (lambda pp=p: self._go(pp)), active=(p == cur))
            last = p
        self._btn(">", (lambda: self._go(self.page + 1)) if self.page < tp else None)

class ModMcWindow(ModrinthModMixin, ForgeModMixin, tk.Toplevel):

    def __init__(self, parent, callback_lam_moi=None):
        super().__init__(parent)
        self.title("Content Manager")
        self.geometry("860x660")
        self.resizable(True, True)
        self.minsize(760, 500)
        self.callback_lam_moi = callback_lam_moi
        gan_icon_app(self)

        self._so_tac_vu_dang_chay = 0
        self._cancel_event        = threading.Event()

        self._last_progress_pct   = None
        self._last_progress_label = ""
        self._debounce_search     = None

        self._modmr_ver_idx_map = []
        self._modcf_ver_idx_map = []
        self._rsp_ver_idx_map   = []
        self._sh_ver_idx_map    = []
        self._rsp_cf_ver_idx_map = []
        self._sh_cf_ver_idx_map  = []

        self.protocol("WM_DELETE_WINDOW", self._xu_ly_dong_cua_so)
        self._build_ui()

    def _tang_tac_vu(self):
        self._so_tac_vu_dang_chay += 1
        self._cancel_event.clear()

    def _giam_tac_vu(self):
        self._so_tac_vu_dang_chay = max(0, self._so_tac_vu_dang_chay - 1)
        if self._so_tac_vu_dang_chay == 0:
            self._cancel_event.clear()
            self._last_progress_pct = None
            self._last_progress_label = ""

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

    def _xu_ly_dong_cua_so(self):
        if self._dang_co_tac_vu():
            messagebox.showwarning(
                "Đang cài đặt",
                "Đang cài đặt Mod, Modpack, Resource Pack hoặc Shader.\n"
                "Vui lòng đợi!",
                parent=self)
            return
        self.destroy()

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

        search_bar = tk.Frame(self)
        search_bar.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(search_bar, text="Tìm kiếm:", font=("Arial", 10)).pack(side="left")
        self.ent_search = tk.Entry(search_bar, font=("Arial", 10), width=34)
        self.ent_search.pack(side="left", padx=6)
        self.ent_search.bind("<Return>", lambda e: self._search_current_tab())
        self.ent_search.bind("<KeyRelease>", self._on_search_key)
        tk.Button(search_bar, text="Tìm", font=("Arial", 9, "bold"),
                  bg="#1E88E5", fg="white", activebackground="#1E88E5", activeforeground="white",
                  width=6, command=self._search_current_tab).pack(side="left")
        tk.Button(search_bar, text="Top", font=("Arial", 9), bg="#607D8B", fg="white",
                  activebackground="#607D8B", activeforeground="white",
                  command=self._top_current_tab).pack(side="left", padx=4)

        # Da an chu trang thai nho o goc trai man hinh theo yeu cau; widget van ton tai
        # (khong pack) de cac noi khac trong code goi self.lbl_status.config(...) khong loi.
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

        threading.Thread(target=self._load_mr_top,  daemon=True).start()
        threading.Thread(target=self._load_cf_top,  daemon=True).start()
        threading.Thread(target=self._load_rsp_top, daemon=True).start()
        threading.Thread(target=self._load_sh_top,  daemon=True).start()

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

    def _on_search_key(self, e):
        # Bo qua cac phim khong lam thay doi noi dung (Caps Lock, Shift, mui ten...)
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
        """Dong bo bo loc (MC version + Loader) trong FilterBar theo Instance dang chon.
        So khop khong phan biet hoa/thuong de tranh sai lech chinh ta (vd 'Neoforge' vs 'NeoForge')."""
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

    def _done(self):
        if self.callback_lam_moi:
            self.callback_lam_moi()
        messagebox.showinfo("Thành công",
            "Đã cài đặt thành công!\nInstance mới đã xuất hiện trong danh sách.", parent=self)

    def _thong_bao_cai_xong(self, loai, ten, ten_inst):
        messagebox.showinfo("Thành công",
            f"Đã cài đặt {loai} '{ten}' vào Instance '{ten_inst}' thành công!", parent=self)

class ModMcFrame(ModrinthModMixin, ForgeModMixin, tk.Frame):

    def __init__(self, parent, callback_lam_moi=None):
        super().__init__(parent)
        self.callback_lam_moi = callback_lam_moi

        self._so_tac_vu_dang_chay = 0
        self._cancel_event        = threading.Event()

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
        # Bo qua cac phim khong lam thay doi noi dung (Caps Lock, Shift, mui ten...)
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
        """Dong bo bo loc (MC version + Loader) trong FilterBar theo Instance dang chon.
        So khop khong phan biet hoa/thuong de tranh sai lech chinh ta (vd 'Neoforge' vs 'NeoForge')."""
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

    def _done(self):
        if self.callback_lam_moi:
            self.callback_lam_moi()
        messagebox.showinfo("Thành công",
            "Đã cài đặt thành công!\nInstance mới đã xuất hiện trong danh sách.", parent=self)

    def _thong_bao_cai_xong(self, loai, ten, ten_inst):
        messagebox.showinfo("Thành công",
            f"Đã cài đặt {loai} '{ten}' vào Instance '{ten_inst}' thành công!", parent=self)

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

        search_bar = tk.Frame(self)
        search_bar.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(search_bar, text="Tìm kiếm:", font=("Arial", 10)).pack(side="left")
        self.ent_search = tk.Entry(search_bar, font=("Arial", 10), width=34)
        self.ent_search.pack(side="left", padx=6)
        self.ent_search.bind("<Return>", lambda e: self._search_current_tab())
        self.ent_search.bind("<KeyRelease>", self._on_search_key)
        tk.Button(search_bar, text="Tìm", font=("Arial", 9, "bold"),
                  bg="#1E88E5", fg="white", activebackground="#1E88E5", activeforeground="white",
                  width=6, command=self._search_current_tab).pack(side="left")
        tk.Button(search_bar, text="Top", font=("Arial", 9), bg="#607D8B", fg="white",
                  activebackground="#607D8B", activeforeground="white",
                  command=self._top_current_tab).pack(side="left", padx=4)

        # Da an chu trang thai nho o goc trai man hinh theo yeu cau; widget van ton tai
        # (khong pack) de cac noi khac trong code goi self.lbl_status.config(...) khong loi.
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

        threading.Thread(target=self._load_mr_top,  daemon=True).start()
        threading.Thread(target=self._load_cf_top,  daemon=True).start()
        threading.Thread(target=self._load_rsp_top, daemon=True).start()
        threading.Thread(target=self._load_sh_top,  daemon=True).start()

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
