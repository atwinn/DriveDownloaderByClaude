# Drive Downloader

App desktop gọn nhẹ để tải file Google Drive nội bộ bằng cách dán link — ổn định
hơn tải qua trình duyệt (tự retry khi rớt mạng, vượt được trang chặn "virus scan"
của file lớn). Dùng **rclone** làm lõi tải, giao diện chạy trong cửa sổ native
(**pywebview**).

## Cài đặt (một lần)

```bash
# 1. rclone (lõi tải + đăng nhập Google)
brew install rclone

# 2. Môi trường Python + thư viện GUI
cd "DriveDownloader"
python3.12 -m venv .venv          # cần Python 3.12+
./.venv/bin/pip install -r requirements.txt
```

## Chạy

- **macOS**: double-click `Drive Downloader.command`
- Hoặc dòng lệnh:
  ```bash
  ./.venv/bin/python app.py
  ```

## Cài đặt từ bản đóng gói (.app / .dmg)

Bản build sẵn nằm trong `dist/`:
- **`Drive Downloader.dmg`** — mở ra, kéo **Drive Downloader** vào thư mục **Applications**.
- **`Drive Downloader.app`** — chạy trực tiếp không cần cài.

App đã **bundle sẵn rclone** bên trong nên máy cài KHÔNG cần `brew install rclone`.

> ⚠️ App chưa mua chứng chỉ Apple (chưa notarize). Lần đầu mở, nếu macOS báo
> *"không xác minh được nhà phát triển"*: **chuột phải vào app → Open → Open**,
> hoặc vào *System Settings → Privacy & Security → Open Anyway*. Chỉ cần làm 1 lần.

### Build lại từ mã nguồn (macOS)

```bash
./.venv/bin/pip install -r requirements.txt pyinstaller pillow
./build_mac.sh        # tạo dist/Drive Downloader.app + .dmg
```

## Build cho Windows

PyInstaller **không cross-compile** — phải build trên **máy Windows**. Script
tự sinh `icon.ico` và tự tải `rclone.exe` (Windows x64) nếu chưa có.

1. Cài Python 3.10–3.12 từ python.org (nhớ tick *Add to PATH*).
2. Mở PowerShell trong thư mục dự án, chạy:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\build_win.ps1
   ```
   → ra app chạy trực tiếp: `dist\Drive Downloader\Drive Downloader.exe`
3. (Tuỳ chọn) Tạo **Setup.exe** cài đặt: cài [Inno Setup](https://jrsoftware.org/isdl.php) rồi:
   ```powershell
   & 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' installer.iss
   ```
   → ra `Output\DriveDownloader-Setup.exe`

> Windows dùng WebView2 (có sẵn trên Win10/11 đã cập nhật). Nếu app không mở,
> cài *Microsoft Edge WebView2 Runtime*. Bản build Windows cần được test trên
> Windows — mã đã xử lý ẩn cửa sổ console và tìm `rclone.exe` trong bundle.

## Ngôn ngữ

App hỗ trợ **Tiếng Việt** và **English**. Bấm nút **VI/EN** ở góc trên phải để
chuyển; lựa chọn được lưu lại cho lần mở sau.

## Cách dùng

1. Lần đầu bấm **Đăng nhập** → trình duyệt mở ra, đăng nhập tài khoản Google có
   quyền xem file công ty, cấp quyền (chỉ-đọc Drive). Token lưu lại, không phải
   đăng nhập lại.
2. Dán link Drive (file hoặc folder) → bấm **Tải xuống**.
3. Theo dõi thanh tiến độ, tốc độ, thời gian còn lại. Huỷ / thử lại / xoá / mở
   thư mục ngay trên từng thẻ.
4. Đổi thư mục lưu mặc định bằng nút **Chọn thư mục**.

## Ghi chú kỹ thuật

- File thường tải bằng `rclone backend copyid` (theo file-ID bóc từ link).
- **Folder**: app lấy đúng **tên folder gốc trên Drive** (qua Drive API, dùng
  token rclone đã lưu) và tạo `thư-mục-đích/<Tên folder>/` rồi tải nội dung vào
  đó — không còn đổ lẫn vào thư mục đích. Nếu trùng tên sẽ tự thêm ` (2)`, ` (3)`.
  Bấm **Thử lại** trên 1 folder dở sẽ tải tiếp vào đúng folder cũ (rclone bỏ qua
  file đã xong).
- **Resume**: rclone tự retry khi rớt mạng *trong lúc đang tải*
  (`--low-level-retries 20`) — đây là điểm browser thua. Nếu tải bị ngắt hẳn
  (đóng app, mất mạng dài), bấm **Thử lại** sẽ tải lại file đó.
- File **Google Docs/Sheets/Slides** là định dạng riêng của Google, không tải
  nhị phân trực tiếp được — app sẽ báo và bạn dùng *File > Tải xuống* trong Docs.
- Trạng thái lưu ở `jobs.json` cùng thư mục app.

## Nếu nút Đăng nhập trong app gặp trục trặc

Đăng nhập thủ công một lần qua terminal, rồi app sẽ nhận ra:

```bash
rclone config create drivedl drive scope drive.readonly
```
