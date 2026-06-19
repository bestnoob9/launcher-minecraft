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

import concurrent.futures

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


def _tai_file_don_gian(url, dest_path, cancel_event=None, so_lan_thu=3):
    """
    Tai 1 file vao file tam roi rename — dam bao khong bi corrupt neu bi ngat.
    Co kiem tra Content-Length sau khi tai xong, tu dong retry neu thieu byte.
    """
    headers = {"User-Agent": MODRINTH_USER_AGENT}
    tmp_path = dest_path + ".part"

    for lan in range(so_lan_thu):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                content_length = int(resp.headers.get("Content-Length") or 0)
                da_tai = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            raise Exception("__HUY__")
                        block = resp.read(65536)
                        if not block:
                            break
                        f.write(block)
                        da_tai += len(block)

            # Kiem tra du byte
            if content_length > 0 and da_tai < content_length:
                raise IOError(
                    f"Tai thieu byte: nhan {da_tai}/{content_length} "
                    f"({os.path.basename(dest_path)})"
                )

            # Thanh cong — rename file tam thanh file that
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
            return  # thoat thanh cong

        except Exception as e:
            # Xoa file tam neu con
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

            if isinstance(e, Exception) and str(e) == "__HUY__":
                raise  # truyen huy len tren, khong retry

            if lan < so_lan_thu - 1:
                print(f"[retry {lan+1}/{so_lan_thu}] {os.path.basename(dest_path)}: {e}")
                import time; time.sleep(1.5 * (lan + 1))  # back-off
            else:
                raise  # het luot thu, nem loi len tren


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


