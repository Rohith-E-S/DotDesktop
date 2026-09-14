#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="DotDesktop"
APP_DIR="$SCRIPT_DIR/AppDir"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="$SCRIPT_DIR/dist"

echo "==> Cleaning old build artifacts..."
rm -rf "$APP_DIR" "$BUILD_DIR" "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "==> Compiling application with Nuitka..."
python3 -m nuitka \
    --standalone \
    --enable-plugin=pyside6 \
    --include-data-file=logo.png=logo.png \
    --output-dir="$BUILD_DIR" \
    desktop_editor.py

echo "==> Setting up AppDir..."
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

cp -r "$BUILD_DIR/desktop_editor.dist"/* "$APP_DIR/usr/bin/"
if [ -f "$APP_DIR/usr/bin/desktop_editor.bin" ] && [ ! -f "$APP_DIR/usr/bin/desktop_editor" ]; then
    ln -s desktop_editor.bin "$APP_DIR/usr/bin/desktop_editor"
fi
cp "$SCRIPT_DIR/AppRun" "$APP_DIR/AppRun"
chmod +x "$APP_DIR/AppRun"

cp "$SCRIPT_DIR/dotdesktop.desktop" "$APP_DIR/dotdesktop.desktop"
cp "$SCRIPT_DIR/dotdesktop.desktop" "$APP_DIR/usr/share/applications/dotdesktop.desktop"

cp "$SCRIPT_DIR/logo.png" "$APP_DIR/dotdesktop.png"
cp "$SCRIPT_DIR/logo.png" "$APP_DIR/.DirIcon"
cp "$SCRIPT_DIR/logo.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/dotdesktop.png"

echo "==> Ensuring appimagetool is available..."
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL=(appimagetool)
else
    if [ ! -f "$SCRIPT_DIR/appimagetool" ]; then
        curl -fsSL -o "$SCRIPT_DIR/appimagetool" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        chmod +x "$SCRIPT_DIR/appimagetool"
    fi
    APPIMAGETOOL=("$SCRIPT_DIR/appimagetool" "--appimage-extract-and-run")
fi

echo "==> Packaging AppImage..."
ARCH=x86_64 "${APPIMAGETOOL[@]}" "$APP_DIR" "$OUTPUT_DIR/${APP_NAME}-x86_64.AppImage"

echo "==> Done: $OUTPUT_DIR/${APP_NAME}-x86_64.AppImage"
