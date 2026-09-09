import os
import json
import re
import shutil
import time
import zipfile
import config
from components.install_utils import ten_folder_an_toan
try:
    from PIL import Image
    _PIL_OK = True
except Exception:
    _PIL_OK = False
LOADER_ICON = {
    "Vanilla":  "🟫",
    "Forge":    "⚒",
    "NeoForge": "🔶",
    "Fabric":   "🧵",
    "Quilt":    "🧶",
}
LOADER_LETTER = {
    "Vanilla":  "V",
    "Forge":    "Fo",
    "NeoForge": "N",
    "Fabric":   "F",
    "Quilt":    "Q",
}
LOADER_COLOR = {
    "Vanilla":  "#6D8A96",
    "Forge":    "#6B4A2B",
    "NeoForge": "#D3762A",
    "Fabric":   "#9C6BD6",
    "Quilt":    "#7A56D6",
}
_COVER_NAMES = ("icon.png", "cover.png", "instance.png",
                "icon.jpg", "cover.jpg", "instance.jpg")
_TEN_THU_MUC_MOD_ICONS = ".mod_icons"
_FALLBACK_ICON_THEO_LOAI = {
    "mods": "mod.png",
    "sh":   "shader.png",
    "rp":   "resourcepack.png",
    "dp":   "datapack.png",
}
_FALLBACK_ICON_MAC_DINH = "default.png"
def thu_muc_mod_icons(ten_instance: str) -> str:
    return os.path.join(thu_muc_instance(ten_instance), _TEN_THU_MUC_MOD_ICONS)
def duong_dan_icon_da_tai(ten_instance: str, source, project_id):
    if not source or not project_id:
        return None
    ten_file = f"{source}_{project_id}.png"
    p = os.path.join(thu_muc_mod_icons(ten_instance), ten_file)
    return p if os.path.exists(p) else None
def duong_dan_icon_notfind(loai_tab: str) -> str:
    base = os.path.join(config._ASSETS_DIR, "iconinstance", "notfind")
    ten = _FALLBACK_ICON_THEO_LOAI.get(loai_tab, _FALLBACK_ICON_MAC_DINH)
    p = os.path.join(base, ten)
    if os.path.exists(p):
        return p
    return os.path.join(base, _FALLBACK_ICON_MAC_DINH)
def thu_muc_goc_game():
    return config.current_config.get("thu_muc_game", "") or ""
def thu_muc_instance(ten_instance: str) -> str:
    goc = thu_muc_goc_game()
    ten_folder = ten_folder_an_toan(ten_instance)
    return os.path.join(goc, "Instances", ten_folder)
def duong_dan_info(ten_instance: str) -> str:
    return os.path.join(thu_muc_instance(ten_instance), "instance_info.json")
def doc_instance_info(ten_instance: str) -> dict:
    path = duong_dan_info(ten_instance)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
def ghi_cap_nhat_instance_info(ten_instance: str, updates: dict):
    path = duong_dan_info(ten_instance)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = doc_instance_info(ten_instance)
        data.update(updates)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[InstanceInfo] Không thể ghi {ten_instance}: {e}")
def lay_gia_tri_instance(ten_instance: str) -> dict:
    cfg = config.current_config.get("danh_sach_instances", {}).get(ten_instance, {})
    info = doc_instance_info(ten_instance)
    return {
        "version_goc": cfg.get("version_goc", info.get("version_goc", "")),
        "loai_game":   cfg.get("loai_game", info.get("loai_game", "Vanilla")),
        "version_mod": cfg.get("version_mod", info.get("version_mod", "Vanilla")),
        "author":      info.get("author", ""),
        "last_played": info.get("last_played"),
        "play_time_giay": info.get("play_time_giay", 0),
    }
def tim_anh_bia(ten_instance: str):
    folder = thu_muc_instance(ten_instance)
    for name in _COVER_NAMES:
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p
    return None
_DUOI_ANH_HOP_LE = (".png", ".jpg", ".jpeg", ".webp", ".gif")
_COVER_CANH_DAI_TOI_DA = 512
def thu_muc_instancefree() -> str:
    return os.path.join(config._ASSETS_DIR, "iconinstance", "instancefree")
