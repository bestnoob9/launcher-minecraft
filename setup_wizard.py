"""
setup_wizard.py
---------------
Hiển thị cửa sổ chọn/nhập đường dẫn lưu game khi chưa có cấu hình.
Gọi hàm `kiem_tra_va_chay_wizard(root)` trước khi khởi chạy launcher chính.
Trả về True nếu đường dẫn hợp lệ (có thể tiếp tục), False nếu người dùng đóng cửa sổ.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import config


def _duong_dan_hop_le(path: str) -> bool:
    """Kiểm tra đường dẫn không rỗng và có thể tạo được."""
    if not path or not path.strip():
        return False
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False


def kiem_tra_va_chay_wizard(root) -> bool:
    """
    Kiểm tra xem đường dẫn lưu game đã được cấu hình chưa.
    - Nếu đã có và thư mục tồn tại → bỏ qua, trả về True ngay.
    - Nếu chưa có hoặc thư mục không tồn tại → mở wizard.
    """
    thu_muc_hien_tai = config.current_config.get("thu_muc_game", "").strip()

    # Kiểm tra xem đường dẫn có phải là giá trị mặc định chưa được người dùng chọn không
    duong_dan_mac_dinh = os.path.normpath(os.path.join(os.getcwd(), ".MinecraftFile"))
    da_cau_hinh = (
        thu_muc_hien_tai
        and thu_muc_hien_tai != duong_dan_mac_dinh
        and os.path.exists(thu_muc_hien_tai)
    )

    if da_cau_hinh:
        return True  # Đã có đường dẫn hợp lệ, không cần wizard

    # Chạy wizard
    return _mo_cua_so_wizard(root)


def _mo_cua_so_wizard(root) -> bool:
    ket_qua = {"ok": False}

    win = tk.Toplevel(root)
    win.title("⚙️ Thiết lập ban đầu — Chọn thư mục lưu game")
    win.geometry("520x280")
    win.resizable(False, False)
    win.grab_set()
    win.protocol("WM_DELETE_WINDOW", lambda: _dong_cua_so(win, ket_qua, root))

    # ── Tiêu đề ──────────────────────────────────────────────
    tk.Label(
        win,
        text="Chào mừng đến với Minecraft Launcher!",
        font=("Arial", 13, "bold"),
        fg="#1E88E5",
    ).pack(pady=(22, 4))

    tk.Label(
        win,
        text="Vui lòng chọn thư mục để lưu dữ liệu game.\n"
             "Thư mục này sẽ chứa game files, mod, resource pack, v.v.",
        font=("Arial", 10),
        fg="#444",
        justify="center",
    ).pack(pady=(0, 16))

    # ── Ô nhập đường dẫn ─────────────────────────────────────
    frame_path = tk.Frame(win)
    frame_path.pack(padx=28, fill="x")

    var_path = tk.StringVar(value=os.path.normpath(os.path.join(os.path.expanduser("~"), ".Minecraftfile")))

    ent_path = tk.Entry(frame_path, textvariable=var_path, font=("Arial", 10), width=42)
    ent_path.pack(side="left", ipady=4)

    def chon_thu_muc():
        duong_dan = filedialog.askdirectory(
            title="Chọn thư mục lưu game",
            initialdir=var_path.get() if os.path.exists(var_path.get()) else os.path.expanduser("~"),
        )
        if duong_dan:
            var_path.set(os.path.normpath(duong_dan))

    tk.Button(
        frame_path,
        text="📂",
        font=("Arial", 11),
        bg="#455A64",
        fg="white",
        padx=6,
        command=chon_thu_muc,
    ).pack(side="left", padx=(6, 0))

    # ── Nhãn lỗi ─────────────────────────────────────────────
    lbl_loi = tk.Label(win, text="", font=("Arial", 9), fg="red")
    lbl_loi.pack(pady=(6, 0))

    # ── Nút xác nhận ─────────────────────────────────────────
    def xac_nhan():
        duong_dan = var_path.get().strip()
        if not duong_dan:
            lbl_loi.config(text="⚠  Đường dẫn không được để trống!")
            return
        if not _duong_dan_hop_le(duong_dan):
            lbl_loi.config(text="⚠  Không thể tạo thư mục tại đường dẫn này. Vui lòng chọn lại!")
            return

        # Lưu vào config
        config.current_config["thu_muc_game"] = duong_dan
        config.luu_toan_bo_cau_hinh()

        ket_qua["ok"] = True
        win.grab_release()
        win.destroy()

    tk.Button(
        win,
        text="✅  Xác nhận & Bắt đầu",
        font=("Arial", 11, "bold"),
        bg="#1E88E5",
        fg="white",
        padx=16,
        pady=6,
        command=xac_nhan,
    ).pack(pady=(14, 0))

    # Đợi cửa sổ đóng
    root.wait_window(win)
    return ket_qua["ok"]


def _dong_cua_so(win, ket_qua, root):
    """Người dùng đóng wizard mà không xác nhận."""
    if messagebox.askyesno(
        "Thoát?",
        "Bạn chưa chọn thư mục lưu game.\nThoát launcher?",
        parent=win,
    ):
        ket_qua["ok"] = False
        win.grab_release()
        win.destroy()
        root.destroy()  # Đóng toàn bộ ứng dụng