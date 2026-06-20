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
from tkinter import ttk

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
    install_cb   : callable(version_data) -> goi khi nhan "Cai dat"
                   version_data la dict phien ban dang chon
    on_back      : callable() -> goi khi nguoi dung nhan "Quay lai danh sach"
                   (de container chuyen view tro lai bang danh sach)
    accent       : mau accent (hex string)
    """

    def __init__(self, parent, source, data, versions_raw,
                 install_cb, on_back=None, accent="#1E88E5"):
        super().__init__(parent)
        self._source   = source
        self._data     = data
        self._versions = list(versions_raw) if versions_raw else []
        self._install_cb = install_cb
        self._on_back   = on_back
        self._accent   = accent
        self._banner_photo = None   # giu ref tranh GC

        # --- Lay thong tin co ban ---
        if source == "modrinth":
            self._title   = data.get("title", "")
            self._author  = data.get("author", "")
            self._desc    = data.get("description", "")
            self._dl      = data.get("downloads", 0)
            self._icon_url  = data.get("icon_url", "")
            self._pid     = data.get("project_id", data.get("slug", ""))
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

        self._build_ui()
        self._load_banner()

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
        tk.Button(
            back_bar, text="←  Quay lại danh sách",
            font=("Arial", 9, "bold"),
            bg="#78909C", fg="white",
            activebackground="#607D8B", activeforeground="white",
            relief="flat", padx=10, pady=4,
            command=self._go_back).pack(side="left")

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

        # === ROW 5: THANH NUT CAI DAT (co dinh o day) ===
        btn_bar = tk.Frame(self, bg=BG)
        btn_bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(6, 12))

        self.btn_install = tk.Button(
            btn_bar, text="⬇  Cài đặt",
            font=("Arial", 10, "bold"),
            bg=self._accent, fg="white",
            activebackground=self._accent, activeforeground="white",
            relief="flat", padx=16, pady=6,
            command=self._on_install)
        self.btn_install.pack(side="left", padx=(0, 8))

        self.lbl_detail_status = tk.Label(
            btn_bar, text="", font=("Arial", 9, "italic"),
            fg=self._accent, bg=BG, anchor="w")
        self.lbl_detail_status.pack(side="left", padx=12)

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
        """Goi khi nguoi dung nhan nut 'Quay lai danh sach'."""
        if self._on_back:
            self._on_back()

    def _on_install(self):
        idx = self.cbo_ver.current()
        if idx < 0 or not self._versions:
            return
        vd = self._versions[idx]
        self._go_back()
        self._install_cb(vd)