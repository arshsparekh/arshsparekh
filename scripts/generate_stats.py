"""Draw the profile's activity graphics from the GitHub GraphQL API.

Standard library only, so the nightly workflow needs no installs. Writes, for each theme:
    assets/stats-{theme}.svg   total, weekly sparkline, current and longest streak
    assets/year-{theme}.svg    the year at one character per day, in the portrait's ramp
    assets/langs-{theme}.svg   top languages across public repos, by bytes

    GITHUB_TOKEN=... GH_LOGIN=arshsparekh python3 scripts/generate_stats.py
    python3 scripts/generate_stats.py --fixture data.json   # offline, same output path
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from theme import THEMES  # noqa: E402

RAMP = " .`:-=+*cs#%@"
W = 830  # GitHub's README column
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      nodes { name languages(first: 20) { edges { size node { name } } } }
    }
  }
}
"""


def window(today: date) -> tuple[date, date]:
    """The last 365 whole UTC days, ending today. Pinned so two runs on one day agree."""
    return today - timedelta(days=364), today


def fetch(login: str, token: str, start: date, end: date) -> dict:
    body = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "login": login,
                "from": f"{start.isoformat()}T00:00:00Z",
                "to": f"{end.isoformat()}T23:59:59Z",
            },
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "User-Agent": login},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if out.get("errors"):
        raise SystemExit(f"GraphQL errors: {out['errors']}")
    return out["data"]["user"]


def daily(user: dict, start: date, end: date) -> list[tuple[date, int]]:
    counts = {
        d["date"]: d["contributionCount"]
        for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]
        for d in w["contributionDays"]
    }
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return [(d, counts.get(d.isoformat(), 0)) for d in days]


def languages(user: dict) -> list[tuple[str, int, int]]:
    """(language, bytes, repos using it), largest first; ties broken by name."""
    size: dict[str, int] = {}
    repos: dict[str, int] = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            size[name] = size.get(name, 0) + e["size"]
            repos[name] = repos.get(name, 0) + 1
    return sorted(((n, size[n], repos[n]) for n in size), key=lambda t: (-t[1], t[0]))


def streaks(days: list[tuple[date, int]]) -> tuple[tuple[int, date, date], tuple[int, date, date]]:
    """Current and longest runs of days with a contribution. Today counts only once it has one."""
    runs: list[tuple[int, date, date]] = []
    run_start = None
    for i, (d, n) in enumerate(days):
        if n and run_start is None:
            run_start = i
        if run_start is not None and (not n or i == len(days) - 1):
            last = i if n else i - 1
            runs.append((last - run_start + 1, days[run_start][0], days[last][0]))
            run_start = None
    longest = max(runs, key=lambda r: (r[0], r[2]), default=(0, days[-1][0], days[-1][0]))
    end = days[-1][0]
    current = next(
        (r for r in runs if r[2] == end or (r[2] == end - timedelta(days=1) and not days[-1][1])),
        (0, end, end),
    )
    return current, longest


# ---- drawing ---------------------------------------------------------------


def fonts() -> str:
    faces = []
    for fam, file in (("M", "mono-latin.woff2"), ("B", "mono-medium-latin.woff2")):
        data = base64.b64encode((ROOT / "fonts" / "subsets" / file).read_bytes()).decode()
        faces.append(f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{data})format('woff2')}}")
    return "".join(faces)


FONTS = ""


def head(h: int, label: str, c: dict, extra: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" '
        f'role="img" aria-label="{label}"><style>{FONTS}'
        f"text{{font-family:M,monospace;fill:{c['body']};font-size:12px}}"
        f".b{{font-family:B,M,monospace;fill:{c['text']}}}.m{{fill:{c['muted']}}}"
        f".a{{fill:{c['accent']}}}{extra}</style>"
    )


def fmt_range(a: date, b: date) -> str:
    if a == b:
        return f"{MONTHS[a.month - 1]} {a.day}"
    left = f"{MONTHS[a.month - 1]} {a.day}" + (f", {a.year}" if a.year != b.year else "")
    right = f"{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{MONTHS[b.month - 1]} {b.day}"
    return f"{left} – {right}, {b.year}"


