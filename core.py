import os
import json
import urllib.request
import minecraft_launcher_lib
import subprocess
import re
import sys

# =====================================================================
# AN TOAN BO CUA SO CMD DEN CHO MOI TIEN TRINH CON TREN WINDOWS
# (vd: java -jar installer khi minecraft_launcher_lib cai Fabric/Forge/
#  Quilt/NeoForge ben trong). Patch nay ghi de subprocess.Popen.__init__
# nen ap dung cho CA cac lenh subprocess goi tu ben trong cac thu vien
# khac (minecraft_launcher_lib), khong chi lenh ta tu goi.
# =====================================================================
if sys.platform == "win32":
    _popen_init_goc = subprocess.Popen.__init__

    def _popen_init_an_cmd(self, *args, **kwargs):
        if kwargs.get("startupinfo") is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = si
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        _popen_init_goc(self, *args, **kwargs)

    subprocess.Popen.__init__ = _popen_init_an_cmd

# =====================================================================
# ĐĂNG NHẬP MICROSOFT (PREMIUM)
# =====================================================================

# Azure App client ID dùng để login Microsoft OAuth
# Đây là Client ID mặc định của minecraft-launcher-lib (dùng được cho mục đích cá nhân)
_MS_CLIENT_ID = "00000000402b5328"
_MS_REDIRECT_URL = "https://login.live.com/oauth20_desktop.srf"

def bat_dau_dang_nhap_microsoft():
    """
    Trả về (login_url, state, code_verifier) để mở trình duyệt.
    Gọi hàm này để lấy URL, sau đó mở trình duyệt cho người dùng đăng nhập.
    """
    login_url, state, code_verifier = minecraft_launcher_lib.microsoft_account.get_secure_login_data(
        _MS_CLIENT_ID, _MS_REDIRECT_URL
    )
    return login_url, state, code_verifier

def hoan_tat_dang_nhap_microsoft(code_url, state, code_verifier):
    """
    Nhận URL callback sau khi người dùng đăng nhập.
    Trả về dict login_data với các key: name, id, access_token, refresh_token
    hoặc raise Exception nếu thất bại.
    """
    try:
        auth_code = minecraft_launcher_lib.microsoft_account.parse_auth_code_url(code_url, state)
    except AssertionError:
        raise Exception("Xác thực thất bại: State không khớp. Hãy thử lại.")
    except KeyError:
        raise Exception("URL không hợp lệ. Hãy copy đúng URL từ trình duyệt.")

    login_data = minecraft_launcher_lib.microsoft_account.complete_login(
        _MS_CLIENT_ID, None, _MS_REDIRECT_URL, auth_code, code_verifier
    )
    return {
        "name": login_data["name"],
        "uuid": login_data["id"],
        "access_token": login_data["access_token"],
        "refresh_token": login_data.get("refresh_token", ""),
        "loai": "premium"
    }

def lam_moi_token_microsoft(refresh_token):
    """
    Làm mới access token bằng refresh token.
    Trả về login_data mới hoặc None nếu thất bại.
    """
    try:
        login_data = minecraft_launcher_lib.microsoft_account.complete_refresh(
            _MS_CLIENT_ID, None, _MS_REDIRECT_URL, refresh_token
        )
        return {
            "name": login_data["name"],
            "uuid": login_data["id"],
            "access_token": login_data["access_token"],
            "refresh_token": login_data.get("refresh_token", refresh_token),
            "loai": "premium"
        }
    except Exception as e:
        print(f"Lỗi làm mới token: {e}")
        return None

def lay_danh_sach_phien_ban_chinh():
    try:
        all_versions = minecraft_launcher_lib.utils.get_version_list()
        return [v["id"] for v in all_versions if v["type"] == "release"]
    except:
        return ["1.21.1", "1.20.1", "1.16.5"]