def danh_sach_anh_instancefree():
    folder = thu_muc_instancefree()
    if not os.path.isdir(folder):
        return []
    ket_qua = []
    try:
        for name in sorted(os.listdir(folder)):
            if name.startswith("."):
                continue
            if not name.lower().endswith(_DUOI_ANH_HOP_LE):
                continue
            p = os.path.join(folder, name)
            if os.path.isfile(p):
                ket_qua.append(p)
    except Exception:
        pass
    return ket_qua
def luu_anh_bia(ten_instance: str, duong_dan_nguon: str) -> bool:
    if not duong_dan_nguon or not os.path.exists(duong_dan_nguon):
        return False
    try:
        thu_muc = thu_muc_instance(ten_instance)
        os.makedirs(thu_muc, exist_ok=True)
        dich = os.path.join(thu_muc, "icon.png")
        if os.path.abspath(duong_dan_nguon) == os.path.abspath(dich):
            return True
        da_luu = False
        if _PIL_OK:
            try:
                img = Image.open(duong_dan_nguon)
                co_alpha = (img.mode in ("RGBA", "LA")
                            or (img.mode == "P" and "transparency" in img.info))
                img = img.convert("RGBA") if co_alpha else img.convert("RGB")
                w, h = img.size
                canh_dai = max(w, h)
                if canh_dai > _COVER_CANH_DAI_TOI_DA:
                    ti_le = _COVER_CANH_DAI_TOI_DA / canh_dai
                    kich_thuoc_moi = (max(1, round(w * ti_le)), max(1, round(h * ti_le)))
                    img = img.resize(kich_thuoc_moi, Image.LANCZOS)
                if img.mode == "RGBA":
                    nen = Image.new("RGB", img.size, (30, 30, 30))
                    nen.paste(img, mask=img.split()[-1])
                    img = nen
                tmp = dich + ".part"
                img.save(tmp, "PNG")
                if os.path.exists(dich):
                    os.remove(dich)
                os.rename(tmp, dich)
                da_luu = True
            except Exception:
                da_luu = False
        if not da_luu:
            shutil.copy2(duong_dan_nguon, dich)
        ghi_cap_nhat_instance_info(ten_instance, {"cover": "icon.png"})
        return True
    except Exception:
        return False
_TI_LE_GALLERY_TOI_THIEU = 1.35
def anh_bia_hien_tai_la_gallery(ten_instance: str) -> bool:
    if not _PIL_OK:
        return False
    path = tim_anh_bia(ten_instance)
    if not path:
        return False
    try:
        with Image.open(path) as img:
            w, h = img.size
        if not w or not h:
            return False
        canh_dai = max(w, h)
        canh_ngan = min(w, h)
        return (canh_dai / canh_ngan) >= _TI_LE_GALLERY_TOI_THIEU
    except Exception:
        return False
