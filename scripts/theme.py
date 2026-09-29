"""Colors and embedded fonts shared by every generated SVG.

Teal and gray only. Each graphic ships a light and a dark file; the README picks one
with <picture> so it follows the viewer's GitHub theme.
"""

from __future__ import annotations

import io
from functools import cache
from pathlib import Path

FONTS = Path(__file__).resolve().parent.parent / "fonts"

THEMES = {
    "light": {
        "portrait": "#171C1F",
        "text": "#171C1F",
        "body": "#4A555A",
        "muted": "#79837F",
        "rule": "#DDDED7",
        "accent": "#0E6E63",
        "fill": "#5FD3C2",
        "soft": "#E3EDEA",
    },
    "dark": {
        "portrait": "#DCE3E0",
        "text": "#F4F4F1",
        "body": "#B7C0BC",
        "muted": "#8A9591",
        "rule": "#2A3236",
        "accent": "#5FD3C2",
        "fill": "#0E6E63",
        "soft": "#123A35",
    },
}

FILES = {
    "ramp": "JetBrainsMono-Regular.ttf",
    "mono": "JetBrainsMono-Regular.ttf",
    "mono-medium": "JetBrainsMono-Medium.ttf",
    "serif": "Spectral-Medium.woff2",
}


@cache
def font_face(role: str, text: str) -> bytes:
    """woff2 subset of a role's font holding only the characters in `text`.

    Needs fontTools and brotli, so it runs locally; CI reads the subsets committed
    under fonts/subsets/ instead (written by build_fonts.py).
    """
    from fontTools import subset

    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.hinting = False
    opts.name_IDs = []
    opts.notdef_outline = False
    font = subset.load_font(str(FONTS / FILES[role]), opts)
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(set(text))))
    sub.subset(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, opts)
    return buf.getvalue()
