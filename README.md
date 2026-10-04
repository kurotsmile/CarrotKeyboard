# CarrotKeyboard

Tool Python có GUI để dùng bàn phím và chuột Mac điều khiển nhập liệu trên Windows PC trong cùng mạng LAN.

Tool chỉ đi một chiều:

```text
Mac keyboard/mouse -> Windows PC
Mac keyboard/mouse -> Android Phone
```

Mỗi hệ điều hành có file riêng để tránh xung đột thư viện/phím đặc thù:

- `mac.py`: chạy trên Mac, bắt phím/chuột và gửi qua mạng.
- `win.py`: chạy trên Windows, nhận phím/chuột và nhập vào hệ thống.
- `android_receiver/`: app Android receiver, nhận lệnh qua LAN và thao tác bằng Accessibility Service.

## Cách chạy

### Trên Windows PC

1. Cài Python 3.12 hoặc mới hơn nếu máy chưa có. Python 3.12.10 chạy được.
2. Chạy `run_windows_receiver.bat`.
3. Bấm `Start`.
5. Cho phép qua Windows Firewall nếu được hỏi.
6. Xem IP trong dòng `This machine IP`, hoặc dùng lệnh:

```bat
ipconfig
```

### Trên Mac

1. Mở `CarrotKeyboard.app` hoặc chạy `run_mac_sender.command`.
2. Nhập IP vào ô riêng: `Windows PC IP` hoặc `Android Phone IP`.
3. Bấm `▶ Windows` hoặc `▶ Android`, hoặc dùng hotkey tương ứng.
4. Bấm lại cùng nút/hotkey để tắt target đang chạy.
5. Nếu macOS hỏi quyền, cấp quyền trong:
   - System Settings > Privacy & Security > Accessibility
   - System Settings > Privacy & Security > Input Monitoring

Nếu mở bằng `CarrotKeyboard.app`, cấp quyền cho `CarrotKeyboard`. Nếu chạy bằng `.command`, cấp quyền cho Terminal/iTerm.

`run_mac_sender.command` chỉ mở `CarrotKeyboard.app` rồi tự đóng cửa sổ Terminal. Tool tiếp tục chạy trong app.

File chạy Mac và `CarrotKeyboard.app` tạo môi trường Python ở `$HOME/.carrot_keyboard_venv` để tránh lỗi cài package chậm/kẹt khi project nằm trong `/Volumes/htdocs`.
File chạy Windows tạo môi trường riêng ở `.venv_windows` để không dùng nhầm venv được tạo từ Mac.

Nếu mở app mà không thấy cửa sổ, xem log:

```bash
tail -100 "$HOME/Library/Logs/CarrotKeyboard.log"
```

### Trên Android Phone

1. Build APK:

```bash
cd android_receiver
./build_apk.command
```

2. Cài APK:

```bash
adb install -r android_receiver/build/CarrotKeyboardReceiver-debug.apk
```

Nếu đang đứng trong thư mục `android_receiver`, dùng:

```bash
adb install -r build/CarrotKeyboardReceiver-debug.apk
```

3. Mở app `CarrotKeyboard Receiver`.
4. Bấm `Accessibility`, bật service `CarrotKeyboard Receiver`.
5. Quay lại app, bấm `Start`.
6. Nếu muốn dùng hotkey xoay dọc/ngang, bấm `Rotation Permission` và bật quyền `Allow modify system settings`.
7. Xem `Phone IP`, nhập IP này vào Mac app ở ô `Android Phone IP`.

APK đã build nằm tại:

```text
android_receiver/build/CarrotKeyboardReceiver-debug.apk
```

## Build Mac App

Mac app được build từ `mac.py` và icon `icon.png`:

```bash
./build_mac_app.command
```

Kết quả:

```text
CarrotKeyboard.app
```

Khi đang chạy, mặc định phím sẽ được chặn ở Mac và gửi sang Windows. Nếu muốn vừa gõ trên Mac vừa gửi sang Windows, bỏ chọn `Block keys on Mac while forwarding`.
Chuột mặc định được gửi sang Windows nhưng không bị chặn ở Mac. Nếu muốn chuột chỉ điều khiển Windows, chọn `Block mouse on Mac`.
Bạn có thể đổi từng hotkey bằng nút `Record`: bấm `Record`, nhấn tổ hợp phím muốn dùng, rồi bấm `Save`.
Nếu bật `Auto Start`, lần sau mở app tool sẽ tự Start target đã dùng gần nhất, miễn là target đó đã có IP.

