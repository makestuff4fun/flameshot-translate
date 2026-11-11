#!/usr/bin/env bash
# Build flameshot_<version>+translate<N>_<arch>.deb from this checkout.
#   translate/make-deb.sh [N]     (N = package revision, default 1)
# Output goes to dist/. Built against the host's Qt 6, so build on the oldest
# Ubuntu you want to support (this was first built on 24.04 noble).
#
# The package replaces the distro's `flameshot` and adds:
#   /usr/bin/flameshot-translate-helper   wrapper: per-user venv python + the script below
#   /usr/bin/flameshot-translate-setup    per-user: venv with RapidOCR, ~/.config .env, API key
#   /usr/share/flameshot-translate/       helper script, env.example
# OCR libraries are not packaged (onnxruntime is ~50 MB of wheels that pip handles
# better than dpkg), so each user runs flameshot-translate-setup once.
set -euo pipefail
rev="${1:-1}"
root="$(cd "$(dirname "$0")/.." && pwd)"
build="$root/build-deb"
dist="$root/dist"
arch="$(dpkg --print-architecture)"

cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
      -DFETCHCONTENT_FULLY_DISCONNECTED=OFF >/dev/null
cmake --build "$build" -j"$(nproc)"
upstream="$(sed -n 's/^CMAKE_PROJECT_VERSION:STATIC=//p' "$build/CMakeCache.txt")"
version="${upstream}+translate${rev}"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
DESTDIR="$stage" cmake --install "$build" >/dev/null
rm -rf "$stage/usr/include" "$stage/usr/lib"   # as upstream's debian/rules does
strip --strip-unneeded "$stage/usr/bin/flameshot"

share="$stage/usr/share/flameshot-translate"
install -Dm 644 "$root/translate/flameshot-translate-helper.py" "$share/flameshot-translate-helper.py"
install -Dm 644 "$root/translate/env.example" "$share/env.example"
install -Dm 644 "$root/translate/README.md" "$stage/usr/share/doc/flameshot/README.translate.md"
install -Dm 755 "$root/translate/flameshot-translate-setup" "$stage/usr/bin/flameshot-translate-setup"
cat > "$stage/usr/bin/flameshot-translate-helper" <<'SH'
#!/bin/sh
venv="${XDG_DATA_HOME:-$HOME/.local/share}/flameshot-translate/venv"
if [ ! -x "$venv/bin/python" ]; then
    echo '{"error": "Translate is not set up: run flameshot-translate-setup in a terminal"}'
    exit 1
fi
exec "$venv/bin/python" -I /usr/share/flameshot-translate/flameshot-translate-helper.py "$@"
SH
chmod 755 "$stage/usr/bin/flameshot-translate-helper"

mkdir -p "$stage/DEBIAN"
cat > "$stage/DEBIAN/control" <<EOF
Package: flameshot
Version: $version
Architecture: $arch
Maintainer: makestuff4fun <makestuff4fun@users.noreply.github.com>
Installed-Size: $(du -sk --exclude=DEBIAN "$stage" | cut -f1)
Depends: libc6 (>= 2.35), libgcc-s1 (>= 11), libstdc++6 (>= 11), hicolor-icon-theme,
 qt6-qpa-plugins (>= 6.2.4~), libqt6core6 (>= 6.2.4~) | libqt6core6t64 (>= 6.2.4~),
 libqt6dbus6 (>= 6.2.4~) | libqt6dbus6t64 (>= 6.2.4~),
 libqt6gui6 (>= 6.2.4~) | libqt6gui6t64 (>= 6.2.4~),
 libqt6network6 (>= 6.2.4~) | libqt6network6t64 (>= 6.2.4~),
 libqt6widgets6 (>= 6.2.4~) | libqt6widgets6t64 (>= 6.2.4~),
 libqt6svg6 (>= 6.2.4~), python3 (>= 3.9), python3-venv
Recommends: xdg-desktop-portal-gtk | xdg-desktop-portal-gnome | xdg-desktop-portal-kde | xdg-desktop-portal-wlr
Section: graphics
Priority: optional
Homepage: https://github.com/makestuff4fun/flameshot-translate
Description: Flameshot screenshot tool with a Chinese-to-English Translate button
 Flameshot $upstream with one addition: the Translate tool (Ctrl+T) reads the
 Simplified Chinese in a selection with local OCR (RapidOCR) and paints the
 English over each label in its own colours, as editable annotations. Only the
 recognised text is sent for translation (DeepSeek API by default; any
 OpenAI-compatible endpoint works). Run flameshot-translate-setup once per user.
EOF
mkdir -p "$dist"
out="$dist/flameshot_${version}_${arch}.deb"
dpkg-deb --root-owner-group -Zxz --build "$stage" "$out" >/dev/null
echo "$out"
