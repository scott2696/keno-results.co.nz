#!/usr/bin/env python3
"""Draw the article header illustrations, locally and deterministically.

    python3 tools/make_art.py               # draw anything missing
    python3 tools/make_art.py --force SLUG  # redraw one
    python3 tools/make_art.py --all         # redraw everything

Why this is not a call to an image model
----------------------------------------
It was, and the model is no longer reachable: every Gemini image endpoint on
this key returns 429, with the free tier's per-day image quota reported as
absent rather than merely spent. Generating these needs billing enabled.

But look at what the prompt was asking that model for: flat vector shapes, a
strict six-colour palette, no people, no text, no photorealism, generous
negative space, 16:9. That is not a description that needs a diffusion model -
it is a specification, and a specification is better executed than sampled.
Drawing it directly gives exact palette control instead of approximate, 3 KB
of SVG instead of 200 KB of PNG, crisp at any size, and the same image every
time from the same slug. It also costs nothing and cannot run out.

Each article gets a composition chosen from its subject and a layout seeded
from its slug, so two articles never collide and any article always redraws
identically.

Stdlib only.
"""
import argparse
import hashlib
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "data")
OUT = os.path.join(ROOT, "assets", "img", "articles")

W, H = 1200, 675                      # 16:9, also a serviceable og:image

# The site's own decade tones, on a deep slate ground. Dark artwork was the
# deliberate choice: the page has two themes and an <img> cannot follow a
# data-theme toggle, so a single dark plate sits correctly on both - the way a
# photograph does - where a light one would glare on the dark theme.
GROUND = "#0D1117"
GROUND_2 = "#141B24"
BANDS = ["#126447", "#0E5D6F", "#15568A", "#284791",
         "#453B92", "#662F88", "#852764", "#8D3E27"]
ACCENT = "#34D399"
PAPER = "#E8ECF2"


def seeded(slug):
    return random.Random(int(hashlib.sha256(slug.encode()).hexdigest()[:12], 16))


# --------------------------------------------------------------- compositions

def scatter(r, cols):
    """Irregularly spaced discs - randomness made visible. (Keno)"""
    out, placed = [], []
    for _ in range(320):
        if len(placed) >= 26:
            break
        x, y = r.uniform(60, W - 60), r.uniform(60, H - 60)
        rad = r.choice([9, 12, 14, 18, 22, 27, 34])
        if any((x - px) ** 2 + (y - py) ** 2 < (rad + pr + 26) ** 2
               for px, py, pr in placed):
            continue
        placed.append((x, y, rad))
        c = r.choice(cols)
        op = round(r.uniform(.30, .95), 2)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad}" fill="{c}" '
                   f'opacity="{op}"/>')
        if rad > 20 and r.random() < .5:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad + 9}" '
                       f'fill="none" stroke="{c}" stroke-width="1" opacity=".35"/>')
    return out


def converge(r, cols):
    """Discs drawing toward one bright point. (Lotto, Powerball)

    First pass put every disc between 10% and 22% opacity on a near-black
    ground, which is invisible, and clustered them all around the focus, which
    left half the frame empty. Discs now start wide and opaque and tighten in.
    """
    fx, fy = W * r.uniform(.58, .68), H * r.uniform(.44, .56)
    out = []
    for i in range(20):
        t = i / 19
        spread = (1 - t) ** 1.25
        x = fx + r.uniform(-1, 1) * 760 * spread
        y = fy + r.uniform(-1, 1) * 430 * spread
        rad = 120 * (1 - t) + 14
        c = cols[i % len(cols)]
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.0f}" fill="{c}" '
                   f'opacity="{.20 + .34 * t:.2f}"/>')
        if r.random() < .4:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad + 12:.0f}" '
                       f'fill="none" stroke="{c}" stroke-width="1" '
                       f'opacity="{.16 + .22 * t:.2f}"/>')
    # a few small solid marks so the eye has something crisp to land on
    for _ in range(9):
        a = r.uniform(0, 6.283)
        d = r.uniform(120, 480)
        out.append(f'<circle cx="{fx + d * __import__("math").cos(a):.0f}" '
                   f'cy="{fy + d * .58 * __import__("math").sin(a):.0f}" '
                   f'r="{r.choice([3, 4, 5])}" fill="{PAPER}" '
                   f'opacity="{r.uniform(.20, .48):.2f}"/>')
    out.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="30" fill="{ACCENT}" opacity=".95"/>')
    out.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="52" fill="none" '
               f'stroke="{ACCENT}" stroke-width="1.6" opacity=".55"/>')
    out.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="84" fill="none" '
               f'stroke="{ACCENT}" stroke-width="1" opacity=".28"/>')
    out.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="124" fill="none" '
               f'stroke="{ACCENT}" stroke-width="1" opacity=".12"/>')
    return out


def rings(r, cols):
    """Concentric rings thinning outward, one picked out. (Bullseye)"""
    cx, cy = W * r.uniform(.34, .46), H * r.uniform(.46, .56)
    pick = r.randint(3, 6)
    out = []
    for i in range(14, 0, -1):
        rad = 34 * i
        sel = i == pick
        out.append(
            f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad}" fill="none" '
            f'stroke="{ACCENT if sel else cols[i % len(cols)]}" '
            f'stroke-width="{2.4 if sel else max(.5, 2.2 - i * .12):.1f}" '
            f'opacity="{.85 if sel else max(.08, .55 - i * .035):.2f}"/>')
    out.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="13" fill="{ACCENT}" opacity=".9"/>')
    return out


