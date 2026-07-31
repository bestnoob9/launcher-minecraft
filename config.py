import os
import json
import hashlib
import uuid as _uuid_mod
import minecraft_launcher_lib

def _lay_phien_ban_moi_nhat():
    try:
        all_versions = minecraft_launcher_lib.utils.get_version_list()
        releases = [v["id"] for v in all_versions if v["type"] == "release"]
        return releases[0] if releases else "26.2"
    except:
        return "26.2"

import sys as _sys
if getattr(_sys, "frozen", False):
    _LAUNCHER_DIR = os.path.dirname(os.path.abspath(_sys.executable))
else:
    _LAUNCHER_DIR = os.path.dirname(os.path.abspath(__file__))
_FILE_CONFIG_TAM = os.path.join(_LAUNCHER_DIR, "launcher_config.json")
_THU_MUC_LAUNCHERCF = "launchercf"
_TEN_FILE_CONFIG    = "launcher_config.json"

_FILE_POINTER = os.path.join(_LAUNCHER_DIR, "launcher_path.json")

import re as _re

def chuan_hoa_duong_dan_thu_muc(duong_dan: str) -> str:
    """Chuẩn hóa đường dẫn thư mục do người dùng chọn.

    Sửa 2 lỗi thường gặp trên Windows:
    1) Khi chọn thư mục là GỐC của một ổ đĩa (vd "D:\\"),
       tkinter.filedialog.askdirectory() có thể trả về "D:" (thiếu "\\"
       ở cuối). Chuỗi "D:" là đường dẫn TƯƠNG ĐỐI theo "thư mục hiện tại
       của ổ D", không phải tuyệt đối.
    2) Khi người dùng gõ tay đường dẫn và quên dấu ":" sau chữ cái ổ đĩa
       (vd gõ "D\\gota" thay vì "D:\\gota"). Chuỗi "D\\gota" bị Windows
       hiểu là đường dẫn tương đối, dẫn tới việc tạo nhầm thư mục con
       tên "D" ngay cạnh launcher.
    Cả 2 trường hợp trên nếu không sửa sẽ khiến os.path.join(...) ghép
    sai và ghi dữ liệu nhầm chỗ. Hàm này chuẩn hóa để luôn ra một đường
    dẫn tuyệt đối hợp lệ.
    """
    if not duong_dan:
        return duong_dan
    duong_dan = duong_dan.strip()
    # Vá lỗi thiếu dấu ":" ngay sau 1 chữ cái ổ đĩa ở đầu chuỗi,
    # vd "D\gota" -> "D:\gota", "D/gota" -> "D:/gota"
    m = _re.match(r'^([A-Za-z])([\\/])(.*)$', duong_dan)
    if m:
        duong_dan = f"{m.group(1)}:{m.group(2)}{m.group(3)}"
    duong_dan = os.path.normpath(duong_dan)
    drive, tail = os.path.splitdrive(duong_dan)
    if drive and not tail:
        duong_dan = drive + os.sep
    return duong_dan

def duong_dan_hop_le(duong_dan: str) -> bool:
    """Kiểm tra đường dẫn đã tuyệt đối và hợp lệ hay chưa (sau khi đã
    chuan_hoa_duong_dan_thu_muc). Dùng để chặn lưu các giá trị dở dang,
    ví dụ thiếu dấu hai chấm sau ổ đĩa."""
    if not duong_dan:
        return False
    return os.path.isabs(duong_dan)

def _doc_pointer() -> str:
    try:
        with open(_FILE_POINTER, "r", encoding="utf-8") as f:
            return chuan_hoa_duong_dan_thu_muc(json.load(f).get("thu_muc_game", "").strip())
    except Exception:
        return ""

