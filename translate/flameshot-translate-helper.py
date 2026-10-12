#!/usr/bin/env python3
"""OCR + translate helper for Flameshot's Translate tool.

Usage: flameshot-translate-helper IMAGE.png

Reads the Simplified Chinese text in IMAGE (UI labels: buttons, menus, tabs),
translates each line to English and prints JSON on stdout:

    {"items": [{"box": [x, y, w, h], "src": "立即购买", "text": "Buy Now",
                "bg": "#1677ff", "fg": "#ffffff"}, ...]}

Boxes are in IMAGE pixels. bg/fg are sampled from the image so Flameshot can
paint the English over the Chinese in the label's own colours. On failure it
prints {"error": "..."} and exits non-zero.

OCR runs locally (RapidOCR = PaddleOCR models on onnxruntime). Only the
recognised strings, never the image, go to Claude for translation, through
the `claude` CLI and its existing login. Translations are cached, so a label
seen before costs nothing.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
MIN_SCORE = 0.5
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / \
    "flameshot-translate" / "translations.json"
MODEL = os.environ.get("FLAMESHOT_TRANSLATE_MODEL", "haiku")

SYSTEM_PROMPT = """\
You translate Simplified Chinese UI strings (buttons, menus, tabs, labels and \
short messages on webpages and apps) into English, worded the way an English \
UI would label the same control. Keep each translation as short as the \
original allows. If a string has no Chinese in it, return it unchanged.
Input: a JSON array of strings. Output: ONLY a JSON array of the same length, \
with the translations in the same order. No commentary, no code fences."""


def fail(msg):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(1)


def hexcolor(rgb):
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb)


def label_colours(img, x0, y0, x1, y1):
    """Background = median of a thin ring around the box; foreground = the
    pixels inside the box that differ most from it (the glyph strokes)."""
    import numpy as np

    h, w = img.shape[:2]
    rx0, ry0 = max(x0 - 2, 0), max(y0 - 2, 0)
    rx1, ry1 = min(x1 + 2, w), min(y1 + 2, h)
    region = img[ry0:ry1, rx0:rx1].reshape(-1, 3)
    ring = np.concatenate([
        img[ry0:ry0 + 2, rx0:rx1].reshape(-1, 3),
        img[ry1 - 2:ry1, rx0:rx1].reshape(-1, 3),
        img[ry0:ry1, rx0:rx0 + 2].reshape(-1, 3),
        img[ry0:ry1, rx1 - 2:rx1].reshape(-1, 3),
    ])
    bg = np.median(ring if len(ring) else region, axis=0)
    inner = img[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    dist = np.linalg.norm(inner - bg, axis=1)
    if len(dist) and dist.max() > 60:
        far = inner[dist >= np.percentile(dist, 90)]
        fg = np.median(far, axis=0)
    else:
        lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        fg = (0, 0, 0) if lum > 140 else (255, 255, 255)
    return hexcolor(bg), hexcolor(fg)


def ocr(path):
    import numpy as np
    from PIL import Image
    from rapidocr import RapidOCR

    img = np.asarray(Image.open(path).convert("RGB"))
    result = RapidOCR()(img)
    items = []
    if result.boxes is None:
        return items
    for box, text, score in zip(result.boxes, result.txts, result.scores):
        if score < MIN_SCORE or not CJK.search(text):
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, y0 = int(min(xs)), int(min(ys))
        x1, y1 = int(round(max(xs))), int(round(max(ys)))
        bg, fg = label_colours(img, x0, y0, x1, y1)
        items.append({"box": [x0, y0, x1 - x0, y1 - y0], "src": text,
                      "bg": bg, "fg": fg})
    return items


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
        tmp.replace(CACHE)
    except OSError:
        pass


def claude_translate(strings):
    exe = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    if not Path(exe).exists():
        fail("claude CLI not found")
    cmd = [exe, "-p", "--model", MODEL, "--tools", "",
           "--no-session-persistence", "--disable-slash-commands",
           "--strict-mcp-config", "--system-prompt", SYSTEM_PROMPT]
    try:
        out = subprocess.run(cmd, input=json.dumps(strings, ensure_ascii=False),
                             capture_output=True, text=True, timeout=90,
                             cwd=str(Path.home()))
    except subprocess.TimeoutExpired:
        fail("translation timed out")
    if out.returncode != 0:
        fail("claude failed: " + (out.stdout + out.stderr).strip()[:300])
    text = out.stdout.strip()
    m = re.search(r"\[.*\]", text, re.S)
    try:
        result = json.loads(m.group(0) if m else text)
    except ValueError:
        fail("could not parse translation: " + text[:300])
    if not isinstance(result, list) or len(result) != len(strings):
        fail("translation returned %s items for %d strings"
             % (len(result) if isinstance(result, list) else "?", len(strings)))
    return [str(t) for t in result]


def main():
    if len(sys.argv) != 2:
        fail("usage: flameshot-translate-helper IMAGE.png")
    try:
        items = ocr(sys.argv[1])
    except Exception as e:  # noqa: BLE001 - report anything to the UI
        fail("OCR failed: %s" % e)

    cache = load_cache()
    todo = sorted({it["src"] for it in items if it["src"] not in cache})
    if todo:
        for src, en in zip(todo, claude_translate(todo)):
            cache[src] = en
        save_cache(cache)
    for it in items:
        it["text"] = cache[it["src"]]
    print(json.dumps({"items": items}, ensure_ascii=False))


if __name__ == "__main__":
    main()