def distribution(r, cols):
    """Marks settling from spiky to flat - short samples versus long ones."""
    out, n = [], 46
    for i in range(n):
        t = i / (n - 1)
        x = 90 + t * (W - 180)
        swing = (1 - t) ** 2.1
        y = H * .60 - (r.uniform(-1, 1) * 210 * swing) - 34 * (1 - t) * .4
        rad = 4.5 + 4 * (1 - t)
        c = cols[int(t * (len(cols) - 1))]
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.1f}" fill="{c}" '
                   f'opacity="{.45 + .40 * t:.2f}"/>')
    out.append(f'<path d="M 80 {H*.60:.0f} L {W-80} {H*.60:.0f}" stroke="{ACCENT}" '
               f'stroke-width="1.2" opacity=".40" stroke-dasharray="2 7"/>')
    return out


def grid(r, cols):
    """A field of tiles evening out toward one edge. (Data, archive)"""
    out, cw, ch = [], 15, 8
    for gy in range(ch):
        for gx in range(cw):
            t = gx / (cw - 1)
            if r.random() > .30 + .68 * (1 - t):
                continue
            x = 80 + gx * ((W - 160) / cw)
            y = 78 + gy * ((H - 156) / ch)
            out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{(W-160)/cw-9:.0f}" '
                       f'height="{(H-156)/ch-9:.0f}" rx="4" '
                       f'fill="{cols[gy % len(cols)]}" '
                       f'opacity="{.16 + .60 * (1 - t) * r.uniform(.55, 1):.2f}"/>')
    return out


def bands(r, cols):
    """Four measured columns of light - a repeating schedule. (Draw times)"""
    out = []
    for i in range(4):
        x = 150 + i * 240
        w = r.choice([54, 62, 70])
        out.append(f'<rect x="{x}" y="96" width="{w}" height="{H-192}" rx="10" '
                   f'fill="{cols[(i*2) % len(cols)]}" opacity=".55"/>')
        out.append(f'<rect x="{x}" y="96" width="{w}" height="{H-192}" rx="10" '
                   f'fill="none" stroke="{PAPER}" stroke-width="1" opacity=".10"/>')
        out.append(f'<circle cx="{x + w/2:.0f}" cy="{H*.5:.0f}" r="7" '
                   f'fill="{ACCENT}" opacity="{.85 if i == 1 else .30:.2f}"/>')
    return out


SHAPES = {"scatter": scatter, "converge": converge, "rings": rings,
          "distribution": distribution, "grid": grid, "bands": bands}


def pick_shape(a):
    text = (a.get("tag", "") + " " + a.get("title", "") + " " +
            a.get("summary", "")).lower()
    # Ordered most specific first. "schedule" and "odds" turn up in the body of
    # almost any piece, so a subject word like "multiplier" has to be tested
    # before them or a general word wins by accident - which is how the
    # multiplier article first came out drawn as a timetable.
    if "bullseye" in text:
        return "rings"
    if "multiplier" in text:
        return "grid"
    if "draw time" in text or "draw times" in text or "timetable" in text:
        return "bands"
    if "powerball" in text or "lotto" in text:
        return "converge"
    if any(w in text for w in ("hot", "cold", "frequency", "distribution",
                               "analysis", "probability")):
        return "distribution"
    if any(w in text for w in ("archive", "dataset", "record")):
        return "grid"
    return "scatter"


def render(a):
    slug = a["slug"]
    r = seeded(slug)
    cols = BANDS[:]
    r.shuffle(cols)
    shape = pick_shape(a)
    body = "\n    ".join(SHAPES[shape](r, cols))
    gx, gy = r.uniform(.20, .80), r.uniform(.10, .40)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" \
width="{W}" height="{H}" role="img" aria-label="Abstract illustration">
  <defs>
    <radialGradient id="g" cx="{gx:.2f}" cy="{gy:.2f}" r="1">
      <stop offset="0" stop-color="{GROUND_2}"/>
      <stop offset="1" stop-color="{GROUND}"/>
    </radialGradient>
    <filter id="n"><feTurbulence type="fractalNoise" baseFrequency=".9" \
numOctaves="3"/><feColorMatrix type="saturate" values="0"/></filter>
    <linearGradient id="v" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{GROUND}" stop-opacity=".00"/>
      <stop offset="1" stop-color="{GROUND}" stop-opacity=".55"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#g)"/>
  <g>
    {body}
  </g>
  <rect width="{W}" height="{H}" fill="url(#v)"/>
  <rect width="{W}" height="{H}" filter="url(#n)" opacity=".045"/>
</svg>
'''


def entries():
    out = []
    for fname, key in (("blog.json", "posts"), ("news.json", "articles")):
        try:
            with open(os.path.join(SRC, fname), encoding="utf-8") as fh:
                out += json.load(fh).get(key, [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--force", metavar="SLUG")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    made = 0
    for a in entries():
        slug = a.get("slug")
        if not slug or (args.force and args.force != slug):
            continue
        dest = os.path.join(OUT, slug + ".svg")
        if os.path.exists(dest) and not (args.all or args.force == slug):
            continue
        svg = render(a)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(svg)
        made += 1
        print(f"  {pick_shape(a):<12} {len(svg)//1024 or 1} KB  {slug}")
    print(f"article art: {made} drawn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
