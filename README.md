# CarrotKeyboard

Tool Python có GUI để dùng bàn phím và chuột Mac điều khiển nhập liệu trên Windows PC trong cùng mạng LAN.

Tool chỉ đi một chiều:

```text
Mac keyboard/mouse -> Windows PC
```

Mỗi hệ điều hành có file riêng để tránh xung đột thư viện/phím đặc thù:

- `mac.py`: chạy trên Mac, bắt phím/chuột và gửi qua mạng.
- `win.py`: chạy trên Windows, nhận phím/chuột và nhập vào hệ thống.

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
2. Nhập IP của Windows PC vào ô `Windows PC IP`.
3. Bấm `Start`.
4. Nếu macOS hỏi quyền, cấp quyền trong:
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
Bạn có thể đổi tổ hợp phím Start/Stop bằng nút `Record`: bấm `Record`, nhấn tổ hợp phím muốn dùng, rồi bấm `Save`.
Nếu bật `Auto Start`, lần sau mở app tool sẽ tự Start sau khi khởi động xong, miễn là đã có `Windows PC IP`.

## GUI trên Mac

- `Windows PC IP`: IP của máy Windows.
- `Port`: cổng TCP, mặc định `50505`.
- `Block keys on Mac while forwarding`: chặn phím ở Mac để bàn phím chỉ điều khiển Windows.
- `Forward mouse to Windows`: gửi di chuyển/click/scroll chuột sang Windows.
- `Block mouse on Mac`: chặn chuột ở Mac khi đang gửi sang Windows.
- `Auto Start`: tự bật sender khi app mở xong.
- `Start/Stop hotkey`: hiển thị tổ hợp phím bật/tắt sender, mặc định `⌘ + ⌥ + ⌃ + Q`.
- `● Record`: học tổ hợp phím mới bằng cách nhấn trực tiếp trên bàn phím.
- `↺ Reset`: đưa hotkey về mặc định.
- `▶ Start` / `■ Stop`: bật hoặc tắt sender.
- `Log`: xem trạng thái kết nối và lỗi nếu có.

## GUI trên Windows

- `This PC IP`: IP để nhập vào GUI trên Mac.
- `Port`: cổng TCP, mặc định `50505`.
- `▶ Start` / `■ Stop`: bật hoặc tắt receiver.
- `⌫ Clear Log`: xóa log trên màn hình.
- `Log`: xem trạng thái kết nối và lỗi nếu có.

## Chạy bằng dòng lệnh

Mac sender:

```bash
python mac.py --send --host WINDOWS_IP
```

Đổi hotkey khi chạy CLI:

```bash
python mac.py --send --host WINDOWS_IP --hotkey cmd+option+control+q
```

Windows receiver:

```bat
python win.py --receive
```

## Dừng tool

Trên Mac nhấn:

```text
Command + Option + Control + Q
```

Hoặc dùng tổ hợp phím bạn đã thiết lập trong `Start/Stop hotkey`, hoặc bấm `Stop` trong GUI.

## Ghi chú

- Tool dùng cổng TCP `50505`.
- Cấu hình Mac được lưu tại `~/Library/Application Support/CarrotKeyboard/config.json`.
- Hai máy cần ở cùng mạng LAN và Windows Firewall cần cho phép kết nối vào.
- Tool phát lại phím và chuột bằng thư viện `pynput`, phù hợp cho nhập liệu thường, hotkey, phím điều hướng, di chuyển chuột, click và scroll.
