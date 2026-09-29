"""Write the font subsets the nightly workflow embeds (fonts/subsets/). Run locally after
changing which characters the graphics use; needs fontTools and brotli.

    .venv/bin/python scripts/build_fonts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from theme import font_face  # noqa: E402

LATIN = "".join(chr(i) for i in range(0x20, 0x7F)) + "–·"

out = ROOT / "fonts" / "subsets"
out.mkdir(exist_ok=True)
for role, name in (("mono", "mono-latin"), ("mono-medium", "mono-medium-latin")):
    data = font_face(role, LATIN)
    (out / f"{name}.woff2").write_bytes(data)
    print(f"{name}.woff2  {len(data) / 1024:.1f} KB")