def dinh_dang_thoi_gian_choi(giay: float) -> str:
    if not giay:
        return "Chưa chơi"
    giay = int(giay)
    if giay < 3600:
        phut = max(1, giay // 60)
        return f"{phut} phút"
    gio = giay / 3600
    if gio < 10:
        return f"{gio:.1f} giờ".replace(".0", "")
    return f"{int(gio)} giờ"
def dinh_dang_lan_choi_cuoi(ts) -> str:
    if not ts:
        return "Chưa chơi"
    try:
        ts = float(ts)
    except Exception:
        return "Chưa chơi"
    delta = max(0, time.time() - ts)
    if delta < 60:
        return "Vừa xong"
    if delta < 3600:
        return f"{int(delta // 60)} phút trước"
    if delta < 86400:
        return f"{int(delta // 3600)} giờ trước"
    ngay = int(delta // 86400)
    if ngay == 1:
        return "1 ngày trước"
    if ngay < 30:
        return f"{ngay} ngày trước"
    thang = ngay // 30
    return f"{thang} tháng trước"
def bien_the_duong_dan_jar(duong_dan_jar: str):
    a = duong_dan_jar
    b = a[: -len(".disabled")] if a.endswith(".disabled") else a
    c = a if a.endswith(".disabled") else a + ".disabled"
    ket_qua = []
    for p in (a, b, c):
        if p not in ket_qua:
            ket_qua.append(p)
    return ket_qua
def _phien_ban_hop_le(v):
    if not v or not isinstance(v, str):
        return None
    v = v.strip()
    if not v or "${" in v or v.lower() in ("unknown", "none"):
        return None
    return v
_RE_VERSION_ANCHOR = re.compile(r'\d+(?:\.\d+){1,}')
def phien_ban_tu_ten_file(filename: str):
    if not filename:
        return None
    base = filename[: -len(".disabled")] if filename.endswith(".disabled") else filename
    stem = os.path.splitext(base)[0]
    diem_neo = list(_RE_VERSION_ANCHOR.finditer(stem))
    if not diem_neo:
        return None
    bat_dau_nhom_cuoi = diem_neo[0].start()
    for m in diem_neo[1:]:
        i = m.start()
        ky_tu_truoc = stem[i - 1] if i > 0 else ""
        if ky_tu_truoc in ("-", "_"):
            bat_dau_nhom_cuoi = i
    return stem[bat_dau_nhom_cuoi:]
def doc_meta_jar(duong_dan_jar: str):
    path_thuc = duong_dan_jar
    for p in bien_the_duong_dan_jar(duong_dan_jar):
        if os.path.exists(p):
            path_thuc = p
            break
    try:
        with zipfile.ZipFile(path_thuc, "r") as zf:
            try:
                data = json.loads(zf.read("fabric.mod.json").decode("utf-8", "ignore"))
                ten = data.get("name") or None
                tac_gia = "—"
                authors = data.get("authors", [])
                if authors:
                    tens = [a if isinstance(a, str) else a.get("name", "") for a in authors]
                    tens = [t for t in tens if t]
                    if tens:
                        tac_gia = tens[0]
                phien_ban = _phien_ban_hop_le(data.get("version"))
                if ten or tac_gia != "—" or phien_ban:
                    return ten, tac_gia, phien_ban
            except KeyError:
                pass
            except Exception:
                pass
            try:
                data = json.loads(zf.read("quilt.mod.json").decode("utf-8", "ignore"))
                ql_meta = data.get("quilt_loader", {})
                ten = (data.get("name")
                       or ql_meta.get("metadata", {}).get("name")
                       or None)
                tac_gia = "—"
                contributors = ql_meta.get("contributors", {})
                if contributors:
                    tac_gia = list(contributors.keys())[0]
                phien_ban = _phien_ban_hop_le(ql_meta.get("version") or data.get("version"))
                if ten or tac_gia != "—" or phien_ban:
                    return ten, tac_gia, phien_ban
            except KeyError:
                pass
            except Exception:
                pass
            for meta in ("META-INF/mods.toml", "META-INF/neoforge.mods.toml"):
                try:
                    raw = zf.read(meta).decode("utf-8", "ignore")
                    ten = None
                    tac_gia = "—"
                    m_ten = re.search(r'displayName\s*=\s*"([^"]+)"', raw)
                    if m_ten:
                        ten = m_ten.group(1)
                    m_tg = re.search(r'authors\s*=\s*"([^"]+)"', raw)
                    if m_tg:
                        tac_gia = m_tg.group(1).split(",")[0].strip()
                    m_pb = re.search(r'^\s*version\s*=\s*"([^"]+)"', raw, re.MULTILINE)
                    phien_ban = _phien_ban_hop_le(m_pb.group(1)) if m_pb else None
                    if ten or tac_gia != "—" or phien_ban:
                        return ten, tac_gia, phien_ban
                except KeyError:
                    continue
                except Exception:
                    continue
            try:
                raw = zf.read("mcmod.info").decode("utf-8", "ignore")
                data = json.loads(raw)
                if isinstance(data, list) and data:
                    data = data[0]
                ten = data.get("name") or None
                tac_gia = "—"
                authors = data.get("authorList") or data.get("authors")
                if authors:
                    tac_gia = authors[0]
                phien_ban = _phien_ban_hop_le(data.get("version"))
                if ten or tac_gia != "—" or phien_ban:
                    return ten, tac_gia, phien_ban
            except KeyError:
                pass
            except Exception:
                pass
    except Exception:
        pass
    return None, "—", None
def doc_tac_gia_jar(duong_dan_jar: str) -> str:
    _, tac_gia, _ = doc_meta_jar(duong_dan_jar)
    return tac_gia