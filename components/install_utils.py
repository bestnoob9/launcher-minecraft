
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

_KY_TU_CAM_FOLDER = '\\/:*?"<>|'

def ten_folder_an_toan(ten_instance: str) -> str:
    ten = "".join(c for c in ten_instance if c not in _KY_TU_CAM_FOLDER)
    return ten.strip().rstrip(".") or "instance"

def tai_file(url, duong_dan_luu, callback_tien_do=None, extra_headers=None):
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
    headers = {"User-Agent": MODRINTH_USER_AGENT}
    tmp_path = dest_path + ".part"

    for lan in range(so_lan_thu):
        if cancel_event and cancel_event.is_set():
            raise Exception("__HUY__")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
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

            if content_length > 0 and da_tai < content_length:
                raise IOError(
                    f"Tai thieu byte: nhan {da_tai}/{content_length} "
                    f"({os.path.basename(dest_path)})"
                )

            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
            return

        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

            if isinstance(e, Exception) and str(e) == "__HUY__":
                raise

            if lan < so_lan_thu - 1:
                print(f"[retry {lan+1}/{so_lan_thu}] {os.path.basename(dest_path)}: {e}")
                import time; time.sleep(1.5 * (lan + 1))
            else:
                raise

def cai_rsp_shader_tu_file(duong_dan_zip, ten_instance, loai, lbl_status,
                            callback_xong=None, progress_cb=None):
    thu_muc_game     = config.current_config.get("thu_muc_game", "")
    ten_folder       = ten_folder_an_toan(ten_instance)
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    sub_dir          = "resourcepacks" if loai == "rsp" else "shaderpacks"
    thu_muc_dest     = os.path.join(thu_muc_instance, sub_dir)
    os.makedirs(thu_muc_dest, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _chay():
        if progress_cb:
            lbl_status.after(0, lambda: progress_cb(0, 1))
        try:
            ten_file = os.path.basename(duong_dan_zip)
            dest     = os.path.join(thu_muc_dest, ten_file)
            shutil.copy2(duong_dan_zip, dest)
            _cap(f"Đã cài: {ten_file} -> {sub_dir}/", "#2b8c54")
            if progress_cb:
                lbl_status.after(0, lambda: progress_cb(1, 1))
            if callback_xong:
                lbl_status.after(500, callback_xong)
        except Exception as e:
            _cap(f"Lỗi cài đặt: {e}", "red")

    threading.Thread(target=_chay, daemon=True).start()

def cai_mod_tu_file(duong_dan_jar, ten_instance, lbl_status, callback_xong=None, progress_cb=None):
    thu_muc_game     = config.current_config.get("thu_muc_game", "")
    ten_folder       = ten_folder_an_toan(ten_instance)
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    thu_muc_mods     = os.path.join(thu_muc_instance, "mods")
    os.makedirs(thu_muc_mods, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _chay():
        if progress_cb:
            lbl_status.after(0, lambda: progress_cb(0, 1))
        try:
            ten_file = os.path.basename(duong_dan_jar)
            dest     = os.path.join(thu_muc_mods, ten_file)
            shutil.copy2(duong_dan_jar, dest)
            _cap(f"Đã cài mod: {ten_file}", "#2b8c54")
            if progress_cb:
                lbl_status.after(0, lambda: progress_cb(1, 1))
            if callback_xong:
                lbl_status.after(500, callback_xong)
        except Exception as e:
            _cap(f"Lỗi cài mod: {e}", "red")

    threading.Thread(target=_chay, daemon=True).start()

_dang_cai_modpack = False

def dang_cai_modpack():
    return _dang_cai_modpack

def cai_modpack_tu_file(duong_dan_zip, ten_instance, lbl_status, callback_xong=None,
                         cancel_event=None, progress_cb=None, callback_huy=None):
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    ten_instance     = ten_instance.strip()
    ten_folder       = ten_folder_an_toan(ten_instance)
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    os.makedirs(thu_muc_instance, exist_ok=True)

    def _cap(text, mau="gray"):
        lbl_status.after(0, lambda: lbl_status.config(text=text, fg=mau))

    def _bao_tien_do(da, tong):
        if progress_cb:
            try:
                lbl_status.after(0, lambda: progress_cb(da, tong))
            except Exception:
                pass

    def _don_dep_va_huy():
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
        if cancel_event and cancel_event.is_set():
            _don_dep_va_huy()
            raise Exception("__HUY__")

    def _chay():
        global _dang_cai_modpack
        _dang_cai_modpack = True
        try:
            _cap("Đang giải nén modpack...", "#1E88E5")
            loai_game, version_goc, version_mod = "Vanilla", "1.21.1", "Vanilla"
            modrinth_files = []
            cf_mods        = []

            with zipfile.ZipFile(duong_dan_zip, "r") as z:
                names = z.namelist()

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

                        if version_mod and version_goc and not version_mod.startswith(version_goc):
                            version_mod = f"{version_goc}-{version_mod}"
                    elif deps.get("neoforge"):
                        loai_game   = "NeoForge"
                        version_mod = deps.get("neoforge", "")

                    modrinth_files = index_data.get("files", [])
                    prefix         = "overrides/"

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

                            if loai_game == "Forge" and not version_mod.startswith(version_goc):
                                version_mod = f"{version_goc}-{version_mod}"
                        else:
                            loai_game = loader_id.capitalize()

                    cf_mods = manifest.get("files", [])

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
                        prefix = None

                else:
                    prefix = None

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

                    for member in names:
                        _check_huy()
                        dest = os.path.join(thu_muc_instance, member.replace("/", os.sep))
                        if member.endswith("/"):
                            os.makedirs(dest, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with z.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())

            _check_huy()

            if modrinth_files:
                tong_mod = len(modrinth_files)
                loi_tai  = []
                da_tai   = [0]
                lock     = threading.Lock()

                def _tai_mot_mod(args):
                    i, mf = args
                    if cancel_event and cancel_event.is_set():
                        return

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
                                _cap(f"Bỏ qua (đã có): {os.path.basename(rel_path)}  ({da_tai[0]}/{tong_mod})", "#607D8B")
                                _bao_tien_do(da_tai[0], tong_mod)
                            return
                        else:

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
                                return
                            continue

                    with lock:
                        da_tai[0] += 1
                        if thanh_cong:
                            _cap(f"Đã tải ({da_tai[0]}/{tong_mod}): {ten_mod}", "#1E88E5")
                        else:
                            loi_tai.append(ten_mod)
                        _bao_tien_do(da_tai[0], tong_mod)

                MAX_WORKERS = 8
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
                try:
                    futures = [pool.submit(_tai_mot_mod, arg) for arg in enumerate(modrinth_files)]
                    con_lai = set(futures)
                    while con_lai:
                        if cancel_event and cancel_event.is_set():

                            try:
                                pool.shutdown(wait=False, cancel_futures=True)
                            except TypeError:

                                for f in con_lai:
                                    f.cancel()
                            break

                        xong, con_lai = concurrent.futures.wait(
                            con_lai, timeout=0.3,
                            return_when=concurrent.futures.FIRST_COMPLETED)
                        for fut in xong:
                            try:
                                fut.result()
                            except Exception:
                                pass
                finally:

                    pool.shutdown(wait=False)

                _check_huy()
                if loi_tai:
                    _cap(f"Hoàn thành (lỗi {len(loi_tai)} mod): {', '.join(loi_tai[:3])}...", "orange")
                else:
                    _cap(f"Đã tải xong {tong_mod} mod!", "#2b8c54")

            if cf_mods:
                tong_cf  = len(cf_mods)
                loi_cf   = []
                da_cf    = [0]
                lock_cf  = threading.Lock()

                def _thu_muc_theo_loai(ten_file, class_id_cf):
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

                        if cancel_event and cancel_event.is_set():
                            return

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

                        if cancel_event and cancel_event.is_set():
                            return

                        thu_muc_dich = _thu_muc_theo_loai(ten_file, class_id_cf)
                        dest = os.path.join(thu_muc_dich, ten_file)
                        if not os.path.exists(dest):
                            _tai_file_don_gian(dl_url, dest, cancel_event)

                        with lock_cf:
                            da_cf[0] += 1
                            _cap(f"OK: {ten_file}  ({da_cf[0]}/{tong_cf})", "#2b8c54")
                            _bao_tien_do(da_cf[0], tong_cf)

                    except Exception as ex:
                        if cancel_event and cancel_event.is_set():
                            return
                        with lock_cf:
                            da_cf[0] += 1
                            loi_cf.append(str(file_id))
                            _bao_tien_do(da_cf[0], tong_cf)
                        print(f"[CF mod] Loi {file_id}: {ex}")

                MAX_WORKERS_CF = 5
                pool_cf = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CF)
                try:
                    futures_cf = [pool_cf.submit(_tai_mot_mod_cf, entry) for entry in cf_mods]
                    con_lai_cf = set(futures_cf)
                    while con_lai_cf:
                        if cancel_event and cancel_event.is_set():
                            try:
                                pool_cf.shutdown(wait=False, cancel_futures=True)
                            except TypeError:
                                for f in con_lai_cf:
                                    f.cancel()
                            break

                        xong, con_lai_cf = concurrent.futures.wait(
                            con_lai_cf, timeout=0.3,
                            return_when=concurrent.futures.FIRST_COMPLETED)
                        for fut in xong:
                            try:
                                fut.result()
                            except Exception:
                                pass
                finally:
                    pool_cf.shutdown(wait=False)

                _check_huy()
                if loi_cf:
                    _cap(f"Hoàn thành CF (lỗi {len(loi_cf)} mod). Kiểm tra thủ công.", "orange")
                else:
                    _cap(f"Đã tải xong {tong_cf} mod CurseForge!", "#2b8c54")

            _check_huy()

            with open(os.path.join(thu_muc_instance, "instance_info.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {"loai_game": loai_game, "version_goc": version_goc, "version_mod": version_mod},
                    f, indent=4, ensure_ascii=False,
                )

            config.current_config["danh_sach_instances"][ten_instance] = {
                "version_goc": version_goc, "loai_game": loai_game, "version_mod": version_mod,
            }
            config.current_config["current_instance"] = ten_instance
            config.luu_toan_bo_cau_hinh()

            print(f"[modpack] Da luu: {ten_instance} | {loai_game} {version_goc} | mod={version_mod}")
            _cap(f"Đã cài đặt: {ten_instance}  ({loai_game} {version_goc})", "#2b8c54")
            if callback_xong:
                lbl_status.after(500, callback_xong)

        except Exception as e:
            if str(e) == "__HUY__":
                _cap("Đã hủy. Đã xóa dữ liệu cài đặt đó.", "#E53935")
            else:
                _cap(f"Lỗi cài đặt: {e}", "red")

            if callback_huy:
                lbl_status.after(500, callback_huy)
            elif callback_xong:

                lbl_status.after(500, callback_xong)
        finally:
            _dang_cai_modpack = False

    threading.Thread(target=_chay, daemon=True).start()

_TEN_FILE_INDEX = ".mcmgr_index.json"

def _duong_dan_thu_muc_instance(ten_instance):
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    return os.path.join(thu_muc_game, "Instances", ten_folder_an_toan(ten_instance))

def doc_index_instance(ten_instance):
    path = os.path.join(_duong_dan_thu_muc_instance(ten_instance), _TEN_FILE_INDEX)
    mac_dinh = {"modpack": None, "mods": {}, "resourcepacks": {}, "shaderpacks": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in mac_dinh.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return mac_dinh

def ghi_index_instance(ten_instance, data):
    path = os.path.join(_duong_dan_thu_muc_instance(ten_instance), _TEN_FILE_INDEX)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def lay_muc_da_cai(ten_instance, loai, project_id):
    if not project_id:
        return None
    idx = doc_index_instance(ten_instance)
    return idx.get(loai, {}).get(str(project_id))

def luu_muc_da_cai(ten_instance, loai, project_id, source, version_id,
                    version_number, filename, ngay=None):
    if not project_id:
        return
    idx  = doc_index_instance(ten_instance)
    nhom = idx.setdefault(loai, {})
    cu   = nhom.get(str(project_id))
    if cu and cu.get("filename") and cu["filename"] != filename:
        try:
            duong_dan_cu = os.path.join(
                _duong_dan_thu_muc_instance(ten_instance), loai, cu["filename"])
            if os.path.exists(duong_dan_cu):
                os.remove(duong_dan_cu)
        except Exception:
            pass
    nhom[str(project_id)] = {
        "source": source, "version_id": version_id,
        "version_number": version_number, "filename": filename,
        "ngay": ngay,
    }
    ghi_index_instance(ten_instance, idx)

def lay_modpack_da_cai(source, project_id):
    ds = config.current_config.get("danh_sach_instances", {})
    for ten_inst in ds:
        mp = doc_index_instance(ten_inst).get("modpack")
        if mp and mp.get("source") == source and str(mp.get("project_id")) == str(project_id):
            return ten_inst, mp.get("version_number"), mp.get("version_id"), mp.get("ngay")
    return None, None, None, None

def luu_modpack_da_cai(ten_instance, source, project_id, version_id, version_number, ngay=None):
    idx = doc_index_instance(ten_instance)
    idx["modpack"] = {
        "source": source, "project_id": project_id,
        "version_id": version_id, "version_number": version_number,
        "ngay": ngay,
    }
    ghi_index_instance(ten_instance, idx)

def lay_trang_thai_da_cai(loai, source, project_id, ten_instance=None):
    if not project_id:
        return None
    if loai == "modpack":
        ten_inst, ver_num, ver_id, ngay = lay_modpack_da_cai(source, project_id)
        if not ten_inst:
            return None
        return {"ten_instance": ten_inst, "source": source,
                "version_id": ver_id, "version_number": ver_num, "ngay": ngay}
    if not ten_instance:
        return None
    info = lay_muc_da_cai(ten_instance, loai, project_id)
    if not info:
        return None
    return {"ten_instance": ten_instance, **info}
