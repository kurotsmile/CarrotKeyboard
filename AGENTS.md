# AGENTS.md - CarrotKeyboard

Tài liệu này giúp Codex/AI hiểu nhanh cấu trúc repo trước khi sửa code. Đọc file này trước, sau đó chỉ mở các file liên quan trực tiếp đến yêu cầu để giảm token quét.

## Mục tiêu dự án

CarrotKeyboard cho phép dùng bàn phím/chuột Mac để điều khiển nhập liệu trên máy khác trong cùng LAN:

- Mac sender -> Windows receiver.
- Mac sender -> Android receiver.

Giao tiếp dùng TCP line-delimited JSON, mặc định port `50505`. Sender nằm ở `mac.py`; receiver Windows nằm ở `win.py`; receiver Android nằm trong `android_receiver/`.

## Bản đồ file/thư mục

### Root

- `mac.py`: source chính cho app Mac. Có cả GUI Tkinter và chế độ CLI `--send`.
- `win.py`: source chính cho receiver Windows. Có cả GUI Tkinter và chế độ CLI `--receive`.
- `requirements.txt`: dependency Python chung, hiện dùng `pynput`.
- `README.md`: hướng dẫn người dùng chạy/build.
- `run_mac_sender.command`: mở `CarrotKeyboard.app`; nếu app chưa có thì chạy build.
- `run_windows_receiver.bat`: tạo/sửa `.venv_windows`, cài dependency và chạy `win.py`.
- `build_mac_app.command`: build lại `CarrotKeyboard.app` từ `mac.py`, `requirements.txt`, `icon.png`.
- `icon.png`: icon nguồn cho Mac app.
- `error.txt`: log/ghi chú lỗi cục bộ, không phải source logic.

### Android

- `android_receiver/src/com/carrot/keyboardreceiver/MainActivity.java`: UI receiver Android, start/stop TCP server, hiển thị IP, mở quyền Accessibility/Rotation, đổi click mode.
- `android_receiver/src/com/carrot/keyboardreceiver/CarrotAccessibilityService.java`: xử lý event JSON trên Android bằng Accessibility Service: nhập text, backspace, tap/click, scroll/swipe, rotate, overlay con trỏ.
- `android_receiver/AndroidManifest.xml`: permission, activity, service Accessibility.
- `android_receiver/res/xml/accessibility_service.xml`: cấu hình Accessibility Service.
- `android_receiver/res/values/*.xml`: string/theme Android.
- `android_receiver/build_apk.command`: build APK bằng Android SDK tools trực tiếp, không dùng Gradle.

### Artifact/generated, hạn chế đọc/sửa

- `.venv/`, `.venv_windows/`: môi trường Python cục bộ, bỏ qua khi quét.
- `build/`, `android_receiver/build/`: output build, bỏ qua trừ khi cần kiểm tra artifact.
- `CarrotKeyboard.app/`: app bundle đã build. Không sửa trực tiếp logic trong đây; sửa `mac.py` ở root rồi chạy `./build_mac_app.command`.
- `CarrotKeyboard.app/Contents/Resources/mac.py`: bản copy generated từ root `mac.py`.
- `.DS_Store`: metadata macOS, bỏ qua.

## Luồng chạy chính

### Mac sender (`mac.py`)

- Entry point: `main()`.
- GUI: `MacGui`, chạy khi không có `--send`.
- CLI sender: `MacSender(...).run()`, chạy khi có `--send --host ...`.
- Config lưu tại `~/Library/Application Support/CarrotKeyboard/config.json`.
- Hotkey mặc định:
  - Windows: `cmd+option+control+w`.
  - Android: `cmd+option+control+a`.
  - Android rotate: `cmd+option+control+r`.
- `MacGui.toggle_target()` spawn process con gọi lại chính file `mac.py` với `--send`; GUI đọc stdout để cập nhật log.
- `MacSender` dùng `pynput.keyboard.Listener` và `pynput.mouse.Listener` để bắt event, rồi gửi JSON qua TCP.

Các helper quan trọng trong `mac.py`:

- `key_to_payload()`: đổi phím `pynput` thành payload JSON.
- `parse_hotkey()`, `format_hotkey()`, `serialize_hotkey()`: chuẩn hóa hotkey.
- `key_to_hotkey_token()`, `tk_keysym_to_hotkey_token()`: đổi event phím từ `pynput`/Tkinter sang token hotkey.
- `load_config()`, `save_config()`: đọc/ghi config Mac.

### Windows receiver (`win.py`)

