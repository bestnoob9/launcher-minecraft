import os
import io
import re
import json
import shutil
import hashlib
import threading
import urllib.request
import urllib.parse
import zipfile
import concurrent.futures
import config
from components import perf
from components.api_helpers import (
    MODRINTH_USER_AGENT,
    CURSEFORGE_PROXY_BASE,
    _request_json,
    lay_version_theo_hash_modrinth,
    lay_project_modrinth,
    lay_team_modrinth,
    lay_nhieu_project_modrinth,
    lay_nhieu_team_modrinth,
    lay_version_files_modrinth,
    lay_nhieu_mod_curseforge,
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
_ten_dang_cai_instance = set()
_lock_ten_dang_cai = threading.Lock()
_lock_ghi_index_modpack = threading.Lock()
def _dang_ky_dang_cai(*ten_list):
    with _lock_ten_dang_cai:
        for t in ten_list:
            if t:
                _ten_dang_cai_instance.add(t)
def _huy_dang_ky_dang_cai(*ten_list):
    with _lock_ten_dang_cai:
        for t in ten_list:
            _ten_dang_cai_instance.discard(t)
def instance_dang_duoc_cai(ten):
    with _lock_ten_dang_cai:
        return ten in _ten_dang_cai_instance
def cai_modpack_tu_file(duong_dan_zip, ten_instance, lbl_status, callback_xong=None,
                         cancel_event=None, progress_cb=None, callback_huy=None):
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    ten_instance     = ten_instance.strip()
    ten_folder       = ten_folder_an_toan(ten_instance)
    thu_muc_instance = os.path.join(thu_muc_game, "Instances", ten_folder)
    os.makedirs(thu_muc_instance, exist_ok=True)
    def _cap(text, mau="gray"):
        def _thuc_thi():
            if cancel_event and cancel_event.is_set():
                return
            try:
                lbl_status.config(text=text, fg=mau)
            except Exception:
                pass
        lbl_status.after(0, _thuc_thi)
    def _bao_tien_do(da, tong):
        if progress_cb:
            def _thuc_thi():
                if cancel_event and cancel_event.is_set():
                    return
                try:
                    progress_cb(da, tong)
                except Exception:
                    pass
            lbl_status.after(0, _thuc_thi)
    def _don_dep_va_huy():
        try:
            if os.path.exists(thu_muc_instance):
                shutil.rmtree(thu_muc_instance)
        except Exception:
            pass
        try:
            ds = config.current_config.get("danh_sach_instances", {})
            da_xoa = False
            for ten in {ten_instance, ten_folder}:
                if ten in ds:
                    del ds[ten]
                    da_xoa = True
            if da_xoa:
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
        _dang_ky_dang_cai(ten_instance, ten_folder)
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
                            loai_game = (loai_game.capitalize()
                                         if loai_game.lower() != "neoforge" else "NeoForge")
                            if loai_game == "Forge" and not version_mod.startswith(version_goc):
                                version_mod = f"{version_goc}-{version_mod}"
                        else:
                            loai_game = (loader_id.capitalize()
                                         if loader_id.lower() != "neoforge" else "NeoForge")
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
                    if cancel_event and cancel_event.is_set():
                        return
                    with lock:
                        da_tai[0] += 1
                        if thanh_cong:
                            _cap(f"Đã tải ({da_tai[0]}/{tong_mod}): {ten_mod}", "#1E88E5")
                        else:
                            loi_tai.append(ten_mod)
                        _bao_tien_do(da_tai[0], tong_mod)
                MAX_WORKERS = perf.get_perf()["tai_modrinth"]
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
                try:
                    futures = [pool.submit(_tai_mot_mod, arg) for arg in enumerate(modrinth_files)]
                    con_lai = set(futures)
                    while con_lai:
                        if cancel_event and cancel_event.is_set():
                            try:
                                pool.shutdown(wait=True, cancel_futures=True)
                            except TypeError:
                                for f in con_lai:
                                    f.cancel()
                                pool.shutdown(wait=True)
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
                    pool.shutdown(wait=True)
                _check_huy()
                if loi_tai:
                    _cap(f"Hoàn thành (lỗi {len(loi_tai)} mod): {', '.join(loi_tai[:3])}...", "orange")
                else:
                    _cap(f"Đã tải xong {tong_mod} mod!", "#2b8c54")
                cai_icon_mod_modpack_modrinth_nen(ten_instance, modrinth_files)
            if cf_mods:
                tong_cf  = len(cf_mods)
                loi_cf   = []
                da_cf    = [0]
                lock_cf  = threading.Lock()
                def _thu_muc_theo_loai(ten_file, class_id_cf):
                    if class_id_cf == 12 or "resourcepack" in ten_file.lower():
                        sub, loai_index = "resourcepacks", "resourcepacks"
                    elif class_id_cf == 6552 or "shader" in ten_file.lower():
                        sub, loai_index = "shaderpacks", "shaderpacks"
                    elif class_id_cf == 4546 or "datapack" in ten_file.lower():
                        sub, loai_index = os.path.join("saves", "datapacks"), None
                    else:
                        sub, loai_index = "mods", "mods"
                    thu_muc = os.path.join(thu_muc_instance, sub)
                    os.makedirs(thu_muc, exist_ok=True)
                    return thu_muc, loai_index
                cf_can_lap_meta = []
                def _tai_mot_mod_cf(entry):
                    if cancel_event and cancel_event.is_set():
                        return
                    project_id = entry.get("projectID")
                    file_id    = entry.get("fileID")
                    required   = entry.get("required", True)
                    if not required or not project_id or not file_id:
                        return
                    try:
                        url_info  = f"{CURSEFORGE_PROXY_BASE}/v1/mods/{project_id}/files/{file_id}"
                        file_data = _request_json(url_info)
                        file_info = file_data.get("data", {})
                        ten_file  = file_info.get("fileName", f"{file_id}.jar")
                        dl_url    = file_info.get("downloadUrl", "")
                        if cancel_event and cancel_event.is_set():
                            return
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
                        thu_muc_dich, loai_index = _thu_muc_theo_loai(ten_file, 6)
                        dest = os.path.join(thu_muc_dich, ten_file)
                        if not os.path.exists(dest):
                            _tai_file_don_gian(dl_url, dest, cancel_event)
                        if cancel_event and cancel_event.is_set():
                            return
                        if loai_index:
                            try:
                                with _lock_ghi_index_modpack:
                                    luu_muc_da_cai(
                                        ten_instance, loai_index, project_id,
                                        "curseforge", file_id,
                                        file_info.get("displayName") or file_info.get("fileName"),
                                        ten_file)
                            except Exception:
                                pass
                            with lock_cf:
                                cf_can_lap_meta.append((project_id, loai_index, ten_file))
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
                MAX_WORKERS_CF = perf.get_perf()["tai_curseforge"]
                pool_cf = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_CF)
                try:
                    futures_cf = [pool_cf.submit(_tai_mot_mod_cf, entry) for entry in cf_mods]
                    con_lai_cf = set(futures_cf)
                    while con_lai_cf:
                        if cancel_event and cancel_event.is_set():
                            try:
                                pool_cf.shutdown(wait=True, cancel_futures=True)
                            except TypeError:
                                for f in con_lai_cf:
                                    f.cancel()
                                pool_cf.shutdown(wait=True)
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
                    pool_cf.shutdown(wait=True)
                _check_huy()
                if loi_cf:
                    _cap(f"Hoàn thành CF (lỗi {len(loi_cf)} mod). Kiểm tra thủ công.", "orange")
                else:
                    _cap(f"Đã tải xong {tong_cf} mod CurseForge!", "#2b8c54")
                _lap_meta_icon_cf_nen(ten_instance, cf_can_lap_meta)
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
            _huy_dang_ky_dang_cai(ten_instance, ten_folder)
    threading.Thread(target=_chay, daemon=True).start()
