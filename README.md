# NoName MCL

**NoName MCL** là một Minecraft Launcher được viết bằng Python, hỗ trợ cài đặt mod, shader và modpack trực tiếp từ **CurseForge** và **Modrinth** — không cần rời khỏi launcher.

## ✨ Tính năng

- 🚀 **Khởi chạy Minecraft** với nhiều phiên bản (Vanilla, Forge, Fabric, Quilt, NeoForge...)
- 📦 **Cài đặt mod** trực tiếp từ CurseForge và Modrinth chỉ với vài cú click
- 🎨 **Tích hợp sẵn RSP Shader Modpack** — cài đặt nhanh gói shader chất lượng cao
- 📥 **Import modpack** từ CurseForge (`.zip`) và Modrinth (`.mrpack`)
- 🔄 Tự động tải và quản lý dependency của mod (loader, thư viện đi kèm)
- 🗂️ Quản lý nhiều profile/instance Minecraft độc lập
- ⚙️ Tùy chỉnh RAM, Java, JVM Arguments

> ⚠️ **Lưu ý:** NoName MCL **không hỗ trợ đăng nhập tài khoản Microsoft/Mojang (premium)**. Điều này nhằm tránh việc launcher bị nghi ngờ thu thập cookie/token tài khoản Microsoft của người dùng. Launcher chỉ hỗ trợ chơi ở chế độ offline.

## 🖥️ Yêu cầu hệ thống

- Python 3.9+
- Java (khuyến nghị Java 17+ cho các phiên bản Minecraft mới)
- Hệ điều hành: Windows ✅ / Linux ❌ / macOS ❌

## 📦 Cài đặt

```bash
git clone https://github.com/bestnoob9/launcher-minecraft.git
cd launcher-minecraft
pip install -r requirements.txt
python main.py
```

## 🚀 Sử dụng

1. Mở NoName MCL
2. Đăng nhập tài khoản Minecraft
3. Tạo hoặc chọn một profile
4. Vào tab **Mods** để duyệt và cài mod từ CurseForge / Modrinth
5. Vào tab **Shaders** để cài nhanh **RSP Shader Modpack**
6. Hoặc dùng chức năng **Import Modpack** để nhập file `.zip` (CurseForge) hoặc `.mrpack` (Modrinth)
7. Nhấn **Play** để khởi chạy game

## 📥 Import Modpack

NoName MCL hỗ trợ import trực tiếp:

| Nguồn | Định dạng | Cách dùng |
|---|---|---|
| CurseForge | `.zip` | Import Modpack → chọn file `.zip` xuất từ CurseForge |
| Modrinth | `.mrpack` | Import Modpack → chọn file `.mrpack` xuất từ Modrinth |

Launcher sẽ tự động tải mod loader phù hợp cùng toàn bộ mod trong modpack.

## 🎨 RSP Shader Modpack

RSP Shader Modpack được tích hợp sẵn trong launcher, cho phép cài đặt chỉ với một click mà không cần tải thủ công hay cấu hình thêm.

## 🛠️ Công nghệ sử dụng

- Python
- CurseForge API
- Modrinth API

## 🤝 Đóng góp

Mọi đóng góp, báo lỗi hoặc đề xuất tính năng đều được hoan nghênh. Hãy tạo Issue hoặc Pull Request trên repository.

Made with ❤️ by bestnoob9.
