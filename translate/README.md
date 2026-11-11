# Translate tool (fork addition)

Adds a **Translate** button (文A icon, `Ctrl+T`) to the Flameshot editor. It reads the
Simplified Chinese in the selection (buttons, menus, tabs, short labels) and paints the
English over each label in that label's own background and text colours. Each label is a
normal annotation: you can select it, drag it, delete it, resize its text with the size
wheel, and undo the whole batch in one step. Copy and Save include it like any other edit.

## How it works

1. `CaptureWidget::translate()` writes the **unannotated** selection to a temp PNG and
   runs `flameshot-translate-helper` on it in the background, so the editor stays usable.
2. The helper (`flameshot-translate-helper.py`):
   - **OCR runs locally** with RapidOCR (PaddleOCR models on onnxruntime). This took 0.9 s
     on miku and read 11/11 test labels correctly. Lines without CJK or with a score
     below 0.5 are dropped.
   - samples each label's background (a ring around the box) and text colour (the pixels
     that differ most from it);
   - **translates only the text strings, never the image**, in one batch through an
     OpenAI-compatible chat API: DeepSeek `deepseek-flash` (V4.1 Flash) at
     `reasoning_effort=low` by default. That takes ~1 s (Claude Haiku via `claude -p`
     took ~3.5 s). Results are cached in `~/.cache/flameshot-translate/translations.json`,
     so a label seen before costs nothing.
3. Each result becomes a `TranslationLabelTool` object (`src/tools/translate/`).

The engine is outside Flameshot on purpose: you can swap the OCR or the translator
without rebuilding. Set `FLAMESHOT_TRANSLATE_HELPER` to use another helper.

## Settings: `~/.config/flameshot-translate/.env`

`flameshot-translate-setup` creates it from [`env.example`](env.example) (mode 600) if it is missing;
it never overwrites an existing one. It lives outside the checkout, so the API key
cannot be committed. A variable already set in the environment wins over the file.

| Variable | Default |
|---|---|
| `FLAMESHOT_TRANSLATE_API_KEY` | *(required)* |
| `FLAMESHOT_TRANSLATE_API_BASE` | `https://api.deepseek.com/v1` (any OpenAI-compatible endpoint) |
| `FLAMESHOT_TRANSLATE_MODEL` | `deepseek-flash` (`deepseek-v4-pro` is the other option) |
| `FLAMESHOT_TRANSLATE_EFFORT` | `low` (`high`, `max`; empty = don't send `reasoning_effort`) |
| `FLAMESHOT_TRANSLATE_TIMEOUT` | `60` seconds |

The helper reads the file on every run, so a change takes effect on the next Translate
with no reinstall or daemon restart.

## Install

**From the release `.deb`** (what other people use):
`sudo apt install ./flameshot_*.deb`, then `flameshot-translate-setup` once per user. That
command creates the OCR venv in `~/.local/share/flameshot-translate/venv` and the `.env`, and
asks for the API key. `/usr/bin/flameshot-translate-helper` runs
`/usr/share/flameshot-translate/flameshot-translate-helper.py` in that venv.

**Building a release:** `translate/make-deb.sh [rev]` writes
`dist/flameshot_<upstream>+translate<rev>_amd64.deb`. It links against the host's Qt 6, so
build on the oldest Ubuntu you want to support (24.04 for the first release). Upload it with
`gh release create v<upstream>-translate<rev> dist/*.deb`.

**Developer install from this checkout (miku):**

```bash
translate/install.sh                          # setup + helper copy in ~/.local/share, launcher in ~/.local/bin
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=$HOME/.local/opt/flameshot-translate
cmake --build build -j && cmake --install build
ln -sfn ~/.local/opt/flameshot-translate/bin/flameshot ~/.local/bin/flameshot
pkill -x flameshot; setsid -f flameshot       # restart the tray daemon
```

**Nothing runs from this checkout.** The binary runs from `~/.local/opt/flameshot-translate`,
the helper from `~/.local/share/flameshot-translate`. Re-run the install steps to
ship a change; editing the repo alone changes nothing that is live.

`~/.local/bin` comes before `/usr/bin` on PATH, so the autostart entry and the
`Super+Shift+S` shortcut (both run plain `flameshot`) pick up this build. **To go back to
the apt version:** `rm ~/.local/bin/flameshot` and restart the daemon.

## Testing without touching the desktop

Run it in a throwaway X server with its own D-Bus, and drive it with xdotool:
`Xvfb :77` → `DISPLAY=:77 dbus-run-session -- …` → `flameshot gui -r > out.png`, drag a
selection, `ctrl+t`, wait, `Return`. Point `XDG_CACHE_HOME` at a temporary directory to
force a fresh translation.

## ⚠️ Set `useX11LegacyScreenshot=true` on X11 (miku)

Upstream v15 captures through the xdg-desktop-portal Screenshot API even on X11. On
GNOME that brings up a permission dialog and returns a full-screen capture, not the
area selector. The apt build (12.x) never did this. The fix is the "Legacy X11 method"
setting, which goes in `~/.config/flameshot/flameshot.ini` under `[General]`:

    useX11LegacyScreenshot=true

It was set on miku on 2026-10-12. Restart the daemon after you change it.