_TEN_FILE_INDEX = ".mcmgr_index.json"
def _duong_dan_thu_muc_instance(ten_instance):
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    return os.path.join(thu_muc_game, "Instances", ten_folder_an_toan(ten_instance))
_cache_index_instance = {}   
def doc_index_instance(ten_instance):
    path = os.path.join(_duong_dan_thu_muc_instance(ten_instance), _TEN_FILE_INDEX)
    mac_dinh = {"modpack": None, "mods": {}, "resourcepacks": {}, "shaderpacks": {}}
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return dict(mac_dinh)
    cache = _cache_index_instance.get(ten_instance)
    if cache is not None and cache[0] == mtime:
        return cache[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in mac_dinh.items():
            data.setdefault(k, v)
    except Exception:
        data = dict(mac_dinh)
    _cache_index_instance[ten_instance] = (mtime, data)
    return data
def ghi_index_instance(ten_instance, data):
    path = os.path.join(_duong_dan_thu_muc_instance(ten_instance), _TEN_FILE_INDEX)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            mtime = os.stat(path).st_mtime
            _cache_index_instance[ten_instance] = (mtime, data)
        except OSError:
            _cache_index_instance.pop(ten_instance, None)
    except Exception:
        pass
def _thu_muc_mod_icons_instance(ten_instance):
    return os.path.join(_duong_dan_thu_muc_instance(ten_instance), ".mod_icons")
def tai_icon_offline(ten_instance, source, project_id, icon_url):
    if not icon_url or not project_id or not source:
        return
    ten_file = f"{source}_{project_id}.png"
    duong_dan = os.path.join(_thu_muc_mod_icons_instance(ten_instance), ten_file)
    if os.path.exists(duong_dan):
        return  
    threading.Thread(target=_tai_icon_offline_dong_bo,
                      args=(duong_dan, icon_url), daemon=True).start()
def _tai_icon_offline_dong_bo(duong_dan, icon_url):
    tmp = duong_dan + ".part"
    try:
        os.makedirs(os.path.dirname(duong_dan), exist_ok=True)
        req = urllib.request.Request(
            icon_url, headers={"User-Agent": MODRINTH_USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        with open(tmp, "wb") as f:
            f.write(raw)
        if os.path.exists(duong_dan):
            os.remove(duong_dan)
        os.rename(tmp, duong_dan)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
def chon_url_anh_modpack(source, project_obj):
    if not isinstance(project_obj, dict):
        return None
    if source == "modrinth":
        icon_url = project_obj.get("icon_url")
        if icon_url:
            return icon_url
        gallery = project_obj.get("gallery") or []
        muc_hop_le = []
        for g in gallery:
            if isinstance(g, dict) and g.get("url"):
                muc_hop_le.append(g)
            elif isinstance(g, str) and g:
                muc_hop_le.append({"url": g})
        if muc_hop_le:
            for g in muc_hop_le:
                if g.get("featured") is True:
                    return g["url"]
            muc_hop_le.sort(key=lambda g: g.get("ordering", 0) or 0)
            return muc_hop_le[0]["url"]
        return None
    if source == "curseforge":
        logo = project_obj.get("logo") or {}
        if isinstance(logo, dict):
            url = logo.get("thumbnailUrl") or logo.get("url")
            if url:
                return url
        screenshots = project_obj.get("screenshots") or []
        if screenshots and isinstance(screenshots[0], dict):
            url = screenshots[0].get("thumbnailUrl") or screenshots[0].get("url")
            if url:
                return url
        return None
    return None
def _luu_anh_bia_modpack_tu_url(ten_instance, url_anh):
    from components.instance_common import (
        luu_anh_bia, tim_anh_bia, anh_bia_hien_tai_la_gallery)
    if not url_anh or not ten_instance:
        return
    if tim_anh_bia(ten_instance) and not anh_bia_hien_tai_la_gallery(ten_instance):
        return
    thu_muc_game = config.current_config.get("thu_muc_game", "")
    thu_muc_tmp  = os.path.join(thu_muc_game, "_modpack_cover_tmp")
    tmp = None
    try:
        os.makedirs(thu_muc_tmp, exist_ok=True)
        tmp = os.path.join(
            thu_muc_tmp, f"_cover_{ten_folder_an_toan(ten_instance)}.png")
        req = urllib.request.Request(
            url_anh, headers={"User-Agent": MODRINTH_USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        with open(tmp, "wb") as f:
            f.write(raw)
        luu_anh_bia(ten_instance, tmp)
    except Exception:
        pass
    finally:
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
def tai_anh_bia_modpack_nen(ten_instance, url_anh):
    if not url_anh or not ten_instance:
        return
    threading.Thread(target=_luu_anh_bia_modpack_tu_url,
                      args=(ten_instance, url_anh), daemon=True).start()
def cai_anh_bia_modpack_modrinth_nen(ten_instance, project_id, item_hien_tai=None):
    if not project_id or not ten_instance:
        return
    def _worker():
        obj = item_hien_tai if isinstance(item_hien_tai, dict) else {}
        url_anh = chon_url_anh_modpack("modrinth", obj)
        if not url_anh:
            try:
                from components.api_helpers import lay_project_modrinth
                obj = lay_project_modrinth(project_id)
                url_anh = chon_url_anh_modpack("modrinth", obj)
            except Exception:
                url_anh = None
        _luu_anh_bia_modpack_tu_url(ten_instance, url_anh)
    threading.Thread(target=_worker, daemon=True).start()
_RE_MODRINTH_CDN_PID = re.compile(r"cdn\.modrinth\.com/data/([A-Za-z0-9]+)/")
_LO_MODRINTH_PROJECTS = 25
_SONG_SONG_TAI_ICON_MODPACK = 3
def cai_icon_mod_modpack_modrinth_nen(ten_instance, modrinth_files):
    if not modrinth_files or not ten_instance:
        return
    def _worker():
        from components.instance_common import duong_dan_icon_da_tai
        perf_now = perf.get_perf()
        ung_vien = []  
        for mf in modrinth_files:
            rel_path = mf.get("path", "")
            urls = mf.get("downloads", []) or []
            if not rel_path or not urls:
                continue
            m = None
            for u in urls:
                m = _RE_MODRINTH_CDN_PID.search(u)
                if m:
                    break
            if not m:
                continue
            rel_norm = rel_path.replace("\\", "/").lstrip("/")
            if rel_norm.startswith("resourcepacks/"):
                loai_mf = "resourcepacks"
            elif rel_norm.startswith("shaderpacks/"):
                loai_mf = "shaderpacks"
            else:
                loai_mf = "mods"
            ung_vien.append((m.group(1), os.path.basename(rel_path), loai_mf))
        if not ung_vien:
            return
        try:
            with _lock_ghi_index_modpack:
                for pid, filename, loai_mf in ung_vien:
                    luu_muc_da_cai(ten_instance, loai_mf, pid, "modrinth",
                                   None, None, filename)
        except Exception:
            pass
        if not perf_now.get("icon_luc_cai", True):
            return
        can_lay, da_thay = [], set()
        for pid, _fn, _loai_mf in ung_vien:
            if pid in da_thay:
                continue
            da_thay.add(pid)
            if not duong_dan_icon_da_tai(ten_instance, "modrinth", pid):
                can_lay.append(pid)
        if not can_lay:
            return
        from components.api_helpers import lay_nhieu_project_modrinth
        icon_url_theo_pid = {}
        for i in range(0, len(can_lay), _LO_MODRINTH_PROJECTS):
            lo = can_lay[i:i + _LO_MODRINTH_PROJECTS]
            try:
                for proj in lay_nhieu_project_modrinth(lo):
                    pid = proj.get("id") or proj.get("slug")
                    icon_url = proj.get("icon_url")
                    if pid and icon_url:
                        icon_url_theo_pid[pid] = icon_url
            except Exception:
                continue  
        if not icon_url_theo_pid:
            return
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=perf_now.get("tai_icon", _SONG_SONG_TAI_ICON_MODPACK))
        try:
            for pid, icon_url in icon_url_theo_pid.items():
                if perf.dang_choi():
                    break
                duong_dan = os.path.join(
                    _thu_muc_mod_icons_instance(ten_instance), f"modrinth_{pid}.png")
                if os.path.exists(duong_dan):
                    continue
                pool.submit(_tai_icon_offline_dong_bo, duong_dan, icon_url)
        finally:
            pool.shutdown(wait=True)
    threading.Thread(target=_worker, daemon=True).start()
def _lap_meta_icon_cf_nen(ten_instance, muc_can_lap_meta):
    if not muc_can_lap_meta or not ten_instance:
        return
    def _worker():
        perf_now = perf.get_perf()
        ids = list(dict.fromkeys(pid for pid, _loai, _fn in muc_can_lap_meta))
        theo_id = {}
        for i in range(0, len(ids), 50):
            if perf.dang_choi():
                return
            lo = ids[i:i + 50]
            try:
                for m in lay_nhieu_mod_curseforge(lo):
                    mid = m.get("id")
                    if mid is not None:
                        theo_id[mid] = m
            except Exception:
                continue
        if not theo_id:
            return
        can_icon = []  
        for pid, loai_index, ten_file in muc_can_lap_meta:
            m = theo_id.get(pid)
            if not m:
                continue
            authors_cf = m.get("authors") or []
            ten_tac_gia = ", ".join(
                a.get("name", "") for a in authors_cf
                if isinstance(a, dict) and a.get("name")) or None
            try:
                upsert_meta_nhan_dien(
                    ten_instance, loai_index, pid, "curseforge", None, None,
                    ten_file, title=m.get("name"), author=ten_tac_gia)
            except Exception:
                pass
            logo = m.get("logo") or {}
            icon_url = logo.get("thumbnailUrl") or logo.get("url")
            if icon_url:
                can_icon.append((pid, icon_url))
        if not can_icon:
            return
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=perf_now.get("tai_icon", 3))
        try:
            for pid, icon_url in can_icon:
                if perf.dang_choi():
                    break
                duong_dan = os.path.join(
                    _thu_muc_mod_icons_instance(ten_instance), f"curseforge_{pid}.png")
                if os.path.exists(duong_dan):
                    continue
                pool.submit(_tai_icon_offline_dong_bo, duong_dan, icon_url)
        finally:
            pool.shutdown(wait=True)
    threading.Thread(target=_worker, daemon=True).start()
def _sha1_file(duong_dan):
    try:
        h = hashlib.sha1()
        with open(duong_dan, "rb") as f:
            for khoi in iter(lambda: f.read(65536), b""):
                h.update(khoi)
        return h.hexdigest()
    except Exception:
        return None
def nhan_dien_mod_qua_hash_modrinth(duong_dan_jar):
    try:
        sha1 = _sha1_file(duong_dan_jar)
        if not sha1:
            return None
        ver = lay_version_theo_hash_modrinth(sha1, "sha1")
        if not ver or not ver.get("project_id"):
            return None
        proj = lay_project_modrinth(ver["project_id"]) or {}
        title = proj.get("title") or None
        icon_url = proj.get("icon_url")
        author = None
        thanh_vien = lay_team_modrinth(proj.get("team"))
        if thanh_vien:
            chu = next((m for m in thanh_vien
                        if (m.get("role") or "").lower() == "owner"), thanh_vien[0])
            author = (chu.get("user") or {}).get("username") or None
        version_number = ver.get("version_number") or None
        if not (title or author or version_number):
            return None
        return {
            "project_id": ver["project_id"], "source": "modrinth",
            "version_id": ver.get("id"), "version_number": version_number,
            "title": title, "author": author, "icon_url": icon_url,
        }
    except Exception:
        return None
_cache_sha1_version = {}      
_cache_project_modrinth = {}  
_cache_team_modrinth = {}     
def _sha1_va_version_hang_loat(items_can_hash):
    if not items_can_hash:
        return []
    perf_now = perf.get_perf()
    if perf.ram_avail_gb_hien_tai() < 1.5 or perf.dang_choi():
        return [(it, None) for it in items_can_hash]
    so_luong_hash = perf_now.get("hash", 2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=so_luong_hash) as ex:
        sha1_list = list(ex.map(lambda it: _sha1_file(it["path"]), items_can_hash))
    can_goi = list(dict.fromkeys(
        sha1 for sha1 in sha1_list if sha1 and sha1 not in _cache_sha1_version))
    for i in range(0, len(can_goi), 50):
        lo = can_goi[i:i + 50]
        ket_qua_lo = lay_version_files_modrinth(lo)
        for sha1 in lo:
            _cache_sha1_version[sha1] = ket_qua_lo.get(sha1)
    return [(it, (_cache_sha1_version.get(sha1) if sha1 else None))
            for it, sha1 in zip(items_can_hash, sha1_list)]
def _lay_nhieu_project_cached(project_ids):
    ids = list(dict.fromkeys(str(pid) for pid in (project_ids or []) if pid))
    ket_qua = {pid: _cache_project_modrinth[pid] for pid in ids if pid in _cache_project_modrinth}
    can_lay = [pid for pid in ids if pid not in _cache_project_modrinth]
    for i in range(0, len(can_lay), 25):
        lo = can_lay[i:i + 25]
        try:
            projs = lay_nhieu_project_modrinth(lo)
        except Exception:
            projs = []
        theo_id = {}
        for p in (projs or []):
            pid = str(p.get("id") or p.get("slug") or "")
            if pid:
                theo_id[pid] = p
        for pid in lo:
            proj = theo_id.get(pid)
            _cache_project_modrinth[pid] = proj
            ket_qua[pid] = proj
    return ket_qua
def _lay_nhieu_team_cached(team_ids):
    ids = list(dict.fromkeys(str(t) for t in (team_ids or []) if t))
    ket_qua = {tid: _cache_team_modrinth[tid] for tid in ids if tid in _cache_team_modrinth}
    can_lay = [tid for tid in ids if tid not in _cache_team_modrinth]
    for i in range(0, len(can_lay), 25):
        lo = can_lay[i:i + 25]
        theo_id = lay_nhieu_team_modrinth(lo)
        for tid in lo:
            thanh_vien = theo_id.get(tid) or []
            _cache_team_modrinth[tid] = thanh_vien
            ket_qua[tid] = thanh_vien
    return ket_qua
def _author_tu_project(proj, teams_theo_id):
    if not proj:
        return None
    team_id = proj.get("team")
    thanh_vien = teams_theo_id.get(str(team_id)) if team_id else None
    if not thanh_vien:
        return None
    chu = next((m for m in thanh_vien
                if (m.get("role") or "").lower() == "owner"), thanh_vien[0])
    return (chu.get("user") or {}).get("username") or None
def lap_day_meta_hang_loat_mods(items_nhom1, items_nhom2, con_hieu_luc):
    if not con_hieu_luc() or (not items_nhom1 and not items_nhom2):
        return []
    item_version_nhom2 = _sha1_va_version_hang_loat(items_nhom2) if items_nhom2 else []
    if not con_hieu_luc():
        return []
    can_project_ids = set(str(it["project_id"]) for it in items_nhom1)
    for it, ver in item_version_nhom2:
        if ver and ver.get("project_id"):
            can_project_ids.add(str(ver["project_id"]))
    if not can_project_ids:
        return []
    projects = _lay_nhieu_project_cached(can_project_ids)
    if not con_hieu_luc():
        return []
    team_ids = set(str(p["team"]) for p in projects.values() if p and p.get("team"))
    teams = _lay_nhieu_team_cached(team_ids) if team_ids else {}
    if not con_hieu_luc():
        return []
    ket_qua = []
    for it in items_nhom1:
        proj = projects.get(str(it["project_id"]))
        if not proj:
            continue
        ket_qua.append({
            "item": it, "title": proj.get("title") or None,
            "author": _author_tu_project(proj, teams),
            "version_number": None, "version_id": None,
            "icon_url": proj.get("icon_url"),
        })
    for it, ver in item_version_nhom2:
        if not ver or not ver.get("project_id"):
            continue
        pid = str(ver["project_id"])
        proj = projects.get(pid)
        ket_qua.append({
            "item": it, "title": (proj.get("title") if proj else None),
            "author": _author_tu_project(proj, teams) if proj else None,
            "version_number": ver.get("version_number") or None,
            "version_id": ver.get("id"),
            "icon_url": (proj.get("icon_url") if proj else None),
            "project_id": pid, "source": "modrinth",
        })
    return ket_qua
def lay_muc_da_cai(ten_instance, loai, project_id):
    if not project_id:
        return None
    idx = doc_index_instance(ten_instance)
    return idx.get(loai, {}).get(str(project_id))
def luu_muc_da_cai(ten_instance, loai, project_id, source, version_id,
                    version_number, filename, ngay=None,
                    title=None, author=None, icon_url=None):
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
        "title": title if title is not None else (cu.get("title") if cu else None),
        "author": author if author is not None else (cu.get("author") if cu else None),
        "icon_url": icon_url if icon_url is not None else (cu.get("icon_url") if cu else None),
    }
    ghi_index_instance(ten_instance, idx)
    icon_url_hien = icon_url if icon_url is not None else (cu.get("icon_url") if cu else None)
    tai_icon_offline(ten_instance, source, project_id, icon_url_hien)
def upsert_meta_nhan_dien(ten_instance, loai, project_id, source, version_id,
                           version_number, filename, title=None, author=None,
                           icon_url=None):
    if not project_id:
        return
    idx = doc_index_instance(ten_instance)
    nhom = idx.setdefault(loai, {})
    cu = nhom.get(str(project_id))
    nhom[str(project_id)] = {
        "source": source, "version_id": version_id,
        "version_number": version_number if version_number is not None else (cu.get("version_number") if cu else None),
        "filename": filename,
        "ngay": (cu.get("ngay") if cu else None),
        "title": title if title is not None else (cu.get("title") if cu else None),
        "author": author if author is not None else (cu.get("author") if cu else None),
        "icon_url": icon_url if icon_url is not None else (cu.get("icon_url") if cu else None),
    }
    ghi_index_instance(ten_instance, idx)
    icon_url_hien = icon_url if icon_url is not None else (cu.get("icon_url") if cu else None)
    tai_icon_offline(ten_instance, source, project_id, icon_url_hien)
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
_cache_quet_thu_muc = {}   
def _chuan_hoa_ten(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s
def _quet_thu_muc_map(ten_instance, loai):
    if not ten_instance or loai not in ("mods", "resourcepacks", "shaderpacks"):
        return {}
    duong_dan = os.path.join(_duong_dan_thu_muc_instance(ten_instance), loai)
    try:
        mtime = os.stat(duong_dan).st_mtime
    except OSError:
        return {}
    khoa = (ten_instance, loai)
    cache = _cache_quet_thu_muc.get(khoa)
    if cache is not None and cache[0] == mtime:
        return cache[1]
    ket_qua = {}
    try:
        for f in os.listdir(duong_dan):
            if os.path.isfile(os.path.join(duong_dan, f)):
                ket_qua[_chuan_hoa_ten(os.path.splitext(f)[0])] = f
    except OSError:
        ket_qua = {}
    _cache_quet_thu_muc[khoa] = (mtime, ket_qua)
    return ket_qua
def quet_ten_file_da_cai(ten_instance, loai):
    return frozenset(_quet_thu_muc_map(ten_instance, loai).keys())
def kiem_tra_ten_da_cai(ten_instance, loai, ten_hien_thi):
    ten_chuan = _chuan_hoa_ten(ten_hien_thi)
    if not ten_chuan:
        return False
    for f in quet_ten_file_da_cai(ten_instance, loai):
        if not f:
            continue
        if ten_chuan in f or f in ten_chuan:
            return True
    return False
def tim_ten_file_da_cai(ten_instance, loai, ten_hien_thi):
    ten_chuan = _chuan_hoa_ten(ten_hien_thi)
    if not ten_chuan:
        return None
    for chuan, goc in _quet_thu_muc_map(ten_instance, loai).items():
        if not chuan:
            continue
        if ten_chuan in chuan or chuan in ten_chuan:
            return goc
    return None
def xoa_file_theo_ten(ten_instance, loai, filename):
    if not (ten_instance and loai and filename):
        return
    try:
        path = os.path.join(_duong_dan_thu_muc_instance(ten_instance), loai, filename)
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass