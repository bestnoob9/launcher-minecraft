import tkinter as tk
from tkinter import messagebox
import threading
import config
import theme
from icon_utils import gan_icon_app
from components.dropdown_selector import DropdownSelector
class AccountFrame(tk.Frame):
    def __init__(self, parent, on_change_callback, modal=None):
        super().__init__(parent)
        self.on_change_callback = on_change_callback
        self.modal = modal
        self.on_open_add_panel = None
        self._ms_login_busy = False
        self._ms_login_session = {"server": None, "cancel_event": None}
        config.dong_bo_username_json(
            config.current_config.get("thu_muc_game", ""),
            config.current_config.get("danh_sach_acc", []),
        )
        self.create_widgets()
    def create_widgets(self):
        lbl_user = tk.Label(self, text="Chọn tài khoản (Profile):", font=("Arial", 9), anchor="w")
        lbl_user.pack(fill="x")
        self.selector = DropdownSelector(
            self,
            on_select=self._khi_chon_tai_khoan,
            on_delete=self.xoa_tai_khoan,
            bottom_text="➕ Thêm tài khoản",
            on_bottom_click=self.them_tai_khoan,
            show_icon_box=False,
            placeholder="(Chưa có tài khoản)",
            badge_fn=self._nhan_loai_tai_khoan,
        )
        self.selector.set_items(config.ten_danh_sach_acc(config.current_config["danh_sach_acc"]))
        self.selector.set(config.current_config.get("current_account", ""))
        self.selector.pack(fill="x", pady=(3, 5))
    def _nhan_loai_tai_khoan(self, ten):
        acc = config.tim_tai_khoan(config.current_config["danh_sach_acc"], ten)
        if acc is None:
            return ""
        return "(premium)" if acc.get("type") == "microsoft" else "(Offline)"
    def _refresh_selector(self):
        self.selector.set_items(config.ten_danh_sach_acc(config.current_config["danh_sach_acc"]))
    def _khi_chon_tai_khoan(self, ten):
        ten = (ten or "").strip()
        if ten:
            config.current_config["current_account"] = ten
            config.luu_toan_bo_cau_hinh()
        self.on_change_callback()
    def get_username(self):
        return self.selector.get().strip()
    def get_current_account(self):
        return self.selector.get().strip()
    def khoa(self, tat: bool):
        self.selector.configure_state(not tat)
    def _huy_phien_dang_nhap_ms(self):
        ev = self._ms_login_session.get("cancel_event")
        if ev is not None:
            ev.set()
    def them_tai_khoan(self):
        if self.on_open_add_panel:
            self.on_open_add_panel()
            return
        if self.modal is not None:
            self._ms_login_busy = False
            self._huy_phien_dang_nhap_ms()
            self._ms_login_session = {"server": None, "cancel_event": None}
            def _co_the_dong():
                if self._ms_login_session.get("server") is not None:
                    self._huy_phien_dang_nhap_ms()
                    return True
                return not self._ms_login_busy
            self.modal.open(self.build_add_panel, width=400,
                             close_guard=_co_the_dong)
            return
        self._them_tai_khoan_toplevel()
    def build_add_panel(self, parent, close):
        colors = theme.colors()
        accent = theme.sidebar_colors().get("accent", "#1E88E5")
        parent.configure(bg=colors["bg_alt"])
        content = tk.Frame(parent, bg=colors["bg_alt"])
        content.pack(fill="both", expand=True, padx=18, pady=16)
        bar = tk.Frame(content, bg=colors["bg_alt"])
        bar.pack(fill="x", pady=(0, 12))
        tk.Label(bar, text="➕ Thêm tài khoản", font=("Arial", 12, "bold"),
                 bg=colors["bg_alt"], fg=colors["fg_title"]).pack(side="left")
        tk.Button(bar, text="✕", font=("Arial", 9, "bold"), bg=colors["bg_alt"],
                  fg=colors["fg_desc"], relief="flat", bd=0, cursor="hand2",
                  command=close).pack(side="right")
        tab_bar = tk.Frame(content, bg=colors["bg_alt"])
        tab_bar.pack(fill="x", pady=(0, 12))
        body = tk.Frame(content, bg=colors["bg_alt"])
        body.pack(fill="both", expand=True)
        loai_dang_chon = {"value": "offline"}
        def _xoa_body():
            for w in body.winfo_children():
                w.destroy()
        def _cap_nhat_tab_style():
            for loai, btn in (("offline", btn_offline), ("microsoft", btn_microsoft)):
                dang_chon = (loai_dang_chon["value"] == loai)
                btn.configure(
                    bg=accent if dang_chon else colors["bg"],
                    fg="white" if dang_chon else colors["fg_title"],
                )
        def _chon_tab(loai):
            if self._ms_login_busy:
                return
            self._huy_phien_dang_nhap_ms()
            loai_dang_chon["value"] = loai
            _cap_nhat_tab_style()
            _xoa_body()
            if loai == "offline":
                self._build_offline_form(body, colors, close)
            else:
                self._build_microsoft_form(body, colors, close)
        btn_offline = tk.Button(tab_bar, text="Offline", font=("Arial", 10, "bold"),
                                 relief="flat", padx=14, pady=6, cursor="hand2",
                                 command=lambda: _chon_tab("offline"))
        btn_offline.pack(side="left", padx=(0, 6))
        btn_microsoft = tk.Button(tab_bar, text="Microsoft", font=("Arial", 10, "bold"),
                                   relief="flat", padx=14, pady=6, cursor="hand2",
                                   command=lambda: _chon_tab("microsoft"))
        btn_microsoft.pack(side="left")
        _cap_nhat_tab_style()
        self._build_offline_form(body, colors, close)
    def _build_offline_form(self, body, colors, close):
        tk.Label(body, text="Nhập tên tài khoản mới:", font=("Arial", 10),
                 bg=colors["bg_alt"], fg=colors["fg_title"], anchor="w"
                 ).pack(fill="x", pady=(0, 6))
        ent_new_name = tk.Entry(body, font=("Arial", 11), width=24,
                                 bg=colors["entry_bg"], fg=colors["entry_fg"],
                                 insertbackground=colors["entry_fg"], relief="solid", bd=1)
        ent_new_name.pack(fill="x")
        ent_new_name.focus_set()
        lbl_loi = tk.Label(body, text="", font=("Arial", 8, "italic"),
                            bg=colors["bg_alt"], fg="#E53935", anchor="w")
        lbl_loi.pack(fill="x", pady=(4, 0))
        def xu_ly_them():
            ten_moi = ent_new_name.get().strip()
            if not ten_moi:
                lbl_loi.config(text="⚠ Tên không được để trống!")
                return
            if config.tim_tai_khoan(config.current_config["danh_sach_acc"], ten_moi):
                lbl_loi.config(text="⚠ Tên tài khoản này đã tồn tại!")
                return
            config.current_config["danh_sach_acc"].append({"type": "offline", "name": ten_moi})
            config.current_config["current_account"] = ten_moi
            config.luu_toan_bo_cau_hinh()
            config.lay_hoac_luu_uuid(ten_moi, config.current_config.get("thu_muc_game", ""))
            self._refresh_selector()
            self.selector.set(ten_moi)
            self.on_change_callback()
            close()
        btn_bar = tk.Frame(body, bg=colors["bg_alt"])
        btn_bar.pack(fill="x", pady=(14, 0))
        tk.Button(btn_bar, text="Hủy", font=("Arial", 10), bg=colors["bg"],
                  fg=colors["fg_title"], relief="flat", padx=14, pady=6,
                  command=close).pack(side="right", padx=(8, 0))
        tk.Button(btn_bar, text="✔ Xác nhận", font=("Arial", 10, "bold"),
                  bg="#4CAF50", fg="white", relief="flat", padx=14, pady=6,
                  command=xu_ly_them).pack(side="right")
        ent_new_name.bind("<Return>", lambda e: xu_ly_them())
    def _build_microsoft_form(self, body, colors, close):
        if not (config.MICROSOFT_CLIENT_ID or "").strip():
            tk.Label(
                body,
                text=("⚠ Chưa cấu hình Microsoft Client ID.\n\n"
                      "Cần tạo 1 Azure App (loại Public client/native, "
                      "KHÔNG dùng client secret) rồi điền Client ID vào "
                      "config.MICROSOFT_CLIENT_ID hoặc biến môi trường "
                      "MC_LAUNCHER_MS_CLIENT_ID trước khi dùng đăng nhập "
                      "Microsoft."),
                font=("Arial", 9), bg=colors["bg_alt"], fg="#E53935",
                anchor="w", justify="left", wraplength=340,
            ).pack(fill="x")
            return
        lbl_info = tk.Label(
            body,
            text=("Bấm \"Đăng nhập Microsoft\" để mở trình duyệt. Đăng nhập "
                  "xong, launcher sẽ tự nhận và lưu tài khoản - không cần "
                  "dán URL nào cả."),
            font=("Arial", 9), bg=colors["bg_alt"], fg=colors["fg_desc"],
            anchor="w", justify="left", wraplength=340,
        )
        lbl_info.pack(fill="x", pady=(0, 10))
        lbl_status = tk.Label(body, text="", font=("Arial", 9, "italic"),
                               bg=colors["bg_alt"], fg=colors["fg_desc"],
                               anchor="w", justify="left", wraplength=340)
        lbl_status.pack(fill="x")
        def _dat_trang_thai(text, mau=None):
            lbl_status.config(text=text, fg=(mau or colors["fg_desc"]))
        login_state = {"oauth_state": None, "code_verifier": None}
        btn_huy = tk.Button(body, text="Hủy chờ đăng nhập", font=("Arial", 10),
                             bg=colors["bg"], fg=colors["fg_title"],
                             relief="flat", padx=14, pady=6, cursor="hand2")
        def _bam_huy():
            self._huy_phien_dang_nhap_ms()
            btn_huy.pack_forget()
            btn_login.config(state="normal")
            _dat_trang_thai("Đã hủy chờ đăng nhập.")
        btn_huy.config(command=_bam_huy)
        def _bat_dau_dang_nhap():
            import http.server
            import urllib.parse
            import webbrowser
            import minecraft_launcher_lib
            try:
                url, oauth_state, code_verifier = (
                    minecraft_launcher_lib.microsoft_account.get_secure_login_data(
                        config.MICROSOFT_CLIENT_ID, config.MICROSOFT_REDIRECT_URI))
            except Exception as e:
                _dat_trang_thai(f"⚠ Không tạo được liên kết đăng nhập: {e}", "#E53935")
                return
            login_state["oauth_state"] = oauth_state
            login_state["code_verifier"] = code_verifier
            class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    if "code" in qs or "error" in qs:
                        self.server.ket_qua_url = config.MICROSOFT_REDIRECT_URI + self.path
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        if "code" in qs:
                            noi_dung = ("<html><head><meta charset='utf-8'>"
                                        "<title>Đăng nhập thành công</title></head><body "
                                        "style='font-family:sans-serif;text-align:center;"
                                        "padding-top:60px;'><h2>Đăng nhập thành công ✔</h2>"
                                        "<p>Có thể đóng tab này và quay lại launcher.</p>"
                                        "</body></html>")
                        else:
                            noi_dung = ("<html><head><meta charset='utf-8'>"
                                        "<title>Đăng nhập bị hủy</title></head><body "
                                        "style='font-family:sans-serif;text-align:center;"
                                        "padding-top:60px;'><h2>Đăng nhập không thành công</h2>"
                                        "<p>Có thể đóng tab này và quay lại launcher.</p>"
                                        "</body></html>")
                        self.wfile.write(noi_dung.encode("utf-8"))
                    else:
                        self.send_response(404)
                        self.end_headers()
                def log_message(self, format, *args):
                    pass  
            try:
                server = http.server.HTTPServer(
                    ("127.0.0.1", config.MICROSOFT_LOGIN_PORT), _OAuthCallbackHandler)
            except OSError:
                _dat_trang_thai(
                    f"⚠ Cổng {config.MICROSOFT_LOGIN_PORT} đang bận (có thể "
                    "do ứng dụng khác đang dùng, hoặc 1 phiên đăng nhập cũ "
                    "chưa đóng). Hãy đổi MICROSOFT_LOGIN_PORT sang cổng "
                    "khác trong config.py và khai đúng Redirect URI đó "
                    "trên Azure rồi thử lại.", "#E53935")
                return
            server.ket_qua_url = None
            server.timeout = 1.0  
            cancel_event = threading.Event()
            session_obj = {"server": server, "cancel_event": cancel_event}
            self._ms_login_session = session_obj
            btn_login.config(state="disabled")
            btn_huy.pack(fill="x", pady=(8, 0))
            _dat_trang_thai("Đã mở trình duyệt. Đăng nhập rồi quay lại launcher.")
            webbrowser.open(url)
            THOI_GIAN_CHO_GIAY = 180
            def _server_loop():
                import time
                han_chot = time.time() + THOI_GIAN_CHO_GIAY
                while time.time() < han_chot and not cancel_event.is_set():
                    server.handle_request()
                    if server.ket_qua_url is not None:
                        break
                try:
                    server.server_close()
                except Exception:
                    pass
                ket_qua_url = server.ket_qua_url
                def _ve_main_thread():
                    if self._ms_login_session is not session_obj:
                        return
                    self._ms_login_session = {"server": None, "cancel_event": None}
                    if ket_qua_url is None:
                        btn_huy.pack_forget()
                        btn_login.config(state="normal")
                        _dat_trang_thai(
                            "⚠ Hết thời gian chờ đăng nhập, hãy bấm "
                            "\"Đăng nhập Microsoft\" lại.", "#E53935")
                        return
                    btn_huy.pack_forget()
                    _xu_ly_ket_qua(ket_qua_url)
                self.after(0, _ve_main_thread)
            threading.Thread(target=_server_loop, daemon=True).start()
        def _xu_ly_ket_qua(url):
            import minecraft_launcher_lib
            try:
                auth_code = minecraft_launcher_lib.microsoft_account.parse_auth_code_url(
                    url, login_state["oauth_state"])
            except Exception:
                btn_login.config(state="normal")
                _dat_trang_thai(
                    "⚠ Đăng nhập không hợp lệ hoặc bị hủy trên trình "
                    "duyệt/Azure, hãy bấm \"Đăng nhập Microsoft\" lại.",
                    "#E53935")
                return
            self._ms_login_busy = True
            _dat_trang_thai("Đang xác thực với Microsoft…")
            def _ve_luong_chinh(fn):
                self.after(0, fn)
            def _bao_loi(msg):
                self._ms_login_busy = False
                btn_login.config(state="normal")
                _dat_trang_thai(f"⚠ {msg}", "#E53935")
            def _luu_tai_khoan(profile):
                self._ms_login_busy = False
                ten_moi = profile["name"]
                da_co = config.tim_tai_khoan(config.current_config["danh_sach_acc"], ten_moi)
                if da_co is not None:
                    da_co["type"] = "microsoft"
                    da_co["uuid"] = profile["id"]
                    da_co["refresh_token"] = profile["refresh_token"]
                else:
                    config.current_config["danh_sach_acc"].append({
                        "type": "microsoft",
                        "name": ten_moi,
                        "uuid": profile["id"],
                        "refresh_token": profile["refresh_token"],
                    })
                config.current_config["current_account"] = ten_moi
                config.luu_toan_bo_cau_hinh()
                self._refresh_selector()
                self.selector.set(ten_moi)
                self.on_change_callback()
                close()
            def _luong():
                try:
                    profile = minecraft_launcher_lib.microsoft_account.complete_login(
                        config.MICROSOFT_CLIENT_ID, None, config.MICROSOFT_REDIRECT_URI,
                        auth_code, login_state["code_verifier"])
                except minecraft_launcher_lib.microsoft_account.AccountNotOwnMinecraft:
                    _ve_luong_chinh(lambda: _bao_loi(
                        "Tài khoản Microsoft này chưa sở hữu Minecraft. Không thể thêm."))
                    return
                except minecraft_launcher_lib.microsoft_account.AzureAppNotPermitted:
                    _ve_luong_chinh(lambda: _bao_loi(
                        "Azure App chưa được cấp quyền dùng Minecraft API."))
                    return
                except Exception as e:
                    _ve_luong_chinh(lambda: _bao_loi(f"Đăng nhập thất bại: {e}"))
                    return
                _ve_luong_chinh(lambda: _luu_tai_khoan(profile))
            threading.Thread(target=_luong, daemon=True).start()
        btn_login = tk.Button(body, text="Đăng nhập Microsoft", font=("Arial", 10, "bold"),
                               bg="#1E88E5", fg="white", relief="flat", padx=14, pady=8,
                               cursor="hand2", command=_bat_dau_dang_nhap)
        btn_login.pack(fill="x", pady=(10, 0))
    def _them_tai_khoan_toplevel(self):
        win_add = tk.Toplevel(self)
        win_add.title("Thêm tài khoản")
        win_add.geometry("300x150")
        win_add.resizable(False, False)
        win_add.grab_set()
        gan_icon_app(win_add)
        tk.Label(win_add, text="Nhập tên tài khoản mới:", font=("Arial", 10)).pack(pady=10)
        ent_new_name = tk.Entry(win_add, font=("Arial", 11), width=20)
        ent_new_name.pack(pady=5)
        ent_new_name.focus()
        def xu_ly_them():
            ten_moi = ent_new_name.get().strip()
            if not ten_moi:
                messagebox.showwarning("Chú ý", "Tên không được để trống!")
                return
            if config.tim_tai_khoan(config.current_config["danh_sach_acc"], ten_moi):
                messagebox.showwarning("Chú ý", "Tên tài khoản này đã tồn tại!")
                return
            config.current_config["danh_sach_acc"].append({"type": "offline", "name": ten_moi})
            config.current_config["current_account"] = ten_moi
            config.luu_toan_bo_cau_hinh()
            config.lay_hoac_luu_uuid(ten_moi, config.current_config.get("thu_muc_game", ""))
            self._refresh_selector()
            self.selector.set(ten_moi)
            self.on_change_callback()
            win_add.destroy()
        tk.Button(win_add, text="Xác nhận", font=("Arial", 10, "bold"), bg="#4CAF50", fg="white", command=xu_ly_them).pack(pady=10)
    def xoa_tai_khoan(self, ten=None):
        acc_dang_chon = ten if ten is not None else self.selector.get()
        if not acc_dang_chon:
            return
        def _thuc_hien_xoa():
            ds = config.current_config["danh_sach_acc"]
            acc = config.tim_tai_khoan(ds, acc_dang_chon)
            if acc is None:
                return
            ds.remove(acc)
            if acc.get("type") == "offline":
                config.xoa_username(acc_dang_chon, config.current_config.get("thu_muc_game", ""))
            dang_chon_bi_xoa = (acc_dang_chon == self.selector.get())
            if not ds:
                config.current_config["current_account"] = ""
                self._refresh_selector()
                self.selector.set("")
            else:
                self._refresh_selector()
                if dang_chon_bi_xoa:
                    config.current_config["current_account"] = ds[0]["name"]
                    self.selector.set(config.current_config["current_account"])
            config.luu_toan_bo_cau_hinh()
            self.on_change_callback()
        if self.modal is not None:
            self.modal.confirm(
                title="Xóa tài khoản",
                message=f"Bạn có chắc muốn xóa tài khoản '{acc_dang_chon}' không?",
                on_confirm=_thuc_hien_xoa,
                confirm_text="Xóa",
            )
            return
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn xóa tài khoản '{acc_dang_chon}' không?"):
            _thuc_hien_xoa()