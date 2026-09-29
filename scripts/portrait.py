"""Turn src/photo.jpg into a self-typing ASCII portrait (portrait-light.svg, portrait-dark.svg).

Run locally; the nightly workflow never touches the portrait.
    .venv/bin/python scripts/portrait.py [--preview]
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from theme import THEMES, font_face  # noqa: E402

RAMP = " .`:-=+*cs#%@"  # light to dark; the space clears the background
COLS = 90
FONT_SIZE = 12.9
CHAR_W = FONT_SIZE * 0.6  # JetBrains Mono advance is exactly 600/1000
LINE_H = FONT_SIZE * 1.18
ROW_STAGGER = 0.09  # seconds between rows starting
ROW_DUR = 0.55  # seconds for one row to type
DISPLAY_W = 460

# crop box as fractions of the photo: top of hair to the collar
CROP = (0.24, 0.12, 0.76, 0.70)  # left, top, right, bottom
GAMMA = 1.5  # the guide uses 1.7; past ~1.6 the face merges with the hair
CLAHE_CLIP = 2.5
DARK_GAMMA = 1.0  # 1.5 left the face dim; 1/1.5 washed it out


def cutout(photo: Path) -> Image.Image:
    cache = ROOT / "src" / "cutout.png"
    if cache.exists() and cache.stat().st_mtime > photo.stat().st_mtime:
        return Image.open(cache)
    from rembg import remove

    img = remove(Image.open(photo).convert("RGB"))
    img.save(cache)
    return img


def to_ascii(photo: Path, theme: str = "light") -> list[str]:
    """Dense characters mark dark areas on a light page and bright areas on a dark one,
    so the dark-theme portrait is a positive, not a negative. The background stays blank."""
    rgba = np.array(cutout(photo).convert("RGBA"))
    h, w = rgba.shape[:2]
    l, t, r, b = CROP
    rgba = rgba[int(t * h) : int(b * h), int(l * w) : int(r * w)]
    alpha = rgba[:, :, 3].astype(np.float32) / 255
    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)

    gray = cv2.bilateralFilter(gray, 9, 40, 9)
    gray = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(8, 8)).apply(gray)
    # on a dark page the dense end marks highlights; the light-page curve would dim the face there
    v = (gray.astype(np.float32) / 255) ** (GAMMA if theme == "light" else DARK_GAMMA)
    ch, cw = v.shape
    rows = round(COLS * (ch / cw) * 0.48)
    small = cv2.resize(v, (COLS, rows), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(alpha, (COLS, rows), interpolation=cv2.INTER_AREA)
    ink = (1 - small) if theme == "light" else small
    ink = ink * mask  # background forced to blank
    idx = np.clip(np.rint(ink * (len(RAMP) - 1)), 0, len(RAMP) - 1).astype(int)
    lines = ["".join(RAMP[i] for i in row).rstrip() for row in idx]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(lines: list[str], theme: str) -> str:
    c = THEMES[theme]
    width = COLS * CHAR_W
    height = len(lines) * LINE_H + 8
    font = base64.b64encode(font_face("ramp", RAMP)).decode()
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
        f'width="{width:.1f}" height="{height:.1f}" role="img" aria-label="ASCII portrait of Arsh Parekh">',
        "<style>@font-face{font-family:R;src:url(data:font/woff2;base64,"
        + font
        + ")format('woff2')}"
        f"text{{font-family:R,monospace;font-size:{FONT_SIZE}px;fill:{c['portrait']};white-space:pre}}"
        f".k{{fill:{c['accent']}}}</style>",
        "<defs>",
    ]
    for i, line in enumerate(lines):
        if not line:
            continue
        lw = len(line) * CHAR_W
        begin = i * ROW_STAGGER
        out.append(
            f'<clipPath id="c{i}"><rect x="0" y="{i * LINE_H:.2f}" width="0" height="{LINE_H + 1:.2f}">'
            f'<animate attributeName="width" from="0" to="{lw:.1f}" begin="{begin:.2f}s" '
            f'dur="{ROW_DUR}s" fill="freeze"/></rect></clipPath>'
        )
    out.append("</defs>")
    for i, line in enumerate(lines):
        if not line:
            continue
        lw = len(line) * CHAR_W
        begin = i * ROW_STAGGER
        y = (i + 0.82) * LINE_H
        out.append(
            f'<text x="0" y="{y:.2f}" clip-path="url(#c{i})" xml:space="preserve">{esc(line)}</text>'
        )
        # a block cursor rides the wipe edge, then disappears
        out.append(
            f'<rect class="k" x="0" y="{i * LINE_H + 1:.2f}" width="{CHAR_W:.2f}" '
            f'height="{LINE_H - 2:.2f}" fill="{c["accent"]}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
            f'<animate attributeName="x" from="0" to="{lw:.1f}" begin="{begin:.2f}s" '
            f'dur="{ROW_DUR}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0" begin="{begin + ROW_DUR:.2f}s"/></rect>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def preview(lines: list[str]) -> None:
    from PIL import ImageDraw, ImageFont

    f = ImageFont.truetype(str(ROOT / "fonts" / "JetBrainsMono-Regular.ttf"), 26)
    img = Image.new("RGB", (int(COLS * 15.6) + 20, int(len(lines) * 30.7) + 20), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((10, 10 + i * 30.7), line, font=f, fill=THEMES["light"]["portrait"])
    img.save(ROOT / "src" / "preview.png")


def main() -> None:
    for theme in THEMES:
        lines = to_ascii(ROOT / "src" / "photo.jpg", theme)
        (ROOT / "assets" / f"portrait-{theme}.svg").write_text(svg(lines, theme))
    if "--preview" in sys.argv:
        preview(to_ascii(ROOT / "src" / "photo.jpg"))
    print(f"{len(lines)} rows x {COLS} cols")


if __name__ == "__main__":
    main()
