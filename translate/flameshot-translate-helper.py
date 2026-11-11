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
recognised strings, never the image, go to an OpenAI-compatible chat API for
translation (DeepSeek by default). Translations are cached, so a label seen
before costs nothing.

Settings come from ~/.config/flameshot-translate/.env (see env.example next to
this script). A variable already set in the environment wins over the file.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
MIN_SCORE = 0.5
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / \
    "flameshot-translate" / "translations.json"
ENV_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / \
    "flameshot-translate" / ".env"


def load_env(path):
    """Minimal .env reader: KEY=VALUE lines, # comments, optional quotes and
    `export`. Values never override variables already in the environment."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        os.environ.setdefault(key, val)


load_env(ENV_FILE)
API_BASE = os.environ.get("FLAMESHOT_TRANSLATE_API_BASE",
                          "https://api.deepseek.com/v1").rstrip("/")
API_KEY = os.environ.get("FLAMESHOT_TRANSLATE_API_KEY", "")
MODEL = os.environ.get("FLAMESHOT_TRANSLATE_MODEL", "deepseek-flash")
# Short UI strings need no reasoning: "low" took ~1 s vs the default "high".
# Set it empty to omit the parameter for APIs that reject it.
EFFORT = os.environ.get("FLAMESHOT_TRANSLATE_EFFORT", "low")
TIMEOUT = float(os.environ.get("FLAMESHOT_TRANSLATE_TIMEOUT", "60"))

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


def api_translate(strings):
    if not API_KEY:
        fail("FLAMESHOT_TRANSLATE_API_KEY is not set (put it in %s)" % ENV_FILE)
    body = {"model": MODEL, "stream": False, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(strings, ensure_ascii=False)}]}
    if EFFORT:
        body["reasoning_effort"] = EFFORT
    req = urllib.request.Request(
        API_BASE + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + API_KEY,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        fail("translation API HTTP %d: %s"
             % (e.code, e.read().decode(errors="replace")[:300]))
    except (urllib.error.URLError, TimeoutError) as e:
        fail("translation API unreachable: %s" % getattr(e, "reason", e))
    except ValueError:
        fail("translation API returned non-JSON")
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        fail("unexpected API response: " + json.dumps(data)[:300])
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
        for src, en in zip(todo, api_translate(todo)):
            cache[src] = en
        save_cache(cache)
    for it in items:
        it["text"] = cache[it["src"]]
    print(json.dumps({"items": items}, ensure_ascii=False))


if __name__ == "__main__":
    main()