def stats_svg(days: list[tuple[date, int]], c: dict) -> str:
    total = sum(n for _, n in days)
    # 52 whole weeks counted back from the last day; the leftover first day is left out
    weeks = [sum(n for _, n in days[len(days) - 7 * (k + 1) : len(days) - 7 * k]) for k in range(52)][::-1]
    (cur, cs, ce), (lng, ls, le) = streaks(days)

    h = 150
    out = [head(h, f"{total:,} contributions in the last year", c)]
    out.append(f'<text class="b" x="0" y="46" style="font-size:44px">{total:,}</text>')
    out.append(f'<text class="m" x="2" y="70">contributions, {fmt_range(days[0][0], days[-1][0])}</text>')

    # weekly area: continuity is defensible for weekly sums, not for sparse daily counts
    x0, x1, top, base = 330, W, 12, 78
    peak = max(weeks) or 1
    step = (x1 - x0) / (len(weeks) - 1)
    pts = [(x0 + i * step, base - (v / peak) * (base - top)) for i, v in enumerate(weeks)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(f'<polygon points="{x0},{base} {line} {x1},{base}" fill="{c["soft"]}"/>')
    out.append(f'<polyline points="{line}" fill="none" stroke="{c["accent"]}" stroke-width="1.5" stroke-linejoin="round"/>')
    out.append(f'<line x1="{x0}" y1="{base + 0.5}" x2="{x1}" y2="{base + 0.5}" stroke="{c["rule"]}"/>')
    out.append(f'<text class="m" x="{x0}" y="{base + 16}" style="font-size:11px">52 weeks</text>')
    out.append(f'<text class="m" x="{x1}" y="{base + 16}" style="font-size:11px" text-anchor="end">peak week {max(weeks):,}</text>')

    out.append(f'<line x1="0" y1="104.5" x2="{W}" y2="104.5" stroke="{c["rule"]}"/>')
    for x, label, n, a, b in ((0, "current streak", cur, cs, ce), (W / 2, "longest streak", lng, ls, le)):
        unit = "day" if n == 1 else "days"
        out.append(f'<text x="{x}" y="128"><tspan class="m">{label}</tspan>  <tspan class="b">{n} {unit}</tspan></text>')
        rng = fmt_range(a, b) if n else "none yet"
        out.append(f'<text class="m" x="{x}" y="146" style="font-size:11px">{rng}</text>')
    out.append("</svg>")
    return "".join(out)


def year_svg(days: list[tuple[date, int]], c: dict) -> str:
    """One character per day, weeks as columns (Sunday on top), density from the portrait's ramp."""
    nonzero = sorted(n for _, n in days if n)

    def char(n: int) -> str:
        if not n:
            return "."
        # rank among active days, so one huge day doesn't flatten the rest
        rank = sum(1 for v in nonzero if v <= n) / len(nonzero)
        return RAMP[3 + min(int(rank * (len(RAMP) - 3)), len(RAMP) - 4)]

    cw, lh, left, top = 14.4, 15, 40, 26
    first = days[0][0]
    offset = (first.weekday() + 1) % 7  # Sunday = 0
    ncols = (offset + len(days) + 6) // 7
    h = top + 7 * lh + 10
    out = [head(h, "Contributions per day over the last year", c, f".z{{fill:{c['rule']}}}.k{{fill:{c['accent']}}}")]
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text class="m" x="0" y="{top + r * lh + 11}" style="font-size:11px">{name}</text>')
    last_month = None
    for i, (d, n) in enumerate(days):
        col, row = divmod(offset + i, 7)
        x, y = left + col * cw, top + row * lh + 11
        if d.month != last_month and row <= 1 and col < ncols - 2:
            out.append(f'<text class="m" x="{x:.1f}" y="12" style="font-size:11px">{MONTHS[d.month - 1]}</text>')
            last_month = d.month
        ch = char(n)
        out.append(f'<text class="{"z" if not n else "k"}" x="{x:.1f}" y="{y}">{ch}</text>')
    out.append("</svg>")
    return "".join(out)


def langs_svg(langs: list[tuple[str, int, int]], c: dict) -> str:
    top = langs[:5]
    total = sum(s for _, s, _ in langs) or 1
    row, h = 26, 26 * max(len(top), 1) + 4
    out = [head(h, "Top languages in public repositories", c)]
    bar_x, bar_w = 150, 520
    for i, (name, size, repos) in enumerate(top):
        y = i * row + 17
        share = size / total
        out.append(f'<text class="b" x="0" y="{y}">{name}</text>')
        out.append(f'<rect x="{bar_x}" y="{y - 9}" width="{bar_w}" height="8" fill="{c["soft"]}"/>')
        out.append(f'<rect x="{bar_x}" y="{y - 9}" width="{max(bar_w * share, 1.5):.1f}" height="8" fill="{c["accent"]}"/>')
        n = "repo" if repos == 1 else "repos"
        out.append(f'<text x="{W}" y="{y}" text-anchor="end"><tspan class="b">{share * 100:.1f}%</tspan><tspan class="m">  {repos} {n}</tspan></text>')
    if not top:
        out.append('<text class="m" x="0" y="17">No public code yet.</text>')
    out.append("</svg>")
    return "".join(out)


def main() -> None:
    global FONTS
    FONTS = fonts()
    today = datetime.now(timezone.utc).date()
    if "--fixture" in sys.argv:
        user = json.loads(Path(sys.argv[sys.argv.index("--fixture") + 1]).read_text())
        end = max(
            date.fromisoformat(d["date"])
            for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]
        )
        start, end = window(end)
    else:
        start, end = window(today)
        user = fetch(os.environ["GH_LOGIN"], os.environ["GITHUB_TOKEN"], start, end)
    days = daily(user, start, end)
    langs = languages(user)
    for theme, c in THEMES.items():
        (ROOT / "assets" / f"stats-{theme}.svg").write_text(stats_svg(days, c) + "\n")
        (ROOT / "assets" / f"year-{theme}.svg").write_text(year_svg(days, c) + "\n")
        (ROOT / "assets" / f"langs-{theme}.svg").write_text(langs_svg(langs, c) + "\n")
    print(f"{start} to {end}: {sum(n for _, n in days)} contributions, {len(langs)} languages")


if __name__ == "__main__":
    main()
