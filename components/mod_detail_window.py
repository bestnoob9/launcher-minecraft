import io
import re
import html
import threading
import urllib.request
import webbrowser

import tkinter as tk
from tkinter import ttk, messagebox

from components.install_utils import lay_trang_thai_da_cai, xoa_file_theo_ten
from components.widgets import _dinh_dang_so_luot, _dinh_dang_dung_luong

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

# Ten loader (viet thuong) can loai khoi danh sach "Game Versions" khi doc
# gameVersions cua CurseForge - field nay tron lan ca MC version lan ten
# loader trong cung 1 mang (vd ["1.20.1", "Forge"]).
_TEN_LOADER_BIET = {"forge", "fabric", "quilt", "neoforge", "vanilla",
                     "liteloader", "rift"}

def _ver_sort_key(s):
    """Khoa sap xep phien ban MC kieu '1.20.1' -> (1,20,1) de sap xep dung
    thu tu so hoc thay vi thu tu chuoi (vd '1.9' dung truoc '1.10')."""
    parts = re.findall(r"\d+", s or "")
    return tuple(int(p) for p in parts) if parts else (0,)

def _fmt_ngay_full(chuoi_iso):
    """Dinh dang 1 chuoi ngay ISO (vd '2026-08-20T12:00:00Z') thanh dd/mm/yyyy
    de hien trong bang phien ban - khac voi _dinh_dang_ngay_tuong_doi (dang
    'X ngay truoc') dung trong danh sach duyet mod, o day can ngay tuyet doi
    ro rang de nguoi dung so sanh cac phien ban voi nhau."""
    if not chuoi_iso:
        return ""
    try:
        d = chuoi_iso[:10]
        y, m, day = d.split("-")
        return f"{day}/{m}/{y}"
    except Exception:
        return chuoi_iso[:10] if len(chuoi_iso) >= 10 else chuoi_iso

