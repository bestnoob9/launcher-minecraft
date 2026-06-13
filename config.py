import os
import json
import minecraft_launcher_lib

def _lay_phien_ban_moi_nhat():
    try:
        all_versions = minecraft_launcher_lib.utils.get_version_list()
        releases = [v["id"] for v in all_versions if v["type"] == "release"]
        return releases[0] if releases else "1.21.1"
    except:
        return "1.21.1"

# ──────────────────────────────────────────────────────────────────────
# Đường dẫn file config
# - Lần đầu (chưa có thu_muc_game): lưu tạm bên cạnh launcher (cwd)
# - Sau khi wizard chọn xong: chuyển hẳn vào <thu_muc_game>/launchercf/
# ──────────────────────────────────────────────────────────────────────

_FILE_CONFIG_TAM = os.path.join(os.getcwd(), "launcher_config.json")
_THU_MUC_LAUNCHERCF = "launchercf"
_TEN_FILE_CONFIG    = "launcher_config.json"

def _lay_duong_dan_config(thu_muc_game: str = "") -> str:
    """Trả về đường dẫn tuyệt đối tới file config JSON."""
    if thu_muc_game and thu_muc_game.strip():
        return os.path.join(thu_muc_game, _THU_MUC_LAUNCHERCF, _TEN_FILE_CONFIG)
    return _FILE_CONFIG_TAM

# Biến module-level, sẽ được cập nhật bởi cap_nhat_duong_dan_config()
file_config_json = _FILE_CONFIG_TAM

def cap_nhat_duong_dan_config(thu_muc_game: str):
    """
    Gọi sau khi wizard xác nhận thu_muc_game.
    - Cập nhật file_config_json trỏ vào <thu_muc_game>/launchercf/
    - Di chuyển file tạm (nếu có) sang vị trí mới.
    - Lưu lại config ngay để chắc chắn.
    """
    global file_config_json
    duong_dan_moi = _lay_duong_dan_config(thu_muc_game)
    if duong_dan_moi == file_config_json:
        return  # Không thay đổi gì

    # Tạo thư mục đích nếu chưa có
    os.makedirs(os.path.dirname(duong_dan_moi), exist_ok=True)

    # Di chuyển file tạm nếu tồn tại và file đích chưa có
    if os.path.exists(file_config_json) and not os.path.exists(duong_dan_moi):
        import shutil
        try:
            shutil.move(file_config_json, duong_dan_moi)
        except Exception as e:
            print(f"Không thể di chuyển file config: {e}")

    file_config_json = duong_dan_moi
    luu_toan_bo_cau_hinh()


