#!/bin/bash
set -e

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
APP_PATH="$PROJECT_DIR/CarrotKeyboard.app"

if [ ! -d "$APP_PATH" ]; then
  "$PROJECT_DIR/build_mac_app.command"
fi

open "$APP_PATH"

if [ "${TERM_PROGRAM:-}" = "Apple_Terminal" ]; then
  (
    sleep 0.5
    osascript -e 'tell application "Terminal" to if (count of windows) > 0 then close front window'
  ) >/dev/null 2>&1 &
fi

exit 0
