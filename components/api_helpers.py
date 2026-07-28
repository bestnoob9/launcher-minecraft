import urllib.request
import urllib.parse
import urllib.error
import json

CURSEFORGE_PROXY_BASE = "https://dark-thunder-4c52.vubest2009.workers.dev"

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

        cats = category if isinstance(category, (list, tuple, set)) else [category]
        cats = [c for c in cats if c and c not in ("Tất cả", "")]
        if cats:

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
    return _request_json(f"https://api.modrinth.com/v2/project/{project_id}")

def lay_curseforge_popular(class_id=4471, limit=50, offset=0):
    params = urllib.parse.urlencode({
        "gameId": 432, "classId": class_id,
        "pageSize": limit, "index": offset, "sortField": 2, "sortOrder": "desc",
    })
    data = _request_json(f"{CURSEFORGE_PROXY_BASE}/v1/mods/search?{params}")
    total = data.get("pagination", {}).get("totalCount", 0)
    return data.get("data", []), total

def lay_category_curseforge(class_id=4471):
    params = urllib.parse.urlencode({"gameId": 432, "classId": class_id})
    data = _request_json(f"{CURSEFORGE_PROXY_BASE}/v1/categories?{params}")
    cats = data.get("data", [])

    return sorted(
        [{"id": c.get("id"), "name": c.get("name", "")} for c in cats
         if c.get("classId") == class_id],
        key=lambda c: c["name"]
    )

def tim_kiem_curseforge(tu_khoa, mc_version="", loader="", limit=50, class_id=4471,
                         offset=0, category_id=None):
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
    data = _request_json(f"{CURSEFORGE_PROXY_BASE}/v1/mods/search?{urllib.parse.urlencode(p)}")
    total = data.get("pagination", {}).get("totalCount", 0)
    return data.get("data", []), total

def lay_phien_ban_curseforge(mod_id):
    data = _request_json(f"{CURSEFORGE_PROXY_BASE}/v1/mods/{mod_id}/files?pageSize=30")
    return data.get("data", [])