# ──────────────────────────────────────────────────────────────────────
# Cấu hình mặc định
# "thu_muc_game" để rỗng — setup_wizard.py sẽ yêu cầu nhập lần đầu.
# ──────────────────────────────────────────────────────────────────────
config_mac_dinh = {
    "danh_sach_acc": [],
    "current_account": "",
    "thu_muc_game": "",
    "ram_max": "4GB",
    "do_phan_giai": "854x480",
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
    """
    Thử đọc config theo thứ tự ưu tiên:
    1. File tạm bên cạnh launcher (để lấy thu_muc_game đã lưu trước)
    2. File chính thức trong <thu_muc_game>/launchercf/
    Sau khi đọc xong, cập nhật file_config_json trỏ đúng vị trí.
    """
    global file_config_json

    data = None

    # Bước 1 — thử đọc file tạm để lấy thu_muc_game
    if os.path.exists(_FILE_CONFIG_TAM):
        try:
            with open(_FILE_CONFIG_TAM, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = None

    # Bước 2 — nếu có thu_muc_game, thử đọc file chính thức
    thu_muc = (data or {}).get("thu_muc_game", "").strip()
    if thu_muc:
        file_chinh_thuc = _lay_duong_dan_config(thu_muc)
        if os.path.exists(file_chinh_thuc):
            try:
                with open(file_chinh_thuc, "r", encoding="utf-8") as f:
                    data = json.load(f)
                file_config_json = file_chinh_thuc  # Trỏ sang file chính thức
            except:
                pass
        else:
            # File chính thức chưa tồn tại — cập nhật đường dẫn để lưu vào đó
            file_config_json = file_chinh_thuc

    if data is None:
        data = config_mac_dinh.copy()

    # Bổ sung key thiếu
    for key in config_mac_dinh:
        if key not in data:
            data[key] = config_mac_dinh[key]

    # Tự động cập nhật version mới nhất
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


# Khởi tạo biến cấu hình toàn cục khi import module
current_config = tai_toan_bo_cau_hinh()


# ──────────────────────────────────────────────────────────────────────
# JVM ARGUMENTS BUILDER
# Các preset chỉ chứa flags tối ưu, KHÔNG hardcode -Xmx/-Xms.
# RAM luôn được lấy từ current_config["ram_max"] (thanh kéo setting).
# ──────────────────────────────────────────────────────────────────────

# Chỉ chứa GC flags & tối ưu, KHÔNG có -Xmx/-Xms (sẽ inject tự động)
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
    """Chuyển chuỗi RAM (vd: '4GB', '2 GB', '2048MB') sang số MB."""
    s = str(s).strip().upper().replace(" ", "")
    if s.endswith("GB"):  return int(float(s[:-2]) * 1024)
    if s.endswith("MB"):  return int(s[:-2])
    if s.endswith("G"):   return int(float(s[:-1]) * 1024)
    if s.endswith("M"):   return int(s[:-1])
    try:    return int(s)
    except: return 2048


def _mb_to_jvm(mb: int) -> str:
    """Chuyển MB sang chuỗi JVM gọn nhất: '4G' hoặc '512M'."""
    if mb >= 1024 and mb % 1024 == 0:
        return f"{mb // 1024}G"
    return f"{mb}M"


def build_jvm_args(cfg: dict | None = None) -> list[str]:
    """
    Trả về list JVM arguments dựa theo cấu hình hiện tại.

    - RAM (-Xmx / -Xms) luôn lấy từ cfg["ram_max"] (thanh kéo).
    - Preset chỉ cung cấp GC flags & tối ưu, không hardcode RAM.
    - Chế độ "default": trả về [] để Mojang launcher tự xử lý.

    Dùng:
        jvm_args = config.build_jvm_args()
        # hoặc
        jvm_args = config.build_jvm_args(config.current_config)
    """
    if cfg is None:
        cfg = current_config

    ram_mb  = _parse_ram_to_mb(cfg.get("ram_max", "2GB"))
    ram_mb  = max(512, ram_mb)                        # tối thiểu 512 MB
    xmx     = _mb_to_jvm(ram_mb)
    xms     = _mb_to_jvm(max(512, ram_mb // 2))      # Xms = 50% Xmx

    mode = cfg.get("jvm_mode", "default")

    # ── Chế độ 1: Mặc định Mojang ──────────────────────────────────
    if mode == "default":
        return []  # Để Mojang launcher tự inject RAM

    # ── Chế độ 2: Gói tối ưu sẵn ──────────────────────────────────
    if mode == "preset":
        preset_key  = cfg.get("preset_jvm_args", "aikar_optimized")
        gc_flags    = _PRESET_JVM_FLAGS.get(preset_key, _PRESET_JVM_FLAGS["aikar_optimized"])
        full_args   = f"-Xmx{xmx} -Xms{xms} {gc_flags}"
        return full_args.split()

    # ── Chế độ 3: Nhập tay (Custom) ────────────────────────────────
    if mode == "custom":
        raw = cfg.get("custom_jvm_args", "").strip()
        if not raw:
            return []
        # Nếu người dùng không tự nhập -Xmx thì tự inject vào đầu
        import re
        if not re.search(r"-Xmx", raw, re.IGNORECASE):
            raw = f"-Xmx{xmx} -Xms{xms} {raw}"
        return raw.split()

    return []