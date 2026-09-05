
import io
import re
import html
import threading
import urllib.request
import webbrowser

import tkinter as tk
from tkinter import ttk, messagebox

from components.install_utils import lay_trang_thai_da_cai, xoa_file_theo_ten

try:
    import theme as _theme
except ImportError:
    _theme = None

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

MODRINTH_UA = "MinecraftLauncher/1.0 (github.com/user/mc-launcher)"

# Nhan hien thi khi chua chon Instance nao trong combobox chon instance.
_NO_INST = "— Chưa chọn —"

def _fetch_image(url, size=(500, 180)):
    if not url or not _PIL_OK:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MODRINTH_UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img.thumbnail(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

def _html_to_md(text):
    if not text:
        return ""
    t = text
    t = re.sub(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "\n" + "#" * int(m.group(1)) + " " + m.group(2) + "\n", t)
    t = re.sub(r"(?is)<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", t)
    t = re.sub(r"(?is)<(em|i)[^>]*>(.*?)</\1>", r"*\2*", t)
    t = re.sub(r'(?is)<img[^>]*src="([^"]+)"[^>]*>', r"\n![](\1)\n", t)
    t = re.sub(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", t)
    t = re.sub(r"(?is)<li[^>]*>(.*?)</li>", lambda m: "\n- " + m.group(1), t)
    t = re.sub(r"(?is)</p>|<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)<[^>]+>", "", t)
    t = html.unescape(t)
    return t

def _parse_rich_blocks(raw):
    blocks = []
    para_lines = []

    def _flush():
        if para_lines:
            blocks.append(("p", " ".join(para_lines).strip()))
            para_lines.clear()

    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            _flush()
            continue
        m_img = re.match(r"^!\[[^\]]*\]\(([^)]+)\)$", line)
        m_h   = re.match(r"^(#{1,6})\s+(.*)$", line)
        m_li  = re.match(r"^[-*]\s+(.*)$", line)
        if m_img:
            _flush()
            blocks.append(("img", m_img.group(1)))
        elif m_h:
            _flush()
            blocks.append(("h", len(m_h.group(1)), m_h.group(2).strip()))
        elif m_li:
            _flush()
            blocks.append(("li", m_li.group(1).strip()))
        else:
            para_lines.append(line)
    _flush()
    return blocks

_INLINE_RE = re.compile(r"\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)]+)\)")

def _strip_md(text):
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()

class ModDetailWindow(tk.Frame):

    def __init__(self, parent, source, data, versions_raw,
                 install_cb, on_back=None, cancel_cb=None, accent="#1E88E5",
                 installed_info=None, instance_ctl=None, loai=None):
        super().__init__(parent)
        self._source   = source
        self._data     = data
        self._versions = list(versions_raw) if versions_raw else []
        self._ver_idx_map = list(range(len(self._versions)))
        self._install_cb = install_cb
        # loai: "modpack" / "mods" / "resourcepacks" / "shaderpacks" - can de
        # sau khi cai xong co the tu truy lai trang thai da cai moi nhat.
        self._loai = loai
        self._on_back   = on_back
        self._cancel_cb = cancel_cb
        self._accent   = accent
        self._banner_photo = None
        self._dang_cai  = False

        # instance_ctl: dict {"get_list", "get", "set"} cho phep chon Instance de
        # cai vao ngay trong man hinh chi tiet. Modpack khong dung (tao instance moi
        # nen khong truyen instance_ctl khi mo ModDetailWindow cho modpack).
        self._instance_ctl = instance_ctl
        self.cbo_inst = None

        self._installed_info = installed_info
        self._nhan_nut_hien_tai = "⬇  Cài đặt"

        self._owner = getattr(cancel_cb, "__self__", None)
        self._poll_after_id = None

        if source == "modrinth":
            self._title   = data.get("title", "")
            self._author  = data.get("author", "")
            self._desc    = data.get("description", "")
            self._dl      = data.get("downloads", 0)
            self._icon_url  = data.get("icon_url", "")
            self._pid     = data.get("project_id", data.get("slug", ""))
            self._project_url = f"https://modrinth.com/project/{self._pid}" if self._pid else ""

            self._gallery_pending = "gallery" not in data
            gallery = data.get("gallery") or []
            self._gallery_urls = [
                g.get("url", "") for g in gallery if isinstance(g, dict) and g.get("url")
            ]

            self._desc_full = data.get("body") or self._desc
        else:
            self._title   = data.get("name", "")
            authors       = data.get("authors", [])
            self._author  = authors[0].get("name", "") if authors else ""
            self._desc    = data.get("summary", "")
            self._dl      = data.get("downloadCount", 0)
            logo          = data.get("logo") or {}
            self._icon_url = (logo.get("url", "") or
                              logo.get("thumbnailUrl", ""))
            self._pid     = data.get("id", "")
            links = data.get("links") or {}
            self._project_url = links.get("websiteUrl", "") or (f"https://www.curseforge.com/projects/{self._pid}" if self._pid else "")
            self._gallery_pending = False

            shots = data.get("screenshots") or []
            self._gallery_urls = [
                s.get("url", "") or s.get("thumbnailUrl", "")
                for s in shots if isinstance(s, dict)
            ]
            self._gallery_urls = [u for u in self._gallery_urls if u]

            self._desc_full = data.get("description") or self._desc

        self._gallery_photos = []
        self._gallery_big_photo = None

        self._build_ui()
        self._load_banner()
        self._load_gallery()

        if not self._versions:
            self._load_versions_async()
        else:
            self._fill_versions(self._versions)

        self._dong_bo_trang_thai_ban_dau()

    def _dong_bo_trang_thai_ban_dau(self):
        if self._owner is None or not hasattr(self._owner, "_dang_co_tac_vu"):
            return
        try:
            dang_ban = bool(self._owner._dang_co_tac_vu())
        except Exception:
            dang_ban = False
        if dang_ban:
            self._dang_cai = True
            self._set_install_ui_state(installing=True)
            self._schedule_poll_busy()

    _ICON_FULL  = 96
    _ICON_SMALL = 48
    _HIDE_ICON_BELOW = 340

    def _build_ui(self):
        clr = _theme.colors() if _theme else {}
        BG     = clr.get("bg_alt", "#f5f5f7")
        FG     = clr.get("fg_title", "#1a1a1a")
        FG_SUB = clr.get("fg_author", "#5b6b8c")
        FG_DL  = clr.get("fg_stat",  "#2e7d32")
        FG_DSC = clr.get("fg_desc",  "#444444")
        ICON_BG = clr.get("icon_bg", "#e1e4ea")
        TXT_BG  = clr.get("row_bg",  "#ffffff")
        TXT_FG  = clr.get("fg_desc", "#222222")

        self.configure(bg=BG)

        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

        back_bar = tk.Frame(self, bg=BG)
        back_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 0))
        self.btn_back = tk.Button(
            back_bar, text="←  Quay lại danh sách",
            font=("Arial", 9, "bold"),
            bg="#78909C", fg="white",
            activebackground="#607D8B", activeforeground="white",
            relief="flat", padx=10, pady=4,
            command=self._go_back)
        self.btn_back.pack(side="left")

        self._top = tk.Frame(self, bg=BG)
        self._top.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 6))
        self._top.columnconfigure(1, weight=1)
        self._top.columnconfigure(2, weight=0)

        self._icon_cell = tk.Frame(self._top, bg=BG)
        self._icon_cell.grid(row=0, column=0, padx=(0, 12), sticky="nw")

        self.lbl_banner = tk.Label(
            self._icon_cell, bg=ICON_BG,
            width=self._ICON_FULL // 8,
            height=self._ICON_FULL // 16,
            relief="flat", bd=0)
        self.lbl_banner.pack()

        self._header_btns = tk.Frame(self._top, bg=BG)
        self._header_btns.grid(row=0, column=2, sticky="ne", padx=(8, 0))

        self.btn_install = tk.Button(
            self._header_btns, text="⬇  Cài đặt",
            font=("Arial", 10, "bold"),
            bg=self._accent, fg="white",
            activebackground=self._accent, activeforeground="white",
            relief="flat", padx=16, pady=6,
            command=self._on_install_or_cancel)
        self.btn_install.pack(side="left", padx=(0, 6))

        if self._project_url:
            tk.Button(
                self._header_btns, text="🌐  Mở trình duyệt",
                font=("Arial", 9),
                bg=BG, fg=FG,
                activebackground="#3a3a3a", activeforeground=FG,
                relief="flat", padx=10, pady=6,
                command=lambda: webbrowser.open(self._project_url)
            ).pack(side="left")

        info = tk.Frame(self._top, bg=BG)
        info.grid(row=0, column=1, sticky="nsew")

        self.lbl_title = tk.Label(
            info, text=self._title,
            font=("Arial", 15, "bold"), fg=FG, bg=BG,
            anchor="w", justify="left", wraplength=380)
        self.lbl_title.pack(fill="x", anchor="w")

        sub = f"by {self._author}" if self._author else ""
        self._lbl_author = tk.Label(
            info, text=sub, font=("Arial", 10), fg=FG_SUB,
            bg=BG, anchor="w")
        self._lbl_author.pack(fill="x", anchor="w", pady=(2, 4))

        self._lbl_dl = tk.Label(
            info, text=f"⬇ {int(self._dl or 0):,} lượt tải",
            font=("Arial", 10, "bold"), fg=FG_DL,
            bg=BG, anchor="w")
        self._lbl_dl.pack(fill="x", anchor="w")

        desc_short = (self._desc or "").replace("\n", " ").strip()
        if len(desc_short) > 180:
            desc_short = desc_short[:177].rstrip() + "..."
        self._lbl_desc = tk.Label(
            info, text=desc_short, font=("Arial", 9), fg=FG_DSC,
            bg=BG, anchor="w", justify="left", wraplength=390)
        self._lbl_desc.pack(fill="x", anchor="w", pady=(6, 0))

        ttk.Separator(self, orient="horizontal").grid(
            row=2, column=0, sticky="ew", padx=12, pady=6)

        ver_fr = tk.Frame(self, bg=BG)
        ver_fr.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))
        ver_fr.columnconfigure(1, weight=1)

        self._lbl_ver_label = tk.Label(
            ver_fr, text="Phiên bản:", font=("Arial", 10, "bold"), bg=BG, fg=FG)
        self._lbl_ver_label.grid(row=0, column=0, padx=(0, 8))

        self.cbo_ver = ttk.Combobox(ver_fr, font=("Arial", 9),
                                     state="readonly", width=50)
        self.cbo_ver.grid(row=0, column=1, sticky="ew")
        self.cbo_ver.set("Đang tải phiên bản...")
        self.cbo_ver.bind("<<ComboboxSelected>>", self._on_ver_selected)

        self.lbl_detail_status = tk.Label(
            ver_fr, text="", font=("Arial", 9, "italic"),
            fg=self._accent, bg=BG, anchor="w")
        self.lbl_detail_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        if self._instance_ctl:
            self._lbl_inst_label = tk.Label(
                ver_fr, text="Cài vào Instance:", font=("Arial", 10, "bold"), bg=BG, fg=FG)
            self._lbl_inst_label.grid(row=2, column=0, padx=(0, 8), pady=(6, 0), sticky="w")

            self.cbo_inst = ttk.Combobox(ver_fr, font=("Arial", 9),
                                          state="readonly", width=50)
            self.cbo_inst.grid(row=2, column=1, sticky="ew", pady=(6, 0))
            self._refresh_inst_list()
            self.cbo_inst.bind("<<ComboboxSelected>>", self._on_inst_selected)
            self.cbo_inst.bind("<ButtonPress>", self._refresh_inst_list)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 0))

        tab_intro = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_intro, text="  Giới thiệu  ")

        intro_frame = tk.Frame(tab_intro, bg=BG)
        intro_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.txt_intro = tk.Text(
            intro_frame, wrap="word", font=("Arial", 9),
            bg=TXT_BG, fg=TXT_FG, relief="flat",
            state="disabled", padx=10, pady=8, spacing3=4, cursor="arrow")
        intro_sb = ttk.Scrollbar(intro_frame, orient="vertical",
                                  command=self.txt_intro.yview)
        self.txt_intro.configure(yscrollcommand=intro_sb.set)
        intro_sb.pack(side="right", fill="y")
        self.txt_intro.pack(side="left", fill="both", expand=True)

        link_color = self._accent
        self.txt_intro.tag_configure("h1", font=("Arial", 15, "bold"),
                                      foreground=FG, spacing1=10, spacing3=8)
        self.txt_intro.tag_configure("h2", font=("Arial", 13, "bold"),
                                      foreground=FG, spacing1=8, spacing3=6)
        self.txt_intro.tag_configure("h3", font=("Arial", 11, "bold"),
                                      foreground=FG, spacing1=6, spacing3=4)
        self.txt_intro.tag_configure("b", font=("Arial", 9, "bold"))
        self.txt_intro.tag_configure("i", font=("Arial", 9, "italic"))
        self.txt_intro.tag_configure("li", lmargin1=18, lmargin2=30, spacing3=3)
        self.txt_intro.tag_configure("p", spacing3=6)
        self.txt_intro.tag_configure("link", foreground=link_color, underline=True)
        self.txt_intro.tag_configure("img_pad", spacing1=4, spacing3=8)

        self._intro_photos = []
        self._intro_render_id = 0
        self._render_intro_async(self._desc_full)

        tab_log = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_log, text="  Bản ghi thay đổi  ")

        cl_frame = tk.Frame(tab_log, bg=BG)
        cl_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.txt_log = tk.Text(
            cl_frame, wrap="word", font=("Arial", 9),
            bg=TXT_BG, fg=TXT_FG, relief="flat",
            state="disabled", padx=8, pady=6)
        sb = ttk.Scrollbar(cl_frame, orient="vertical",
                           command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

        self._set_changelog("Chọn phiên bản để xem bản ghi thay đổi.")

        tab_gallery = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_gallery, text="  Hình ảnh  ")

        self._gal_big_frame = tk.Frame(tab_gallery, bg=BG)
        self._gal_big_frame.pack(fill="x", padx=4, pady=(4, 0))

        gal_big_bar = tk.Frame(self._gal_big_frame, bg=BG)
        gal_big_bar.pack(fill="x")
        tk.Button(
            gal_big_bar, text="✕ Đóng", font=("Arial", 8),
            bg="#78909C", fg="white", activebackground="#607D8B",
            activeforeground="white", relief="flat", padx=6,
            command=self._hide_gallery_big,
        ).pack(side="right", pady=(0, 2))

        self.lbl_gallery_big = tk.Label(
            self._gal_big_frame, bg=ICON_BG, relief="flat", bd=0)
        self.lbl_gallery_big.pack()
        self._gal_big_frame.pack_forget()

        self._gal_outer = tk.Frame(tab_gallery, bg=BG)
        self._gal_outer.pack(fill="both", expand=True, padx=4, pady=4)

        self._gal_canvas = tk.Canvas(self._gal_outer, bg=BG, highlightthickness=0)
        gal_sb = ttk.Scrollbar(self._gal_outer, orient="vertical",
                                command=self._gal_canvas.yview)
        self._gal_canvas.configure(yscrollcommand=gal_sb.set)
        gal_sb.pack(side="right", fill="y")
        self._gal_canvas.pack(side="left", fill="both", expand=True)

        self._gal_inner = tk.Frame(self._gal_canvas, bg=BG)
        self._gal_canvas.create_window((0, 0), window=self._gal_inner,
                                        anchor="nw", tags=("inner",))

        self._gal_inner.bind(
            "<Configure>",
            lambda e: self._gal_canvas.configure(
                scrollregion=self._gal_canvas.bbox("all")))
        self._gal_canvas.bind(
            "<Configure>",
            lambda e: self._gal_canvas.itemconfigure("inner", width=e.width))

        self.lbl_gallery_status = tk.Label(
            self._gal_inner,
            text="Đang tải hình ảnh..." if (self._gallery_urls or self._gallery_pending)
            else "Mod này chưa có hình ảnh nào.",
            font=("Arial", 9, "italic"), fg=FG_SUB, bg=BG)
        self.lbl_gallery_status.pack(anchor="w", padx=8, pady=8)

        btn_bar = tk.Frame(self, bg=BG)
        btn_bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(6, 12))
        btn_bar.columnconfigure(0, weight=1)

        self._progress_var = tk.DoubleVar(value=0)
        self.pb_install = ttk.Progressbar(
            btn_bar, orient="horizontal", mode="determinate",
            variable=self._progress_var, maximum=100, length=200)

        self.lbl_progress_pct = tk.Label(
            btn_bar, text="", font=("Arial", 9, "bold"),
            fg=self._accent, bg=BG)

        self.lbl_cancel_hint = tk.Label(
            btn_bar, text="💡 Đang cài đặt — bấm nút Hủy ở góc trên để dừng.",
            font=("Arial", 8, "italic"), fg=FG_SUB, bg=BG, anchor="w")

        if _theme:
            _theme.apply_theme(self)

        self.update_idletasks()
        self._btn_col_w = self._header_btns.winfo_reqwidth()

        self.bind("<Configure>", self._on_resize)

    def _load_banner(self):
        url = self._icon_url
        if not url or not _PIL_OK:
            return

        def _t():
            photo = _fetch_image(url, size=(180, 180))
            if photo:
                self._safe_after(lambda: self._set_banner(photo))

        threading.Thread(target=_t, daemon=True).start()

    def _set_banner(self, photo):
        self._banner_photo = photo
        try:
            self.lbl_banner.configure(image=photo, width=photo.width(),
                                       height=photo.height())
            self.lbl_banner.image = photo
        except tk.TclError:
            pass

    _GAL_THUMB_SIZE = (140, 90)

    def _load_gallery(self):
        if self._source == "modrinth" and self._gallery_pending:
            self._fetch_modrinth_gallery_then_load()
            return
        self._load_gallery_thumbnails()

    def _fetch_modrinth_gallery_then_load(self):
        def _t():
            urls = []
            body = ""
            try:
                from components.api_helpers import lay_project_modrinth
                proj = lay_project_modrinth(self._pid)
                gallery = proj.get("gallery") or []
                urls = [
                    g.get("url", "") for g in gallery
                    if isinstance(g, dict) and g.get("url")
                ]
                urls = [u for u in urls if u]
                body = proj.get("body") or ""
            except Exception:
                urls = []
            self._safe_after(lambda: self._on_modrinth_gallery_fetched(urls, body))

        threading.Thread(target=_t, daemon=True).start()

    def _on_modrinth_gallery_fetched(self, urls, body=""):
        self._gallery_pending = False
        self._gallery_urls = urls
        if body and body != self._desc_full:
            self._desc_full = body
            try:
                self._render_intro_async(body)
            except tk.TclError:
                pass
        if not urls:
            try:
                self.lbl_gallery_status.config(text="Mod này chưa có hình ảnh nào.")
            except tk.TclError:
                pass
            return
        self._load_gallery_thumbnails()

    def _load_gallery_thumbnails(self):
        urls = self._gallery_urls
        if not urls or not _PIL_OK:
            return

        def _t():
            results = []
            for url in urls:
                photo = _fetch_image(url, size=self._GAL_THUMB_SIZE)
                results.append((url, photo))
            self._safe_after(lambda: self._render_gallery(results))

        threading.Thread(target=_t, daemon=True).start()

    def _render_gallery(self, results):
        try:
            self.lbl_gallery_status.destroy()
        except tk.TclError:
            pass

        ok_results = [(u, p) for u, p in results if p is not None]
        if not ok_results:
            clr = _theme.colors() if _theme else {}
            BG = clr.get("bg_alt", "#f5f5f7")
            FG_SUB = clr.get("fg_author", "#5b6b8c")
            tk.Label(
                self._gal_inner, text="Không thể tải hình ảnh.",
                font=("Arial", 9, "italic"), fg=FG_SUB, bg=BG
            ).pack(anchor="w", padx=8, pady=8)
            return

        clr = _theme.colors() if _theme else {}
        BG = clr.get("bg_alt", "#f5f5f7")

        cols = 3
        for i, (url, photo) in enumerate(ok_results):
            self._gallery_photos.append(photo)
            r, c = divmod(i, cols)
            cell = tk.Frame(self._gal_inner, bg=BG)
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="n")

            btn = tk.Label(
                cell, image=photo, bg=BG, cursor="hand2",
                relief="flat", bd=0)
            btn.image = photo
            btn.pack()
            btn.bind("<Button-1>",
                     lambda e, u=url: self._show_gallery_big(u))

    def _show_gallery_big(self, url):
        def _t():
            photo = _fetch_image(url, size=(640, 360))
            if photo:
                self._safe_after(lambda: self._set_gallery_big(photo))

        threading.Thread(target=_t, daemon=True).start()

    def _set_gallery_big(self, photo):
        self._gallery_big_photo = photo
        try:
            self.lbl_gallery_big.configure(image=photo)
            self.lbl_gallery_big.image = photo

            self._gal_big_frame.pack(fill="x", padx=4, pady=(4, 0), before=self._gal_outer)
        except tk.TclError:
            pass

    def _hide_gallery_big(self):
        try:
            self._gal_big_frame.pack_forget()
        except tk.TclError:
            pass

    def _on_resize(self, event=None):
        try:
            w = self.winfo_width()
        except Exception:
            return

        ICON_COL = self._ICON_FULL + 12
        BTN_COL  = getattr(self, "_btn_col_w", 0)

        if w < self._HIDE_ICON_BELOW:

            self._icon_cell.grid_remove()
            info_w = max(w - 40 - BTN_COL, 60)
        else:

            self._icon_cell.grid()
            info_w = max(w - 40 - ICON_COL - BTN_COL, 60)

        self.lbl_title.configure(wraplength=info_w)
        self._lbl_desc.configure(wraplength=info_w)

    def _load_versions_async(self):
        self.cbo_ver.set("Đang tải phiên bản...")
        self.lbl_detail_status.config(text="Đang tải danh sách phiên bản...",
                                       fg=self._accent)

        def _t():
            try:
                if self._source == "modrinth":
                    from components.api_helpers import lay_phien_ban_modrinth
                    vs = lay_phien_ban_modrinth(self._pid)
                else:
                    from components.api_helpers import lay_phien_ban_curseforge
                    vs = lay_phien_ban_curseforge(self._pid)
                self._versions = vs
                self._safe_after(lambda: self._fill_versions(vs))
            except Exception as e:
                self._safe_after(lambda e=e: (
                    self.cbo_ver.set("Lỗi tải phiên bản"),
                    self.lbl_detail_status.config(
                        text=f"Lỗi: {e}", fg="red")
                ))

        threading.Thread(target=_t, daemon=True).start()

    def _safe_after(self, fn):
        def _wrapped():
            if not self.winfo_exists():
                return
            try:
                fn()
            except tk.TclError:
                pass
        try:
            self.after(0, _wrapped)
        except tk.TclError:
            pass

    def _raw_ver_idx(self, disp_idx):
        """Quy doi tu index hien thi tren cbo_ver (sau khi da loc theo Instance)
        ve index thuc trong self._versions (danh sach day du, chua loc)."""
        if disp_idx is None or disp_idx < 0:
            return -1
        if disp_idx < len(self._ver_idx_map):
            return self._ver_idx_map[disp_idx]
        return disp_idx

    def _loc_theo_instance(self, versions):
        """Tra ve danh sach index cua 'versions' phu hop voi MC version + Loader
        cua Instance dang duoc chon (neu co). Tra ve None neu khong co Instance
        nao dang chon, khong lay duoc thong tin, hoac khong co phien ban nao khop
        - de noi goi fallback ve hien thi toan bo danh sach (khong loc)."""
        if not self._instance_ctl:
            return None
        get_ml = self._instance_ctl.get("get_mc_loader")
        if not get_ml:
            return None
        try:
            mcv, loader = get_ml()
        except Exception:
            return None
        if not mcv:
            return None
        loader_l = (loader or "").lower()
        idxs = []
        if self._source == "modrinth":
            for i, v in enumerate(versions):
                if mcv not in v.get("game_versions", []):
                    continue
                lds = [l.lower() for l in v.get("loaders", [])]
                if loader_l and loader_l != "vanilla" and lds and loader_l not in lds:
                    continue
                idxs.append(i)
        else:
            for i, fi in enumerate(versions):
                gvs = fi.get("gameVersions", [])
                gvs_lower = [g.lower() for g in gvs]
                if mcv not in gvs and mcv.lower() not in gvs_lower:
                    continue
                if loader_l and loader_l != "vanilla" and loader_l not in gvs_lower:
                    continue
                idxs.append(i)
        return idxs or None

    def _fill_versions(self, versions):
        if not versions:
            self.cbo_ver.set("Không có phiên bản")
            self._ver_idx_map = []
            self.lbl_detail_status.config(text="", fg=self._accent)
            return

        if self._source == "modrinth":
            ds_all = [
                f"{v.get('name','?')}  —  MC {', '.join(v.get('game_versions',[]))}"
                for v in versions
            ]
        else:
            ds_all = [
                f"{fi.get('displayName', fi.get('fileName',''))}  —  MC {', '.join(fi.get('gameVersions',[]))}"
                for fi in versions
            ]

        idxs = self._loc_theo_instance(versions)
        if idxs:
            self._ver_idx_map = idxs
            ds = [ds_all[i] for i in idxs]
        else:
            self._ver_idx_map = list(range(len(versions)))
            ds = ds_all

        self.cbo_ver.config(values=ds)
        self.cbo_ver.current(0)
        self.lbl_detail_status.config(text="", fg=self._accent)
        self._show_changelog(self._ver_idx_map[0])
        self._cap_nhat_nhan_nut_cai_dat()

    def _on_ver_selected(self, event=None):
        idx = self._raw_ver_idx(self.cbo_ver.current())
        if idx >= 0:
            self._show_changelog(idx)
            self._cap_nhat_nhan_nut_cai_dat()

    def _lay_khoa_so_sanh_phien_ban(self, version_data):
        if self._source == "modrinth":
            return str(version_data.get("id", "")), (version_data.get("date_published", "") or "")
        return str(version_data.get("id", "")), (version_data.get("fileDate", "") or "")

    def _cap_nhat_nhan_nut_cai_dat(self):
        if not self._installed_info:
            self._nhan_nut_hien_tai = "⬇  Cài đặt"
        else:
            idx = self._raw_ver_idx(self.cbo_ver.current())
            if idx < 0 or idx >= len(self._versions):
                self._nhan_nut_hien_tai = "⬆  Cập nhật"
            else:
                vid, ngay = self._lay_khoa_so_sanh_phien_ban(self._versions[idx])
                old_vid = str(self._installed_info.get("version_id") or "")
                old_ngay = self._installed_info.get("ngay", "") or ""
                if vid and old_vid and vid == old_vid:
                    self._nhan_nut_hien_tai = "🔁  Cài lại"
                elif ngay and old_ngay:
                    self._nhan_nut_hien_tai = ("⬇  Hạ phiên bản" if ngay < old_ngay
                                                else "⬆  Cập nhật")
                else:

                    self._nhan_nut_hien_tai = "⬆  Cập nhật"
        if not self._dang_cai:
            try:
                self.btn_install.configure(text=self._nhan_nut_hien_tai)
            except tk.TclError:
                pass

    def _show_changelog(self, idx):
        if idx < 0 or idx >= len(self._versions):
            return
        v = self._versions[idx]

        if self._source == "modrinth":
            raw = v.get("changelog", "") or ""
        else:
            raw = v.get("changelog", "") or ""

        if raw:
            text = _strip_md(raw)
        else:
            text = "(Không có bản ghi thay đổi cho phiên bản này.)"

        self._set_changelog(text)

    def _render_intro_async(self, raw):
        self._intro_render_id += 1
        token = self._intro_render_id

        if not raw:
            self._fill_intro_blocks([("p", "(Không có giới thiệu cho mục này.)")], [], token)
            return

        md = _html_to_md(raw) if self._source == "curseforge" else raw

        def _worker():
            blocks = _parse_rich_blocks(md)
            photos = []
            for b in blocks:
                if b[0] == "img":
                    photo = _fetch_image(b[1], size=(480, 260))
                    photos.append(photo)
                else:
                    photos.append(None)
            self._safe_after(lambda: self._fill_intro_blocks(blocks, photos, token))

        threading.Thread(target=_worker, daemon=True).start()

    def _fill_intro_blocks(self, blocks, photos, token):
        if token != self._intro_render_id:
            return
        try:
            w = self.txt_intro
            w.config(state="normal")
            w.delete("1.0", "end")
            self._intro_photos = []

            for i, b in enumerate(blocks):
                kind = b[0]
                if kind == "h":
                    _, level, text = b
                    tag = "h1" if level <= 1 else ("h2" if level == 2 else "h3")
                    self._insert_inline(w, text, (tag,))
                    w.insert("end", "\n")
                elif kind == "li":
                    w.insert("end", "•  ", ("li",))
                    self._insert_inline(w, b[1], ("li",))
                    w.insert("end", "\n")
                elif kind == "img":
                    photo = photos[i] if i < len(photos) else None
                    if photo is not None:
                        self._intro_photos.append(photo)
                        w.image_create("end", image=photo)
                        w.insert("end", "\n", ("img_pad",))
                elif kind == "p":
                    self._insert_inline(w, b[1], ("p",))
                    w.insert("end", "\n")

            w.config(state="disabled")
            w.yview_moveto(0)
        except tk.TclError:
            pass

    def _insert_inline(self, w, text, base_tags):
        pos = 0
        for m in _INLINE_RE.finditer(text):
            if m.start() > pos:
                w.insert("end", text[pos:m.start()], base_tags)
            if m.group(1) is not None:
                w.insert("end", m.group(1), base_tags + ("b",))
            elif m.group(2) is not None:
                w.insert("end", m.group(2), base_tags + ("i",))
            else:
                link_text, url = m.group(3), m.group(4)
                tag = f"link_{id(m)}"
                w.tag_configure(tag, foreground=self._accent, underline=True)
                w.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
                w.tag_bind(tag, "<Enter>", lambda e: w.config(cursor="hand2"))
                w.tag_bind(tag, "<Leave>", lambda e: w.config(cursor="arrow"))
                w.insert("end", link_text, base_tags + ("link", tag))
            pos = m.end()
        if pos < len(text):
            w.insert("end", text[pos:], base_tags)

    def _set_changelog(self, text):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.insert("1.0", text)
        self.txt_log.config(state="disabled")
        self.txt_log.yview_moveto(0)

    def _refresh_inst_list(self, e=None):
        if not self._instance_ctl or self.cbo_inst is None:
            return
        try:
            ds_inst = list(self._instance_ctl["get_list"]())
        except Exception:
            ds_inst = []
        values = [_NO_INST] + ds_inst
        self.cbo_inst.configure(values=values)
        try:
            cur = self._instance_ctl["get"]() or ""
        except Exception:
            cur = ""
        self.cbo_inst.set(cur if cur in ds_inst else _NO_INST)

    def _on_inst_selected(self, e=None):
        if not self._instance_ctl or self.cbo_inst is None:
            return
        val = self.cbo_inst.get().strip()
        val = "" if val == _NO_INST else val
        try:
            self._instance_ctl["set"](val)
        except Exception:
            pass
        # Doi Instance -> loc/chon lai phien ban phu hop (MC ver + Loader) ngay.
        if self._versions:
            self._fill_versions(self._versions)

    def _go_back(self):
        if self._on_back:
            self._on_back()

    _TEN_LOAI_HIEN_THI = {"mods": "mod", "resourcepacks": "resource pack",
                           "shaderpacks": "shader"}

    def _on_install_or_cancel(self):
        if self._dang_cai:
            if self._cancel_cb:
                try:
                    self._cancel_cb()
                except Exception:
                    pass
            return

        idx = self._raw_ver_idx(self.cbo_ver.current())
        if idx < 0 or not self._versions:
            return
        vd = self._versions[idx]

        if self._nhan_nut_hien_tai.endswith("Hạ phiên bản"):
            ten_phien_ban = vd.get("version_number") or vd.get("displayName") or vd.get("name", "")
            if not messagebox.askyesno(
                "Hạ phiên bản",
                f"Bạn có chắc muốn HẠ xuống phiên bản '{ten_phien_ban}' không?\n"
                "Phiên bản cũ hơn có thể không tương thích hoặc thiếu tính năng mới.",
                parent=self,
            ):
                return
        elif self._nhan_nut_hien_tai.endswith("Cập nhật") and self._loai != "modpack":
            ten_loai = self._TEN_LOAI_HIEN_THI.get(self._loai, "mod")
            if not messagebox.askyesno(
                "Cập nhật",
                f"Cập nhật bản {ten_loai} có thể dẫn đến 1 vài lỗi không lường trước được.\n"
                "Bạn có muốn cập nhật không?",
                parent=self,
            ):
                return

        # Truong hop mod duoc phat hien qua quet ten file (khong co trong index vi
        # khong cai qua launcher) thi khong co co che nao khac don dep file cu, nen
        # phai tu xoa o day truoc khi cai ban moi - tranh 2 ban (cu + moi) cung ton
        # tai gay xung dot. Voi mod da co trong index, viec don dep file cu duoc
        # luu_muc_da_cai tu lam SAU KHI cai xong (an toan hon, khong mat file neu
        # cai loi giua chung), nen khong can xoa som o day.
        if (self._installed_info and self._loai and self._loai != "modpack"
                and xoa_file_theo_ten is not None
                and self._installed_info.get("version_id") is None):
            ten_inst_cu = self._installed_info.get("ten_instance")
            ten_file_cu = self._installed_info.get("filename")
            if ten_inst_cu and ten_file_cu:
                try:
                    xoa_file_theo_ten(ten_inst_cu, self._loai, ten_file_cu)
                except Exception:
                    pass

        self._dang_cai = True
        self._progress_var.set(0)
        self.lbl_progress_pct.configure(text="")
        self._set_install_ui_state(installing=True)

        self._schedule_poll_busy()
        self._install_cb(vd, on_done=self._on_install_done, progress_cb=self.update_progress)

    def _schedule_poll_busy(self):
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
        self._poll_after_id = self.after(400, self._poll_busy)

    def _poll_busy(self):
        self._poll_after_id = None
        if not self.winfo_exists() or not self._dang_cai:
            return
        busy = True
        try:
            if self._owner is not None and hasattr(self._owner, "_dang_co_tac_vu"):
                busy = bool(self._owner._dang_co_tac_vu())
        except Exception:
            busy = False
        if not busy:
            self._on_install_done()
            return
        self._schedule_poll_busy()

    def _on_install_done(self):
        if not self.winfo_exists():
            return
        self._dang_cai = False
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None

        # BUG CU: truoc day ham nay chi goi _set_install_ui_state(installing=False),
        # ma ham do lai dat text = self._nhan_nut_hien_tai - la nhan da tinh TRUOC
        # khi cai (vi du "Cai dat"). Vi installed_info khong duoc lam moi nen nut
        # luon quay lai chu "Cai dat" du da cai xong thanh cong.
        # Fix: truy lai trang thai da cai moi nhat roi tinh lai nhan nut truoc khi
        # rebuild UI.
        if self._loai and self._pid:
            ten_inst = None
            if self._instance_ctl:
                try:
                    ten_inst = self._instance_ctl["get"]()
                except Exception:
                    ten_inst = None
            try:
                self._installed_info = lay_trang_thai_da_cai(
                    self._loai, self._source, self._pid, ten_instance=ten_inst)
            except Exception:
                pass
            self._cap_nhat_nhan_nut_cai_dat()

        try:
            self._set_install_ui_state(installing=False)
        except tk.TclError:
            pass

    def update_progress(self, da, tong, label_text=None):
        if not self.winfo_exists():
            return
        try:
            pct = 0 if not tong else max(0, min(100, int(da / tong * 100)))
            self._progress_var.set(pct)
            self.lbl_progress_pct.configure(text=label_text if label_text else f"{pct}%")
        except (tk.TclError, ZeroDivisionError):
            pass

    def _set_install_ui_state(self, installing):
        if installing:
            self.btn_install.configure(
                text="✕  Hủy", bg="#E53935", activebackground="#E53935",
                state="normal")
            try:
                self.cbo_ver.configure(state="disabled")
            except tk.TclError:
                pass
            self.pb_install.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self.lbl_progress_pct.grid(row=0, column=1, sticky="w")
            self.lbl_cancel_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        else:
            self.btn_install.configure(
                text=self._nhan_nut_hien_tai, bg=self._accent, activebackground=self._accent,
                state="normal")
            try:
                self.cbo_ver.configure(state="readonly")
            except tk.TclError:
                pass
            self.pb_install.grid_remove()
            self.lbl_progress_pct.grid_remove()
            self.lbl_cancel_hint.grid_remove()