def cai_modpack_tu_file(duong_dan_zip, ten_instance, lbl_status, callback_xong=None, cancel_event=None):
    """
    Giai nen va cai Modpack vao instance moi.
    Ho tro:
      - Modrinth .mrpack  (co modrinth.index.json)
      - CurseForge .zip   (co manifest.json)
      - ZIP thong thuong  (giai nen thang vao instance/)
    cancel_event: threading.Event — neu duoc set thi dung lai, xoa folder dang do va xoa config.
    """
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    # ten_instance dung cho key config (dau cach), ten_folder dung cho thu muc (gach duoi)
    ten_instance     = ten_instance.replace("_", " ").strip()
    ten_folder       = ten_instance.replace(" ", "_")
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    os.makedirs(thu_muc_instance, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _don_dep_va_huy():
        """Xoa folder instance dang tao do va xoa khoi config neu da ghi."""
        try:
            if os.path.exists(thu_muc_instance):
                shutil.rmtree(thu_muc_instance)
        except Exception:
            pass
        try:
            if ten_instance in config.current_config.get("danh_sach_instances", {}):
                del config.current_config["danh_sach_instances"][ten_instance]
                config.luu_toan_bo_cau_hinh()
        except Exception:
            pass

    def _check_huy():
        """Kiem tra co huy — neu co thi don dep va nem exception de thoat thread."""
        if cancel_event and cancel_event.is_set():
            _don_dep_va_huy()
            raise Exception("__HUY__")

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

                    version_goc = deps.get("minecraft", "").strip()
                    if not version_goc:
                        import re
                        for k, v in deps.items():
                            m = re.match(r"(\d+\.\d+(?:\.\d+)?)", str(v))
                            if m:
                                version_goc = m.group(1)
                                break

                    if deps.get("quilt-loader"):
                        loai_game   = "Quilt"
                        version_mod = deps.get("quilt-loader", "")
                    elif deps.get("fabric-loader"):
                        loai_game   = "Fabric"
                        version_mod = deps.get("fabric-loader", "")
                    elif deps.get("forge"):
                        loai_game   = "Forge"
                        version_mod = deps.get("forge", "")
                    elif deps.get("neoforge"):
                        loai_game   = "NeoForge"
                        version_mod = deps.get("neoforge", "")

                    modrinth_files = index_data.get("files", [])
                    prefix         = "overrides/"

                # ── CurseForge .zip ───────────────────────────────────
                elif "manifest.json" in names:
                    manifest   = json.loads(z.read("manifest.json"))
                    mc_info    = manifest.get("minecraft", {})
                    version_goc = mc_info.get("version", "1.21.1")
                    loaders    = mc_info.get("modLoaders", [])
                    if loaders:
                        loader_id = loaders[0].get("id", "")
                        if "-" in loader_id:
                            loai_game, version_mod = loader_id.split("-", 1)
                            loai_game = loai_game.capitalize()
                            # Forge dung format "1.19.2-43.5.0", nhung CurseForge manifest
                            # chi luu "forge-43.5.0" -> phai them prefix MC version vao
                            if loai_game == "Forge" and not version_mod.startswith(version_goc):
                                version_mod = f"{version_goc}-{version_mod}"
                        else:
                            loai_game = loader_id.capitalize()

                    cf_mods = manifest.get("files", [])

                    # Giai nen overrides CurseForge
                    matched_prefix = None
                    for candidate in ("overrides/", "Overrides/"):
                        if any(n.startswith(candidate) for n in names):
                            matched_prefix = candidate
                            break
                    if matched_prefix:
                        for member in names:
                            _check_huy()
                            if not member.startswith(matched_prefix):
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
                        _check_huy()
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
                        _check_huy()
                        dest = os.path.join(thu_muc_instance, member.replace("/", os.sep))
                        if member.endswith("/"):
                            os.makedirs(dest, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with z.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())

            # Kiem tra huy sau khi giai nen xong, truoc khi tai mod
            _check_huy()

            # ── Tai mod tu Modrinth (mrpack) — SONG SONG ────────────────────
            if modrinth_files:
                tong_mod = len(modrinth_files)
                loi_tai  = []
                da_tai   = [0]  # dung list de cap nhat tu ben trong closure
                lock     = threading.Lock()

                def _tai_mot_mod(args):
                    i, mf = args
                    if cancel_event and cancel_event.is_set():
                        return  # dung lai som

                    rel_path = mf.get("path", "")
                    urls     = mf.get("downloads", [])
                    if not rel_path or not urls:
                        return

                    dest_file = os.path.join(thu_muc_instance, rel_path.replace("/", os.sep))
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

                    kich_thuoc_mong_doi = mf.get("fileSize", 0)
                    if os.path.exists(dest_file) and kich_thuoc_mong_doi > 0:
                        kich_thuoc_thuc = os.path.getsize(dest_file)
                        if kich_thuoc_thuc == kich_thuoc_mong_doi:
                            with lock:
                                da_tai[0] += 1
                                _cap(f"Bo qua (da co): {os.path.basename(rel_path)}  ({da_tai[0]}/{tong_mod})", "#607D8B")
                            return
                        else:
                            # File bi thieu byte, xoa de tai lai
                            try:
                                os.remove(dest_file)
                                print(f"[fix] Xoa file thieu byte: {os.path.basename(dest_file)} "
                                      f"({kich_thuoc_thuc} / {kich_thuoc_mong_doi} bytes)")
                            except Exception:
                                pass

                    ten_mod    = os.path.basename(rel_path)
                    thanh_cong = False
                    for url in urls:
                        try:
                            _tai_file_don_gian(url, dest_file, cancel_event)
                            thanh_cong = True
                            break
                        except Exception as _e:
                            if cancel_event and cancel_event.is_set():
                                return  # dung ngay, khong thu URL tiep
                            continue

                    with lock:
                        da_tai[0] += 1
                        if thanh_cong:
                            _cap(f"Da tai ({da_tai[0]}/{tong_mod}): {ten_mod}", "#1E88E5")
                        else:
                            loi_tai.append(ten_mod)

                MAX_WORKERS = 8  # tai toi da 8 mod cung luc
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                    futures = [pool.submit(_tai_mot_mod, arg) for arg in enumerate(modrinth_files)]
                    for fut in concurrent.futures.as_completed(futures):
                        if cancel_event and cancel_event.is_set():
                            for f in futures:
                                f.cancel()
                            break
                        try:
                            fut.result()
                        except Exception:
                            pass

                _check_huy()
                if loi_tai:
                    _cap(f"Hoan thanh (loi {len(loi_tai)} mod): {', '.join(loi_tai[:3])}...", "orange")
                else:
                    _cap(f"Da tai xong {tong_mod} mod!", "#2b8c54")

            # ── Tai mod tu CurseForge manifest — SONG SONG ─────────────────
            if cf_mods:
                tong_cf  = len(cf_mods)
                loi_cf   = []
                da_cf    = [0]
                lock_cf  = threading.Lock()

                def _thu_muc_theo_loai(ten_file, class_id_cf):
                    """
                    Chon thu muc dich dua tren class_id CurseForge hoac phan mo rong file.
                    class_id: 6=Mods, 12=ResourcePacks, 6552=Shaders, 4546=DataPacks
                    """
                    if class_id_cf == 12 or "resourcepack" in ten_file.lower():
                        sub = "resourcepacks"
                    elif class_id_cf == 6552 or "shader" in ten_file.lower():
                        sub = "shaderpacks"
                    elif class_id_cf == 4546 or "datapack" in ten_file.lower():
                        sub = os.path.join("saves", "datapacks")
                    else:
                        sub = "mods"
                    thu_muc = os.path.join(thu_muc_instance, sub)
                    os.makedirs(thu_muc, exist_ok=True)
                    return thu_muc

                def _tai_mot_mod_cf(entry):
                    if cancel_event and cancel_event.is_set():
                        return

                    project_id = entry.get("projectID")
                    file_id    = entry.get("fileID")
                    required   = entry.get("required", True)
                    if not required or not project_id or not file_id:
                        return

                    try:
                        url_info  = f"https://api.curseforge.com/v1/mods/{project_id}/files/{file_id}"
                        file_data = _request_json(url_info, {"x-api-key": CURSEFORGE_API_KEY})
                        file_info = file_data.get("data", {})
                        ten_file  = file_info.get("fileName", f"{file_id}.jar")
                        dl_url    = file_info.get("downloadUrl", "")

                        try:
                            proj_data = _request_json(
                                f"https://api.curseforge.com/v1/mods/{project_id}",
                                {"x-api-key": CURSEFORGE_API_KEY})
                            class_id_cf = proj_data.get("data", {}).get("classId", 6)
                        except Exception:
                            class_id_cf = 6

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
                            _tai_file_don_gian(dl_url, dest, cancel_event)

                        with lock_cf:
                            da_cf[0] += 1
                            _cap(f"OK: {ten_file}  ({da_cf[0]}/{tong_cf})", "#2b8c54")

                    except Exception as ex:
                        with lock_cf:
                            da_cf[0] += 1
                            loi_cf.append(str(file_id))
                        print(f"[CF mod] Loi {file_id}: {ex}")

                MAX_WORKERS_CF = 5  # CF API co rate-limit nen dung it worker hon
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CF) as pool:
                    futures_cf = [pool.submit(_tai_mot_mod_cf, entry) for entry in cf_mods]
                    for fut in concurrent.futures.as_completed(futures_cf):
                        if cancel_event and cancel_event.is_set():
                            for f in futures_cf:
                                f.cancel()
                            break
                        try:
                            fut.result()
                        except Exception:
                            pass

                _check_huy()
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
            if str(e) == "__HUY__":
                _cap("Da huy. Da xoa du lieu cai dat do.", "#E53935")
            else:
                _cap(f"Loi cai dat: {e}", "red")
        finally:
            _dang_cai_modpack = False

    threading.Thread(target=_chay, daemon=True).start()