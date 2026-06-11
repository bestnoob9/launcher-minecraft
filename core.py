import os
import json
import urllib.request
import minecraft_launcher_lib

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
            # --- CẬP NHẬT CHUẨN API CHO NEOFORGE ---
            # API này trả về danh sách phiên bản đầy đủ và chính xác nhất của NeoForge
            url = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                tat_ca_versions = data.get("versions", [])
                
                # Định dạng phiên bản của NeoForge từ bản 1.20.1 trở đi thường bắt đầu bằng số phiên bản phụ (Ví dụ: 20.x, 21.x)
                # Ta bóc tách số phụ từ version_goc (Ví dụ: "1.21.1" -> "21")
                parts = version_goc.split('.')
                sub_ver = parts[1] if len(parts) > 1 else ""
                
                # Lọc ra các phiên bản tương thích và đảo ngược để bản mới nhất lên đầu
                ds_loader = [v for v in tat_ca_versions if v.startswith(f"{sub_ver}.")]
                ds_loader.sort(key=lambda s: list(map(int, s.split('.'))), reverse=True)
                
                if ds_loader:
                    return ds_loader
                else:
                    # Nếu là bản MC quá mới chưa có NeoForge chính thức, tự sinh ra mã tương thích gần đúng
                    return [f"{sub_ver}.1.0", f"{sub_ver}.0.0"]

        elif loai_game == "Forge":
            forge_list = minecraft_launcher_lib.forge.list_forge_versions()
            return [f for f in forge_list if str(version_goc) in str(f)][::-1]

    except Exception as e:
        print(f"Lỗi tải API Mod cho {loai_game}: {e}")
    
    # Dự phòng (Fallback) nếu mất mạng hoặc API chặn kết nối
    if loai_game == "NeoForge":
        parts = version_goc.split('.')
        sub_ver = parts[1] if len(parts) > 1 else "21"
        return [f"{sub_ver}.1.70", f"{sub_ver}.1.0"] # Các bản release phổ biến thay vì chuỗi -beta lỗi
        
    return []

# Giữ nguyên các hàm lay_danh_sach_phien_ban_chinh và tai_danh_sach_mod của bạn...

def cai_dat_va_lay_lenh_chay(loai_game, version_goc, version_mod_da_chon, thu_muc_game, ten_instance, options):
    """
    thu_muc_game: Đường dẫn gốc lưu cốt lõi (Ví dụ: Minecraft_Cua_Toi)
    ten_instance: Tên thư mục phiên bản riêng (Ví dụ: May_Ao_1)
    """
    # 1. Định nghĩa thư mục Instance riêng biệt
    thu_muc_instance_rieng = os.path.join(thu_muc_game, "Instances", ten_instance)
    os.makedirs(thu_muc_instance_rieng, exist_ok=True)
    
    # Đè đường dẫn chạy game trong options thành thư mục riêng này
    # Điều này khiến cho thế giới (saves), mods, resourcepacks sẽ nằm tại đây
    options["gameDirectory"] = thu_muc_instance_rieng

    # 2. Tiến hành cài đặt lõi game vào thư mục chung (Để không phải tải lại nếu trùng bản gốc)
    minecraft_launcher_lib.install.install_minecraft_version(version_goc, thu_muc_game)
    id_phien_ban_chay = version_goc
    thu_muc_versions = os.path.join(thu_muc_game, "versions")

    # 3. Cài đặt các bản Mod Loader tương ứng (vẫn dùng bản cũ của bạn)
    if loai_game == "Fabric":
        minecraft_launcher_lib.fabric.install_fabric(version_goc, thu_muc_game, loader_version=version_mod_da_chon)
        if os.path.exists(thu_muc_versions):
            for folder in os.listdir(thu_muc_versions):
                if "fabric" in folder.lower() and version_goc in folder:
                    id_phien_ban_chay = folder
                    break

    elif loai_game == "Quilt":
        minecraft_launcher_lib.quilt.install_quilt(version_goc, thu_muc_game, loader_version=version_mod_da_chon)
        if os.path.exists(thu_muc_versions):
            for folder in os.listdir(thu_muc_versions):
                if "quilt" in folder.lower() and version_goc in folder:
                    id_phien_ban_chay = folder
                    break

    elif loai_game == "NeoForge":
        minecraft_launcher_lib.neoforge.install_neoforge_version(version_mod_da_chon, thu_muc_game)
        id_phien_ban_chay = version_mod_da_chon
        if os.path.exists(thu_muc_versions):
            for folder in os.listdir(thu_muc_versions):
                if "neoforge" in folder.lower() and version_mod_da_chon in folder:
                    id_phien_ban_chay = folder
                    break

    elif loai_game == "Forge":
        minecraft_launcher_lib.forge.install_forge_version(version_mod_da_chon, thu_muc_game)
        id_phien_ban_chay = version_mod_da_chon
        if os.path.exists(thu_muc_versions):
            for folder in os.listdir(thu_muc_versions):
                if "forge" in folder.lower() and version_goc in folder:
                    id_phien_ban_chay = folder
                    break

    # Lấy lệnh chạy: Lõi đọc từ thu_muc_game nhưng thực thi lệnh với options đã hướng về thu_muc_instance_rieng
    return minecraft_launcher_lib.command.get_minecraft_command(id_phien_ban_chay, thu_muc_game, options)