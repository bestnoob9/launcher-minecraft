import os
import json
import urllib.request
import minecraft_launcher_lib
import subprocess
import re

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
            # --- ĐOẠN ĐƯỢC SỬA LẠI THỤT LỀ TỪ ĐÂY ---
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                tat_ca_versions = data.get("versions", [])

                parts = version_goc.split('.')
                sub_ver = parts[1] if len(parts) > 1 else ""

                # Lọc đúng prefix
                ds_loader = [v for v in tat_ca_versions if v.startswith(f"{sub_ver}.")]

                # Sort an toàn — bỏ qua version không parse được
                def safe_sort_key(s):
                    try:
                        return list(map(int, s.split('.')))
                    except:
                        return [0]

                ds_loader.sort(key=safe_sort_key, reverse=True)

                if ds_loader:
                    return ds_loader

                # Fallback nếu không tìm thấy — lấy tất cả bản mới nhất
                ds_loader = list(tat_ca_versions)
                ds_loader.sort(key=safe_sort_key, reverse=True)
                return ds_loader[:20]  # trả về 20 bản mới nhất
            # --- KẾT THÚC ĐOẠN SỬA THỤT LỀ ---

        elif loai_game == "Forge":
            forge_list = minecraft_launcher_lib.forge.list_forge_versions()
            return [f for f in forge_list if str(version_goc) in str(f)][::-1]

    except Exception as e:
        print(f"Lỗi tải API Mod cho {loai_game}: {e}")

    if loai_game == "NeoForge":
        parts = version_goc.split('.')
        sub_ver = parts[1] if len(parts) > 1 else "21"
        return [f"{sub_ver}.1.70", f"{sub_ver}.1.0"]

    return []

# =====================================================================
# TÍNH NĂNG ĐỒNG BỘ THỜI GIAN THỰC (DYNAMIC INSTANCE SCANNER)
# =====================================================================
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
            "-XX:+UseG1GC", "-XX:+AlwaysPreTouch", "-XX:+UseNUMA", "-XX:+UseFastAccessorMethods",
            "-XX:+ThreadPriorityPolicy=4", "-XX:+EmitSync=0", "-XX:MaxGCPauseMillis=50"
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

def build_jvm_arguments(current_config, ram_min, ram_max):
    final_args = []
    final_args.append(f"-Xms{ram_min}")
    final_args.append(f"-Xmx{ram_max}")

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

    minecraft_launcher_lib.install.install_minecraft_version(version_goc, thu_muc_game, _callbacks)
    id_phien_ban_chay = version_goc
    thu_muc_versions = os.path.join(thu_muc_game, "versions")

    if loai_game == "Fabric" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        minecraft_launcher_lib.fabric.install_fabric(version_goc, thu_muc_game, loader_version=version_mod_da_chon, callback=_callbacks)
        if os.path.exists(thu_muc_versions):
            # Uu tien khop chinh xac ca version_goc lan version_mod (tranh lay sai loader version)
            best = None
            for folder in os.listdir(thu_muc_versions):
                if "fabric" in folder.lower() and version_goc in folder:
                    if version_mod_da_chon in folder:
                        id_phien_ban_chay = folder
                        best = folder
                        break
                    elif best is None:
                        best = folder
            if id_phien_ban_chay == version_goc and best:
                id_phien_ban_chay = best

    elif loai_game == "Quilt" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        minecraft_launcher_lib.quilt.install_quilt(version_goc, thu_muc_game, loader_version=version_mod_da_chon, callback=_callbacks)
        if os.path.exists(thu_muc_versions):
            best = None
            for folder in os.listdir(thu_muc_versions):
                if "quilt" in folder.lower() and version_goc in folder:
                    if version_mod_da_chon in folder:
                        id_phien_ban_chay = folder
                        best = folder
                        break
                    elif best is None:
                        best = folder
            if id_phien_ban_chay == version_goc and best:
                id_phien_ban_chay = best

    elif loai_game == "NeoForge" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        try:
            minecraft_launcher_lib.neoforge.install_neoforge_version(version_mod_da_chon, thu_muc_game, callback=_callbacks)
        except AttributeError:
            raise Exception("NeoForge chưa được hỗ trợ. Hãy chạy: pip install --upgrade minecraft-launcher-lib")
        if os.path.exists(thu_muc_versions):
            for folder in os.listdir(thu_muc_versions):
                if "neoforge" in folder.lower() and version_mod_da_chon in folder:
                    id_phien_ban_chay = folder
                    break

    elif loai_game == "Forge" and version_mod_da_chon and version_mod_da_chon != "Vanilla":
        minecraft_launcher_lib.forge.install_forge_version(version_mod_da_chon, thu_muc_game, callback=_callbacks)
        if os.path.exists(thu_muc_versions):
            for folder in os.listdir(thu_muc_versions):
                if "forge" in folder.lower() and version_goc in folder:
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

    danh_sach_jvm_args = build_jvm_arguments(config.current_config, ram_min, ram_max)

    import uuid as _uuid
    offline_uuid = str(_uuid.uuid3(_uuid.NAMESPACE_DNS, f"OfflinePlayer:{tai_khoan}"))

    options = {
        "username": tai_khoan,
        "uuid": offline_uuid,
        "token": "",
        "jvmArguments": danh_sach_jvm_args,
        "customResolution": True,
        "resolutionWidth": rong,
        "resolutionHeight": cao,
    }

    if "selected_java_path" in config.current_config:
        options["executablePath"] = config.current_config["selected_java_path"]

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
        err = str(e)
        lbl_status.after(0, lambda: lbl_status.config(text=f"Thất bại: {err}", fg="red"))
        return None
def lay_danh_sach_phien_ban_theo_loai(loai):
    """loai: release | snapshot | old_beta | old_alpha"""
    try:
        all_versions = minecraft_launcher_lib.utils.get_version_list()
        return [v["id"] for v in all_versions if v["type"] == loai]
    except:
        return []