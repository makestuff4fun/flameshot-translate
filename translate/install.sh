#!/usr/bin/env bash
# Install flameshot-translate-helper: a venv with RapidOCR, a COPY of the
# helper script, and a launcher in ~/.local/bin that Flameshot finds on PATH.
# The installed copy runs from ~/.local/share, never from the checkout, so
# editing or moving the repo cannot break the running tool. Re-run after
# changing the helper.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
share="$HOME/.local/share/flameshot-translate"
venv="$share/venv"
[ -x "$venv/bin/python" ] || python3 -m venv "$venv"
# Tsinghua mirror: direct from China it is far faster than pypi.org via proxy.
"$venv/bin/pip" install -q -i "${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
    rapidocr onnxruntime pillow
install -m 755 "$here/flameshot-translate-helper.py" "$share/flameshot-translate-helper.py"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/flameshot-translate-helper" <<SH
#!/bin/sh
exec "$venv/bin/python" -I "$share/flameshot-translate-helper.py" "\$@"
SH
chmod +x "$HOME/.local/bin/flameshot-translate-helper"
conf="${XDG_CONFIG_HOME:-$HOME/.config}/flameshot-translate"
if [ ! -e "$conf/.env" ]; then
    mkdir -p "$conf"
    install -m 600 "$here/env.example" "$conf/.env"
    echo "created $conf/.env: set FLAMESHOT_TRANSLATE_API_KEY in it"
fi
echo "installed: $HOME/.local/bin/flameshot-translate-helper"