def _ghi_pointer(thu_muc_game: str):
    try:
        with open(_FILE_POINTER, "w", encoding="utf-8") as f:
            json.dump({"thu_muc_game": thu_muc_game}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Không thể ghi file pointer: {e}")

def _lay_duong_dan_config(thu_muc_game: str = "") -> str:
    if thu_muc_game and thu_muc_game.strip():
        return os.path.join(thu_muc_game, _THU_MUC_LAUNCHERCF, _TEN_FILE_CONFIG)
    return _FILE_CONFIG_TAM

file_config_json = _FILE_CONFIG_TAM

_TEN_FILE_USERNAME = "username.json"

def _lay_duong_dan_username(thu_muc_game: str = "") -> str:
    if thu_muc_game and thu_muc_game.strip():
        return os.path.join(thu_muc_game, _THU_MUC_LAUNCHERCF, _TEN_FILE_USERNAME)
    return os.path.join(_LAUNCHER_DIR, _TEN_FILE_USERNAME)

def _offline_uuid(username: str) -> str:
    data = f"OfflinePlayer:{username}".encode("utf-8")
    digest = bytearray(hashlib.md5(data).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(_uuid_mod.UUID(bytes=bytes(digest)))

def doc_username_json(thu_muc_game: str = "") -> dict:
    duong_dan = _lay_duong_dan_username(thu_muc_game)
    try:
        with open(duong_dan, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def ghi_username_json(du_lieu: dict, thu_muc_game: str = ""):
    duong_dan = _lay_duong_dan_username(thu_muc_game)
    try:
        os.makedirs(os.path.dirname(duong_dan) or ".", exist_ok=True)
        with open(duong_dan, "w", encoding="utf-8") as f:
            json.dump(du_lieu, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Không thể ghi username.json: {e}")

def lay_hoac_luu_uuid(username: str, thu_muc_game: str = "") -> str:
    username = (username or "").strip()
    du_lieu = doc_username_json(thu_muc_game)
    if username in du_lieu and du_lieu[username]:
        return du_lieu[username]

    uuid_moi = _offline_uuid(username)
    du_lieu[username] = uuid_moi
    ghi_username_json(du_lieu, thu_muc_game)
    return uuid_moi

def xoa_username(username: str, thu_muc_game: str = ""):
    du_lieu = doc_username_json(thu_muc_game)
    if username in du_lieu:
        del du_lieu[username]
        ghi_username_json(du_lieu, thu_muc_game)

def dong_bo_username_json(thu_muc_game: str = "", danh_sach_acc: list = None) -> dict:
    if danh_sach_acc is None:
        danh_sach_acc = current_config.get("danh_sach_acc", [])
    du_lieu = doc_username_json(thu_muc_game)
    thay_doi = False
    for ten in danh_sach_acc:
        ten = (ten or "").strip()
        if ten and ten not in du_lieu:
            du_lieu[ten] = _offline_uuid(ten)
            thay_doi = True
    if thay_doi:
        ghi_username_json(du_lieu, thu_muc_game)
    return du_lieu

def cap_nhat_duong_dan_config(thu_muc_game: str):
    global file_config_json
    thu_muc_game = chuan_hoa_duong_dan_thu_muc(thu_muc_game)
    duong_dan_moi = _lay_duong_dan_config(thu_muc_game)

    _ghi_pointer(thu_muc_game)

    file_config_json = duong_dan_moi

    if os.path.exists(duong_dan_moi):
        return

    os.makedirs(os.path.dirname(duong_dan_moi), exist_ok=True)
    if os.path.exists(_FILE_CONFIG_TAM):
        import shutil
        try:
            shutil.copy2(_FILE_CONFIG_TAM, duong_dan_moi)
            return
        except Exception as e:
            print(f"Không thể sao chép file config: {e}")

    luu_toan_bo_cau_hinh()

config_mac_dinh = {
    "danh_sach_acc": [],
    "current_account": "",
    "thu_muc_game": "",
    "ram_max": "4GB",
    "do_phan_giai": "854x480",
    "theme": "light",
    "kich_thuoc_cua_so": "1280x720",
    "an_launcher_khi_choi": True,
    "current_instance": "Latest Version",
    "danh_sach_instances": {
        "Latest Version": {
            "version_goc": _lay_phien_ban_moi_nhat(),
            "loai_game": "Vanilla",
            "version_mod": "Vanilla"
        }
    }
}

def tai_toan_bo_cau_hinh():
    global file_config_json

    data = None

    thu_muc = _doc_pointer()

    if thu_muc:
        file_chinh_thuc = _lay_duong_dan_config(thu_muc)
        if os.path.exists(file_chinh_thuc):
            try:
                with open(file_chinh_thuc, "r", encoding="utf-8") as f:
                    data = json.load(f)
                file_config_json = file_chinh_thuc
            except Exception:
                data = None
        else:

            file_config_json = file_chinh_thuc

    if data is None and os.path.exists(_FILE_CONFIG_TAM):
        try:
            with open(_FILE_CONFIG_TAM, "r", encoding="utf-8") as f:
                data = json.load(f)

            thu_muc_trong_tam = chuan_hoa_duong_dan_thu_muc(data.get("thu_muc_game", "").strip())
            if thu_muc_trong_tam and not thu_muc:
                thu_muc = thu_muc_trong_tam
                file_config_json = _lay_duong_dan_config(thu_muc)
                _ghi_pointer(thu_muc)
        except Exception:
            data = None

    if data is None:
        data = config_mac_dinh.copy()

    for key in config_mac_dinh:
        if key not in data:
            data[key] = config_mac_dinh[key]

    # Luôn tin theo vị trí thư mục thực tế (từ pointer), KHÔNG dùng giá
    # trị "thu_muc_game" cũ ghi sẵn bên trong file đã tải (hoặc giá trị
    # mặc định rỗng), vì file có thể đã bị copy/di chuyển sang thư mục
    # khác, hoặc bị xoá/tái tạo. Áp dụng vô điều kiện, bất kể data đến
    # từ đâu ở trên, để tránh việc mất dấu vết thư mục đang dùng.
    if thu_muc:
        data["thu_muc_game"] = thu_muc

    if "Latest Version" in data.get("danh_sach_instances", {}):
        data["danh_sach_instances"]["Latest Version"]["version_goc"] = _lay_phien_ban_moi_nhat()

    return data

def luu_toan_bo_cau_hinh():
    try:
        os.makedirs(os.path.dirname(file_config_json) or ".", exist_ok=True)
        with open(file_config_json, "w", encoding="utf-8") as f:
            json.dump(current_config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi lưu file cấu hình: {e}")

current_config = tai_toan_bo_cau_hinh()

_PRESET_JVM_FLAGS = {
    "aikar_optimized": (
        "-XX:+UseG1GC "
        "-XX:+ParallelRefProcEnabled "
        "-XX:MaxGCPauseMillis=200 "
        "-XX:+UnlockExperimentalVMOptions "
        "-XX:+DisableExplicitGC "
        "-XX:+AlwaysPreTouch "
        "-XX:G1NewSizePercent=30 "
        "-XX:G1MaxNewSizePercent=40 "
        "-XX:G1HeapRegionSize=8M "
        "-XX:G1ReservePercent=20 "
        "-XX:G1HeapWastePercent=5 "
        "-XX:G1MixedGCCountTarget=4 "
        "-XX:InitiatingHeapOccupancyPercent=15 "
        "-XX:G1MixedGCLiveThresholdPercent=90 "
        "-XX:G1RSetUpdatingPauseTimePercent=5 "
        "-XX:SurvivorRatio=32 "
        "-XX:+PerfDisableSharedMem "
        "-XX:MaxTenuringThreshold=1 "
        "-Dusing.aikars.flags=https://mcflags.emc.gs "
        "-Daikars.new.flags=true"
    ),
    "low_end": (
        "-XX:+UseSerialGC "
        "-XX:+OptimizeStringConcat "
        "-XX:+UseStringDeduplication "
        "-XX:MaxGCPauseMillis=50 "
        "-Xss512k "
        "-XX:MetaspaceSize=64m "
        "-XX:MaxMetaspaceSize=128m"
    ),
    "chunk_loading_heavy": (
        "-XX:+UseZGC "
        "-XX:+UnlockExperimentalVMOptions "
        "-XX:+ZGenerational "
        "-XX:+AlwaysPreTouch "
        "-XX:+DisableExplicitGC "
        "-XX:ConcGCThreads=4 "
        "-XX:ParallelGCThreads=4"
    ),
    "heavy_modded": (
        "-XX:+UseG1GC "
        "-XX:+UnlockExperimentalVMOptions "
        "-XX:+ParallelRefProcEnabled "
        "-XX:MaxGCPauseMillis=200 "
        "-XX:+AlwaysPreTouch "
        "-XX:G1HeapRegionSize=32M "
        "-XX:G1NewSizePercent=20 "
        "-XX:G1MaxNewSizePercent=50 "
        "-XX:G1ReservePercent=15 "
        "-XX:InitiatingHeapOccupancyPercent=20 "
        "-XX:G1MixedGCLiveThresholdPercent=85 "
        "-XX:MetaspaceSize=256m "
        "-XX:MaxMetaspaceSize=512m"
    ),
    "shenandoah_ultra": (
        "-XX:+UseShenandoahGC "
        "-XX:+UnlockExperimentalVMOptions "
        "-XX:ShenandoahGCMode=iu "
        "-XX:+AlwaysPreTouch "
        "-XX:+DisableExplicitGC "
        "-XX:+UseTransparentHugePages "
        "-XX:ConcGCThreads=4"
    ),
}

def _parse_ram_to_mb(s: str) -> int:
    s = str(s).strip().upper().replace(" ", "")
    if s.endswith("GB"):  return int(float(s[:-2]) * 1024)
    if s.endswith("MB"):  return int(s[:-2])
    if s.endswith("G"):   return int(float(s[:-1]) * 1024)
    if s.endswith("M"):   return int(s[:-1])
    try:    return int(s)
    except: return 2048

def _mb_to_jvm(mb: int) -> str:
    if mb >= 1024 and mb % 1024 == 0:
        return f"{mb // 1024}G"
    return f"{mb}M"

def build_jvm_args(cfg: dict | None = None) -> list[str]:
    if cfg is None:
        cfg = current_config

    ram_mb  = _parse_ram_to_mb(cfg.get("ram_max", "2GB"))
    ram_mb  = max(512, ram_mb)
    xmx     = _mb_to_jvm(ram_mb)
    xms     = _mb_to_jvm(max(512, ram_mb // 2))

    mode = cfg.get("jvm_mode", "default")

    if mode == "default":
        return []

    if mode == "preset":
        preset_key  = cfg.get("preset_jvm_args", "aikar_optimized")
        gc_flags    = _PRESET_JVM_FLAGS.get(preset_key, _PRESET_JVM_FLAGS["aikar_optimized"])
        full_args   = f"-Xmx{xmx} -Xms{xms} {gc_flags}"
        return full_args.split()

    if mode == "custom":
        raw = cfg.get("custom_jvm_args", "").strip()
        if not raw:
            return []

        import re
        if not re.search(r"-Xmx", raw, re.IGNORECASE):
            raw = f"-Xmx{xmx} -Xms{xms} {raw}"
        return raw.split()

    return []
