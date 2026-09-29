"""Section headings as SVG, the only way to set them in Spectral on GitHub.

    .venv/bin/python scripts/headings.py
"""

from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from theme import THEMES, font_face  # noqa: E402

HEADINGS = ["Projects", "Activity"]
W, H, SIZE = 830, 44, 26

def advance(text: str) -> float:
    """Width of `text` in px, read from Spectral's own metrics."""
    from fontTools.ttLib import TTFont

    f = TTFont(str(ROOT / "fonts" / "Spectral-Medium.woff2"))
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return sum(hmtx[cmap[ord(ch)]][0] for ch in text) * SIZE / upm


font = base64.b64encode(font_face("serif", "".join(HEADINGS))).decode()
for text in HEADINGS:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    for theme, c in THEMES.items():
        rule_x = advance(text) + 14
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-label="{text}"><style>@font-face{{font-family:S;src:url(data:font/woff2;base64,{font})'
            f"format('woff2')}}text{{font-family:S,Georgia,serif;font-weight:500;font-size:{SIZE}px;fill:{c['text']}}}</style>"
            f'<text x="0" y="30">{text}</text>'
            f'<line x1="{rule_x:.0f}" y1="22.5" x2="{W}" y2="22.5" stroke="{c["rule"]}"/></svg>\n'
        )
        (ROOT / "assets" / f"hd-{slug}-{theme}.svg").write_text(svg)
print(f"{len(HEADINGS)} headings, font subset {len(base64.b64decode(font)) / 1024:.1f} KB")
