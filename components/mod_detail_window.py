"""
mod_detail_window.py
--------------------
Panel xem thong tin chi tiet cua mot Mod / Modpack / Resource Pack / Shader.
Duoc nhung truc tiep vao tab tuong ung trong ModMcWindow (View Switching)
khi nguoi dung double-click vao mot dong trong ContentTableWidget - thay the
ban danh sach bang panel chi tiet, khong mo cua so rieng.

Hien thi:
  - Anh banner / icon (lon)
  - Tieu de, tac gia, so luot tai, mo ta ngan
  - Combobox chon phien ban
  - Tab "Changelog" cua phien ban dang chon
  - Nut "← Quay lai danh sach" -> goi on_back() de container chuyen ve view danh sach
  - Nut "Cai dat" -> goi install_callback(version_data) roi tu quay lai danh sach

Tuong thich ca Modrinth lan CurseForge.
"""

import io
import html
import threading
import urllib.request

import tkinter as tk
from tkinter import ttk, messagebox

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

# ---------------------------------------------------------------
# Helper: tai anh tu URL -> PhotoImage (chay trong thread phu)
# ---------------------------------------------------------------

def _fetch_image(url, size=(500, 180)):
    """Tra ve PhotoImage hoac None neu loi / khong co PIL."""
    if not url or not _PIL_OK:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MODRINTH_UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        # Giu ty le, fit vao size
        img.thumbnail(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def _strip_md(text):
    """Loai bo mot so markdown don gian de hien thi trong Text widget."""
    import re
    # Bo header ##
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Bo **bold** va *italic*
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    # Bo [link](url)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Bo HTML tags co ban
    text = re.sub(r"<[^>]+>", "", text)
    # Giai ma HTML entities
    text = html.unescape(text)
    return text.strip()


# ---------------------------------------------------------------
# CUA SO CHINH
# ---------------------------------------------------------------

class ModDetailWindow(tk.Frame):
    """
    Panel thong tin chi tiet mod - nhung truc tiep vao tab (View Switching),
    thay the cho cua so popup truoc day.

    Parameters
    ----------
    parent       : tk widget cha - frame chua se duoc pack panel nay vao
                   (vd: detail-view container cua mot tab trong ModMcWindow)
    source       : 'modrinth' | 'curseforge'
    data         : dict du lieu cua mod (1 phan tu tu API)
    versions_raw : list phien ban da tai truoc (co the rong -> se tai them)
    install_cb   : callable(version_data, on_done=None, progress_cb=None) -> goi
                   khi nhan "Cai dat". version_data la dict phien ban dang chon.
                   Ben goi (mod_mc.py / modrinthmod.py / forgemod.py) PHAI tu
                   goi on_done() khi tac vu tai/cai dat ket thuc - du la thanh
                   cong, loi, hay bi huy - de panel nay biet duong ma doi nut
                   "Huy" tro lai thanh "Cai dat". Neu duoc cung cap progress_cb,
                   ben goi nen goi progress_cb(da, tong) de cap nhat thanh %.
    on_back      : callable() -> goi khi nguoi dung nhan "Quay lai danh sach"
                   (de container chuyen view tro lai bang danh sach)
    cancel_cb    : callable() -> goi khi nguoi dung nhan nut "Huy" trong luc
                   dang cai dat (thuong la self._huy_tac_vu cua ModMcWindow/
                   ModMcFrame - se tu hoi xac nhan va set _cancel_event).
                   Neu None, nut se khong chuyen thanh "Huy" duoc.
    accent       : mau accent (hex string)
    """

    def __init__(self, parent, source, data, versions_raw,
                 install_cb, on_back=None, cancel_cb=None, accent="#1E88E5"):
        super().__init__(parent)
        self._source   = source
        self._data     = data
        self._versions = list(versions_raw) if versions_raw else []
        self._install_cb = install_cb
        self._on_back   = on_back
        self._cancel_cb = cancel_cb
        self._accent   = accent
        self._banner_photo = None   # giu ref tranh GC
        self._dang_cai  = False     # True trong luc cho install_cb hoan tat

        # --- Lay thong tin co ban ---
        if source == "modrinth":
            self._title   = data.get("title", "")
            self._author  = data.get("author", "")
            self._desc    = data.get("description", "")
            self._dl      = data.get("downloads", 0)
            self._icon_url  = data.get("icon_url", "")
            self._pid     = data.get("project_id", data.get("slug", ""))
            # Gallery: list cac anh chi tiet (modpack / resource pack / shader...)
            gallery = data.get("gallery") or []
            self._gallery_urls = [
                g.get("url", "") for g in gallery if isinstance(g, dict) and g.get("url")
            ]
        else:  # curseforge
            self._title   = data.get("name", "")
            authors       = data.get("authors", [])
            self._author  = authors[0].get("name", "") if authors else ""
            self._desc    = data.get("summary", "")
            self._dl      = data.get("downloadCount", 0)
            logo          = data.get("logo") or {}
            self._icon_url = (logo.get("url", "") or
                              logo.get("thumbnailUrl", ""))
            self._pid     = data.get("id", "")
            # Gallery: screenshots cua CurseForge
            shots = data.get("screenshots") or []
            self._gallery_urls = [
                s.get("url", "") or s.get("thumbnailUrl", "")
                for s in shots if isinstance(s, dict)
            ]
            self._gallery_urls = [u for u in self._gallery_urls if u]

        self._gallery_photos = []   # giu ref PhotoImage tranh GC
        self._gallery_big_photo = None

        self._build_ui()
        self._load_banner()
        self._load_gallery()

        # Neu chua co phien ban -> tai ngay
        if not self._versions:
            self._load_versions_async()
        else:
            self._fill_versions(self._versions)

    # ------------------------------------------------------------------
    # BUILD UI
    # ------------------------------------------------------------------

    # Chieu rong icon khi cua so du rong (px)
    _ICON_FULL  = 96   # hien icon day du
    _ICON_SMALL = 48   # thu nho khi cua so hep
    _HIDE_ICON_BELOW = 340  # an han icon neu qua hep

    def _build_ui(self):
        # Lay mau tu theme hien tai (dark / light)
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

        # Toan bo layout chinh dung grid de kiem soat row expand chinh xac:
        #   row 0 - nut quay lai          (co dinh, khong expand)
        #   row 1 - panel anh + thong tin (co dinh)
        #   row 2 - separator             (co dinh)
        #   row 3 - chon phien ban        (co dinh)
        #   row 4 - notebook changelog    (EXPAND - chiem phan con lai)
        #   row 5 - thanh nut cai dat     (co dinh, luon o day)
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

        # === ROW 0: NUT QUAY LAI ===
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

        # === ROW 1: PANEL TREN - anh + thong tin ===
        self._top = tk.Frame(self, bg=BG)
        self._top.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 6))
        self._top.columnconfigure(1, weight=1)

        # Icon (cot 0) - an/hien theo chieu rong
        self._icon_cell = tk.Frame(self._top, bg=BG)
        self._icon_cell.grid(row=0, column=0, padx=(0, 12), sticky="nw")

        self.lbl_banner = tk.Label(
            self._icon_cell, bg=ICON_BG,
            width=self._ICON_FULL // 8,
            height=self._ICON_FULL // 16,
            relief="flat", bd=0)
        self.lbl_banner.pack()

        # Thong tin (cot 1)
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

        # === ROW 2: SEPARATOR ===
        ttk.Separator(self, orient="horizontal").grid(
            row=2, column=0, sticky="ew", padx=12, pady=6)

        # === ROW 3: CHON PHIEN BAN ===
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

        # === ROW 4: NOTEBOOK changelog (expand de lap day phan con lai) ===
        self.nb = ttk.Notebook(self)
        self.nb.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 0))

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

        # === TAB "Hinh anh" (gallery anh modpack / resource pack / shader) ===
        tab_gallery = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_gallery, text="  Hình ảnh  ")

        # Khung xem anh lon (hien khi click vao thumbnail)
        self._gal_big_frame = tk.Frame(tab_gallery, bg=BG)
        self._gal_big_frame.pack(fill="x", padx=4, pady=(4, 0))

        self.lbl_gallery_big = tk.Label(
            self._gal_big_frame, bg=ICON_BG, relief="flat", bd=0)
        self.lbl_gallery_big.pack()
        self._gal_big_frame.pack_forget()  # an cho den khi co anh duoc chon

        # Khung cuon chua cac thumbnail
        gal_outer = tk.Frame(tab_gallery, bg=BG)
        gal_outer.pack(fill="both", expand=True, padx=4, pady=4)

        self._gal_canvas = tk.Canvas(gal_outer, bg=BG, highlightthickness=0)
        gal_sb = ttk.Scrollbar(gal_outer, orient="vertical",
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
            self._gal_inner, text="Đang tải hình ảnh..." if self._gallery_urls
            else "Mod này chưa có hình ảnh nào.",
            font=("Arial", 9, "italic"), fg=FG_SUB, bg=BG)
        self.lbl_gallery_status.pack(anchor="w", padx=8, pady=8)

        # === ROW 5: THANH NUT CAI DAT (co dinh o day) ===
        btn_bar = tk.Frame(self, bg=BG)
        btn_bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(6, 12))
        btn_bar.columnconfigure(0, weight=1)

        # Thanh tien trinh - an khi khong cai dat, hien khi dang cai
        self._progress_var = tk.DoubleVar(value=0)
        self.pb_install = ttk.Progressbar(
            btn_bar, orient="horizontal", mode="determinate",
            variable=self._progress_var, maximum=100, length=200)
        # Se duoc grid() vao row=0 khi bat dau cai (xem _set_install_ui_state)

        self.lbl_progress_pct = tk.Label(
            btn_bar, text="", font=("Arial", 9, "bold"),
            fg=self._accent, bg=BG)
        # Cung chi grid() khi dang cai

        row_btn = tk.Frame(btn_bar, bg=BG)
        row_btn.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self.btn_install = tk.Button(
            row_btn, text="⬇  Cài đặt",
            font=("Arial", 10, "bold"),
            bg=self._accent, fg="white",
            activebackground=self._accent, activeforeground="white",
            relief="flat", padx=16, pady=6,
            command=self._on_install_or_cancel)
        self.btn_install.pack(side="left", padx=(0, 8))

        self.lbl_detail_status = tk.Label(
            row_btn, text="", font=("Arial", 9, "italic"),
            fg=self._accent, bg=BG, anchor="w")
        self.lbl_detail_status.pack(side="left", padx=12)

        # Goi y dung nut Huy o status bar chinh - chi hien trong luc dang cai
        self.lbl_cancel_hint = tk.Label(
            btn_bar, text="💡 Muốn hủy? Dùng nút Hủy ở thanh trạng thái phía dưới cùng.",
            font=("Arial", 8, "italic"), fg=FG_SUB, bg=BG, anchor="w")
        # Chi grid() khi dang cai (xem _set_install_ui_state)

        # Goi apply_theme ngay sau khi build xong de dong bo mau voi toan bo app
        if _theme:
            _theme.apply_theme(self)

        # Bind resize de tu dong dieu chinh wraplength + hien/an icon
        self.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    # TAI ANH BANNER
    # ------------------------------------------------------------------

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
        self._banner_photo = photo  # giu ref
        try:
            self.lbl_banner.configure(image=photo, width=photo.width(),
                                       height=photo.height())
            self.lbl_banner.image = photo
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # TAI GALLERY ANH (modpack / resource pack / shader...)
    # ------------------------------------------------------------------

    _GAL_THUMB_SIZE = (140, 90)

    def _load_gallery(self):
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
        # Xoa label trang thai "Dang tai..."
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

        # Hien thi thumbnail dang luoi (wrap nhieu dong) bang grid
        cols = 3
        for i, (url, photo) in enumerate(ok_results):
            self._gallery_photos.append(photo)  # giu ref tranh GC
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
        """Phong to anh duoc click trong tab Hinh anh (khong mo cua so moi)."""
        def _t():
            photo = _fetch_image(url, size=(640, 360))
            if photo:
                self._safe_after(lambda: self._set_gallery_big(photo))

        threading.Thread(target=_t, daemon=True).start()

    def _set_gallery_big(self, photo):
        self._gallery_big_photo = photo  # giu ref
        try:
            self.lbl_gallery_big.configure(image=photo)
            self.lbl_gallery_big.image = photo
            self._gal_big_frame.pack(fill="x", padx=4, pady=(4, 0))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # RESPONSIVE RESIZE
    # ------------------------------------------------------------------

    def _on_resize(self, event=None):
        """Goi moi khi panel thay doi chieu rong.
        - An / hien icon ben trai.
        - Cap nhat wraplength cho label title va desc.
        """
        try:
            w = self.winfo_width()
        except Exception:
            return

        ICON_COL = self._ICON_FULL + 12   # rong icon + khoang cach

        if w < self._HIDE_ICON_BELOW:
            # An han icon, danh toan bo chieu rong cho text
            self._icon_cell.grid_remove()
            info_w = max(w - 40, 60)
        else:
            # Hien icon
            self._icon_cell.grid()
            info_w = max(w - 40 - ICON_COL, 60)

        # Cap nhat wraplength dong
        self.lbl_title.configure(wraplength=info_w)
        self._lbl_desc.configure(wraplength=info_w)

    # ------------------------------------------------------------------
    # TAI PHIEN BAN
    # ------------------------------------------------------------------

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
        """
        Lap lich chay fn() tren main thread, nhung chi neu panel nay
        van con ton tai. Tranh loi khi nguoi dung bam 'Quay lai danh sach'
        truoc khi tac vu tai du lieu nen (banner / versions) hoan tat.
        """
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

    def _fill_versions(self, versions):
        if not versions:
            self.cbo_ver.set("Không có phiên bản")
            self.lbl_detail_status.config(text="", fg=self._accent)
            return

        if self._source == "modrinth":
            labels = [
                f"{v.get('name','?')}  —  MC {', '.join(v.get('game_versions',[]))}"
                for v in versions
            ]
        else:
            labels = [
                f"{fi.get('displayName', fi.get('fileName',''))}  —  MC {', '.join(fi.get('gameVersions',[]))}"
                for fi in versions
            ]

        self.cbo_ver.config(values=labels)
        self.cbo_ver.set(labels[0])
        self.lbl_detail_status.config(text="", fg=self._accent)
        self._show_changelog(0)

    # ------------------------------------------------------------------
    # CHANGELOG
    # ------------------------------------------------------------------

    def _on_ver_selected(self, event=None):
        idx = self.cbo_ver.current()
        if idx >= 0:
            self._show_changelog(idx)

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

    def _set_changelog(self, text):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.insert("1.0", text)
        self.txt_log.config(state="disabled")
        self.txt_log.yview_moveto(0)

    # ------------------------------------------------------------------
    # CAI DAT
    # ------------------------------------------------------------------

    def _go_back(self):
        """Goi khi nguoi dung nhan nut 'Quay lai danh sach'.
        Cho phep quay lai NGAY CA KHI dang cai dat - tien trinh van tiep tuc
        chay ngam (giong tinh thần can_switch() luon True cua mod_mc.py).
        progress_cb/on_done deu da tu kiem tra winfo_exists() truoc khi dong
        vao widget, nen an toan khi panel nay bi destroy giua luc dang cai."""
        if self._on_back:
            self._on_back()

    def _on_install_or_cancel(self):
        """Bam nut nay khi CHUA cai -> bat dau cai dat, nut tu disable.
        Khong con vai tro 'Huy' tren nut nay nua - de huy mot tac vu dang
        chay, nguoi dung dung nut Huy o thanh trang thai chinh (status bar
        duoi cung cua mod_mc.py), vi do la noi quan ly tac vu duy nhat va
        dang hoat dong dung/on dinh nhat trong app."""
        if self._dang_cai:
            return  # nut da disable nen binh thuong khong vao day duoc

        idx = self.cbo_ver.current()
        if idx < 0 or not self._versions:
            return
        vd = self._versions[idx]

        self._dang_cai = True
        self._progress_var.set(0)
        self.lbl_progress_pct.configure(text="")
        self._set_install_ui_state(installing=True)
        # KHONG quay lai danh sach ngay - panel o lai de nguoi dung theo doi
        # % tien do, nhung van co the bam "Quay lai danh sach" bat cu luc nao.
        self._install_cb(vd, on_done=self._on_install_done, progress_cb=self.update_progress)

    def _on_install_done(self):
        """Goi boi ben cai dat thuc su (mod_mc.py / modrinthmod.py / forgemod.py)
        khi tac vu tai/cai dat ket thuc - du thanh cong, loi, hay bi huy.
        An toan khi panel da bi destroy (vd nguoi dung da dong cua so)."""
        if not self.winfo_exists():
            return
        self._dang_cai = False
        try:
            self._set_install_ui_state(installing=False)
        except tk.TclError:
            pass

    def update_progress(self, da, tong, label_text=None):
        """Cap nhat thanh tien trinh % - goi boi ben cai dat thuc su qua
        progress_cb(da, tong, label_text=None). 'da'/'tong' dung de tinh % cho
        thanh progressbar (luon theo thang 0-100, vi du so mod da cai/tong so
        mod cho Modpack, hoac % byte da tai cho Mod/RSP/Shader le).
        'label_text' tuy chon - neu duoc truyen se hien thi thay cho '{pct}%'
        (vi du '12/45 mod' cho Modpack). An toan khi panel da bi destroy."""
        if not self.winfo_exists():
            return
        try:
            pct = 0 if not tong else max(0, min(100, int(da / tong * 100)))
            self._progress_var.set(pct)
            self.lbl_progress_pct.configure(text=label_text if label_text else f"{pct}%")
        except (tk.TclError, ZeroDivisionError):
            pass

    def _set_install_ui_state(self, installing):
        """Cap nhat giao dien nut Cai dat (disable luc dang cai, KHONG doi
        thanh nut Huy nua) va thanh tien trinh. Nut 'Quay lai danh sach'
        luon duoc giu o trang thai 'normal', khong bi khoa."""
        if installing:
            self.btn_install.configure(
                text="⏳ Đang cài...", bg="#78909C", activebackground="#78909C",
                state="disabled")
            try:
                self.cbo_ver.configure(state="disabled")
            except tk.TclError:
                pass
            self.pb_install.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self.lbl_progress_pct.grid(row=0, column=1, sticky="w")
            self.lbl_cancel_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        else:
            self.btn_install.configure(
                text="⬇  Cài đặt", bg=self._accent, activebackground=self._accent,
                state="normal")
            try:
                self.cbo_ver.configure(state="readonly")
            except tk.TclError:
                pass
            self.pb_install.grid_remove()
            self.lbl_progress_pct.grid_remove()
            self.lbl_cancel_hint.grid_remove()