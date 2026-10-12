#!/usr/bin/env bash
# Install flameshot-translate-helper: a venv with RapidOCR + a launcher in
# ~/.local/bin that Flameshot finds on PATH.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
venv="$HOME/.local/share/flameshot-translate/venv"
[ -x "$venv/bin/python" ] || python3 -m venv "$venv"
# Tsinghua mirror: direct from China it is far faster than pypi.org via proxy.
"$venv/bin/pip" install -q -i "${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
    rapidocr onnxruntime pillow
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/flameshot-translate-helper" <<SH
#!/bin/sh
exec "$venv/bin/python" -I "$here/flameshot-translate-helper.py" "\$@"
SH
chmod +x "$HOME/.local/bin/flameshot-translate-helper"
echo "installed: $HOME/.local/bin/flameshot-translate-helper"
