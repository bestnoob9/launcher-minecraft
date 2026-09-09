# NoName MCL

Launcher Minecraft: Java Edition viết bằng Python. Cài mod, resource pack, shader và modpack từ **Modrinth** và **CurseForge** ngay trong app.

## Tính năng

- Nhiều instance: Vanilla, Fabric, Forge, Quilt, NeoForge
- Duyệt / cài mod, resource pack, shader từ Modrinth và CurseForge
- Import modpack `.mrpack` (Modrinth) và `.zip` (CurseForge)
- Tự cài dependency *required* (ví dụ Fabric API) khi cài mod
- Kiểm tra cập nhật nội dung đã cài (theo hàng hoặc cả tab)
- Tùy chỉnh RAM, Java, JVM
- Hai loại tài khoản:
  - **Microsoft** — đăng nhập OAuth cho tài khoản đã mua Minecraft (xem bên dưới)
  - **Offline** — đặt tên, chơi đơn hoặc server offline-mode

## Đăng nhập Microsoft

Launcher dùng Azure App (public client) + `minecraft-launcher-lib`:

- Redirect: `http://127.0.0.1:17389`
- Không hỏi mật khẩu trong app; mở trình duyệt hệ thống
- Không gửi token lên máy chủ của NoName MCL; `refresh_token` chỉ lưu trên máy người dùng

App Azure mới phải được Mojang **duyệt App ID** trước khi gọi Minecraft Services. Khi chưa duyệt, nút đăng nhập có thể báo chưa có quyền API. Offline vẫn dùng bình thường.

NoName MCL không phải launcher chính thức của Mojang / Microsoft.

## Yêu cầu

- Windows
- Python 3.9+
- Java 17+ (bản Minecraft mới)

## Chạy từ mã nguồn

```bash
git clone https://github.com/bestnoob9/launcher-minecraft.git
cd launcher-minecraft
pip install -r requirements.txt
python run_app.py
```

Nên dùng `run_app.py` (kiểm tra Python và thư viện trước khi mở UI).

## Dùng nhanh

1. Mở launcher, chọn hoặc tạo instance
2. Thêm tài khoản Offline hoặc Microsoft
3. Tab nội dung: tìm mod / pack / shader, cài vào instance
4. Hoặc Import modpack
5. Chơi

## Công nghệ

Python, Tkinter, minecraft-launcher-lib, Modrinth API, CurseForge API.

## Đóng góp

Issue hoặc Pull Request trên repository này.

## Giấy phép

[MIT](LICENSE)

Made by bestnoob9.
