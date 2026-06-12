import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import urllib.request
import urllib.parse
import urllib.error
import json
import os
import io
import zipfile
import shutil

import config
import core


# =====================================================================
# CONSTANTS
# =====================================================================

CURSEFORGE_API_KEY  = "$2a$10$tlioOAg8vpMZg3nN1c5lautxofMN2DXCzLn4.8nyr.MTBG4IYHVT2"
MODRINTH_USER_AGENT = "MinecraftLauncher/1.0 (github.com/user/mc-launcher)"

# Bang mau giao dien (sang / trang)
BG_DARK   = "#ffffff"   # nen bang danh sach
BG_HOVER  = "#eef3f9"   # hover dong
BG_SEL    = "#cfe3fb"   # dong dang chon
BG_SEP    = "#e0e0e0"   # duong ke
FG_TITLE  = "#1a1a1a"
FG_AUTHOR = "#5b6b8c"
FG_DESC   = "#444444"
FG_STAT   = "#2e7d32"
FG_TAG    = "#b35900"


# =====================================================================
# API HELPERS
# =====================================================================

def _request_json(url, headers=None):
    req_headers = {"User-Agent": MODRINTH_USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    safe_headers = {}
    for k, v in req_headers.items():
        try:
            v.encode("latin-1"); safe_headers[k] = v
        except UnicodeEncodeError:
            safe_headers[k] = v.encode("utf-8").decode("latin-1", errors="replace")

    class _NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hr, newurl):
            r2 = urllib.request.Request(newurl, headers=req.headers)
            r2.get_method = req.get_method
            return r2

    opener = urllib.request.build_opener(_NR())
    req = urllib.request.Request(url, headers=safe_headers)
    try:
        with opener.open(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode(errors="replace")
        except Exception: pass
        raise Exception(f"HTTP {e.code} {e.reason} — {body[:200]}")


def _fetch_image_bytes(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MODRINTH_USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read()
    except Exception:
        return None


# =====================================================================
# MODRINTH API
# =====================================================================

def _modrinth_search(project_type, tu_khoa="", mc_version="", loader="", category="", limit=50, offset=0):
    facets = [[f"project_type:{project_type}"]]
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    if loader and loader not in ("Tat ca", ""):
        facets.append([f"categories:{loader.lower()}"])
    if category and category not in ("Tat ca", ""):
        facets.append([f"categories:{category.lower()}"])
    params = urllib.parse.urlencode({
        "query": tu_khoa,
        "facets": json.dumps(facets),
        "limit": limit,
        "offset": offset,
        "index": "relevance" if tu_khoa else "downloads",
    })
    data = _request_json(f"https://api.modrinth.com/v2/search?{params}")
    return data.get("hits", [])


def lay_modrinth_popular(project_type="modpack", limit=50):
    return _modrinth_search(project_type, limit=limit)


def tim_kiem_modrinth(project_type, tu_khoa, mc_version="", loader="", category="", limit=50):
    return _modrinth_search(project_type, tu_khoa, mc_version, loader, category, limit)


def lay_phien_ban_modrinth(project_id):
    return _request_json(f"https://api.modrinth.com/v2/project/{project_id}/version")


# =====================================================================
# CURSEFORGE API
# =====================================================================

def lay_curseforge_popular(class_id=4471, limit=50):
    """class_id: 4471=modpack, 6=mod"""
    params = urllib.parse.urlencode({
        "gameId": 432, "classId": class_id,
        "pageSize": limit, "index": 0, "sortField": 2, "sortOrder": "desc",
    })
    data = _request_json(
        f"https://api.curseforge.com/v1/mods/search?{params}",
        {"x-api-key": CURSEFORGE_API_KEY})
    return data.get("data", [])


def tim_kiem_curseforge(tu_khoa, mc_version="", loader="", limit=50, class_id=4471):
    """class_id: 4471=modpack, 6=mod"""
    p = {"gameId": 432, "classId": class_id, "searchFilter": tu_khoa,
         "pageSize": limit, "index": 0, "sortField": 2, "sortOrder": "desc"}
    if mc_version:
        p["gameVersion"] = mc_version
    if loader and loader != "Tat ca":
        lm = {"Fabric": 4, "Forge": 1, "Quilt": 5, "NeoForge": 6}
        if loader in lm:
            p["modLoaderType"] = lm[loader]
    data = _request_json(
        f"https://api.curseforge.com/v1/mods/search?{urllib.parse.urlencode(p)}",
        {"x-api-key": CURSEFORGE_API_KEY})
    return data.get("data", [])


def lay_phien_ban_curseforge(mod_id):
    data = _request_json(
        f"https://api.curseforge.com/v1/mods/{mod_id}/files?pageSize=30",
        {"x-api-key": CURSEFORGE_API_KEY})
    return data.get("data", [])


# =====================================================================
# DOWNLOAD & INSTALL
# =====================================================================

def tai_file(url, duong_dan_luu, callback_tien_do=None, extra_headers=None):
    headers = {"User-Agent": MODRINTH_USER_AGENT, "Accept": "application/octet-stream, */*"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        tong    = int(resp.headers.get("Content-Length", 0))
        da_tai  = 0
        with open(duong_dan_luu, "wb") as f:
            while True:
                block = resp.read(8192)
                if not block: break
                f.write(block); da_tai += len(block)
                if callback_tien_do and tong:
                    callback_tien_do(da_tai, tong)


def cai_rsp_shader_tu_file(duong_dan_zip, ten_instance, loai, lbl_status, callback_xong=None):
    """Cai Resource Pack hoac Shader vao thu muc instance tuong ung."""
    thu_muc_game     = config.current_config.get("thu_muc_game", "")
    ten_folder       = ten_instance.replace(" ", "_")
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    sub_dir          = "resourcepacks" if loai == "rsp" else "shaderpacks"
    thu_muc_dest     = os.path.join(thu_muc_instance, sub_dir)
    os.makedirs(thu_muc_dest, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _chay():
        try:
            ten_file = os.path.basename(duong_dan_zip)
            dest     = os.path.join(thu_muc_dest, ten_file)
            shutil.copy2(duong_dan_zip, dest)
            _cap(f"Da cai: {ten_file} -> {sub_dir}/", "#2b8c54")
            if callback_xong:
                lbl_status.after(500, callback_xong)
        except Exception as e:
            _cap(f"Loi cai dat: {e}", "red")

    threading.Thread(target=_chay, daemon=True).start()


def cai_mod_tu_file(duong_dan_jar, ten_instance, lbl_status, callback_xong=None):
    """Copy file .jar mod vao thu muc mods/ cua instance."""
    thu_muc_game     = config.current_config.get("thu_muc_game", "")
    ten_folder       = ten_instance.replace(" ", "_")
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    thu_muc_mods     = os.path.join(thu_muc_instance, "mods")
    os.makedirs(thu_muc_mods, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _chay():
        try:
            ten_file = os.path.basename(duong_dan_jar)
            dest     = os.path.join(thu_muc_mods, ten_file)
            shutil.copy2(duong_dan_jar, dest)
            _cap(f"Da cai mod: {ten_file}", "#2b8c54")
            if callback_xong:
                lbl_status.after(500, callback_xong)
        except Exception as e:
            _cap(f"Loi cai mod: {e}", "red")

    threading.Thread(target=_chay, daemon=True).start()


def _tai_file_don_gian(url, dest_path):
    """Tai 1 file, khong co progress callback, dung cho tung mod."""
    headers = {"User-Agent": MODRINTH_USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest_path, "wb") as f:
            while True:
                block = resp.read(65536)
                if not block: break
                f.write(block)


# Biến toàn cục theo dõi trạng thái đang cài modpack
_dang_cai_modpack = False

def dang_cai_modpack():
    return _dang_cai_modpack

def cai_modpack_tu_file(duong_dan_zip, ten_instance, lbl_status, callback_xong=None):
    thu_muc_game     = config.current_config.get("thu_muc_game", "")
    # ten_instance dùng cho key config (dấu cách), ten_folder dùng cho thư mục (gạch dưới)
    ten_instance     = ten_instance.replace("_", " ").strip()
    ten_folder       = ten_instance.replace(" ", "_")
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    os.makedirs(thu_muc_instance, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _chay():
        global _dang_cai_modpack
        _dang_cai_modpack = True
        try:
            _cap("Dang giai nen modpack...", "#1E88E5")
            loai_game, version_goc, version_mod = "Vanilla", "1.21.1", "Vanilla"
            modrinth_files = []
            cf_mods = []

            with zipfile.ZipFile(duong_dan_zip, "r") as z:
                names = z.namelist()

                if "modrinth.index.json" in names:
                    index_data  = json.loads(z.read("modrinth.index.json"))
                    deps        = index_data.get("dependencies", {})
                    print(f"[mrpack] dependencies doc duoc: {deps}")

                    # Lay version minecraft
                    version_goc = deps.get("minecraft", "")
                    if not version_goc:
                        # Thu tim trong ten file
                        import re as _re
                        m = _re.search(r"(\d+\.\d+\.?\d*)", os.path.basename(duong_dan_zip))
                        version_goc = m.group(1) if m else "1.21.1"

                    # Detect loader — thu nhieu key co the co
                    if "fabric-loader" in deps:
                        loai_game, version_mod = "Fabric", deps["fabric-loader"]
                    elif "quilt-loader" in deps:
                        loai_game, version_mod = "Quilt", deps["quilt-loader"]
                    elif "neoforge" in deps:
                        loai_game, version_mod = "NeoForge", deps["neoforge"]
                    elif "forge" in deps:
                        loai_game, version_mod = "Forge", deps["forge"]
                    elif "minecraftForge" in deps:
                        loai_game, version_mod = "Forge", deps["minecraftForge"]
                    # Neu van la Vanilla thi giu nguyen version_mod = "Vanilla"

                    print(f"[mrpack] Ket qua: loai={loai_game}, mc={version_goc}, mod={version_mod}")
                    modrinth_files = index_data.get("files", [])
                    prefix = "overrides/"

                elif "manifest.json" in names:
                    manifest    = json.loads(z.read("manifest.json"))
                    mc_info     = manifest.get("minecraft", {})
                    version_goc = mc_info.get("version", "")
                    if not version_goc:
                        import re as _re
                        m = _re.search(r"(\d+\.\d+\.?\d*)", os.path.basename(duong_dan_zip))
                        version_goc = m.group(1) if m else "1.21.1"
                    for loader in mc_info.get("modLoaders", []):
                        lid = loader.get("id", "")
                        if lid.startswith("fabric-"):     loai_game, version_mod = "Fabric",   lid[7:]
                        elif lid.startswith("quilt-"):    loai_game, version_mod = "Quilt",    lid[6:]
                        elif lid.startswith("neoforge-"): loai_game, version_mod = "NeoForge", lid[9:]
                        elif lid.startswith("forge-"):    loai_game, version_mod = "Forge",    lid[6:]
                        elif lid.startswith("neoforge"):  loai_game, version_mod = "NeoForge", lid[8:]
                    print(f"[manifest] Ket qua: loai={loai_game}, mc={version_goc}, mod={version_mod}")
                    cf_mods = manifest.get("files", [])  # list {projectID, fileID, required}
                    prefix = "overrides/"

                else:
                    prefix = None

                for member in names:
                    if prefix:
                        if not member.startswith(prefix): continue
                        rel = member[len(prefix):]
                        if not rel: continue
                        dest = os.path.join(thu_muc_instance, rel)
                    else:
                        dest = os.path.join(thu_muc_instance, member)
                    if member.endswith("/"):
                        os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with z.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())

            if modrinth_files:
                tong_mod = len(modrinth_files)
                loi_tai  = []
                for i, mf in enumerate(modrinth_files):
                    rel_path = mf.get("path", "")
                    urls     = mf.get("downloads", [])
                    if not rel_path or not urls:
                        continue

                    dest_file = os.path.join(thu_muc_instance, rel_path.replace("/", os.sep))
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

                    kich_thuoc_mong_doi = mf.get("fileSize", 0)
                    if os.path.exists(dest_file):
                        if kich_thuoc_mong_doi == 0 or os.path.getsize(dest_file) == kich_thuoc_mong_doi:
                            _cap(f"Bo qua (da co): {os.path.basename(rel_path)}  ({i+1}/{tong_mod})", "#607D8B")
                            continue

                    ten_mod = os.path.basename(rel_path)
                    _cap(f"Dang tai mod  {i+1}/{tong_mod}: {ten_mod}", "#1E88E5")

                    thanh_cong = False
                    for url in urls:
                        try:
                            _tai_file_don_gian(url, dest_file)
                            thanh_cong = True
                            break
                        except Exception:
                            continue

                    if not thanh_cong:
                        loi_tai.append(ten_mod)

                if loi_tai:
                    _cap(f"Hoan thanh (loi {len(loi_tai)} mod): {', '.join(loi_tai[:3])}...", "orange")
                else:
                    _cap(f"Da tai xong {tong_mod} mod!", "#2b8c54")

            # ── Tải mod từ CurseForge manifest (manifest.json → files[]) ──
            if cf_mods:
                thu_muc_mods = os.path.join(thu_muc_instance, "mods")
                os.makedirs(thu_muc_mods, exist_ok=True)
                tong_cf = len(cf_mods)
                loi_cf  = []

                for i, entry in enumerate(cf_mods):
                    project_id = entry.get("projectID")
                    file_id    = entry.get("fileID")
                    required   = entry.get("required", True)
                    if not required:
                        continue
                    if not project_id or not file_id:
                        continue

                    _cap(f"Dang tai mod CF  {i+1}/{tong_cf}  (id={file_id})...", "#1E88E5")
                    try:
                        # Lấy thông tin file từ CurseForge API
                        url_info = f"https://api.curseforge.com/v1/mods/{project_id}/files/{file_id}"
                        file_data = _request_json(url_info, {"x-api-key": CURSEFORGE_API_KEY})
                        file_info = file_data.get("data", {})
                        ten_file  = file_info.get("fileName", f"{file_id}.jar")
                        dl_url    = file_info.get("downloadUrl", "")

                        # CurseForge đôi khi trả downloadUrl = null → tự build URL
                        if not dl_url:
                            id_str = str(file_id)
                            p1 = id_str[:4]
                            p2 = id_str[4:].lstrip("0") or "0"
                            dl_url = f"https://mediafilez.forgecdn.net/files/{p1}/{p2}/{urllib.parse.quote(ten_file)}"

                        dest = os.path.join(thu_muc_mods, ten_file)
                        if not os.path.exists(dest):
                            _tai_file_don_gian(dl_url, dest)
                        _cap(f"OK: {ten_file}  ({i+1}/{tong_cf})", "#2b8c54")

                    except Exception as ex:
                        loi_cf.append(str(file_id))
                        print(f"[CF mod] Loi {file_id}: {ex}")

                if loi_cf:
                    _cap(f"Hoan thanh CF (loi {len(loi_cf)} mod). Kiem tra thu cong.", "orange")
                else:
                    _cap(f"Da tai xong {tong_cf} mod CurseForge!", "#2b8c54")

            # Ghi instance_info.json trước
            with open(os.path.join(thu_muc_instance, "instance_info.json"), "w", encoding="utf-8") as f:
                json.dump({"loai_game": loai_game, "version_goc": version_goc, "version_mod": version_mod},
                          f, indent=4, ensure_ascii=False)

            # Cập nhật config với đúng tên key = ten_instance (có dấu cách)
            config.current_config["danh_sach_instances"][ten_instance] = {
                "version_goc": version_goc, "loai_game": loai_game, "version_mod": version_mod}
            config.current_config["current_instance"] = ten_instance
            config.luu_toan_bo_cau_hinh()

            print(f"[modpack] Da luu: {ten_instance} | {loai_game} {version_goc} | mod={version_mod}")
            _cap(f"Da cai dat: {ten_instance}  ({loai_game} {version_goc})", "#2b8c54")
            if callback_xong:
                lbl_status.after(500, callback_xong)
        except Exception as e:
            _cap(f"Loi cai dat: {e}", "red")
        finally:
            _dang_cai_modpack = False

    threading.Thread(target=_chay, daemon=True).start()


# =====================================================================
# WIDGET: FILTER BAR
# =====================================================================

class FilterBar(tk.Frame):
    LOADERS = ["Tat ca", "Fabric", "Forge", "Quilt", "NeoForge"]
    CATEGORIES = [
        "Tat ca", "Adventure", "Combat", "Decoration", "Economy",
        "Equipment", "Fantasy", "Game Mechanics", "Library",
        "Lightweight", "Magic", "Multiplayer", "Optimization",
        "Quests", "Realistic", "RPG", "Simulation", "Social",
        "Storage", "Technology", "Transportation", "Utility", "Worldgen"
    ]

    def __init__(self, parent, on_filter_callback, accent_color="#1E88E5",
                 show_loader=True, show_category=False, **kwargs):
        super().__init__(parent, **kwargs)
        self._cb = on_filter_callback

        tk.Label(self, text="MC Ver:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
        self.ent_ver = tk.Entry(self, font=("Arial", 9), width=8)
        self.ent_ver.pack(side="left", padx=(0, 8))
        self.ent_ver.bind("<Return>", lambda e: self._cb())

        if show_loader:
            tk.Label(self, text="Loader:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
            self.cbo_loader = ttk.Combobox(self, values=self.LOADERS, font=("Arial", 9),
                                           state="readonly", width=10)
            self.cbo_loader.set("Tat ca")
            self.cbo_loader.pack(side="left", padx=(0, 8))
            self.cbo_loader.bind("<<ComboboxSelected>>", lambda e: self._cb())
        else:
            self.cbo_loader = None

        if show_category:
            tk.Label(self, text="Loai:", font=("Arial", 9), bg=self["bg"]).pack(side="left", padx=(0, 2))
            self.cbo_category = ttk.Combobox(self, values=self.CATEGORIES, font=("Arial", 9),
                                             state="readonly", width=14)
            self.cbo_category.set("Tat ca")
            self.cbo_category.pack(side="left", padx=(0, 8))
            self.cbo_category.bind("<<ComboboxSelected>>", lambda e: self._cb())
        else:
            self.cbo_category = None

        tk.Button(self, text="Loc", font=("Arial", 8, "bold"),
                  bg=accent_color, fg="white", activebackground=accent_color, activeforeground="white", pady=1, command=self._cb).pack(side="left", padx=(0, 4))
        tk.Button(self, text="Xoa", font=("Arial", 8),
                  bg="#78909C", fg="white", activebackground="#78909C", activeforeground="white", pady=1, command=self._reset).pack(side="left")

    def get(self):
        ver      = self.ent_ver.get().strip()
        loader   = self.cbo_loader.get() if self.cbo_loader else "Tat ca"
        category = self.cbo_category.get() if self.cbo_category else "Tat ca"
        return ver, loader, category

    def _reset(self):
        self.ent_ver.delete(0, "end")
        if self.cbo_loader:
            self.cbo_loader.set("Tat ca")
        if self.cbo_category:
            self.cbo_category.set("Tat ca")
        self._cb()


# =====================================================================
# WIDGET: TABLE LIST (Treeview - nhanh, khong lag, dung cho moi danh sach)
# =====================================================================

class ContentTableWidget(tk.Frame):
    """Bang danh sach dang Treeview (giong Excel) - render rat nhanh,
    khong tao widget rieng cho moi dong nen khong bi lag voi danh sach lon."""

    COLS    = ("name", "author", "downloads", "mcver", "desc")
    HEADERS = {
        "name": "Tên", "author": "Tác giả", "downloads": "Lượt tải",
        "mcver": "MC Ver", "desc": "Mô tả"
    }
    WIDTHS  = {"name": 220, "author": 110, "downloads": 80, "mcver": 70, "desc": 320}
    ANCHORS = {"name": "w", "author": "w", "downloads": "e", "mcver": "center", "desc": "w"}

    def __init__(self, parent, source, on_select_cb, style_name="Modpack.Treeview", **kwargs):
        super().__init__(parent, **kwargs)
        self._source = source
        self._cb     = on_select_cb
        self._data   = []

        self.tree = ttk.Treeview(
            self, columns=self.COLS, show="headings",
            selectmode="browse", style=style_name
        )
        for c in self.COLS:
            self.tree.heading(c, text=self.HEADERS[c])
            self.tree.column(c, width=self.WIDTHS[c], anchor=self.ANCHORS[c],
                              stretch=(c == "desc"))

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double)

    def load(self, data_list):
        self._data = data_list
        self.tree.delete(*self.tree.get_children())

        for i, d in enumerate(data_list):
            if self._source == "modrinth":
                name      = d.get("title", "")
                author    = d.get("author", "")
                downloads = d.get("downloads", 0)
                versions  = d.get("versions", [])
                mc_ver    = versions[-1] if versions else ""
                desc      = d.get("description", "")
            else:  # curseforge
                name      = d.get("name", "")
                authors   = d.get("authors", [])
                author    = authors[0].get("name", "") if authors else ""
                downloads = d.get("downloadCount", 0)
                idx_files = d.get("latestFilesIndexes", [])
                mc_ver    = idx_files[0].get("gameVersion", "") if idx_files else ""
                desc      = d.get("summary", "")

            desc_short = (desc or "").replace("\n", " ").strip()
            self.tree.insert(
                "", "end", iid=str(i),
                values=(name, author, f"{int(downloads):,}", mc_ver, desc_short)
            )

    def _on_select(self, e=None):
        sel = self.tree.selection()
        if sel:
            self._cb(int(sel[0]), install=False)

    def _on_double(self, e=None):
        sel = self.tree.selection()
        if sel:
            self._cb(int(sel[0]), install=True)

    def get_selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else -1


# =====================================================================
# HELPER: tao bottom panel cai mod vao instance
# =====================================================================

def _make_install_panel(parent, bg, lbl_phien_ban, lbl_instance, btn_text, btn_color, btn_cmd):
    """Tao panel chon phien ban + instance + nut cai, tra ve (cbo_ver, cbo_inst)."""
    bp = tk.Frame(parent, bg=bg)
    bp.pack(fill="x", padx=10, pady=(4, 8))

    tk.Label(bp, text=lbl_phien_ban, font=("Arial", 9), bg=bg).grid(row=0, column=0, sticky="w")
    cbo_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
    cbo_ver.grid(row=0, column=1, padx=6)

    tk.Label(bp, text=lbl_instance, font=("Arial", 9), bg=bg).grid(row=1, column=0, sticky="w", pady=4)
    ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
    cbo_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
    cur = config.current_config.get("current_instance", "")
    if cur in ds_inst:   cbo_inst.set(cur)
    elif ds_inst:        cbo_inst.set(ds_inst[0])
    cbo_inst.grid(row=1, column=1, padx=6)

    tk.Button(bp, text=btn_text, font=("Arial", 9, "bold"),
              bg=btn_color, fg="white", activebackground=btn_color, activeforeground="white", width=14, pady=4,
              command=btn_cmd).grid(row=0, column=2, rowspan=2, padx=8)

    return cbo_ver, cbo_inst


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
        self.grab_set()
        self.callback_lam_moi = callback_lam_moi

        # Debounce IDs
        self._debounce_mr   = None
        self._debounce_cf   = None
        self._debounce_modmr = None
        self._debounce_modcf = None
        self._debounce_rsp  = None
        self._debounce_sh   = None

        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text="Content Manager  —  Modpack / Mod / Resource Pack / Shader",
                 font=("Arial", 13, "bold"), fg="#1E88E5").pack(pady=(10, 4))

        # Style cho bang Treeview (Modpack)
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

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=4)

        BG = "#f5f5f7"
        self.tab_mr    = tk.Frame(self.nb, bg=BG)
        self.tab_cf    = tk.Frame(self.nb, bg=BG)
        self.tab_modmr = tk.Frame(self.nb, bg=BG)
        self.tab_modcf = tk.Frame(self.nb, bg=BG)
        self.tab_rsp   = tk.Frame(self.nb, bg=BG)
        self.tab_sh    = tk.Frame(self.nb, bg=BG)
        self.tab_f     = tk.Frame(self.nb)

        self.nb.add(self.tab_mr,    text="  Modpack Modrinth  ")
        self.nb.add(self.tab_cf,    text="  Modpack CurseForge  ")
        self.nb.add(self.tab_modmr, text="  Mod Modrinth  ")
        self.nb.add(self.tab_modcf, text="  Mod CurseForge  ")
        self.nb.add(self.tab_rsp,   text="  Resource Pack  ")
        self.nb.add(self.tab_sh,    text="  Shaders  ")
        self.nb.add(self.tab_f,     text="  Cai tu File  ")

        self._build_modpack_modrinth()
        self._build_modpack_curseforge()
        self._build_mod_modrinth()
        self._build_mod_curseforge()
        self._build_rsp_tab()
        self._build_shader_tab()
        self._build_file()

        self.lbl_status = tk.Label(self, text="Dang tai...",
                                   font=("Arial", 9, "italic"), fg="#1E88E5", anchor="w")
        self.lbl_status.pack(fill="x", padx=14, pady=(2, 6))

        # Chi load tab dang active, cac tab khac load khi click
        threading.Thread(target=self._load_mr_top,   daemon=True).start()
        threading.Thread(target=self._load_cf_top,   daemon=True).start()
        threading.Thread(target=self._load_rsp_top,  daemon=True).start()
        threading.Thread(target=self._load_sh_top,   daemon=True).start()
        # Mod tabs: load lazy khi user click tab
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, e):
        tab = self.nb.index(self.nb.select())
        # tab 2 = Mod Modrinth, tab 3 = Mod CurseForge
        if tab == 2 and not self._modmr_data:
            threading.Thread(target=self._load_modmr_top, daemon=True).start()
        elif tab == 3 and not self._modcf_data:
            threading.Thread(target=self._load_modcf_top, daemon=True).start()

    # ------------------------------------------------------------------
    # HELPER: debounced search
    # ------------------------------------------------------------------

    def _debounce(self, attr, ms, fn):
        old = getattr(self, attr, None)
        if old:
            try: self.after_cancel(old)
            except: pass
        setattr(self, attr, self.after(ms, fn))

    # ------------------------------------------------------------------
    # MODPACK MODRINTH TAB
    # ------------------------------------------------------------------

    def _build_modpack_modrinth(self):
        f = self.tab_mr
        BG = f["bg"]

        sr = tk.Frame(f, bg=BG)
        sr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(sr, text="Tim kiem:", font=("Arial", 10), bg=BG).pack(side="left")
        self.ent_mr = tk.Entry(sr, font=("Arial", 10), width=30)
        self.ent_mr.pack(side="left", padx=6)
        self.ent_mr.bind("<Return>", lambda e: self._search_mr())
        self.ent_mr.bind("<KeyRelease>", lambda e: self._debounce("_debounce_mr", 400, self._search_mr))
        tk.Button(sr, text="Tim", font=("Arial", 9, "bold"),
                  bg="#1E88E5", fg="white", activebackground="#1E88E5", activeforeground="white", width=6, command=self._search_mr).pack(side="left")
        tk.Button(sr, text="Top", font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
                  command=lambda: threading.Thread(target=self._load_mr_top, daemon=True).start()
                  ).pack(side="left", padx=4)

        self.fb_mr = FilterBar(f, self._search_mr, accent_color="#1E88E5",
                               show_category=True, bg=BG)
        self.fb_mr.pack(fill="x", padx=10, pady=(2, 4))

        self.list_mr = ContentTableWidget(f, "modrinth", self._select_mr)
        self.list_mr.pack(fill="both", expand=True, padx=10)

        bp = tk.Frame(f, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_mr_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_mr_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Ten Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        self.ent_mr_name = tk.Entry(bp, font=("Arial", 9), width=44)
        self.ent_mr_name.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cai Modpack", font=("Arial", 9, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white", width=14, pady=4,
                  command=self._install_mr).grid(row=0, column=2, rowspan=2, padx=8)

        self._mr_data     = []
        self._mr_vers_raw = []

    def _load_mr_top(self):
        try:
            r = lay_modrinth_popular("modpack", 50)
            self._mr_data = r
            self.after(0, lambda: (
                self.list_mr.load(r),
                self.lbl_status.config(text=f"Top {len(r)} Modpack (Modrinth)", fg="#2b8c54")
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi MR: {e}", fg="red"))

    def _search_mr(self):
        kw           = self.ent_mr.get().strip()
        mc, ld, cat  = self.fb_mr.get()
        self.lbl_status.config(text="Dang tim...", fg="#1E88E5")
        def _t():
            try:
                r = tim_kiem_modrinth("modpack", kw, mc, ld, cat)
                self._mr_data = r
                self.after(0, lambda: (
                    self.list_mr.load(r),
                    self.lbl_status.config(text=f"{len(r)} modpack", fg="#2b8c54")
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _select_mr(self, idx, install=False):
        if idx >= len(self._mr_data): return
        r   = self._mr_data[idx]
        ten = r.get("title", "")
        self.ent_mr_name.delete(0, "end")
        self.ent_mr_name.insert(0, ten.replace(" ", "_")[:30])
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
                if install:
                    self.after(200, self._install_mr)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    def _install_mr(self):
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

        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz  = os.path.join(tmp, fname)

                def prog(da, tong):
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#1E88E5"))

                tai_file(url, pz, prog)

                def _done_va_xoa():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self._done()

                cai_modpack_tu_file(pz, ten, self.lbl_status, _done_va_xoa)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # MODPACK CURSEFORGE TAB
    # ------------------------------------------------------------------

    def _build_modpack_curseforge(self):
        f = self.tab_cf
        BG = f["bg"]

        sr = tk.Frame(f, bg=BG)
        sr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(sr, text="Tim kiem:", font=("Arial", 10), bg=BG).pack(side="left")
        self.ent_cf = tk.Entry(sr, font=("Arial", 10), width=30)
        self.ent_cf.pack(side="left", padx=6)
        self.ent_cf.bind("<Return>", lambda e: self._search_cf())
        self.ent_cf.bind("<KeyRelease>", lambda e: self._debounce("_debounce_cf", 400, self._search_cf))
        tk.Button(sr, text="Tim", font=("Arial", 9, "bold"),
                  bg="#E64A19", fg="white", activebackground="#E64A19", activeforeground="white", width=6, command=self._search_cf).pack(side="left")
        tk.Button(sr, text="Top", font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
                  command=lambda: threading.Thread(target=self._load_cf_top, daemon=True).start()
                  ).pack(side="left", padx=4)

        self.fb_cf = FilterBar(f, self._search_cf, accent_color="#E64A19",
                               show_category=True, bg=BG)
        self.fb_cf.pack(fill="x", padx=10, pady=(2, 4))

        self.list_cf = ContentTableWidget(f, "curseforge", self._select_cf)
        self.list_cf.pack(fill="both", expand=True, padx=10)

        bp = tk.Frame(f, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_cf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_cf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Ten Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        self.ent_cf_name = tk.Entry(bp, font=("Arial", 9), width=44)
        self.ent_cf_name.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cai Modpack", font=("Arial", 9, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white", width=14, pady=4,
                  command=self._install_cf).grid(row=0, column=2, rowspan=2, padx=8)

        self._cf_data  = []
        self._cf_files = []

    def _load_cf_top(self):
        try:
            r = lay_curseforge_popular(class_id=4471, limit=50)
            self._cf_data = r
            self.after(0, lambda: (
                self.list_cf.load(r),
                self.lbl_status.config(text=f"Top {len(r)} Modpack (CurseForge)", fg="#2b8c54")
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF: {e}", fg="red"))

    def _search_cf(self):
        kw         = self.ent_cf.get().strip()
        mc, ld, _c = self.fb_cf.get()
        self.lbl_status.config(text="Dang tim CF...", fg="#E64A19")
        def _t():
            try:
                r = tim_kiem_curseforge(kw, mc, ld, class_id=4471)
                self._cf_data = r
                self.after(0, lambda: (
                    self.list_cf.load(r),
                    self.lbl_status.config(text=f"{len(r)} modpack", fg="#2b8c54")
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

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
                if install:
                    self.after(200, self._install_cf)
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

        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz  = os.path.join(tmp, fname)

                def prog(da, tong):
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#E64A19"))

                tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})

                def _done_va_xoa():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self._done()

                cai_modpack_tu_file(pz, ten, self.lbl_status, _done_va_xoa)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # MOD MODRINTH TAB
    # ------------------------------------------------------------------

    def _build_mod_modrinth(self):
        self._modmr_data     = []
        self._modmr_vers_raw = []
        f = self.tab_modmr
        BG = f["bg"]

        sr = tk.Frame(f, bg=BG)
        sr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(sr, text="Tim kiem:", font=("Arial", 10), bg=BG).pack(side="left")
        self.ent_modmr = tk.Entry(sr, font=("Arial", 10), width=30)
        self.ent_modmr.pack(side="left", padx=6)
        self.ent_modmr.bind("<Return>", lambda e: self._search_modmr())
        self.ent_modmr.bind("<KeyRelease>", lambda e: self._debounce("_debounce_modmr", 400, self._search_modmr))
        tk.Button(sr, text="Tim", font=("Arial", 9, "bold"),
                  bg="#00897B", fg="white", activebackground="#00897B", activeforeground="white", width=6, command=self._search_modmr).pack(side="left")
        tk.Button(sr, text="Top", font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
                  command=lambda: threading.Thread(target=self._load_modmr_top, daemon=True).start()
                  ).pack(side="left", padx=4)

        self.fb_modmr = FilterBar(f, self._search_modmr, accent_color="#00897B", bg=BG)
        self.fb_modmr.pack(fill="x", padx=10, pady=(2, 4))

        self.list_modmr = ContentTableWidget(f, "modrinth", self._select_modmr)
        self.list_modmr.pack(fill="both", expand=True, padx=10)

        bp = tk.Frame(f, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban mod:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_modmr_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_modmr_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_modmr_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst:   self.cbo_modmr_inst.set(cur)
        elif ds_inst:        self.cbo_modmr_inst.set(ds_inst[0])
        self.cbo_modmr_inst.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cai Mod", font=("Arial", 9, "bold"),
                  bg="#00897B", fg="white", activebackground="#00897B", activeforeground="white", width=14, pady=4,
                  command=self._install_modmr).grid(row=0, column=2, rowspan=2, padx=8)

    def _load_modmr_top(self):
        try:
            r = lay_modrinth_popular("mod", 50)
            self._modmr_data = r
            self.after(0, lambda: (
                self.list_modmr.load(r),
                self.lbl_status.config(text=f"Top {len(r)} Mod (Modrinth)", fg="#2b8c54")
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi ModMR: {e}", fg="red"))

    def _search_modmr(self):
        kw     = self.ent_modmr.get().strip()
        mc, ld, _c = self.fb_modmr.get()
        self.lbl_status.config(text="Dang tim Mod Modrinth...", fg="#00897B")
        def _t():
            try:
                r = tim_kiem_modrinth("mod", kw, mc, ld)
                self._modmr_data = r
                self.after(0, lambda: (
                    self.list_modmr.load(r),
                    self.lbl_status.config(text=f"{len(r)} mod", fg="#2b8c54")
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _select_modmr(self, idx, install=False):
        if idx >= len(self._modmr_data): return
        r   = self._modmr_data[idx]
        pid = r.get("project_id", "")
        self.cbo_modmr_ver.set("Dang tai phien ban...")

        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._modmr_vers_raw = vs
                ds = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}  [{', '.join(v.get('loaders',[]))}]"
                      for v in vs]
                self.after(0, lambda: (
                    self.cbo_modmr_ver.config(values=ds),
                    self.cbo_modmr_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chon phien ban roi nhan Cai Mod.", fg="gray"),
                ))
                if install: self.after(200, self._install_modmr)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_modmr(self):
        ten_inst = self.cbo_modmr_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_modmr_ver.current()
        if iv < 0 or not self._modmr_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        vd    = self._modmr_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "mod.jar")
        self.lbl_status.config(text="Dang tai Mod...", fg="#00897B")

        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz  = os.path.join(tmp, fname)

                def prog(da, tong):
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai mod: {pct}%", fg="#00897B"))

                tai_file(url, pz, prog)

                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai mod '{fname}' vao {ten_inst}!", fg="#2b8c54"))

                cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # MOD CURSEFORGE TAB
    # ------------------------------------------------------------------

    def _build_mod_curseforge(self):
        self._modcf_data  = []
        self._modcf_files = []
        f = self.tab_modcf
        BG = f["bg"]

        sr = tk.Frame(f, bg=BG)
        sr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(sr, text="Tim kiem:", font=("Arial", 10), bg=BG).pack(side="left")
        self.ent_modcf = tk.Entry(sr, font=("Arial", 10), width=30)
        self.ent_modcf.pack(side="left", padx=6)
        self.ent_modcf.bind("<Return>", lambda e: self._search_modcf())
        self.ent_modcf.bind("<KeyRelease>", lambda e: self._debounce("_debounce_modcf", 400, self._search_modcf))
        tk.Button(sr, text="Tim", font=("Arial", 9, "bold"),
                  bg="#F9A825", fg="white", activebackground="#F9A825", activeforeground="white", width=6, command=self._search_modcf).pack(side="left")
        tk.Button(sr, text="Top", font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
                  command=lambda: threading.Thread(target=self._load_modcf_top, daemon=True).start()
                  ).pack(side="left", padx=4)

        self.fb_modcf = FilterBar(f, self._search_modcf, accent_color="#F9A825", bg=BG)
        self.fb_modcf.pack(fill="x", padx=10, pady=(2, 4))

        self.list_modcf = ContentTableWidget(f, "curseforge", self._select_modcf)
        self.list_modcf.pack(fill="both", expand=True, padx=10)

        bp = tk.Frame(f, bg=BG)
        bp.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(bp, text="Phien ban mod:", font=("Arial", 9), bg=BG).grid(row=0, column=0, sticky="w")
        self.cbo_modcf_ver = ttk.Combobox(bp, font=("Arial", 9), state="readonly", width=42)
        self.cbo_modcf_ver.grid(row=0, column=1, padx=6)
        tk.Label(bp, text="Cai vao Instance:", font=("Arial", 9), bg=BG).grid(row=1, column=0, sticky="w", pady=4)
        ds_inst = list(config.current_config.get("danh_sach_instances", {}).keys())
        self.cbo_modcf_inst = ttk.Combobox(bp, values=ds_inst, font=("Arial", 9), width=42)
        cur = config.current_config.get("current_instance", "")
        if cur in ds_inst:   self.cbo_modcf_inst.set(cur)
        elif ds_inst:        self.cbo_modcf_inst.set(ds_inst[0])
        self.cbo_modcf_inst.grid(row=1, column=1, padx=6)
        tk.Button(bp, text="Cai Mod", font=("Arial", 9, "bold"),
                  bg="#F9A825", fg="white", activebackground="#F9A825", activeforeground="white", width=14, pady=4,
                  command=self._install_modcf).grid(row=0, column=2, rowspan=2, padx=8)

    def _load_modcf_top(self):
        try:
            # classId 6 = Mods tren CurseForge
            r = lay_curseforge_popular(class_id=6, limit=50)
            self._modcf_data = r
            self.after(0, lambda: (
                self.list_modcf.load(r),
                self.lbl_status.config(text=f"Top {len(r)} Mod (CurseForge)", fg="#2b8c54")
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi ModCF: {e}", fg="red"))

    def _search_modcf(self):
        kw     = self.ent_modcf.get().strip()
        mc, ld, _c = self.fb_modcf.get()
        self.lbl_status.config(text="Dang tim Mod CurseForge...", fg="#F9A825")
        def _t():
            try:
                r = tim_kiem_curseforge(kw, mc, ld, class_id=6)
                self._modcf_data = r
                self.after(0, lambda: (
                    self.list_modcf.load(r),
                    self.lbl_status.config(text=f"{len(r)} mod", fg="#2b8c54")
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _select_modcf(self, idx, install=False):
        if idx >= len(self._modcf_data): return
        r   = self._modcf_data[idx]
        mid = r.get("id", "")
        self.cbo_modcf_ver.set("Dang tai phien ban...")
        self.lbl_status.config(text=f"Dang tai phien ban mod...", fg="#F9A825")

        def _t():
            try:
                files = lay_phien_ban_curseforge(mid)
                self._modcf_files = files
                ds = [f"{fi.get('displayName', fi.get('fileName',''))}  -  MC {', '.join(fi.get('gameVersions',[]))}"
                      for fi in files]
                self.after(0, lambda: (
                    self.cbo_modcf_ver.config(values=ds),
                    self.cbo_modcf_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chon phien ban roi nhan Cai Mod.", fg="gray"),
                ))
                if install: self.after(200, self._install_modcf)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi CF ver: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    def _install_modcf(self):
        ten_inst = self.cbo_modcf_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_modcf_ver.current()
        if iv < 0 or not self._modcf_files:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return

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

        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz  = os.path.join(tmp, fname)

                def prog(da, tong):
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai mod: {pct}%  ({da//1024}KB/{tong//1024}KB)", fg="#F9A825"))

                tai_file(url, pz, prog, extra_headers={"x-api-key": CURSEFORGE_API_KEY})

                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai mod '{fname}' vao {ten_inst}!", fg="#2b8c54"))

                cai_mod_tu_file(pz, ten_inst, self.lbl_status, _done)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # RESOURCE PACK TAB
    # ------------------------------------------------------------------

    def _build_rsp_tab(self):
        self._rsp_data     = []
        self._rsp_vers_raw = []
        f = self.tab_rsp
        BG = f["bg"]

        sr = tk.Frame(f, bg=BG)
        sr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(sr, text="Tim kiem:", font=("Arial", 10), bg=BG).pack(side="left")
        self.ent_rsp = tk.Entry(sr, font=("Arial", 10), width=30)
        self.ent_rsp.pack(side="left", padx=6)
        self.ent_rsp.bind("<Return>",    lambda e: self._search_rsp())
        self.ent_rsp.bind("<KeyRelease>", lambda e: self._debounce("_debounce_rsp", 400, self._search_rsp))
        tk.Button(sr, text="Tim",  font=("Arial", 9, "bold"), bg="#8E24AA", fg="white", activebackground="#8E24AA", activeforeground="white",
                  width=6, command=self._search_rsp).pack(side="left")
        tk.Button(sr, text="Top",  font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
                  command=lambda: threading.Thread(target=self._load_rsp_top, daemon=True).start()
                  ).pack(side="left", padx=4)

        self.fb_rsp = FilterBar(f, self._search_rsp, accent_color="#8E24AA",
                                show_loader=False, bg=BG)
        self.fb_rsp.pack(fill="x", padx=10, pady=(2, 4))

        self.list_rsp = ContentTableWidget(f, "modrinth", self._select_rsp)
        self.list_rsp.pack(fill="both", expand=True, padx=10)

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
        tk.Button(bp, text="Cai RSP", font=("Arial", 9, "bold"),
                  bg="#8E24AA", fg="white", activebackground="#8E24AA", activeforeground="white", width=14, pady=4,
                  command=self._install_rsp).grid(row=0, column=2, rowspan=2, padx=8)

    def _load_rsp_top(self):
        try:
            r = lay_modrinth_popular("resourcepack", 50)
            self._rsp_data = r
            self.after(0, lambda: (
                self.list_rsp.load(r),
                self.lbl_status.config(text=f"Top {len(r)} Resource Pack", fg="#2b8c54")
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi RSP: {e}", fg="red"))

    def _search_rsp(self):
        kw     = self.ent_rsp.get().strip()
        mc, _, _c = self.fb_rsp.get()
        self.lbl_status.config(text="Dang tim RSP...", fg="#8E24AA")
        def _t():
            try:
                r = tim_kiem_modrinth("resourcepack", kw, mc)
                self._rsp_data = r
                self.after(0, lambda: (
                    self.list_rsp.load(r),
                    self.lbl_status.config(text=f"{len(r)} resource pack", fg="#2b8c54")
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _select_rsp(self, idx, install=False):
        if idx >= len(self._rsp_data): return
        r   = self._rsp_data[idx]
        pid = r.get("project_id", "")
        self.cbo_rsp_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._rsp_vers_raw = vs
                ds = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]
                self.after(0, lambda: (
                    self.cbo_rsp_ver.config(values=ds),
                    self.cbo_rsp_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chon phien ban roi nhan Cai RSP.", fg="gray"),
                ))
                if install: self.after(200, self._install_rsp)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_rsp(self):
        ten_inst = self.cbo_rsp_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_rsp_ver.current()
        if iv < 0 or not self._rsp_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        vd    = self._rsp_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "resourcepack.zip")
        self.lbl_status.config(text="Dang tai RSP...", fg="#8E24AA")

        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz  = os.path.join(tmp, fname)

                def prog(da, tong):
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai: {pct}%", fg="#8E24AA"))

                tai_file(url, pz, prog)

                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai RSP vao {ten_inst}!", fg="#2b8c54"))

                cai_rsp_shader_tu_file(pz, ten_inst, "rsp", self.lbl_status, _done)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # SHADERS TAB
    # ------------------------------------------------------------------

    def _build_shader_tab(self):
        self._sh_data     = []
        self._sh_vers_raw = []
        f = self.tab_sh
        BG = f["bg"]

        sr = tk.Frame(f, bg=BG)
        sr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(sr, text="Tim kiem:", font=("Arial", 10), bg=BG).pack(side="left")
        self.ent_sh = tk.Entry(sr, font=("Arial", 10), width=30)
        self.ent_sh.pack(side="left", padx=6)
        self.ent_sh.bind("<Return>",    lambda e: self._search_sh())
        self.ent_sh.bind("<KeyRelease>", lambda e: self._debounce("_debounce_sh", 400, self._search_sh))
        tk.Button(sr, text="Tim",  font=("Arial", 9, "bold"), bg="#F57C00", fg="white", activebackground="#F57C00", activeforeground="white",
                  width=6, command=self._search_sh).pack(side="left")
        tk.Button(sr, text="Top",  font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
                  command=lambda: threading.Thread(target=self._load_sh_top, daemon=True).start()
                  ).pack(side="left", padx=4)

        self.fb_sh = FilterBar(f, self._search_sh, accent_color="#F57C00",
                               show_loader=False, bg=BG)
        self.fb_sh.pack(fill="x", padx=10, pady=(2, 4))

        self.list_sh = ContentTableWidget(f, "modrinth", self._select_sh)
        self.list_sh.pack(fill="both", expand=True, padx=10)

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
        tk.Button(bp, text="Cai Shader", font=("Arial", 9, "bold"),
                  bg="#F57C00", fg="white", activebackground="#F57C00", activeforeground="white", width=14, pady=4,
                  command=self._install_sh).grid(row=0, column=2, rowspan=2, padx=8)
        self._debounce_sh = None

    def _load_sh_top(self):
        try:
            r = lay_modrinth_popular("shader", 50)
            self._sh_data = r
            self.after(0, lambda: (
                self.list_sh.load(r),
                self.lbl_status.config(text=f"Top {len(r)} Shader", fg="#2b8c54")
            ))
        except Exception as e:
            self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi Shader: {e}", fg="red"))

    def _search_sh(self):
        kw     = self.ent_sh.get().strip()
        mc, _, _c = self.fb_sh.get()
        self.lbl_status.config(text="Dang tim Shader...", fg="#F57C00")
        def _t():
            try:
                r = tim_kiem_modrinth("shader", kw, mc)
                self._sh_data = r
                self.after(0, lambda: (
                    self.list_sh.load(r),
                    self.lbl_status.config(text=f"{len(r)} shader", fg="#2b8c54")
                ))
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _select_sh(self, idx, install=False):
        if idx >= len(self._sh_data): return
        r   = self._sh_data[idx]
        pid = r.get("project_id", "")
        self.cbo_sh_ver.set("Dang tai phien ban...")
        def _t():
            try:
                vs = lay_phien_ban_modrinth(pid)
                self._sh_vers_raw = vs
                ds = [f"{v.get('name','?')}  -  MC {', '.join(v.get('game_versions',[]))}" for v in vs]
                self.after(0, lambda: (
                    self.cbo_sh_ver.config(values=ds),
                    self.cbo_sh_ver.set(ds[0]) if ds else None,
                    self.lbl_status.config(text="Chon phien ban roi nhan Cai Shader.", fg="gray"),
                ))
                if install: self.after(200, self._install_sh)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))
        threading.Thread(target=_t, daemon=True).start()

    def _install_sh(self):
        ten_inst = self.cbo_sh_inst.get().strip()
        if not ten_inst:
            messagebox.showwarning("Chu y", "Chon Instance de cai vao!", parent=self); return
        iv = self.cbo_sh_ver.current()
        if iv < 0 or not self._sh_vers_raw:
            messagebox.showwarning("Chu y", "Chon phien ban!", parent=self); return
        vd    = self._sh_vers_raw[iv]
        files = vd.get("files", [])
        prim  = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not prim:
            messagebox.showerror("Loi", "Khong tim thay file tai!", parent=self); return
        url   = prim["url"]
        fname = prim.get("filename", "shader.zip")
        self.lbl_status.config(text="Dang tai Shader...", fg="#F57C00")

        def _t():
            try:
                tmp = os.path.join(config.current_config.get("thu_muc_game", ""), "_modpack_tmp")
                os.makedirs(tmp, exist_ok=True)
                pz  = os.path.join(tmp, fname)

                def prog(da, tong):
                    pct = int(da / tong * 100)
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"Dang tai: {pct}%", fg="#F57C00"))

                tai_file(url, pz, prog)

                def _done():
                    try: shutil.rmtree(tmp)
                    except: pass
                    self.lbl_status.after(0, lambda: self.lbl_status.config(
                        text=f"Da cai Shader vao {ten_inst}!", fg="#2b8c54"))

                cai_rsp_shader_tu_file(pz, ten_inst, "shader", self.lbl_status, _done)
            except Exception as e:
                self.after(0, lambda e=e: self.lbl_status.config(text=f"Loi: {e}", fg="red"))

        threading.Thread(target=_t, daemon=True).start()

    # ------------------------------------------------------------------
    # FILE TAB
    # ------------------------------------------------------------------

    def _build_file(self):
        f = self.tab_f
        tk.Label(f, text="Cai tu file  (.mrpack / .zip / .jar)",
                 font=("Arial", 11, "bold"), fg="#37474F").pack(pady=(20, 4))
        tk.Label(f, text="Modpack: Modrinth (.mrpack)  |  CurseForge (.zip)\n"
                         "Mod: file .jar (copy thang vao thu muc mods/)\n"
                         "Resource Pack / Shader: file .zip / .jar",
                 font=("Arial", 9, "italic"), fg="gray", justify="left").pack(pady=(0, 12))

        fr = tk.Frame(f); fr.pack(padx=24)
        tk.Label(fr, text="File:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=6)
        self.ent_fp = tk.Entry(fr, font=("Arial", 9), width=38, state="readonly")
        self.ent_fp.grid(row=0, column=1, padx=6)
        tk.Button(fr, text="Chon file", font=("Arial", 9), bg="#607D8B", fg="white", activebackground="#607D8B", activeforeground="white",
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
                  bg="#4CAF50", fg="white", activebackground="#4CAF50", activeforeground="white", width=22, height=2,
                  command=self._install_file).pack(pady=16)

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
        path  = self.ent_fp.get().strip()
        ten   = self.ent_fn.get().strip()
        loai  = self.cbo_file_type.get()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Chu y", "Chon file hop le!", parent=self); return
        if not ten:
            messagebox.showwarning("Chu y", "Nhap ten!", parent=self); return

        if loai == "Modpack":
            if ten in config.current_config["danh_sach_instances"]:
                messagebox.showwarning("Chu y", "Ten Instance da ton tai!", parent=self); return
            cai_modpack_tu_file(path, ten, self.lbl_status, self._done)
        elif loai == "Mod":
            # ten o day la ten instance de cai vao
            cai_mod_tu_file(path, ten, self.lbl_status)
        else:
            map_loai = {"Resource Pack": "rsp", "Shader": "shader"}
            cai_rsp_shader_tu_file(path, ten, map_loai[loai], self.lbl_status)

    # ------------------------------------------------------------------

    def _done(self):
        if self.callback_lam_moi:
            self.callback_lam_moi()
        messagebox.showinfo("Thanh cong",
            "Da cai dat thanh cong!\nInstance moi da xuat hien trong danh sach.", parent=self)