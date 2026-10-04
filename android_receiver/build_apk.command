#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

SDK_DIR="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
PLATFORM="$SDK_DIR/platforms/android-36/android.jar"
BUILD_TOOLS="$SDK_DIR/build-tools/35.0.0"
AAPT2="$BUILD_TOOLS/aapt2"
D8="$BUILD_TOOLS/d8"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"

APP_ID="com.carrot.keyboardreceiver"
OUT_DIR="$PWD/build"
GEN_DIR="$OUT_DIR/gen"
OBJ_DIR="$OUT_DIR/obj"
DEX_DIR="$OUT_DIR/dex"
RES_ZIP="$OUT_DIR/res.zip"
UNSIGNED_APK="$OUT_DIR/CarrotKeyboardReceiver-unsigned.apk"
ALIGNED_APK="$OUT_DIR/CarrotKeyboardReceiver-aligned.apk"
SIGNED_APK="$OUT_DIR/CarrotKeyboardReceiver-debug.apk"
KEYSTORE="$OUT_DIR/debug.keystore"

rm -rf "$OUT_DIR"
mkdir -p "$GEN_DIR" "$OBJ_DIR" "$DEX_DIR"

"$AAPT2" compile --dir res -o "$RES_ZIP"
"$AAPT2" link \
  -I "$PLATFORM" \
  --manifest AndroidManifest.xml \
  --java "$GEN_DIR" \
  --min-sdk-version 24 \
  --target-sdk-version 35 \
  --no-compile-sdk-metadata \
  -o "$UNSIGNED_APK" \
  "$RES_ZIP"

javac -source 8 -target 8 \
  -classpath "$PLATFORM" \
  -d "$OBJ_DIR" \
  $(find "$GEN_DIR" src -name '*.java')

"$D8" --lib "$PLATFORM" --output "$DEX_DIR" $(find "$OBJ_DIR" -name '*.class')
cp "$UNSIGNED_APK" "$OUT_DIR/base.apk"
cd "$DEX_DIR"
zip -q -r "$OUT_DIR/base.apk" classes.dex
cd "$OLDPWD"

"$ZIPALIGN" -f 4 "$OUT_DIR/base.apk" "$ALIGNED_APK"

if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair \
    -keystore "$KEYSTORE" \
    -storepass android \
    -keypass android \
    -alias androiddebugkey \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US" >/dev/null
fi

"$APKSIGNER" sign \
  --v1-signing-enabled true \
  --v2-signing-enabled true \
  --v3-signing-enabled true \
  --ks "$KEYSTORE" \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$SIGNED_APK" \
  "$ALIGNED_APK"

"$APKSIGNER" verify "$SIGNED_APK"
echo "Built: $SIGNED_APK"
