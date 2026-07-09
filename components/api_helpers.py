"""
api_helpers.py
--------------
Cac ham goi API cho Modrinth va CurseForge.
Import tu day thay vi viet trong mod_mc.py.
"""

import urllib.request
import urllib.parse
import urllib.error
import json

CURSEFORGE_API_KEY  = "$2a$10$tlioOAg8vpMZg3nN1c5lautxofMN2DXCzLn4.8nyr.MTBG4IYHVT2"
MODRINTH_USER_AGENT = "MinecraftLauncher/1.0 (github.com/user/mc-launcher)"


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


def _modrinth_search(project_type, tu_khoa="", mc_version="", loader="", category="", limit=50, offset=0):
    facets = [[f"project_type:{project_type}"]]
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    if loader and loader not in ("Tất cả", ""):
        facets.append([f"categories:{loader.lower()}"])
    if category:
        # category co the la 1 chuoi (tuong thich nguoc) HOAC 1 list/tuple/set
        # cac slug da duoc tick (multi-select giong Modrinth that - xem sidebar
        # "Loai" trong Modrinth App, co the tick nhieu the loai cung luc).
        cats = category if isinstance(category, (list, tuple, set)) else [category]
        cats = [c for c in cats if c and c not in ("Tất cả", "")]
        if cats:
            # Cac category duoc chon se OR voi nhau (cung 1 nhom facet con),
            # va AND voi cac dieu kien khac (phien ban, trinh nap...) - dung
            # dung ngu nghia facet cua Modrinth API.
            facets.append([f"categories:{c.lower()}" for c in cats])
    params = urllib.parse.urlencode({
        "query": tu_khoa,
        "facets": json.dumps(facets),
        "limit": limit,
        "offset": offset,
        "index": "relevance" if tu_khoa else "downloads",
    })
    data = _request_json(f"https://api.modrinth.com/v2/search?{params}")
    return data.get("hits", []), data.get("total_hits", 0)


def lay_modrinth_popular(project_type="modpack", limit=50, offset=0):
    return _modrinth_search(project_type, limit=limit, offset=offset)


def lay_category_modrinth(project_type="modpack"):
    """
    Lay danh sach category THAT cua Modrinth cho 1 loai noi dung (project_type:
    'modpack' / 'mod' / 'resourcepack' / 'shader'), tu endpoint /v2/tag/category
    - giong nhu sidebar "Loai" trong Modrinth App that (xem anh: Chien dau,
    Cong nghe, Nhe, Nhiem vu, Nhieu nguoi choi, Phep thuat, Phieu luu,
    Thu thach, Toi uu hoa, ...).

    Tra ve list dict [{"name": "adventure", "header": "categories"}, ...]
    - dung de fill vao popup chon nhieu the loai (multi-select) cua FilterBar.
    Cac the loai duoc Modrinth nhom theo "header" (vd "categories",
    "resolutions", "performance impact" - rieng cho resource pack/shader);
    giu nguyen header de UI co the hien thi thanh tung nhom.
    """
    data = _request_json("https://api.modrinth.com/v2/tag/category")
    out = []
    for c in data:
        pt = c.get("project_type")
        pts = pt if isinstance(pt, list) else [pt]
        if project_type in pts:
            out.append({"name": c.get("name", ""), "header": c.get("header", "") or "categories"})
    return out


def tim_kiem_modrinth(project_type, tu_khoa, mc_version="", loader="", category="", limit=50, offset=0):
    return _modrinth_search(project_type, tu_khoa, mc_version, loader, category, limit, offset)


def lay_phien_ban_modrinth(project_id):
    return _request_json(f"https://api.modrinth.com/v2/project/{project_id}/version")


def lay_project_modrinth(project_id):
    """
    Lay thong tin chi tiet day du cua 1 project Modrinth (bao gom gallery anh).
    Endpoint /v2/search (dung de hien danh sach) KHONG tra ve field 'gallery',
    chi co o endpoint chi tiet nay - vi vay can goi rieng khi mo ModDetailWindow.
    """
    return _request_json(f"https://api.modrinth.com/v2/project/{project_id}")


def lay_curseforge_popular(class_id=4471, limit=50, offset=0):
    """class_id: 4471=modpack, 6=mod"""
    params = urllib.parse.urlencode({
        "gameId": 432, "classId": class_id,
        "pageSize": limit, "index": offset, "sortField": 2, "sortOrder": "desc",
    })
    data = _request_json(
        f"https://api.curseforge.com/v1/mods/search?{params}",
        {"x-api-key": CURSEFORGE_API_KEY})
    total = data.get("pagination", {}).get("totalCount", 0)
    return data.get("data", []), total


def lay_category_curseforge(class_id=4471):
    """
    Lay danh sach category THAT cua CurseForge cho 1 loai noi dung (class_id).
    Tra ve list dict [{"id": 421, "name": "Adventure and RPG"}, ...] - dung
    de fill vao dropdown Category va tra cuu id khi nguoi dung chon ten.
    class_id: 4471=modpack, 6=mod, 12=resourcepack, 6552=shader.
    """
    params = urllib.parse.urlencode({"gameId": 432, "classId": class_id})
    data = _request_json(
        f"https://api.curseforge.com/v1/categories?{params}",
        {"x-api-key": CURSEFORGE_API_KEY})
    cats = data.get("data", [])
    # Chi giu cac category cap cao nhat thuoc dung class_id nay (CurseForge
    # tra ve ca category con/cha lan nhau qua field parentCategoryId).
    return sorted(
        [{"id": c.get("id"), "name": c.get("name", "")} for c in cats
         if c.get("classId") == class_id],
        key=lambda c: c["name"]
    )


def tim_kiem_curseforge(tu_khoa, mc_version="", loader="", limit=50, class_id=4471,
                         offset=0, category_id=None):
    """class_id: 4471=modpack, 6=mod
    category_id: id so (lay tu lay_category_curseforge) - None/0 nghia la khong loc."""
    p = {"gameId": 432, "classId": class_id, "searchFilter": tu_khoa,
         "pageSize": limit, "index": offset, "sortField": 2, "sortOrder": "desc"}
    if mc_version:
        p["gameVersion"] = mc_version
    if loader and loader != "Tất cả":
        lm = {"Fabric": 4, "Forge": 1, "Quilt": 5, "NeoForge": 6}
        if loader in lm:
            p["modLoaderType"] = lm[loader]
    if category_id:
        p["categoryId"] = category_id
    data = _request_json(
        f"https://api.curseforge.com/v1/mods/search?{urllib.parse.urlencode(p)}",
        {"x-api-key": CURSEFORGE_API_KEY})
    total = data.get("pagination", {}).get("totalCount", 0)
    return data.get("data", []), total


def lay_phien_ban_curseforge(mod_id):
    data = _request_json(
        f"https://api.curseforge.com/v1/mods/{mod_id}/files?pageSize=30",
        {"x-api-key": CURSEFORGE_API_KEY})
    return data.get("data", [])