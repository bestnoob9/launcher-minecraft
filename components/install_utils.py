"""
install_utils.py
----------------
Cac ham tai file va cai dat:
  - tai_file()               : tai 1 file lon co progress callback
  - _tai_file_don_gian()     : tai 1 file don gian (dung cho tung mod)
  - cai_rsp_shader_tu_file() : cai Resource Pack / Shader vao instance
  - cai_mod_tu_file()        : copy .jar mod vao thu muc mods/
  - cai_modpack_tu_file()    : giai nen va cai Modpack (.mrpack / .zip CF)
  - dang_cai_modpack()       : kiem tra trang thai dang cai

Phu thuoc: config, api_helpers
"""

import os
import io
import json
import shutil
import threading
import urllib.request
import urllib.parse
import zipfile

import config
from components.api_helpers import (
    MODRINTH_USER_AGENT,
    CURSEFORGE_API_KEY,
    _request_json,
)


# =====================================================================
# TAI FILE CO PROGRESS
# =====================================================================

def tai_file(url, duong_dan_luu, callback_tien_do=None, extra_headers=None):
    """Tai 1 file lon, co progress callback(da_tai, tong)."""
    headers = {"User-Agent": MODRINTH_USER_AGENT, "Accept": "application/octet-stream, */*"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        tong   = int(resp.headers.get("Content-Length", 0))
        da_tai = 0
        with open(duong_dan_luu, "wb") as f:
            while True:
                block = resp.read(8192)
                if not block:
                    break
                f.write(block)
                da_tai += len(block)
                if callback_tien_do and tong:
                    callback_tien_do(da_tai, tong)


def _tai_file_don_gian(url, dest_path):
    """Tai 1 file, khong co progress callback, dung cho tung mod trong modpack."""
    headers = {"User-Agent": MODRINTH_USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest_path, "wb") as f:
            while True:
                block = resp.read(65536)
                if not block:
                    break
                f.write(block)


# =====================================================================
# CAI RESOURCE PACK / SHADER
# =====================================================================

def cai_rsp_shader_tu_file(duong_dan_zip, ten_instance, loai, lbl_status, callback_xong=None):
    """
    Cai Resource Pack hoac Shader vao thu muc instance tuong ung.
    loai: 'rsp' -> resourcepacks/, 'shader' -> shaderpacks/
    """
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


# =====================================================================
# CAI MOD (.jar)
# =====================================================================

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


# =====================================================================
# CAI MODPACK (.mrpack Modrinth / .zip CurseForge)
# =====================================================================

# Bien toan cuc theo doi trang thai dang cai modpack
_dang_cai_modpack = False

def dang_cai_modpack():
    """Tra ve True neu dang trong qua trinh cai modpack."""
    return _dang_cai_modpack


def cai_modpack_tu_file(duong_dan_zip, ten_instance, lbl_status, callback_xong=None):
    """
    Giai nen va cai Modpack vao instance moi.
    Ho tro:
      - Modrinth .mrpack  (co modrinth.index.json)
      - CurseForge .zip   (co manifest.json)
      - ZIP thong thuong  (giai nen thang vao instance/)
    """
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    # ten_instance dung cho key config (dau cach), ten_folder dung cho thu muc (gach duoi)
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
            cf_mods        = []

            with zipfile.ZipFile(duong_dan_zip, "r") as z:
                names = z.namelist()

                # ── Modrinth .mrpack ──────────────────────────────────
                if "modrinth.index.json" in names:
                    index_data  = json.loads(z.read("modrinth.index.json"))
                    deps        = index_data.get("dependencies", {})
                    print(f"[mrpack] dependencies doc duoc: {deps}")

                    version_goc = deps.get("minecraft", "")
                    if not version_goc:
                        import re as _re
                        m = _re.search(r"(\d+\.\d+\.?\d*)", os.path.basename(duong_dan_zip))
                        version_goc = m.group(1) if m else "1.21.1"

                    if "fabric-loader" in deps:
                        loai_game, version_mod = "Fabric",   deps["fabric-loader"]
                    elif "quilt-loader" in deps:
                        loai_game, version_mod = "Quilt",    deps["quilt-loader"]
                    elif "neoforge" in deps:
                        loai_game, version_mod = "NeoForge", deps["neoforge"]
                    elif "forge" in deps:
                        loai_game, version_mod = "Forge",    deps["forge"]
                    elif "minecraftForge" in deps:
                        loai_game, version_mod = "Forge",    deps["minecraftForge"]

                    print(f"[mrpack] Ket qua: loai={loai_game}, mc={version_goc}, mod={version_mod}")
                    modrinth_files = index_data.get("files", [])
                    prefix = "overrides/"

                # ── CurseForge .zip ───────────────────────────────────
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

                    # CurseForge co the co nhieu prefix overrides
                    CF_PREFIXES = ("overrides/", "client-overrides/")
                    for member in names:
                        matched_prefix = None
                        for pfx in CF_PREFIXES:
                            if member.startswith(pfx):
                                matched_prefix = pfx
                                break
                        if not matched_prefix:
                            continue
                        rel = member[len(matched_prefix):]
                        if not rel:
                            continue
                        dest = os.path.join(thu_muc_instance, rel.replace("/", os.sep))
                        if member.endswith("/"):
                            os.makedirs(dest, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with z.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())
                    prefix = None  # da xu ly o tren, bo qua vong lap chung ben duoi

                # ── ZIP thong thuong ──────────────────────────────────
                else:
                    prefix = None

                # Giai nen files overrides / tat ca (chi cho Modrinth va ZIP thuong)
                if prefix is not None:
                    for member in names:
                        if not member.startswith(prefix):
                            continue
                        rel = member[len(prefix):]
                        if not rel:
                            continue
                        dest = os.path.join(thu_muc_instance, rel.replace("/", os.sep))
                        if member.endswith("/"):
                            os.makedirs(dest, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with z.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())
                elif "manifest.json" not in names:
                    # ZIP thong thuong: giai nen tat ca
                    for member in names:
                        dest = os.path.join(thu_muc_instance, member.replace("/", os.sep))
                        if member.endswith("/"):
                            os.makedirs(dest, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with z.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())

            # ── Tai mod tu Modrinth (mrpack) ──────────────────────────
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

                    ten_mod    = os.path.basename(rel_path)
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

            # ── Tai mod tu CurseForge manifest ────────────────────────
            if cf_mods:
                tong_cf = len(cf_mods)
                loi_cf  = []

                def _thu_muc_theo_loai(ten_file, class_id_cf):
                    """
                    Chon thu muc dich dua tren class_id CurseForge hoac phan mo rong file.
                    class_id: 6=Mods, 12=ResourcePacks, 6552=Shaders, 4546=DataPacks
                    """
                    ext = os.path.splitext(ten_file)[1].lower()
                    if class_id_cf == 12 or "resourcepack" in ten_file.lower():
                        sub = "resourcepacks"
                    elif class_id_cf == 6552 or "shader" in ten_file.lower():
                        sub = "shaderpacks"
                    elif class_id_cf == 4546 or "datapack" in ten_file.lower():
                        sub = os.path.join("saves", "datapacks")
                    else:
                        # Mac dinh la mods (jar hoac zip mod)
                        sub = "mods"
                    thu_muc = os.path.join(thu_muc_instance, sub)
                    os.makedirs(thu_muc, exist_ok=True)
                    return thu_muc

                for i, entry in enumerate(cf_mods):
                    project_id = entry.get("projectID")
                    file_id    = entry.get("fileID")
                    required   = entry.get("required", True)
                    if not required or not project_id or not file_id:
                        continue

                    _cap(f"Dang tai mod CF  {i+1}/{tong_cf}  (id={file_id})...", "#1E88E5")
                    try:
                        # Lay thong tin file va project de biet class_id
                        url_info  = f"https://api.curseforge.com/v1/mods/{project_id}/files/{file_id}"
                        file_data = _request_json(url_info, {"x-api-key": CURSEFORGE_API_KEY})
                        file_info = file_data.get("data", {})
                        ten_file  = file_info.get("fileName", f"{file_id}.jar")
                        dl_url    = file_info.get("downloadUrl", "")

                        # Lay class_id cua project de phan loai thu muc
                        try:
                            proj_data = _request_json(
                                f"https://api.curseforge.com/v1/mods/{project_id}",
                                {"x-api-key": CURSEFORGE_API_KEY})
                            class_id_cf = proj_data.get("data", {}).get("classId", 6)
                        except Exception:
                            class_id_cf = 6  # fallback = Mods

                        # CurseForge doi khi tra downloadUrl = null -> tu build URL
                        if not dl_url:
                            id_str = str(file_id)
                            p1 = id_str[:4]
                            p2 = id_str[4:].lstrip("0") or "0"
                            dl_url = (
                                f"https://mediafilez.forgecdn.net/files/{p1}/{p2}/"
                                f"{urllib.parse.quote(ten_file)}"
                            )

                        thu_muc_dich = _thu_muc_theo_loai(ten_file, class_id_cf)
                        dest = os.path.join(thu_muc_dich, ten_file)
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

            # Ghi instance_info.json
            with open(os.path.join(thu_muc_instance, "instance_info.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {"loai_game": loai_game, "version_goc": version_goc, "version_mod": version_mod},
                    f, indent=4, ensure_ascii=False,
                )

            # Cap nhat config
            config.current_config["danh_sach_instances"][ten_instance] = {
                "version_goc": version_goc, "loai_game": loai_game, "version_mod": version_mod,
            }
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