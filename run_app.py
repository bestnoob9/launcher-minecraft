import os
import sys
_THU_MUC_GOC = os.path.dirname(os.path.abspath(__file__))
os.chdir(_THU_MUC_GOC)
if _THU_MUC_GOC not in sys.path:
    sys.path.insert(0, _THU_MUC_GOC)
_THU_VIEN_BAT_BUOC = {
    "minecraft_launcher_lib": "minecraft-launcher-lib",
    "psutil": "psutil",
    "PIL": "Pillow",
}
def _bao_loi(tieu_de, noi_dung):
    print(f"[LỖI] {tieu_de}\n{noi_dung}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(tieu_de, noi_dung)
        root.destroy()
    except Exception:
        pass
def _kiem_tra_python():
    if sys.version_info < (3, 9):
        _bao_loi(
            "Phiên bản Python quá cũ",
            "NoName MCL cần Python 3.9 trở lên.\n"
            f"Bạn đang dùng Python {sys.version_info.major}.{sys.version_info.minor}.\n\n"
            "Hãy cài Python mới hơn tại https://www.python.org/downloads/",
        )
        sys.exit(1)
def _kiem_tra_thu_vien():
    thieu = []
    for module, ten_pip in _THU_VIEN_BAT_BUOC.items():
        try:
            __import__(module)
        except ImportError:
            thieu.append(ten_pip)
    if thieu:
        lenh = "pip install " + " ".join(thieu)
        _bao_loi(
            "Thiếu thư viện",
            "NoName MCL chưa thể chạy vì thiếu thư viện:\n\n"
            f"  {', '.join(thieu)}\n\n"
            "Hãy mở Command Prompt / Terminal tại thư mục này rồi chạy:\n\n"
            f"  {lenh}\n\n"
            "Sau đó chạy lại run_app.py.",
        )
        sys.exit(1)
def main():
    _kiem_tra_python()
    _kiem_tra_thu_vien()
    try:
        from main import main as _chay_launcher
    except Exception:
        import traceback
        chi_tiet = traceback.format_exc()
        print(chi_tiet)
        _bao_loi(
            "Không thể khởi động",
            "NoName MCL gặp lỗi khi nạp chương trình.\n"
            "Xem chi tiết trong console/log để biết thêm.",
        )
        sys.exit(1)
    try:
        _chay_launcher()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        chi_tiet = traceback.format_exc()
        print(chi_tiet)
        _bao_loi(
            "Lỗi không mong muốn",
            f"NoName MCL gặp lỗi trong lúc chạy:\n\n{e}\n\n"
            "Xem chi tiết trong console/log để biết thêm.",
        )
        sys.exit(1)
if __name__ == "__main__":
    main()