def tai_danh_sach_mod(loai_game, version_goc):
    try:
        if loai_game == "Fabric":
            url = "https://meta.fabricmc.net/v2/versions/loader"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return [item["version"] for item in data]

        elif loai_game == "Quilt":
            url = "https://meta.quiltmc.org/v3/versions/loader"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return [item["version"] for item in data]

        elif loai_game == "NeoForge":
            url = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                tat_ca_versions = data.get("versions", [])

                parts = version_goc.split('.')
                sub_ver = parts[1] if len(parts) > 1 else ""
                ds_loader = [v for v in tat_ca_versions if v.startswith(f"{sub_ver}.")]
                def safe_sort_key(s):
                    try:
                        return list(map(int, s.split('.')))
                    except:
                        return [0]

                ds_loader.sort(key=safe_sort_key, reverse=True)

                if ds_loader:
                    return ds_loader
                ds_loader = list(tat_ca_versions)
                ds_loader.sort(key=safe_sort_key, reverse=True)
                return ds_loader[:20]

        elif loai_game == "Forge":
            forge_list = minecraft_launcher_lib.forge.list_forge_versions()
            return [f for f in forge_list if _khop_chinh_xac_version(str(version_goc), str(f))][::-1]

    except Exception as e:
        print(f"Lỗi tải API Mod cho {loai_game}: {e}")

    if loai_game == "NeoForge":
        parts = version_goc.split('.')
        sub_ver = parts[1] if len(parts) > 1 else "21"
        return [f"{sub_ver}.1.70", f"{sub_ver}.1.0"]

    return []

