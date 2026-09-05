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
python run_app.py
```

> 💡 Nên chạy bằng `run_app.py` thay vì `main.py` — file này tự kiểm tra
> phiên bản Python và thư viện còn thiếu, rồi báo lỗi rõ ràng bằng hộp
> thoại nếu có vấn đề (kể cả khi bạn double-click chạy trực tiếp, không
> mở sẵn terminal). Dùng `main.py` vẫn hoạt động bình thường như trước
> nếu bạn muốn khởi động nhanh mà không cần các bước kiểm tra này.

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

## 🆕 Cập nhật gần đây

- 🩹 **Sửa lỗi chọn nhầm phiên bản Forge loader**: trước đây nếu máy đã cài
  sẵn một bản Forge nào đó cho một phiên bản Minecraft, launcher có thể lỡ
  dùng lại bản Forge cũ dù bạn đã chọn bản khác trong Instance. Giờ launcher
  so khớp chính xác số hiệu Forge loader đã chọn (kể cả với cách đặt tên
  thư mục cài đặt thực tế của Forge) trước khi quyết định cài mới hay dùng
  lại bản đã có.
- 🩹 **Sửa lỗi thanh tiến trình bị kẹt (CurseForge Mod/RSP/Shader)**: khi
  cài Mod/Resource Pack/Shader từ CurseForge, đôi khi chữ tiến trình
  "⬇ x% — ..." ở góc phải bị đứng yên mãi ở giá trị cuối cùng dù đã cài
  xong. Nguyên nhân do launcher đếm nhầm số tác vụ đang chạy; đã sửa để
  tiến trình luôn tự ẩn khi cài xong.
- 🩹 **Sửa lỗi thanh tiến trình bị kẹt khi cài Modpack**: khi cài modpack
  theo kiểu "cài nhanh" (không mở cửa sổ chi tiết) hoặc cài từ file
  `.mrpack`/`.zip` có sẵn, tiến trình bị đứng ở "Đang tải gói: 100%" dù
  các mod bên trong modpack vẫn đang được tải ngầm bình thường. Nguyên
  nhân do callback cập nhật tiến trình bị bỏ qua trong các luồng cài này;
  đã sửa để tiến trình luôn hiển thị đúng "x/xxx mod" trong lúc cài.
- ✨ **Bấm vào thanh tiến trình để xem chi tiết**: bấm vào chữ tiến trình
  ở góc phải khi đang cài đặt sẽ hiện một popup nhỏ cho biết chi tiết hơn
  — ví dụ `x/xxx mod đang được cài` khi cài modpack, hoặc `xKB/xxKB đang
  được cài` khi cài mod/shader/resource pack đơn lẻ.
- ✨ **Thanh tiến trình ngay trong danh sách mod/modpack**: khi cài đặt
  trực tiếp từ danh sách (không cần mở cửa sổ chi tiết), dòng đang cài sẽ
  hiện "Đang cài đặt..." kèm thanh tiến trình và số phần trăm — thay cho
  phần mô tả/thẻ tag trong lúc cài. Dữ liệu này luôn đồng bộ với thanh
  tiến trình trong cửa sổ chi tiết mod và badge tiến trình ở góc trên,
  vì cả ba đều đọc chung một nguồn dữ liệu tiến trình.
- 🩹 **Sửa lỗi instance modpack "ma" còn sót lại sau khi Hủy cài đặt**:
  trước đây, khi cài modpack lớn (mất nhiều thời gian), một luồng đồng bộ
  nền có thể "đoán mò" và thêm nhầm instance đó vào danh sách (thường với
  thông tin sai, ví dụ hiện "Vanilla" dù modpack dùng Forge/NeoForge) ngay
  khi đang tải dở, do tên hiển thị và tên thư mục thực tế (đã lọc ký tự
  cấm như `:`) không khớp nhau khiến việc dọn dẹp khi Hủy bị trượt. Giờ
  launcher đánh dấu rõ instance nào đang được cài để luồng đồng bộ nền bỏ
  qua hoàn toàn cho đến khi cài xong hoặc bị hủy, tránh hiện thông tin sai
  hoặc "mồ côi" instance đã xóa.
- 🚀 **Thêm `run_app.py`**: điểm khởi động mới, thân thiện hơn với người
  dùng phổ thông — tự kiểm tra Python/thư viện còn thiếu trước khi chạy.

## 🛠️ Công nghệ sử dụng

- Python
- CurseForge API
- Modrinth API

## 🤝 Đóng góp

Mọi đóng góp, báo lỗi hoặc đề xuất tính năng đều được hoan nghênh. Hãy tạo Issue hoặc Pull Request trên repository.

## 📄 Giấy phép

Dự án được phát hành theo giấy phép [MIT](LICENSE).

---

Made with ❤️ by bestnoob9.
