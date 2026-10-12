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
   - **translates only the text strings, never the image**, in one batch through the
     `claude` CLI (`claude -p --model haiku`) using the existing login. That took
     ~3.5 s, and results are cached in `~/.cache/flameshot-translate/translations.json`,
     so a label seen before costs nothing.
3. Each result becomes a `TranslationLabelTool` object (`src/tools/translate/`).

The engine is outside Flameshot on purpose: you can swap the OCR or the translator
without rebuilding. Set `FLAMESHOT_TRANSLATE_HELPER` to use another helper, or
`FLAMESHOT_TRANSLATE_MODEL` to use another Claude model.

## Install (miku)

```bash
translate/install.sh                          # venv + ~/.local/bin/flameshot-translate-helper
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=$HOME/.local/opt/flameshot-translate
cmake --build build -j && cmake --install build
ln -sfn ~/.local/opt/flameshot-translate/bin/flameshot ~/.local/bin/flameshot
pkill -x flameshot; setsid -f flameshot       # restart the tray daemon
```

`~/.local/bin` comes before `/usr/bin` on PATH, so the autostart entry and the
`Super+Shift+S` shortcut (both run plain `flameshot`) pick up this build. **To go back to
the apt version:** `rm ~/.local/bin/flameshot` and restart the daemon.

## Testing without touching the desktop

Run it in a throwaway X server with its own D-Bus, and drive it with xdotool:
`Xvfb :77` → `DISPLAY=:77 dbus-run-session -- …` → `flameshot gui -r > out.png`, drag a
selection, `ctrl+t`, wait, `Return`. Point `XDG_CACHE_HOME` at a temporary directory to
force a fresh translation.
