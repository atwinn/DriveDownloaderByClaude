#!/bin/bash
# Build "Drive Downloader.app" + .dmg installer for macOS.
# Run from the project root after: ./.venv/bin/pip install -r requirements.txt pyinstaller pillow
set -e
cd "$(dirname "$0")"
PY=./.venv/bin/python
PYI=./.venv/bin/pyinstaller

echo "==> 1/3  Rendering icon"
$PY make_icon.py
rm -rf AppIcon.iconset && mkdir AppIcon.iconset
for sz in 16 32 128 256 512 1024; do
  sips -z $sz $sz icon_1024.png --out "AppIcon.iconset/icon_${sz}x${sz}.png" >/dev/null
done
sips -z 32  32  icon_1024.png --out AppIcon.iconset/icon_16x16@2x.png   >/dev/null
sips -z 64  64  icon_1024.png --out AppIcon.iconset/icon_32x32@2x.png   >/dev/null
sips -z 256 256 icon_1024.png --out AppIcon.iconset/icon_128x128@2x.png >/dev/null
sips -z 512 512 icon_1024.png --out AppIcon.iconset/icon_256x256@2x.png >/dev/null
cp icon_1024.png AppIcon.iconset/icon_512x512@2x.png
iconutil -c icns AppIcon.iconset -o AppIcon.icns

echo "==> 2/3  Building .app (PyInstaller)"
RCLONE_BIN="$(readlink -f "$(command -v rclone)")"
rm -rf build dist
$PYI --noconfirm --windowed --name "Drive Downloader" \
  --icon AppIcon.icns \
  --osx-bundle-identifier com.chus.drivedownloader \
  --add-data "ui:ui" \
  --add-binary "${RCLONE_BIN}:." \
  --collect-all webview \
  --collect-all certifi --hidden-import certifi \
  app.py

echo "==> 3/3  Packaging .dmg"
STAGE=/tmp/dd_dmg
rm -rf "$STAGE" "dist/Drive Downloader.dmg"
mkdir -p "$STAGE"
cp -R "dist/Drive Downloader.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Drive Downloader" -srcfolder "$STAGE" -ov -format UDZO \
  "dist/Drive Downloader.dmg"

echo "✅ Done:"
echo "   dist/Drive Downloader.app   (chạy trực tiếp)"
echo "   dist/Drive Downloader.dmg   (cài đặt: kéo vào Applications)"
