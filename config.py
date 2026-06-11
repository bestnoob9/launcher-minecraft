import os
import json
import core

file_config_json = os.path.join(os.getcwd(), "launcher_config.json")
def lay_phien_ban_moi_nhat():
    versions = core.lay_danh_sach_phien_ban_chinh()
    return versions[0]

# Định dạng cấu hình mặc định sạch sẽ, đồng bộ hóa các biến RAM và Độ phân giải
config_mac_dinh = {
    "danh_sach_acc": [],
    "current_account": "",
    "thu_muc_game": os.path.normpath(os.path.join(os.getcwd(), "Minecraft_Cua_Toi")),
    
    # Chuẩn hóa biến RAM và Độ phân giải để cửa sổ Setting đọc trực tiếp dạng chuỗi Combobox
    "ram_min": "2GB",
    "ram_max": "4GB",
    "do_phan_giai": "854x480",
    
    "current_instance": "Latest_Version",
    "danh_sach_instances": {
        "Latest Version": {
            "version_goc": lay_phien_ban_moi_nhat(),
            "loai_game": "Vanilla",
            "version_mod": "Vanilla"
        }
    }
}

# Đổi tên hàm thành tai_toan_bo_cau_hinh để main.py gọi chính xác
def tai_toan_bo_cau_hinh():
    global current_config
    if os.path.exists(file_config_json):
        try:
            with open(file_config_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Tự động bù đắp các trường bị thiếu nếu người dùng xài file config cũ
                for key in config_mac_dinh:
                    if key not in data:
                        data[key] = config_mac_dinh[key]
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