- Entry point: `main()`.
- GUI: `WindowsGui`, chạy khi không có `--receive`.
- CLI receiver: `WindowsReceiver(...).run()`, chạy khi có `--receive`.
- `WindowsGui.toggle()` spawn process con gọi lại `win.py --receive`.
- `WindowsReceiver` lắng nghe TCP, nhận từng dòng JSON, replay keyboard/mouse bằng `pynput`.

Các helper quan trọng trong `win.py`:

- `JsonLineReader`: đọc JSON từng dòng từ socket.
- `payload_to_key()`: map payload Mac sang key Windows; chú ý `cmd` được map thành `ctrl`.
- `payload_to_button()`: map tên button chuột.
- `WindowsReceiver.release_all()`: thả phím/chuột còn đang giữ khi client ngắt kết nối.

### Android receiver

- `MainActivity.startServer()` tạo `ServerThread` lắng nghe TCP port `50505`.
- `ServerThread.handleClient()` đọc từng dòng JSON và gọi `CarrotAccessibilityService.handle(event)`.
- `CarrotAccessibilityService.handle()` chuyển event vào main thread rồi gọi `handleEvent()`.
- `handleEvent()` tách `device`: `keyboard`, `mouse`, hoặc `system`.
- `handleKeyboard()` chỉ xử lý action `press`; text được append vào input đang focus qua `ACTION_SET_TEXT`.
- `handleMouse()` dùng `x_ratio`/`y_ratio` để di chuyển overlay; click ngắn thành tap, kéo đủ xa thành swipe.
- `handleSystem()` hiện hỗ trợ `action: "rotate"` nếu app có quyền `WRITE_SETTINGS`.

## Giao thức JSON line

Mỗi event là một object JSON trên một dòng, kết thúc bằng `\n`.

Keyboard:

```json
{"device":"keyboard","action":"press","key":{"type":"char","char":"a","vk":0}}
{"device":"keyboard","action":"release","key":{"type":"special","name":"enter"}}
```

Mouse:

```json
{"device":"mouse","action":"move","x_ratio":0.5,"y_ratio":0.5}
{"device":"mouse","action":"press","button":"left","x_ratio":0.5,"y_ratio":0.5}
{"device":"mouse","action":"release","button":"left","x_ratio":0.5,"y_ratio":0.5}
{"device":"mouse","action":"scroll","dx":0,"dy":-1}
```

System:

```json
{"device":"system","action":"rotate"}
```

Khi thêm action mới, cập nhật cả sender và receiver liên quan. Giữ backward-compatible: receiver nên bỏ qua event/action không biết thay vì crash.

## Quy tắc sửa code

- Sửa source gốc: `mac.py`, `win.py`, `android_receiver/src/...`. Không sửa bản generated trong `.app` hoặc `build/`.
- Nếu sửa logic Mac app, chạy `./build_mac_app.command` để đồng bộ `CarrotKeyboard.app`.
- Nếu sửa Android source/resource/manifest, chạy `cd android_receiver && ./build_apk.command` khi có Android SDK phù hợp.
- Giữ giao thức JSON nhỏ, rõ, có `device` và `action`; tránh thêm field bắt buộc nếu receiver cũ chưa hỗ trợ.
- Trước khi tạo helper mới, tìm bằng `rg` các hàm hiện có: hotkey, payload, screen size, config, socket, JSON reader, click mode.
- Giữ UI Tkinter đơn giản, không thêm framework mới.
- Android hiện không dùng Gradle; đừng thêm Gradle trừ khi người dùng yêu cầu rõ.
- Khi thao tác phím/chuột, luôn nghĩ tới cleanup khi disconnect: Windows có `release_all()`, Mac có `close_socket()`, Android cần không crash nếu Accessibility chưa bật.

## Lệnh kiểm tra nhanh

```bash
python3 -m py_compile mac.py win.py
```

```bash
./build_mac_app.command
```

```bash
cd android_receiver && ./build_apk.command
```

Trên Windows, kiểm tra thực tế bằng:

```bat
run_windows_receiver.bat
```

## Điểm dễ lỗi

- `pynput` trên macOS cần quyền Accessibility và Input Monitoring.
- `pynput` trên Windows có thể bị Firewall/antivirus hoặc quyền hệ thống ảnh hưởng.
- `cmd` từ Mac được map thành `ctrl` trên Windows trong `MAC_TO_WINDOWS_KEY`.
- Android text input hiện append toàn bộ text bằng `ACTION_SET_TEXT`, không gửi key event thật cho mọi phím.
- Android click có 3 mode: Smart, Gesture, Smart + Gesture. Logic nằm cả ở `MainActivity` và `CarrotAccessibilityService`, dùng chung pref `carrot_keyboard/click_mode`.
- Mouse position dùng tỷ lệ màn hình sender (`x_ratio`, `y_ratio`) rồi receiver scale theo màn hình target.