## GUI trên Mac

- `Windows PC IP`: IP của máy Windows, được lưu riêng.
- `Android Phone IP`: IP của điện thoại Android, được lưu riêng.
- `Port`: cổng TCP, mặc định `50505`.
- `Block keys on Mac while forwarding`: chặn phím ở Mac để bàn phím chỉ điều khiển target.
- `Forward mouse to target`: gửi di chuyển/click/scroll chuột sang target đang chọn.
- `Block mouse on Mac`: chặn chuột ở Mac khi đang gửi sang target.
- `Auto Start`: tự bật sender khi app mở xong.
- `Windows hotkey`: bật/tắt điều khiển Windows PC, mặc định `⌘ + ⌥ + ⌃ + W`.
- `Android hotkey`: bật/tắt điều khiển Android Phone, mặc định `⌘ + ⌥ + ⌃ + A`.
- `Android rotate hotkey`: xoay dọc/ngang màn hình Android, mặc định `⌘ + ⌥ + ⌃ + R`. Hotkey này chỉ hoạt động khi Android hotkey đang bật.
- `● Record`: học tổ hợp phím mới bằng cách nhấn trực tiếp trên bàn phím.
- `↺ Reset`: đưa hotkey về mặc định.
- `▶ Windows` / `■ Windows`: bật hoặc tắt Windows PC.
- `▶ Android` / `■ Android`: bật hoặc tắt Android Phone.
- `Log`: xem trạng thái kết nối và lỗi nếu có.

## GUI trên Windows

- `This PC IP`: IP để nhập vào GUI trên Mac.
- `Port`: cổng TCP, mặc định `50505`.
- `▶ Start` / `■ Stop`: bật hoặc tắt receiver.
- `⌫ Clear Log`: xóa log trên màn hình.
- `Log`: xem trạng thái kết nối và lỗi nếu có.

## Android Receiver

- `Phone IP`: IP nhập vào Mac app.
- `Accessibility`: mở màn hình bật Accessibility Service.
- `Rotation Permission`: mở màn hình cấp quyền `Modify system settings` để app có thể xoay dọc/ngang.
- `Click Mode`: đổi cách click trên Android:
  - `Smart`: tìm đúng button/view dưới con trỏ rồi click bằng Accessibility.
  - `Gesture`: tap theo tọa độ như ngón tay.
  - `Smart + Gesture`: thử cả hai, dùng khi một số nút khó click.
- `Start/Stop`: bật hoặc tắt TCP receiver trên Android.
- Khi Accessibility Service bật, app hiển thị một con trỏ nổi cỡ lớn trên màn hình Android.
- Text nhập vào ô đang focus sẽ được append qua Accessibility.
- Chuột Mac: di chuyển làm con trỏ nổi di chuyển, click thành tap, scroll thành swipe.
- Để vuốt qua màn hình Android, nhấn giữ chuột trên Mac, kéo, rồi thả. App sẽ chuyển thao tác đó thành gesture swipe thật trên Android.

## Chạy bằng dòng lệnh

Mac sender:

```bash
python mac.py --send --host WINDOWS_IP
```

Đổi hotkey khi chạy CLI:

```bash
python mac.py --send --host WINDOWS_IP --hotkey cmd+option+control+q
```

Đổi hotkey xoay Android khi chạy CLI:

```bash
python mac.py --send --host PHONE_IP --target "Android Phone" --hotkey cmd+option+control+a --rotate-hotkey cmd+option+control+r
```

Windows receiver:

```bat
python win.py --receive
```

## Dừng tool

Trên Mac nhấn hotkey target đang chạy:

```text
Windows: Command + Option + Control + W
Android: Command + Option + Control + A
Android rotate: Command + Option + Control + R
```

Hoặc bấm lại nút target đang chạy trong GUI.

## Ghi chú

- Tool dùng cổng TCP `50505`.
- Cấu hình Mac được lưu tại `~/Library/Application Support/CarrotKeyboard/config.json`.
- Hai máy cần ở cùng mạng LAN và Windows Firewall cần cho phép kết nối vào.
- Tool phát lại phím và chuột bằng thư viện `pynput`, phù hợp cho nhập liệu thường, hotkey, phím điều hướng, di chuyển chuột, click và scroll.