def cap_nhat_va_quet_instances(thu_muc_game):
    thu_muc_instances_goc = os.path.join(thu_muc_game, "Instances")
    if not os.path.exists(thu_muc_instances_goc):
        os.makedirs(thu_muc_instances_goc, exist_ok=True)
        return []

    ds_instance_thuc_te = []

    for ten_folder in os.listdir(thu_muc_instances_goc):
        duong_dan_folder = os.path.join(thu_muc_instances_goc, ten_folder)

        if os.path.isdir(duong_dan_folder):
            file_info = os.path.join(duong_dan_folder, "instance_info.json")

            if not os.path.exists(file_info):
                data_tu_sinh = {
                    "loai_game": "Vanilla",
                    "version_goc": "1.21.1",
                    "version_mod": ""
                }

                ten_folder_lower = ten_folder.lower()
                if "fabric" in ten_folder_lower:
                    data_tu_sinh["loai_game"] = "Fabric"
                elif "neoforge" in ten_folder_lower:
                    data_tu_sinh["loai_game"] = "NeoForge"
                elif "forge" in ten_folder_lower:
                    data_tu_sinh["loai_game"] = "Forge"
                elif "quilt" in ten_folder_lower:
                    data_tu_sinh["loai_game"] = "Quilt"

                for x in ["1.21.1", "1.20.1", "1.16.5", "1.12.2"]:
                    if x in ten_folder:
                        data_tu_sinh["version_goc"] = x
                        break

                try:
                    with open(file_info, "w", encoding="utf-8") as f:
                        json.dump(data_tu_sinh, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    print(f"Lỗi tạo file info tự động cho {ten_folder}: {e}")
                    continue

            ten_hien_thi = ten_folder.replace("_", " ")
            ds_instance_thuc_te.append(ten_hien_thi)

    return ds_instance_thuc_te

# =====================================================================
# BỘ KHỞI TẠO JVM ARGUMENTS TỐI ƯU HÓA
# =====================================================================
def get_all_jvm_presets():
    return {
        "aikar_optimized": [
            "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8m",
            "-XX:G1ReservePercent=20", "-XX:InitiatingHeapOccupancyPercent=15",
            "-XX:G1MixedGCLiveThresholdPercent=90", "-XX:G1RSetUpdatingPauseTimePercent=5",
            "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem", "-XX:MaxTenuringThreshold=1"
        ],
        "low_end": [
            "-XX:+UseG1GC", "-XX:+OptimizeStringConcat", "-XX:+UseStringDeduplication",
            "-XX:+UseCondCardMark", "-XX:MaxGCPauseMillis=100"
        ],
        "chunk_loading_heavy": [
            "-XX:+UseG1GC",
            "-XX:+AlwaysPreTouch",
            "-XX:+UseNUMA",
            "-XX:MaxGCPauseMillis=50"
        ],
        "heavy_modded": [
            "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=40", "-XX:G1MaxNewSizePercent=50", "-XX:G1HeapRegionSize=16m",
            "-XX:G1ReservePercent=15", "-XX:InitiatingHeapOccupancyPercent=20"
        ],
        "shenandoah_ultra": [
            "-XX:+UnlockExperimentalVMOptions", "-XX:+UseShenandoahGC",
            "-XX:ShenandoahGCHeuristics=adaptive", "-XX:+AlwaysPreTouch", "-XX:+UseNUMA"
        ]
    }

def build_jvm_arguments(current_config, ram_min, ram_max, la_tai_khoan_premium=False):
    final_args = []
    final_args.append(f"-Xms{ram_min}")
    final_args.append(f"-Xmx{ram_max}")
    # Chỉ bypass auth khi dùng tài khoản offline (cracked)
    # Tài khoản premium dùng token thật, KHÔNG cần bypass
    if not la_tai_khoan_premium:
        final_args.append("-Dminecraft.api.auth.enabled=false")
        final_args.append("-Dminecraft.api.auth.host=https://nope.invalid")
        final_args.append("-Dminecraft.api.account.host=https://nope.invalid")
        final_args.append("-Dminecraft.api.session.host=https://nope.invalid")
        final_args.append("-Dminecraft.api.services.host=https://nope.invalid")

    mode = current_config.get("jvm_mode", "default")
    if mode == "preset":
        preset_name = current_config.get("preset_jvm_args", "aikar_optimized")
        presets = get_all_jvm_presets()
        final_args.extend(presets.get(preset_name, presets["aikar_optimized"]))
    elif mode == "custom":
        custom_str = current_config.get("custom_jvm_args", "")
        parsed_custom = [arg for arg in custom_str.split(" ") if arg.strip()]
        final_args.extend(parsed_custom)

    return final_args

# =====================================================================
# CÀI ĐẶT VÀ TIẾN TRÌNH GAME
# =====================================================================

def _da_cai_minecraft_co_ban(thu_muc_game, version_id):
    """
    Kiem tra nhanh xem version Minecraft goc (vanilla) da co day du
    file .json + .jar trong thu muc versions/ chua.
    Neu da co -> bo qua goi install_minecraft_version (do nhanh) de
    khong phai quet/kiem tra lai toan bo assets/libraries moi lan vao game.
    """
    vdir = os.path.join(thu_muc_game, "versions", version_id)
    return (
        os.path.exists(os.path.join(vdir, f"{version_id}.json"))
        and os.path.exists(os.path.join(vdir, f"{version_id}.jar"))
    )


def _tim_phien_ban_loader_da_cai(thu_muc_versions, tu_khoa, dieu_kien_phu=None):
    """
    Quet thu_muc_versions, tim folder co ten chua `tu_khoa` (vd 'fabric',
    'quilt', 'forge', 'neoforge') va da co file .json (nghia la profile
    da duoc cai dat hoan tat truoc do).
    dieu_kien_phu(folder) -> bool: dieu kien loc them (vd khop version goc / loader).
    Tra ve ten folder neu tim thay, None neu chua cai.
    """
    if not os.path.exists(thu_muc_versions):
        return None
    for folder in os.listdir(thu_muc_versions):
        if tu_khoa not in folder.lower():
            continue
        ver_json = os.path.join(thu_muc_versions, folder, f"{folder}.json")
        if not os.path.exists(ver_json):
            continue
        if dieu_kien_phu and not dieu_kien_phu(folder):
            continue
        return folder
    return None


def _khop_chinh_xac_version(ver, text):
    """
    Kiem tra 'ver' co xuat hien trong 'text' nhu mot token phien ban day du,
    KHONG bi nham voi mot phien ban dai hon chua no.
    Vd: _khop_chinh_xac_version("1.21.1", "1.21.1-forge-52.0.11") -> True
        _khop_chinh_xac_version("1.21.1", "1.21.11-forge-52.0.11") -> False
    Cach lam: tim moi vi tri xuat hien cua 'ver' trong 'text', chap nhan
    chi khi ky tu ngay truoc/sau (neu co) khong phai la chu so (tuc 'ver'
    khong bi noi dai them boi cac chu so khac).
    """
    if not ver:
        return False
    for m in re.finditer(re.escape(ver), text):
        start, end = m.start(), m.end()
        truoc_ok = start == 0 or not text[start - 1].isdigit()
        sau_ok   = end == len(text) or not text[end].isdigit()
        if truoc_ok and sau_ok:
            return True
    return False


def cai_dat_va_lay_lenh_chay(loai_game, version_goc, version_mod_da_chon, thu_muc_game, ten_instance, options, callback_progress=None, should_cancel=None):
    thu_muc_instance_rieng = os.path.join(thu_muc_game, "Instances", ten_instance)
    os.makedirs(thu_muc_instance_rieng, exist_ok=True)
    options["gameDirectory"] = thu_muc_instance_rieng

    # --- Tao CallbackDict de cap nhat tien do ---
    _max = [100]  # dung list de co the thay doi ben trong lambda

    def _set_max(val):
        if val and val > 0:
            _max[0] = val

    def _set_progress(val):
        if should_cancel and should_cancel():
            raise InterruptedError("Nguoi dung huy tai xuong")
        if callback_progress and _max[0] > 0:
            phan_tram = min(99.0, val / _max[0] * 100)
            callback_progress(phan_tram, "")

    def _set_status(msg):
        if callback_progress:
            # Giu nguyen phan tram hien tai, chi cap nhat mo ta
            callback_progress(None, str(msg))

    _callbacks = {
        "setStatus":   _set_status,
        "setProgress": _set_progress,
        "setMax":      _set_max,
    }

    if _da_cai_minecraft_co_ban(thu_muc_game, version_goc):
        _set_status(f"Da co Minecraft {version_goc}, bo qua kiem tra lai...")
    else:
        minecraft_launcher_lib.install.install_minecraft_version(version_goc, thu_muc_game, _callbacks)
    id_phien_ban_chay = version_goc
    thu_muc_versions = os.path.join(thu_muc_game, "versions")

    if loai_game == "Fabric" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        da_cai = _tim_phien_ban_loader_da_cai(
            thu_muc_versions, "fabric",
            lambda f: _khop_chinh_xac_version(version_goc, f) and _khop_chinh_xac_version(version_mod_da_chon, f)
        )
        if da_cai:
            id_phien_ban_chay = da_cai
            _set_status(f"Da cai Fabric {version_mod_da_chon}, bo qua cai dat lai...")
        else:
            minecraft_launcher_lib.fabric.install_fabric(version_goc, thu_muc_game, loader_version=version_mod_da_chon, callback=_callbacks)
            if os.path.exists(thu_muc_versions):
                # Uu tien khop chinh xac ca version_goc lan version_mod (tranh lay sai loader version)
                best = None
                for folder in os.listdir(thu_muc_versions):
                    if "fabric" in folder.lower() and _khop_chinh_xac_version(version_goc, folder):
                        if _khop_chinh_xac_version(version_mod_da_chon, folder):
                            id_phien_ban_chay = folder
                            best = folder
                            break
                        elif best is None:
                            best = folder
                if id_phien_ban_chay == version_goc and best:
                    id_phien_ban_chay = best

    elif loai_game == "Quilt" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        da_cai = _tim_phien_ban_loader_da_cai(
            thu_muc_versions, "quilt",
            lambda f: _khop_chinh_xac_version(version_goc, f) and _khop_chinh_xac_version(version_mod_da_chon, f)
        )
        if da_cai:
            id_phien_ban_chay = da_cai
            _set_status(f"Da cai Quilt {version_mod_da_chon}, bo qua cai dat lai...")
        else:
            minecraft_launcher_lib.quilt.install_quilt(version_goc, thu_muc_game, loader_version=version_mod_da_chon, callback=_callbacks)
            if os.path.exists(thu_muc_versions):
                best = None
                for folder in os.listdir(thu_muc_versions):
                    if "quilt" in folder.lower() and _khop_chinh_xac_version(version_goc, folder):
                        if _khop_chinh_xac_version(version_mod_da_chon, folder):
                            id_phien_ban_chay = folder
                            best = folder
                            break
                        elif best is None:
                            best = folder
                if id_phien_ban_chay == version_goc and best:
                    id_phien_ban_chay = best

    elif loai_game == "NeoForge" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        da_cai = _tim_phien_ban_loader_da_cai(
            thu_muc_versions, "neoforge",
            lambda f: _khop_chinh_xac_version(version_mod_da_chon, f)
        )
        if da_cai:
            id_phien_ban_chay = da_cai
            _set_status(f"Da cai NeoForge {version_mod_da_chon}, bo qua cai dat lai...")
        else:
            # Tu ban 8.0, minecraft-launcher-lib BO HAN module "neoforge" rieng,
            # chuyen het sang module "mod_loader" thong nhat cho ca
            # Forge/NeoForge/Fabric/Quilt. Uu tien dung API moi nay; neu thu
            # vien dang dung la ban cu hon 8.0 (chua co mod_loader), fallback
            # ve module "neoforge" cu (neu co) de van tuong thich nguoc.
            if hasattr(minecraft_launcher_lib, "mod_loader"):
                try:
                    loader = minecraft_launcher_lib.mod_loader.get_mod_loader("neoforge")
                    id_phien_ban_chay = loader.install(
                        version_goc, thu_muc_game,
                        loader_version=version_mod_da_chon, callback=_callbacks)
                except Exception as e:
                    raise Exception(f"Cai NeoForge {version_mod_da_chon} thất bại: {e}")
            elif hasattr(minecraft_launcher_lib, "neoforge"):
                try:
                    minecraft_launcher_lib.neoforge.install_neoforge_version(
                        version_mod_da_chon, thu_muc_game, callback=_callbacks)
                except AttributeError:
                    raise Exception("NeoForge chưa được hỗ trợ. Hãy chạy: pip install --upgrade minecraft-launcher-lib")
                if os.path.exists(thu_muc_versions):
                    for folder in os.listdir(thu_muc_versions):
                        if "neoforge" in folder.lower() and _khop_chinh_xac_version(version_mod_da_chon, folder):
                            id_phien_ban_chay = folder
                            break
            else:
                raise Exception("NeoForge chưa được hỗ trợ. Hãy chạy: pip install --upgrade minecraft-launcher-lib")

    elif loai_game == "Forge" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        da_cai = _tim_phien_ban_loader_da_cai(
            thu_muc_versions, "forge",
            lambda f: _khop_chinh_xac_version(version_goc, f)
        )
        if da_cai:
            id_phien_ban_chay = da_cai
            _set_status(f"Da cai Forge cho {version_goc}, bo qua cai dat lai...")
        else:
            minecraft_launcher_lib.forge.install_forge_version(version_mod_da_chon, thu_muc_game, callback=_callbacks)
            if os.path.exists(thu_muc_versions):
                for folder in os.listdir(thu_muc_versions):
                    if "forge" in folder.lower() and _khop_chinh_xac_version(version_goc, folder):
                        id_phien_ban_chay = folder
                        break

    file_info = os.path.join(thu_muc_instance_rieng, "instance_info.json")
    if not os.path.exists(file_info):
        data_ghi = {"loai_game": loai_game, "version_goc": version_goc, "version_mod": version_mod_da_chon}
        with open(file_info, "w", encoding="utf-8") as f:
            json.dump(data_ghi, f, indent=4, ensure_ascii=False)

    return minecraft_launcher_lib.command.get_minecraft_command(id_phien_ban_chay, thu_muc_game, options)


def chay_game_minecraft(tai_khoan, ten_instance, thu_muc_game, lbl_status, callback_progress=None, should_cancel=None):
    import config

    if not ten_instance:
        lbl_status.after(0, lambda: lbl_status.config(text="Lỗi: Vui lòng chọn hoặc tạo 1 Instance!", fg="red"))
        return

    ten_folder_instance = ten_instance.replace(" ", "_")
    thu_muc_instance_rieng = os.path.join(thu_muc_game, "Instances", ten_folder_instance)
    
    # Tự tạo thư mục nếu chưa có
    os.makedirs(thu_muc_instance_rieng, exist_ok=True)

    file_thong_tin = os.path.join(thu_muc_instance_rieng, "instance_info.json")

    # Nếu chưa có file json thì tự tạo từ config thay vì báo lỗi
    if not os.path.exists(file_thong_tin):
        ds_instances = config.current_config.get("danh_sach_instances", {})
        # Thử tìm theo tên gốc hoặc tên có dấu gạch dưới
        data_instance = ds_instances.get(ten_instance) or ds_instances.get(ten_folder_instance)

        if not data_instance:
            data_instance = {"loai_game": "Vanilla", "version_goc": "1.21.1", "version_mod": "Vanilla"}

        try:
            with open(file_thong_tin, "w", encoding="utf-8") as f:
                json.dump(data_instance, f, indent=4, ensure_ascii=False)
        except Exception as e:
            lbl_status.after(0, lambda: lbl_status.config(text=f"Lỗi tạo file cấu hình: {e}", fg="red"))
            return

    # "Latest Version" la instance dac biet LUON phai tro toi ban Minecraft moi
    # nhat - version_goc cua no duoc tu dong cap nhat trong config (xem
    # instance_frame.py) moi lan mo app, nhung instance_info.json tren dia
    # chi duoc ghi 1 lan luc tao nen co the bi "ket" o phien ban cu. Vi vay,
    # voi instance nay, luon dong bo lai version_goc moi nhat tu config truoc
    # khi doc, tranh chay nham phien ban cu (vd 26.1.2 trong khi config da la 26.2).
    if ten_instance == "Latest Version" or ten_folder_instance == "Latest_Version":
        ds_instances = config.current_config.get("danh_sach_instances", {})
        data_latest = ds_instances.get("Latest Version")
        if data_latest:
            try:
                with open(file_thong_tin, "w", encoding="utf-8") as f:
                    json.dump(data_latest, f, indent=4, ensure_ascii=False)
            except Exception:
                pass  # neu ghi loi thi van tiep tuc doc file cu, khong chan nguoi dung

    try:
        with open(file_thong_tin, "r", encoding="utf-8") as f:
            thong_tin_instance = json.load(f)
    except Exception:
        lbl_status.after(0, lambda: lbl_status.config(text="Lỗi: Không thể đọc cấu hình Instance!", fg="red"))
        return

    def _parse_ram(val, default):
        import re as _re
        val = str(val).strip().upper().replace(" ", "")
        m = _re.match(r"^(\d+)\s*(GB|MB|G|M)?$", val)
        if m:
            num, unit = m.group(1), (m.group(2) or "G")
            unit = unit.replace("GB", "G").replace("MB", "M")
            return f"{num}{unit}"
        return default
    ram_min = _parse_ram(config.current_config.get("ram_min", "2GB"), "2G")
    ram_max = _parse_ram(config.current_config.get("ram_max", "4GB"), "4G")

    do_phan_giai = config.current_config.get("do_phan_giai", "854x480")
    match = re.search(r"(\d+)\s*x\s*(\d+)", do_phan_giai)
    rong, cao = (match.group(1), match.group(2)) if match else ("854", "480")

    # Kiểm tra tài khoản premium hay offline
    ds_tai_khoan_ms = config.current_config.get("tai_khoan_microsoft", {})
    thong_tin_ms = ds_tai_khoan_ms.get(tai_khoan)
    la_tai_khoan_premium = thong_tin_ms is not None and thong_tin_ms.get("loai") == "premium"

    # Thử làm mới token nếu là tài khoản premium
    if la_tai_khoan_premium and thong_tin_ms.get("refresh_token"):
        token_moi = lam_moi_token_microsoft(thong_tin_ms["refresh_token"])
        if token_moi:
            thong_tin_ms.update(token_moi)
            ds_tai_khoan_ms[tai_khoan] = thong_tin_ms
            config.current_config["tai_khoan_microsoft"] = ds_tai_khoan_ms
            config.luu_toan_bo_cau_hinh()

    danh_sach_jvm_args = build_jvm_arguments(config.current_config, ram_min, ram_max, la_tai_khoan_premium)

    if la_tai_khoan_premium:
        # Dùng thông tin xác thực thật từ Microsoft
        _username = thong_tin_ms.get("name", tai_khoan)
        _uuid_str = thong_tin_ms.get("uuid", "")
        _token = thong_tin_ms.get("access_token", "")
    else:
        import uuid as _uuid
        _username = tai_khoan
        _uuid_str = str(_uuid.uuid3(_uuid.NAMESPACE_DNS, f"OfflinePlayer:{tai_khoan}"))
        _token = "0"

    options = {
        "username": _username,
        "uuid": _uuid_str,
        "token": _token,
        "jvmArguments": danh_sach_jvm_args,
        "customResolution": True,
        "resolutionWidth": rong,
        "resolutionHeight": cao,
    }

    java_path = config.current_config.get("java_path", "").strip()
    if java_path and os.path.isfile(java_path):
        options["executablePath"] = java_path

    lbl_status.after(0, lambda: lbl_status.config(text="Đang tải và cài đặt game...", fg="#1E88E5"))

    try:
        lenh = cai_dat_va_lay_lenh_chay(
            thong_tin_instance["loai_game"],
            thong_tin_instance["version_goc"],
            thong_tin_instance["version_mod"],
            thu_muc_game,
            ten_folder_instance,
            options,
            callback_progress,
            should_cancel
        )
        lbl_status.after(0, lambda: lbl_status.config(text="Đang khởi động Minecraft...", fg="#2b8c54"))
        if callback_progress:
            callback_progress(100.0, "Hoàn tất!")
        # An cua so CMD den tren Windows
        import sys as _sys
        _startupinfo = None
        _creationflags = 0
        if _sys.platform == "win32":
            _startupinfo = subprocess.STARTUPINFO()
            _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _startupinfo.wShowWindow = subprocess.SW_HIDE
            _creationflags = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(
            lenh,
            startupinfo=_startupinfo,
            creationflags=_creationflags,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        return proc
    except InterruptedError:
        lbl_status.after(0, lambda: lbl_status.config(text="Sẵn sàng", fg="gray"))
        return None
    except Exception as e:
        # QUAN TRONG: KHONG tu "an" loi va return None o day. Truoc day code
        # chi cap nhat lbl_status roi return None, nhung ben goi (main.py)
        # ngay sau do lai TU GHI DE lbl_status thanh "San sang" (vi proc=None
        # duoc hieu la "da huy hop le", giong InterruptedError) - khien thong
        # bao loi thuc su (vd thieu loader NeoForge, version_mod sai dinh
        # dang...) bi xoa mat trong vong chua toi 1 giay, tao cam giac "bam
        # Vao game ma khong co gi xay ra". Raise lai de main.py's except
        # Exception (co messagebox.showerror ro rang) xu ly dung.
        err = str(e)
        lbl_status.after(0, lambda: lbl_status.config(text=f"Thất bại: {err}", fg="red"))
        raise
def lay_danh_sach_phien_ban_theo_loai(loai):
    """loai: release | snapshot | old_beta | old_alpha"""
    try:
        all_versions = minecraft_launcher_lib.utils.get_version_list()
        return [v["id"] for v in all_versions if v["type"] == loai]
    except:
        return []