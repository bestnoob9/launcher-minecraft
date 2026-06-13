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

# =====================================================================
# CONSTANTS
# =====================================================================

CURSEFORGE_API_KEY  = "$2a$10$tlioOAg8vpMZg3nN1c5lautxofMN2DXCzLn4.8nyr.MTBG4IYHVT2"
MODRINTH_USER_AGENT = "MinecraftLauncher/1.0 (github.com/user/mc-launcher)"


# =====================================================================
# LOW-LEVEL HTTP HELPERS
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
    return data.get("hits", []), data.get("total_hits", 0)


def lay_modrinth_popular(project_type="modpack", limit=50, offset=0):
    return _modrinth_search(project_type, limit=limit, offset=offset)


def tim_kiem_modrinth(project_type, tu_khoa, mc_version="", loader="", category="", limit=50, offset=0):
    return _modrinth_search(project_type, tu_khoa, mc_version, loader, category, limit, offset)


def lay_phien_ban_modrinth(project_id):
    return _request_json(f"https://api.modrinth.com/v2/project/{project_id}/version")


# =====================================================================
# CURSEFORGE API
# =====================================================================

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


def tim_kiem_curseforge(tu_khoa, mc_version="", loader="", limit=50, class_id=4471, offset=0):
    """class_id: 4471=modpack, 6=mod"""
    p = {"gameId": 432, "classId": class_id, "searchFilter": tu_khoa,
         "pageSize": limit, "index": offset, "sortField": 2, "sortOrder": "desc"}
    if mc_version:
        p["gameVersion"] = mc_version
    if loader and loader != "Tat ca":
        lm = {"Fabric": 4, "Forge": 1, "Quilt": 5, "NeoForge": 6}
        if loader in lm:
            p["modLoaderType"] = lm[loader]
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