class ModDetailWindow(tk.Frame):

    def __init__(self, parent, source, data, versions_raw,
                 install_cb, on_back=None, cancel_cb=None, accent="#1E88E5",
                 installed_info=None, instance_ctl=None, loai=None):
        super().__init__(parent)
        self._source   = source
        self._data     = data
        self._versions = list(versions_raw) if versions_raw else []
        self._ver_idx_map = list(range(len(self._versions)))
        # Trang thai bang chon phien ban (thay the combobox cu):
        self._selected_ver_idx = -1     # index THAT trong self._versions
        self._ver_filter_gv = "Tất cả"      # bo loc "Game Versions" dang chon
        self._ver_filter_loader = "Tất cả"  # bo loc "Mod Loaders" dang chon
        self._ver_page = 1
        self._ver_per_page = 20
        self._ver_row_widgets = []      # widget cua cac dong dang ve, de don dep
        self._ver_filters_locked = False  # dang khoa 2 bo loc theo Instance?
        self._ver_bao_loi = ""            # thong bao loi hien trong bang (vd Instance Vanilla)
        self._install_cb = install_cb
        # loai: "modpack" / "mods" / "resourcepacks" / "shaderpacks" - can de
        # sau khi cai xong co the tu truy lai trang thai da cai moi nhat.
        self._loai = loai
        self._on_back   = on_back
        self._cancel_cb = cancel_cb
        self._accent   = accent
        self._banner_photo = None
        self._dang_cai  = False
        self._dang_yeu_cau_huy = False  # da bam Huy va DANG CHO backend dung han

        # instance_ctl: dict {"get_list", "get", "set"} cho phep chon Instance de
        # cai vao ngay trong man hinh chi tiet. Modpack khong dung (tao instance moi
        # nen khong truyen instance_ctl khi mo ModDetailWindow cho modpack).
        self._instance_ctl = instance_ctl
        self.cbo_inst = None

        self._installed_info = installed_info
        self._nhan_nut_hien_tai = "⬇  Cài đặt"

        self._owner = getattr(cancel_cb, "__self__", None)
        self._poll_after_id = None
        self._resize_after_id = None
        self._last_resize_w  = None

        if source == "modrinth":
            self._title   = data.get("title", "")
            self._author  = data.get("author", "")
            self._desc    = data.get("description", "")
            self._dl      = data.get("downloads", 0)
            self._icon_url  = data.get("icon_url", "")
            self._pid     = data.get("project_id", data.get("slug", ""))
            self._project_url = f"https://modrinth.com/project/{self._pid}" if self._pid else ""

            # QUAN TRONG: Modrinth tra ve "gallery" o 2 DANG KHAC NHAU tuy API:
            #  - Ket qua tim kiem (/v2/search, chinh la 'data' o day khi mo tu
            #    danh sach): gallery la MANG CHUOI URL (vd ["https://...",..]).
            #  - Trang chi tiet day du (/v2/project/{id}): gallery la MANG
            #    OBJECT {url, featured, title,...}.
            # Code cu chi nhan dang object nen khi mo tu danh sach (dang chuoi)
            # bi loc rong het, ĐỒNG THỜI van tat _gallery_pending (vi key
            # "gallery" van co mat, du la mang chuoi) -> khong bao gio goi
            # sang trang chi tiet de lay anh that -> luon hien "chua co hinh
            # anh nao" ke ca khi mod thuc su co gallery. Sua: nhan ca 2 dang,
            # va CHI coi la "da co du lieu" (khong can fetch them) khi thuc su
            # trich ra duoc it nhat 1 URL hop le.
            gallery = data.get("gallery") or []
            self._gallery_urls = []
            self._gallery_big_urls = []
            for g in gallery:
                if isinstance(g, dict):
                    u = g.get("url", "")
                    big = g.get("raw_url", "") or u
                elif isinstance(g, str):
                    u = g
                    big = g
                else:
                    u, big = "", ""
                if u:
                    self._gallery_urls.append(u)
                    self._gallery_big_urls.append(big)
            self._gallery_pending = not self._gallery_urls

            self._desc_full = data.get("body") or self._desc
            self._desc_pending = False
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
            # Uu tien thumbnailUrl (ban da resize san, nhe) cho luoi thumbnail
            # nho 140x90px - anh goc "url" (co the vai MB) chi tai khi nguoi
            # dung bam vao xem anh lon (_gallery_big_urls). Truoc day lay
            # nguoc lai (uu tien "url") nen luoi gallery nho phai tai anh goc
            # rat nang, gay cham ro ret voi CurseForge.
            self._gallery_urls = []
            self._gallery_big_urls = []
            for s in shots:
                if not isinstance(s, dict):
                    continue
                thumb = s.get("thumbnailUrl", "") or s.get("url", "")
                big   = s.get("url", "") or s.get("thumbnailUrl", "")
                if thumb:
                    self._gallery_urls.append(thumb)
                    self._gallery_big_urls.append(big)

            # Mod object cua CurseForge KHONG co field "description" day du
            # (chi co "summary" ngan 1-2 cau) - phai goi rieng API
            # /v1/mods/{id}/description de lay HTML day du. Truoc day code
            # doc nham data.get("description") (luon rong/None voi du lieu
            # that) nen tab mo ta chi hien lai dung cai summary ngan, chua
            # bao gio la mo ta that. Hien summary tam trong luc cho, roi tai
            # ngam mo ta day du (xem _fetch_curseforge_desc_then_render).
            self._desc_full = self._desc
            self._desc_pending = True

        self._gallery_photos = []
        self._gallery_big_photo = None

        self._build_ui()
        self._load_banner()
        self._load_gallery()
        if self._source == "curseforge" and self._desc_pending:
            self._fetch_curseforge_desc_then_render()

        if not self._versions:
            self._load_versions_async()
        else:
            self._fill_versions(self._versions)

        self._dong_bo_trang_thai_ban_dau()

    def _id_tac_vu_cua_minh(self):
        """Dinh danh (loai, source, project_id) cua CHINH muc dang hien thi
        trong cua so nay - dung de doi chieu voi owner._tac_vu_hien_tai_id/
        owner._hang_doi_cai, tranh nham lan voi tac vu cua 1 muc KHAC."""
        return (self._loai, self._source, self._pid)

    def _dong_bo_tien_do_tu_owner(self):
        """Doc tien do (%) va nhan (label) MOI NHAT ma owner biet duoc (owner
        luu lai qua ghi_tien_do() moi lan co 1 chunk tai xong) va ap vao
        thanh progress + nhan % cua CHINH cua so nay.

        Can thiet vi: thanh progress chi tu cap nhat REAL-TIME qua tham so
        progress_cb ma _install_cb() nhan duoc - nhung progress_cb do CHI
        duoc noi voi cua so DA BAM "Cai dat" luc dau. Neu nguoi dung dong
        cua so chi tiet roi mo lai (hoac mo chi tiet 1 muc dang duoc tai tu
        1 luong khac), cua so MOI nay khong he co progress_cb that, nen
        thanh progress se dung im o 0% vinh vien du tac vu van dang chay
        binh thuong o "hau truong" - day la loi "thanh chua dong bo" duoc
        bao cao. Sua bang cach doc lai tien do da luu o owner (dung chung
        nguon voi nhan trang thai lbl_status) moi 400ms qua _poll_busy."""
        if self._owner is None:
            return
        try:
            pct = getattr(self._owner, "_last_progress_pct", None)
            if pct is None:
                return
            label = getattr(self._owner, "_last_progress_label", "") or f"{pct}%"
            self._progress_var.set(pct)
            self.lbl_progress_pct.configure(text=label)
        except Exception:
            pass

    def _bao_dang_huy(self):
        """Phan hoi NGAY LAP TUC tren nut khi nguoi dung da XAC NHAN huy tac
        vu dang chay that su - tranh cam giac nut Huy "khong an thua/lau",
        vi backend (dac biet modpack nhieu file tai song song) co the mat
        khoang 1-2s de tat het cac luong tai dang chay roi don dep xong,
        trong luc do tien do/nhan cu se dung im neu khong bao hieu gi them."""
        self._dang_yeu_cau_huy = True
        try:
            self.btn_install.configure(
                text="⏳  Đang hủy...", state="disabled",
                bg="#9e9e9e", activebackground="#9e9e9e")
            self.lbl_cancel_hint.configure(
                text="💡 Đang hủy tác vụ, vui lòng đợi trong giây lát...")
        except tk.TclError:
            pass

    def _trang_thai_hang_doi(self):
        """Cho biet CHINH muc dang xem co lien quan gi den tac vu tai/cai
        hien tai khong:
          - "active": muc nay dang duoc tai/cai THAT SU ngay luc nay.
          - "queued": muc nay da bam Cai dat nhung dang CHO trong hang doi
            (co tac vu KHAC dang chay truoc).
          - None: muc nay khong lien quan gi den tac vu dang chay/dang cho
            nao ca (co the co tac vu KHAC dang chay o cua so khac, nhung
            khong phai muc nay - truong hop nay TUYET DOI khong duoc hien
            "dang cai + nut Huy", vi bam Huy se huy nham tac vu that su
            dang chay o noi khac).
        """
        if self._owner is None:
            return None
        my_id = self._id_tac_vu_cua_minh()
        try:
            active_id = getattr(self._owner, "_tac_vu_hien_tai_id", None)
        except Exception:
            active_id = None
        if active_id is not None and active_id == my_id:
            return "active"
        try:
            hang_doi = getattr(self._owner, "_hang_doi_cai", None) or []
            for entry in hang_doi:
                if len(entry) > 2 and entry[2] == my_id:
                    return "queued"
        except Exception:
            pass
        return None

    def _dong_bo_trang_thai_ban_dau(self):
        if self._owner is None or not hasattr(self._owner, "_dang_co_tac_vu"):
            return
        # QUAN TRONG: truoc day cho nay chi kiem tra "co tac vu NAO DO dang
        # chay o dau khong" (owner._dang_co_tac_vu()) roi hien LUON UI "dang
        # cai + nut Huy" cho CUA SO NAY neu co - bat ke tac vu do co phai la
        # chinh muc dang xem hay khong. Hau qua: mo chi tiet 1 modpack/shader
        # KHAC trong luc dang tai 1 mod/modpack khac se bi hien nham thanh
        # "dang cai", va bam nut Huy se HUY NHAM tac vu that su dang chay o
        # noi khac chu khong phai muc dang xem. Sua: chi coi la "active" khi
        # dinh danh tac vu dang chay TRUNG KHOP voi chinh muc nay.
        trang_thai = self._trang_thai_hang_doi()
        if trang_thai == "active":
            self._dang_cai = True
            self._set_install_ui_state(installing=True)
            self._dong_bo_tien_do_tu_owner()
            self._schedule_poll_busy()
        elif trang_thai == "queued":
            self._dang_cai = True
            self._set_install_ui_state(installing=False, queued=True)
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

        self.rowconfigure(3, weight=1)
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

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=3, column=0, sticky="nsew", padx=12, pady=(4, 0))

        tab_intro = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_intro, text="  Description  ")

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
        self._bind_wheel_tree(self._gal_canvas, self._on_gal_mousewheel)

        self.lbl_gallery_status = tk.Label(
            self._gal_inner,
            text="Đang tải hình ảnh..." if (self._gallery_urls or self._gallery_pending)
            else "Mod này chưa có hình ảnh nào.",
            font=("Arial", 9, "italic"), fg=FG_SUB, bg=BG)
        self.lbl_gallery_status.pack(anchor="w", padx=8, pady=8)
        self._bind_wheel_tree(self.lbl_gallery_status, self._on_gal_mousewheel)

        # Tab "Phien ban" - dat CANH tab Hinh anh, chua bang chon phien ban
        # kieu CurseForge (Type/Name/Game Versions/Mod Loaders/Size/
        # Downloads/Uploaded + nut tai) thay cho combobox cu, kem bo loc
        # Game Versions / Mod Loaders va phan trang. Phan chon Instance de
        # cai vao dat O DUOI bang.
        tab_ver = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab_ver, text="  Phiên bản  ")

        # --- Thanh bo loc (Game Versions / Mod Loaders) ---
        ver_filter_bar = tk.Frame(tab_ver, bg=BG)
        ver_filter_bar.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(ver_filter_bar, text="Game Versions", font=("Arial", 9),
                 bg=BG, fg=FG).pack(side="left", padx=(0, 4))
        self.cbo_ver_gv = ttk.Combobox(ver_filter_bar, font=("Arial", 9),
                                        state="readonly", width=14, values=["Tất cả"])
        self.cbo_ver_gv.set("Tất cả")
        self.cbo_ver_gv.pack(side="left", padx=(0, 16))
        self.cbo_ver_gv.bind("<<ComboboxSelected>>", self._on_ver_filter_changed)

        tk.Label(ver_filter_bar, text="Mod Loaders", font=("Arial", 9),
                 bg=BG, fg=FG).pack(side="left", padx=(0, 4))
        self.cbo_ver_loader = ttk.Combobox(ver_filter_bar, font=("Arial", 9),
                                            state="readonly", width=14, values=["Tất cả"])
        self.cbo_ver_loader.set("Tất cả")
        self.cbo_ver_loader.pack(side="left")
        self.cbo_ver_loader.bind("<<ComboboxSelected>>", self._on_ver_filter_changed)

        # Chon Instance de cai vao - dat NGAY CANH 2 bo loc tren, vi chon
        # Instance nao se KHOA cung 2 bo loc do theo dung MC version + Loader
        # cua Instance (xem _apply_instance_lock_to_filters).
        if self._instance_ctl:
            tk.Label(ver_filter_bar, text="Cài vào Instance", font=("Arial", 9),
                     bg=BG, fg=FG).pack(side="left", padx=(16, 4))
            self.cbo_inst = ttk.Combobox(ver_filter_bar, font=("Arial", 9),
                                          state="readonly", width=22)
            self.cbo_inst.pack(side="left", fill="x", expand=True)
            self._refresh_inst_list()
            self.cbo_inst.bind("<<ComboboxSelected>>", self._on_inst_selected)
            self.cbo_inst.bind("<ButtonPress>", self._refresh_inst_list)

        # --- Thanh "Hien thi X-Y trong Z ket qua" + "Moi trang" ---
        ver_info_bar = tk.Frame(tab_ver, bg=BG)
        ver_info_bar.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_ver_range = tk.Label(ver_info_bar, text="", font=("Arial", 9),
                                       bg=BG, fg=FG_SUB)
        self.lbl_ver_range.pack(side="left")

        tk.Label(ver_info_bar, text="Mỗi trang:", font=("Arial", 9),
                 bg=BG, fg=FG_SUB).pack(side="right", padx=(4, 4))
        self.cbo_ver_perpage = ttk.Combobox(
            ver_info_bar, font=("Arial", 9), state="readonly", width=4,
            values=["10", "20", "50", "100"])
        self.cbo_ver_perpage.set(str(self._ver_per_page))
        self.cbo_ver_perpage.pack(side="right")
        self.cbo_ver_perpage.bind("<<ComboboxSelected>>", self._on_ver_perpage_changed)

        # --- Bang phien ban (header co dinh + phan cuon ben duoi) ---
        ver_table_outer = tk.Frame(tab_ver, bg=BG, highlightthickness=1,
                                    highlightbackground=clr.get("icon_border", "#333"))
        # QUAN TRONG: truoc day pack(fill="both", expand=True) khien bang
        # chiem HET khong gian doc con lai cua tab - phan chon Instance dat
        # ben duoi bang (theo yeu cau truoc) vi vay bi day xuong ngoai vung
        # nhin cua cua so khi cua so chua duoc phong to. Gioi han chieu cao
        # bang co dinh (~6 dong, tu cuon rieng ben trong) de phan Instance +
        # phan trang o duoi LUON hien du, khong phu thuoc kich thuoc cua so.
        ver_table_outer.pack(fill="x", padx=8)

        self._ver_col_w = [34, 0, 150, 100, 70, 70, 80, 40]  # 0 = cot Name (co dan)

        self._ver_header = tk.Frame(ver_table_outer, bg=clr.get("bg_alt", "#20242c"))
        self._ver_header.pack(fill="x")
        for c in range(8):
            self._ver_header.columnconfigure(c, weight=(1 if c == 1 else 0),
                                              minsize=self._ver_col_w[c])
        for c, txt in enumerate(["", "Name", "Game Versions", "Mod Loaders",
                                  "Size", "Downloads", "Uploaded", ""]):
            tk.Label(self._ver_header, text=txt, font=("Arial", 8, "bold"),
                     bg=clr.get("bg_alt", "#20242c"), fg=FG_SUB, anchor="w"
                     ).grid(row=0, column=c, sticky="ew", padx=4, pady=4)

        self._ver_canvas = tk.Canvas(ver_table_outer, bg=BG, highlightthickness=0,
                                      height=190)
        ver_sb = ttk.Scrollbar(ver_table_outer, orient="vertical",
                                command=self._ver_canvas.yview)
        self._ver_canvas.configure(yscrollcommand=ver_sb.set)
        ver_sb.pack(side="right", fill="y")
        self._ver_canvas.pack(side="left", fill="both", expand=True)

        self._ver_table_inner = tk.Frame(self._ver_canvas, bg=BG)
        for c in range(8):
            self._ver_table_inner.columnconfigure(
                c, weight=(1 if c == 1 else 0), minsize=self._ver_col_w[c])
        self._ver_canvas.create_window((0, 0), window=self._ver_table_inner,
                                        anchor="nw", tags=("ver_inner",))
        self._ver_table_inner.bind(
            "<Configure>",
            lambda e: self._ver_canvas.configure(scrollregion=self._ver_canvas.bbox("all")))
        self._ver_canvas.bind(
            "<Configure>",
            lambda e: self._ver_canvas.itemconfigure("ver_inner", width=e.width))
        self._bind_wheel_tree(self._ver_canvas, self._on_ver_mousewheel)

        self.lbl_ver_status = tk.Label(
            self._ver_table_inner, text="Đang tải phiên bản...",
            font=("Arial", 9, "italic"), fg=FG_SUB, bg=BG)
        self.lbl_ver_status.grid(row=0, column=0, columnspan=8, sticky="w", padx=8, pady=8)
        self._ver_row_widgets = [self.lbl_ver_status]
        self._bind_wheel_tree(self.lbl_ver_status, self._on_ver_mousewheel)

        # --- Thanh phan trang ---
        ver_pg_bar = tk.Frame(tab_ver, bg=BG)
        ver_pg_bar.pack(fill="x", padx=8, pady=(4, 8))
        self.btn_ver_prev = tk.Button(
            ver_pg_bar, text="‹ Trước", font=("Arial", 8), relief="flat",
            bg=clr.get("bg_alt", "#20242c"), fg=FG, activeforeground=FG,
            command=self._ver_page_prev, state="disabled")
        self.btn_ver_prev.pack(side="left")
        self.lbl_ver_page = tk.Label(ver_pg_bar, text="", font=("Arial", 8),
                                      bg=BG, fg=FG_SUB)
        self.lbl_ver_page.pack(side="left", padx=8)
        self.btn_ver_next = tk.Button(
            ver_pg_bar, text="Sau ›", font=("Arial", 8), relief="flat",
            bg=clr.get("bg_alt", "#20242c"), fg=FG, activeforeground=FG,
            command=self._ver_page_next, state="disabled")
        self.btn_ver_next.pack(side="left")

        self.lbl_detail_status = tk.Label(
            tab_ver, text="", font=("Arial", 9, "italic"),
            fg=self._accent, bg=BG, anchor="w")
        self.lbl_detail_status.pack(fill="x", padx=8)

        btn_bar = tk.Frame(self, bg=BG)
        btn_bar.grid(row=4, column=0, sticky="ew", padx=16, pady=(6, 12))
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
            big_urls = []
            body = ""
            try:
                from components.api_helpers import lay_project_modrinth
                proj = lay_project_modrinth(self._pid)
                gallery = proj.get("gallery") or []
                for g in gallery:
                    if not isinstance(g, dict):
                        continue
                    u = g.get("url", "")
                    if not u:
                        continue
                    urls.append(u)
                    big_urls.append(g.get("raw_url", "") or u)
                body = proj.get("body") or ""
            except Exception:
                urls, big_urls = [], []
            self._safe_after(lambda: self._on_modrinth_gallery_fetched(urls, big_urls, body))

        threading.Thread(target=_t, daemon=True).start()

    def _on_modrinth_gallery_fetched(self, urls, big_urls=None, body=""):
        self._gallery_pending = False
        self._gallery_urls = urls
        self._gallery_big_urls = big_urls if big_urls is not None else list(urls)
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

    def _fetch_curseforge_desc_then_render(self):
        """Tai mo ta day du (HTML) cua mod CurseForge qua API rieng - Mod
        object goc chi co 'summary' ngan, khong co mo ta day du (xem ghi chu
        o __init__ va lay_mo_ta_curseforge trong api_helpers.py)."""
        def _t():
            body = ""
            try:
                from components.api_helpers import lay_mo_ta_curseforge
                body = lay_mo_ta_curseforge(self._pid)
            except Exception:
                body = ""
            self._safe_after(lambda: self._on_curseforge_desc_fetched(body))
        threading.Thread(target=_t, daemon=True).start()

    def _on_curseforge_desc_fetched(self, body):
        self._desc_pending = False
        if not body:
            return  # khong lay duoc (loi mang, mod khong co mo ta...) - giu
                     # nguyen summary ngan da hien san, khong ghi de bang rong.
        self._desc_full = body
        try:
            self._render_intro_async(body)
        except tk.TclError:
            pass

    # Gioi han so anh tai song song (giong pattern worker-pool cua _IconCache
    # trong widgets.py) - tranh mo qua nhieu ket noi cung luc, nhung van nhanh
    # hon rat nhieu so voi tai tuan tu tung anh mot nhu truoc.
    _GAL_MAX_WORKERS = 5

    def _load_gallery_thumbnails(self):
        urls = self._gallery_urls
        big_urls = self._gallery_big_urls if len(self._gallery_big_urls) == len(urls) else urls
        if not urls or not _PIL_OK:
            return

        def _t():
            import concurrent.futures
            results = [None] * len(urls)

            def _tai(i):
                results[i] = (big_urls[i], _fetch_image(urls[i], size=self._GAL_THUMB_SIZE))

            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(self._GAL_MAX_WORKERS, len(urls))) as ex:
                list(ex.map(_tai, range(len(urls))))

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
        self._bind_wheel_tree(self._gal_inner, self._on_gal_mousewheel)

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

    _RESIZE_DEBOUNCE_MS  = 160
    _RESIZE_MIN_DELTA_PX = 20

    def _on_resize(self, event=None):
        # Debounce: khi dang keo chuot de resize, <Configure> ban ra RAT NHIEU
        # lan lien tiep (moi vai pixel 1 lan). Gom lai, chi thuc su tinh toan
        # lai wraplength SAU KHI nguoi dung ngung keo mot chut (~60ms), thay vi
        # lam ngay lap tuc moi lan - day la nguyen nhan chinh gay giat/khung.
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.after(self._RESIZE_DEBOUNCE_MS, self._do_resize)

    def _do_resize(self):
        self._resize_after_id = None
        try:
            w = self.winfo_width()
        except Exception:
            return

        # Bo qua neu be rong gan nhu khong doi (rung tay / thay doi rat nho) -
        # tranh tinh toan lai wraplength mot cach thua thai.
        if (self._last_resize_w is not None
                and abs(w - self._last_resize_w) < self._RESIZE_MIN_DELTA_PX):
            return
        self._last_resize_w = w

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
        self.lbl_ver_status.configure(text="Đang tải phiên bản...")
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
                    self.lbl_ver_status.configure(text=f"Lỗi tải phiên bản: {e}"),
                    self.lbl_detail_status.config(text=f"Lỗi: {e}", fg="red")
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

    def _bind_wheel_tree(self, widget, handler):
        """Bind banh xe vao widget va moi con chau (Label/Button van cuon duoc)."""
        widget.bind("<MouseWheel>", handler)
        widget.bind("<Button-4>", handler)
        widget.bind("<Button-5>", handler)
        for child in widget.winfo_children():
            self._bind_wheel_tree(child, handler)

    def _on_ver_mousewheel(self, e):
        try:
            if not self._ver_canvas.winfo_ismapped():
                return
        except tk.TclError:
            return
        delta = getattr(e, "delta", 0)
        if delta:
            self._ver_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        num = getattr(e, "num", None)
        if num == 4:
            self._ver_canvas.yview_scroll(-3, "units")
        elif num == 5:
            self._ver_canvas.yview_scroll(3, "units")
        return "break"

    def _on_gal_mousewheel(self, e):
        try:
            if not self._gal_canvas.winfo_ismapped():
                return
        except tk.TclError:
            return
        delta = getattr(e, "delta", 0)
        if delta:
            self._gal_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        num = getattr(e, "num", None)
        if num == 4:
            self._gal_canvas.yview_scroll(-3, "units")
        elif num == 5:
            self._gal_canvas.yview_scroll(3, "units")
        return "break"

    def _lay_gv_loader(self, v):
        """Tra ve (danh sach MC version, danh sach loader) cua 1 phien ban -
        rieng cho CurseForge vi field 'gameVersions' cua no tron lan ca MC
        version lan ten loader trong CUNG 1 mang, phai tach ra dua theo
        _TEN_LOADER_BIET."""
        if self._source == "modrinth":
            return list(v.get("game_versions", []) or []), list(v.get("loaders", []) or [])
        gvs = list(v.get("gameVersions", []) or [])
        mc = [g for g in gvs if g.lower() not in _TEN_LOADER_BIET]
        lds = [g for g in gvs if g.lower() in _TEN_LOADER_BIET]
        return mc, lds

    def _lay_ver_type(self, v):
        if self._source == "modrinth":
            return (v.get("version_type") or "release").lower()
        rt = v.get("releaseType")
        return {1: "release", 2: "beta", 3: "alpha"}.get(rt, "release")

    def _lay_ver_ten(self, v):
        if self._source == "modrinth":
            return v.get("name") or v.get("version_number") or "?"
        return v.get("displayName") or v.get("fileName") or "?"

    def _lay_ver_size(self, v):
        if self._source == "modrinth":
            files = v.get("files", []) or []
            prim = next((f for f in files if f.get("primary")), files[0] if files else None)
            return (prim or {}).get("size")
        return v.get("fileLength")

    def _lay_ver_downloads(self, v):
        return v.get("downloads", 0) if self._source == "modrinth" else v.get("downloadCount", 0)

    def _lay_ver_ngay(self, v):
        return v.get("date_published", "") if self._source == "modrinth" else v.get("fileDate", "")

    def _build_ver_filter_options(self):
        gv_set, loader_set = set(), set()
        for v in self._versions:
            mc_list, loader_list = self._lay_gv_loader(v)
            gv_set.update(mc_list)
            loader_set.update(l.strip().title() for l in loader_list if l.strip())
        gv_opts = ["Tất cả"] + sorted(gv_set, key=_ver_sort_key, reverse=True)
        loader_opts = ["Tất cả"] + sorted(loader_set)
        self.cbo_ver_gv.configure(values=gv_opts)
        self.cbo_ver_loader.configure(values=loader_opts)
        return gv_opts, loader_opts

    def _lay_instance_mc_loader(self):
        if not self._instance_ctl:
            return None, None
        get_ml = self._instance_ctl.get("get_mc_loader")
        if not get_ml:
            return None, None
        try:
            return get_ml()
        except Exception:
            return None, None

    def _apply_instance_lock_to_filters(self, gv_opts=None, loader_opts=None):
        """Neu dang chon 1 Instance cu the: HARD-CODE (khoa cung, disable) 2
        bo loc Game Versions/Mod Loaders theo dung MC version + Loader cua
        Instance do - vi cai vao Instance nao thi bat buoc phai dung phien
        ban tuong thich voi Instance do, khong the tuy y chon khac trong luc
        Instance van dang duoc chon. Neu khong co Instance nao dang chon (hoac
        khong lay duoc MC version cua no), mo lai 2 bo loc de duyet tu do.

        Rieng truong hop dang cai MOD (self._loai == "mods") ma Instance dang
        chon la VANILLA (khong co Mod Loader): mod KHONG THE cai duoc vao do
        du chon phien ban nao - danh dau self._ver_bao_loi de _apply_ver_filters
        buoc bang ve rong va bao loi ro rang, thay vi am tham fallback ve
        "Tat ca" loader roi hien nham cac phien ban khong the cai duoc."""
        if gv_opts is None:
            gv_opts = list(self.cbo_ver_gv["values"])
        if loader_opts is None:
            loader_opts = list(self.cbo_ver_loader["values"])

        self._ver_bao_loi = ""

        ten_inst = None
        if self._instance_ctl:
            try:
                ten_inst = self._instance_ctl["get"]()
            except Exception:
                ten_inst = None
        mcv, loader = self._lay_instance_mc_loader()

        if ten_inst and mcv:
            loader_l = (loader or "").strip().lower()
            if self._loai == "mods" and (not loader_l or loader_l == "vanilla"):
                self._ver_filter_gv = mcv if mcv in gv_opts else "Tất cả"
                self._ver_filter_loader = "Tất cả"
                self.cbo_ver_gv.set(self._ver_filter_gv)
                self.cbo_ver_loader.set(self._ver_filter_loader)
                self._ver_bao_loi = (
                    f"Không tìm thấy: Instance '{ten_inst}' là Vanilla (không có "
                    f"Mod Loader) nên không thể cài Mod vào đây.")
            else:
                loader_t = (loader or "").strip().title()
                # QUAN TRONG: neu Mod nay KHONG co phien ban nao khop dung MC
                # version hoac dung Loader cua Instance dang chon, TUYET DOI
                # khong am tham fallback ve "Tat ca" (vi lam vay se hien nham
                # cac phien ban khong tuong thich, nguoi dung co the cai nham
                # va bi loi khi choi). Thay vao do khoa ca 2 bo loc dung theo
                # yeu cau cua Instance va bao loi ro rang - danh sach se rong.
                mc_ok = mcv in gv_opts
                loader_ok = (not loader_t) or (loader_t in loader_opts)
                self._ver_filter_gv = mcv
                self._ver_filter_loader = loader_t if loader_t else "Tất cả"
                self.cbo_ver_gv.set(self._ver_filter_gv)
                self.cbo_ver_loader.set(self._ver_filter_loader)
                if not mc_ok or not loader_ok:
                    thieu = []
                    if not mc_ok:
                        thieu.append(f"Minecraft {mcv}")
                    if not loader_ok:
                        thieu.append(loader_t)
                    self._ver_bao_loi = (
                        f"Mod này không có phiên bản nào hỗ trợ {' + '.join(thieu)} "
                        f"(yêu cầu của Instance '{ten_inst}'). Không thể cài mod này "
                        f"vào Instance đã chọn.")
            try:
                self.cbo_ver_gv.configure(state="disabled")
                self.cbo_ver_loader.configure(state="disabled")
            except tk.TclError:
                pass
            self._ver_filters_locked = True
        else:
            try:
                self.cbo_ver_gv.configure(state="readonly")
                self.cbo_ver_loader.configure(state="readonly")
            except tk.TclError:
                pass
            self._ver_filters_locked = False

    def _fill_versions(self, versions):
        if not versions:
            self._ver_idx_map = []
            self._selected_ver_idx = -1
            self.lbl_ver_status.configure(text="Không có phiên bản nào.")
            self.lbl_detail_status.config(text="", fg=self._accent)
            self.lbl_ver_range.configure(text="")
            self._update_ver_pagination_buttons(0, 0)
            return

        gv_opts, loader_opts = self._build_ver_filter_options()
        self._apply_instance_lock_to_filters(gv_opts, loader_opts)

        self.lbl_detail_status.config(text="", fg=self._accent)
        self._selected_ver_idx = -1
        self._apply_ver_filters()

    def _on_ver_filter_changed(self, event=None):
        self._ver_filter_gv = self.cbo_ver_gv.get() or "Tất cả"
        self._ver_filter_loader = self.cbo_ver_loader.get() or "Tất cả"
        self._apply_ver_filters()

    def _on_ver_perpage_changed(self, event=None):
        try:
            self._ver_per_page = max(1, int(self.cbo_ver_perpage.get()))
        except (ValueError, TypeError):
            self._ver_per_page = 20
        self._ver_page = 1
        self._render_ver_page()

    def _apply_ver_filters(self):
        # Truong hop Instance Vanilla khong the cai Mod (xem
        # _apply_instance_lock_to_filters) - buoc danh sach rong, khong chay
        # bo loc binh thuong (vi lam vay se lai hien nham cac phien ban cua
        # loader khac ma Vanilla khong the chay).
        if getattr(self, "_ver_bao_loi", ""):
            self._ver_idx_map = []
            self._ver_page = 1
            self._render_ver_page()
            return

        gv = self._ver_filter_gv
        loader = self._ver_filter_loader
        idxs = []
        for i, v in enumerate(self._versions):
            mc_list, loader_list = self._lay_gv_loader(v)
            if gv != "Tất cả" and gv not in mc_list:
                continue
            if loader != "Tất cả":
                loader_titled = [l.strip().title() for l in loader_list]
                if loader_titled and loader not in loader_titled:
                    continue
            idxs.append(i)
        self._ver_idx_map = idxs
        self._ver_page = 1
        self._render_ver_page()

    def _clear_ver_rows(self):
        for w in self._ver_row_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._ver_row_widgets = []

    def _update_ver_pagination_buttons(self, page, total_pages):
        try:
            self.btn_ver_prev.configure(state=("normal" if page > 1 else "disabled"))
            self.btn_ver_next.configure(state=("normal" if page < total_pages else "disabled"))
            self.lbl_ver_page.configure(
                text=f"Trang {page}/{total_pages}" if total_pages else "")
        except tk.TclError:
            pass

    def _ver_page_prev(self):
        if self._ver_page > 1:
            self._ver_page -= 1
            self._render_ver_page()

    def _ver_page_next(self):
        total_pages = max(1, (len(self._ver_idx_map) + self._ver_per_page - 1) // self._ver_per_page)
        if self._ver_page < total_pages:
            self._ver_page += 1
            self._render_ver_page()

    _KIEU_MAU = {"release": ("R", "#2e9e5b"), "beta": ("B", "#c98a1e"), "alpha": ("A", "#c94e4e")}

    def _ver_colors(self):
        clr = _theme.colors() if _theme else {}
        return {
            "fg": clr.get("fg_title", "#1a1a1a"),
            "fg_sub": clr.get("fg_author", "#5b6b8c"),
            "row_bg": clr.get("row_bg", "#ffffff"),
            "row_sel": clr.get("row_sel", clr.get("bg_alt", "#dce6f5")),
            "row_sep": clr.get("row_sep", clr.get("icon_border", "#dddddd")),
        }

    def _render_ver_page(self):
        self._clear_ver_rows()
        idxs = self._ver_idx_map
        total = len(idxs)
        per_page = self._ver_per_page
        total_pages = max(1, (total + per_page - 1) // per_page)
        if self._ver_page > total_pages:
            self._ver_page = total_pages
        start = (self._ver_page - 1) * per_page
        end = min(start + per_page, total)

        if not idxs:
            cv = self._ver_colors()
            if getattr(self, "_ver_bao_loi", ""):
                msg = self._ver_bao_loi
            elif self._ver_filters_locked:
                msg = (f"Không tìm thấy phiên bản nào tương thích với Instance đã "
                       f"chọn (MC {self._ver_filter_gv} / {self._ver_filter_loader}).")
            elif self._versions:
                msg = "Không có phiên bản nào phù hợp với bộ lọc."
            else:
                msg = "Đang tải phiên bản..."
            self.lbl_ver_status = tk.Label(
                self._ver_table_inner, text=msg, wraplength=560,
                font=("Arial", 9, "italic"), fg=cv["fg_sub"], bg=cv["row_bg"], justify="left")
            self.lbl_ver_status.grid(row=0, column=0, columnspan=8, sticky="w", padx=8, pady=8)
            self._ver_row_widgets.append(self.lbl_ver_status)
            self._bind_wheel_tree(self.lbl_ver_status, self._on_ver_mousewheel)
            self.lbl_ver_range.configure(text="")
            self._update_ver_pagination_buttons(0, 0)
            self._selected_ver_idx = -1
            self._cap_nhat_nhan_nut_cai_dat()
            return

        self.lbl_ver_range.configure(text=f"Hiển thị {start + 1}-{end} trong {total} kết quả")
        self._update_ver_pagination_buttons(self._ver_page, total_pages)

        if self._selected_ver_idx not in idxs:
            self._selected_ver_idx = idxs[0]
            self._show_changelog(self._selected_ver_idx)
            self._cap_nhat_nhan_nut_cai_dat()

        for row_i, vidx in enumerate(idxs[start:end]):
            self._build_ver_row(row_i, vidx)

    def _build_ver_row(self, row_i, vidx):
        v = self._versions[vidx]
        cv = self._ver_colors()
        selected = (vidx == self._selected_ver_idx)
        bg = cv["row_sel"] if selected else cv["row_bg"]
        FG, FG_SUB = cv["fg"], cv["fg_sub"]

        row = tk.Frame(self._ver_table_inner, bg=bg)
        row.grid(row=row_i, column=0, columnspan=8, sticky="ew")
        for c in range(8):
            row.columnconfigure(c, weight=(1 if c == 1 else 0), minsize=self._ver_col_w[c])
        self._ver_row_widgets.append(row)

        vtype = self._lay_ver_type(v)
        badge_txt, badge_clr = self._KIEU_MAU.get(vtype, self._KIEU_MAU["release"])
        mc_list, loader_list = self._lay_gv_loader(v)
        gv_txt = mc_list[0] if mc_list else "?"
        gv_extra = f" +{len(mc_list) - 1}" if len(mc_list) > 1 else ""
        loader_txt = "/".join(loader_list) if loader_list else "—"
        size_txt = _dinh_dang_dung_luong(self._lay_ver_size(v)) or "—"
        dl_txt = _dinh_dang_so_luot(self._lay_ver_downloads(v))
        ngay_txt = _fmt_ngay_full(self._lay_ver_ngay(v))
        ten_txt = self._lay_ver_ten(v)

        cells = []
        c0 = tk.Label(row, text=badge_txt, font=("Arial", 8, "bold"), fg="white",
                      bg=badge_clr, width=2)
        c0.grid(row=0, column=0, padx=4, pady=3)
        cells.append(c0)

        c1 = tk.Label(row, text=ten_txt, font=("Arial", 9), fg=FG, bg=bg,
                      anchor="w")
        c1.grid(row=0, column=1, sticky="ew", padx=4)
        cells.append(c1)

        c2 = tk.Label(row, text=gv_txt + gv_extra, font=("Arial", 8), fg=FG, bg=bg, anchor="w")
        c2.grid(row=0, column=2, sticky="ew", padx=4)
        cells.append(c2)

        c3 = tk.Label(row, text=loader_txt, font=("Arial", 8), fg=FG_SUB, bg=bg, anchor="w")
        c3.grid(row=0, column=3, sticky="ew", padx=4)
        cells.append(c3)

        c4 = tk.Label(row, text=size_txt, font=("Arial", 8), fg=FG_SUB, bg=bg, anchor="w")
        c4.grid(row=0, column=4, sticky="ew", padx=4)
        cells.append(c4)

        c5 = tk.Label(row, text=dl_txt, font=("Arial", 8), fg=FG_SUB, bg=bg, anchor="w")
        c5.grid(row=0, column=5, sticky="ew", padx=4)
        cells.append(c5)

        c6 = tk.Label(row, text=ngay_txt, font=("Arial", 8), fg=FG_SUB, bg=bg, anchor="w")
        c6.grid(row=0, column=6, sticky="ew", padx=4)
        cells.append(c6)

        c7 = tk.Button(row, text="⬇", font=("Arial", 9), relief="flat", bd=0,
                        bg=bg, fg=FG, activebackground=bg, cursor="hand2",
                        command=lambda vi=vidx: self._select_ver_row(vi))
        c7.grid(row=0, column=7, padx=4)
        cells.append(c7)

        sep = tk.Frame(row, bg=cv["row_sep"], height=1)
        sep.grid(row=1, column=0, columnspan=8, sticky="ew")
        cells.append(sep)

        for w in [row] + cells:
            if w is c7:
                continue
            w.bind("<Button-1>", lambda e, vi=vidx: self._select_ver_row(vi))
        self._bind_wheel_tree(row, self._on_ver_mousewheel)

    def _select_ver_row(self, vidx):
        if vidx == self._selected_ver_idx:
            return
        self._selected_ver_idx = vidx
        self._show_changelog(vidx)
        self._cap_nhat_nhan_nut_cai_dat()
        self._render_ver_page()

    def _lay_khoa_so_sanh_phien_ban(self, version_data):
        if self._source == "modrinth":
            return str(version_data.get("id", "")), (version_data.get("date_published", "") or "")
        return str(version_data.get("id", "")), (version_data.get("fileDate", "") or "")

    def _cap_nhat_nhan_nut_cai_dat(self):
        if self._selected_ver_idx < 0 or not self._versions:
            self._nhan_nut_hien_tai = "Không có phiên bản phù hợp"
            if not self._dang_cai:
                try:
                    self.btn_install.configure(text=self._nhan_nut_hien_tai, state="disabled")
                except tk.TclError:
                    pass
            return

        if not self._installed_info:
            self._nhan_nut_hien_tai = "⬇  Cài đặt"
        else:
            idx = self._selected_ver_idx
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
                self.btn_install.configure(text=self._nhan_nut_hien_tai, state="normal")
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
            trang_thai = self._trang_thai_hang_doi()
            if trang_thai == "queued":
                # Muc nay MOI CHI dang nam trong hang doi cho, CHUA thuc su
                # bat dau chay - chi can rut no khoi hang doi, KHONG duoc
                # dung den _cancel_event/_huy_tac_vu (do se huy nham tac vu
                # KHAC dang chay that su o noi khac).
                try:
                    if self._owner is not None and hasattr(self._owner, "_huy_khoi_hang_doi"):
                        self._owner._huy_khoi_hang_doi(self._id_tac_vu_cua_minh())
                except Exception:
                    pass
                self._on_install_done()
                return
            if self._cancel_cb:
                try:
                    self._cancel_cb()
                except Exception:
                    pass
            # Neu owner GHI NHAN da xac nhan huy that (cancel_event vua duoc
            # bat sau khi nguoi dung dong y trong hop thoai xac nhan cua
            # _huy_tac_vu), bao hieu "Dang huy..." NGAY tren nut thay vi de
            # nguyen chu "Huy"/tien do cu dung im - vi backend (nhat la
            # modpack nhieu file tai song song qua ThreadPoolExecutor) co
            # the mat khoang 1-2s de dung het cac luong roi don dep xong,
            # neu khong bao gi them se tao cam giac bam Huy "khong an thua".
            try:
                dang_huy = bool(getattr(self._owner, "_cancel_event", None)
                                 and self._owner._cancel_event.is_set())
            except Exception:
                dang_huy = False
            if dang_huy:
                self._bao_dang_huy()
            return

        idx = self._selected_ver_idx
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
        self._dang_yeu_cau_huy = False
        self._progress_var.set(0)
        self.lbl_progress_pct.configure(text="")
        self._set_install_ui_state(installing=True)

        self._schedule_poll_busy()
        self._install_cb(vd, on_done=self._on_install_done, progress_cb=self.update_progress)

        # _install_cb() goi vao _chay_hoac_xep_hang() cua owner, quyet dinh
        # NGAY LAP TUC (dong bo) la chay muc nay luon hay xep vao hang doi
        # cho (vi dang co tac vu KHAC chay truoc). Neu bi xep hang, phai sua
        # lai UI thanh trang thai "dang cho" thay vi "dang cai + Huy" - neu
        # khong, nut Huy luc nay se huy nham tac vu THAT SU dang chay o noi
        # khac chu khong phai muc nay (dung goc cua bug duoc bao cao).
        if self._dang_cai and self._trang_thai_hang_doi() == "queued":
            self._set_install_ui_state(installing=False, queued=True)

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
        trang_thai = self._trang_thai_hang_doi()
        if trang_thai == "active":
            # Toi luot minh chay that su (co the vua chuyen tu "queued" sang) -
            # dam bao UI dang o dung trang thai "dang cai + Huy", TRU KHI
            # nguoi dung vua bam Huy va dang cho backend dung han (khong
            # duoc ghi de chu "Dang huy..." lai thanh "Huy" nhu chua bam gi).
            if not self._dang_yeu_cau_huy:
                self._set_install_ui_state(installing=True)
            # Luon dong bo lai % tien do moi lan poll (400ms/lan), vi day la
            # cua so KHONG nhan progress_cb truc tiep tu luong tai that su -
            # xem docstring _dong_bo_tien_do_tu_owner().
            self._dong_bo_tien_do_tu_owner()
            self._schedule_poll_busy()
            return
        if trang_thai == "queued":
            self._set_install_ui_state(installing=False, queued=True)
            self._schedule_poll_busy()
            return
        # Khong con active, cung khong con queued: hoac tac vu cua CHINH
        # minh vua xong that (on_done thuc su se duoc goi rieng, day chi la
        # luoi an toan du phong), hoac chua bao gio thuoc dien active/queued
        # (vi du _tac_vu_hien_tai_id bi mat dau vet vi ly do nao do) - fallback
        # ve kiem tra co ban "con tac vu nao dang chay khong" de tranh treo
        # UI o trang thai "dang cai" mai neu co bat thuong.
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
        self._dang_yeu_cau_huy = False
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

    def _set_install_ui_state(self, installing, queued=False):
        if installing:
            self.btn_install.configure(
                text="✕  Hủy", bg="#E53935", activebackground="#E53935",
                state="normal")
            try:
                self.cbo_ver_gv.configure(state="disabled")
                self.cbo_ver_loader.configure(state="disabled")
            except tk.TclError:
                pass
            self.pb_install.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self.lbl_progress_pct.grid(row=0, column=1, sticky="w")
            self.lbl_cancel_hint.configure(
                text="💡 Đang cài đặt — bấm nút Hủy ở góc trên để dừng.")
            self.lbl_cancel_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        elif queued:
            # Muc nay da bam "Cai dat" nhung dang CHO trong hang doi (co tac
            # vu KHAC dang chay truoc) - KHONG duoc hien nhu dang cai that su:
            # nut Huy o day chi rut muc nay khoi hang doi (_on_install_or_cancel),
            # khong dung cancel_cb/_cancel_event vi se huy nham tac vu that su
            # dang chay o noi khac.
            self.btn_install.configure(
                text="✕  Hủy chờ", bg="#9e9e9e", activebackground="#8a8a8a",
                state="normal")
            try:
                self.cbo_ver_gv.configure(state="disabled")
                self.cbo_ver_loader.configure(state="disabled")
            except tk.TclError:
                pass
            self.pb_install.grid_remove()
            self.lbl_progress_pct.grid_remove()
            self.lbl_cancel_hint.configure(
                text="💡 Đang có tác vụ khác chạy — mục này đã xếp vào hàng đợi, "
                     "sẽ tự động tải khi đến lượt.")
            self.lbl_cancel_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        else:
            self.btn_install.configure(
                text=self._nhan_nut_hien_tai, bg=self._accent, activebackground=self._accent,
                state="normal")
            try:
                state = "disabled" if self._ver_filters_locked else "readonly"
                self.cbo_ver_gv.configure(state=state)
                self.cbo_ver_loader.configure(state=state)
            except tk.TclError:
                pass
            self.pb_install.grid_remove()
            self.lbl_progress_pct.grid_remove()
            self.lbl_cancel_hint.grid_remove()