#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="CarrotKeyboard"
APP_DIR="$PWD/${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
ICONSET_DIR="$PWD/build/${APP_NAME}.iconset"

if [ ! -f "icon.png" ]; then
  echo "Missing icon.png"
  exit 1
fi

if [ ! -f "mac.py" ]; then
  echo "Missing mac.py"
  exit 1
fi

rm -rf "$APP_DIR" "$ICONSET_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$ICONSET_DIR"

cp "mac.py" "$RESOURCES_DIR/mac.py"
cp "requirements.txt" "$RESOURCES_DIR/requirements.txt"
cp "icon.png" "$RESOURCES_DIR/icon.png"

sips -z 16 16     icon.png --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
sips -z 32 32     icon.png --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
sips -z 32 32     icon.png --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
sips -z 64 64     icon.png --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
sips -z 128 128   icon.png --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
sips -z 256 256   icon.png --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
sips -z 256 256   icon.png --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
sips -z 512 512   icon.png --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
sips -z 512 512   icon.png --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
sips -z 1024 1024 icon.png --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET_DIR" -o "$RESOURCES_DIR/CarrotKeyboard.icns"

cat > "$CONTENTS_DIR/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>CarrotKeyboard</string>
  <key>CFBundleExecutable</key>
  <string>CarrotKeyboard</string>
  <key>CFBundleIconFile</key>
  <string>CarrotKeyboard</string>
  <key>CFBundleIdentifier</key>
  <string>com.carrot.keyboard.mac</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>CarrotKeyboard</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.13</string>
  <key>LSUIElement</key>
  <false/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

cat > "$MACOS_DIR/CarrotKeyboard" <<'LAUNCHER'
#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$APP_DIR/Resources"
VENV_DIR="$HOME/.carrot_keyboard_venv"
LOG_FILE="$HOME/Library/Logs/CarrotKeyboard.log"

mkdir -p "$(dirname "$LOG_FILE")"
exec >>"$LOG_FILE" 2>&1

echo ""
echo "==== CarrotKeyboard started at $(date) ===="

show_error() {
  /usr/bin/osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\" with icon stop" >/dev/null 2>&1 || true
}

if ! command -v python3 >/dev/null 2>&1; then
  show_error "Python 3 is required to run CarrotKeyboard."
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --no-compile -r "$RESOURCES_DIR/requirements.txt"
exec "$VENV_DIR/bin/python" "$RESOURCES_DIR/mac.py"
LAUNCHER

chmod +x "$MACOS_DIR/CarrotKeyboard"
chmod +x "$APP_DIR"
plutil -lint "$CONTENTS_DIR/Info.plist"

echo "Built: $APP_DIR"
