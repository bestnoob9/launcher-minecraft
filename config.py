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

file_config_json = os.path.join(os.getcwd(), "launcher_config.json")

# Định dạng cấu hình mặc định
config_mac_dinh = {
    "danh_sach_acc": [],
    "current_account": "",
    "thu_muc_game": os.path.normpath(os.path.join(os.getcwd(), "Minecraft_Cua_Toi")),
    "ram_min": "2GB",
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
    global current_config
    if os.path.exists(file_config_json):
        try:
            with open(file_config_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in config_mac_dinh:
                    if key not in data:
                        data[key] = config_mac_dinh[key]
                
                # Tự động cập nhật version mới nhất cho "Latest Version"
                if "Latest Version" in data.get("danh_sach_instances", {}):
                    data["danh_sach_instances"]["Latest Version"]["version_goc"] = _lay_phien_ban_moi_nhat()
                
                return data
        except:
            pass
    return config_mac_dinh.copy()

def luu_toan_bo_cau_hinh():
    try:
        with open(file_config_json, "w", encoding="utf-8") as f:
            json.dump(current_config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi lưu file cấu hình: {e}")

# Khởi tạo biến cấu hình toàn cục khi import module
current_config = tai_toan_bo_cau_hinh()

