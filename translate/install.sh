#!/usr/bin/env bash
# Developer install of the helper from this checkout (the .deb does this for you).
# Runs flameshot-translate-setup (venv with RapidOCR + ~/.config .env), then puts
# a COPY of the helper in ~/.local/share and a launcher in ~/.local/bin, which
# comes before /usr/bin on PATH. The installed copy never runs from the checkout,
# so editing or moving the repo cannot break the running tool. Re-run after
# changing the helper.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
share="${XDG_DATA_HOME:-$HOME/.local/share}/flameshot-translate"
# Tsinghua mirror: from China it is far faster than pypi.org via the proxy.
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
    "$here/flameshot-translate-setup"
install -m 755 "$here/flameshot-translate-helper.py" "$share/flameshot-translate-helper.py"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/flameshot-translate-helper" <<SH
#!/bin/sh
exec "$share/venv/bin/python" -I "$share/flameshot-translate-helper.py" "\$@"
SH
chmod +x "$HOME/.local/bin/flameshot-translate-helper"
echo "installed: $HOME/.local/bin/flameshot-translate-helper"
