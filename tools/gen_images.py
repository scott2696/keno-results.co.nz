#!/usr/bin/env python3
"""Generate a header image for each blog post and news article.

    python3 tools/gen_images.py              # only what is missing
    python3 tools/gen_images.py --dry-run    # show prompts, call nothing
    python3 tools/gen_images.py --force SLUG # regenerate one

Uses Google's Gemini image model ("Nano Banana"), with the key read from the
macOS keychain (service `nano-banana-api`) or the GEMINI_API_KEY environment
variable. The key is never written to disk or committed.

Images are generated ONCE per article and committed to the repo, so a rebuild
costs nothing. Existing files are skipped unless --force names them.

House rule, enforced in the prompt: these are abstract editorial illustrations.
No people, no photorealism, no depiction of real events, tickets, winners or
branding. On a site whose position is verified data and honest sourcing, an
image that could pass for a photograph of a real draw would undercut
everything else. Every image is labelled as an illustration in the page.

Stdlib only.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "data")
OUT = os.path.join(ROOT, "assets", "img", "articles")
MODEL = "gemini-2.5-flash-image"          # "Nano Banana"
ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            f"{MODEL}:generateContent")

# The site's own palette, so images sit inside the design rather than beside it.
PALETTE = ("deep forest green #123326, champagne gold #C9A961, warm alabaster "
           "#F7F1E9, terracotta #C6642F, and deep obsidian #12100E")

STYLE = (
    "Abstract editorial illustration for a lottery results website. "
    f"Strict palette: {PALETTE}. "
    "Flat vector-like shapes with subtle grain, soft directional light from the "
    "upper right, generous negative space, calm and premium. "
    "Wide 16:9 composition suitable for a page header. "
    "STRICTLY NO people, no faces, no hands, no text, no lettering, no numbers, "
    "no logos, no brand marks, no photorealism, no casino imagery, no slot "
    "machines, no money or banknotes, no scratch cards, no real-world locations. "
    "Purely abstract geometric composition."
)

SUBJECTS = {
    "keno":      "Scattered spheres on a calm field, a few catching gold rimlight, "
                 "arranged with deliberate irregular spacing suggesting randomness.",
    "lotto":     "Overlapping translucent circles converging toward a single bright "
                 "point, suggesting accumulation and convergence.",
    "bullseye":  "Concentric rings radiating from an off-centre point, thinning "
                 "outward, one ring picked out in gold.",
    "analysis":  "A gentle distribution curve formed from small circular marks, "
                 "flattening from left to right toward an even baseline.",
    "data":      "A grid of small tiles at varying opacity, settling into an even "
                 "field toward one edge.",
    "reference": "Four evenly spaced vertical bands of light on a calm ground, "
                 "regular and measured, suggesting a repeating schedule.",
    "default":   "Balanced abstract composition of circles and soft bands, quiet "
                 "and premium.",
}


def api_key():
    env = os.environ.get("GEMINI_API_KEY") or os.environ.get("NANO_BANANA_API_KEY")
    if env:
        return env.strip()
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "nano-banana-api", "-w"],
            capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def entries():
    """Every blog post and news article, newest first."""
    out = []
    for fname, key, kind in (("blog.json", "posts", "blog"),
                             ("news.json", "articles", "news")):
        try:
            with open(os.path.join(SRC, fname), encoding="utf-8") as fh:
                items = json.load(fh).get(key, [])
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for a in items:
            a = dict(a)
            a["_kind"] = kind
            out.append(a)
    return out


def subject_for(a):
    tag = (a.get("tag") or "").lower()
    text = (a.get("title", "") + " " + a.get("summary", "")).lower()
    for k in ("bullseye", "keno", "lotto"):
        if k in tag or k in text:
            return SUBJECTS[k]
    for k in ("analysis", "data", "reference"):
        if k in tag:
            return SUBJECTS[k]
    return SUBJECTS["default"]


def build_prompt(a):
    return f"{STYLE} Subject: {subject_for(a)}"


def generate(key, prompt, timeout=120, attempts=4):
    """Generate one image, backing off on 429.

    The free tier rate-limits per minute as well as per day, so a 429 is often
    just pacing rather than a hard stop. We honour the API's own retryDelay
    when it gives one."""
    last = None
    for i in range(attempts):
        try:
            return _generate_once(key, prompt, timeout)
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == attempts - 1:
                raise
            delay = 20 * (i + 1)
            try:
                body = json.loads(e.read().decode())
                for det in body.get("error", {}).get("details", []):
                    if det.get("@type", "").endswith("RetryInfo"):
                        secs = det.get("retryDelay", "")
                        if secs.endswith("s"):
                            delay = max(int(float(secs[:-1])) + 2, 5)
            except Exception:
                pass
            print(f"    rate limited, waiting {delay}s", file=sys.stderr)
            time.sleep(delay)
            last = e
    raise last


def _generate_once(key, prompt, timeout=120):
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()
    req = urllib.request.Request(
        ENDPOINT, data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)

    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise ValueError("no image part in response: " + json.dumps(data)[:220])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", metavar="SLUG", default=None)
    ap.add_argument("--limit", type=int, default=6, help="max generations per run")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    todo = []
    for a in entries():
        slug = a.get("slug")
        if not slug:
            continue
        dest = os.path.join(OUT, f"{slug}.png")
        if os.path.exists(dest) and args.force != slug:
            continue
        if args.force and args.force != slug:
            continue
        todo.append((a, dest))

    if not todo:
        print("images: all articles already have one")
        return 0

    if args.dry_run:
        for a, dest in todo:
            print(f"\n  {a['slug']}")
            print(f"    -> {os.path.relpath(dest, ROOT)}")
            print(f"    prompt: {build_prompt(a)[:150]}...")
        print(f"\n  {len(todo)} would be generated")
        return 0

    key = api_key()
    if not key:
        print("images: no API key found (keychain 'nano-banana-api' or "
              "GEMINI_API_KEY); skipping", file=sys.stderr)
        return 0

    made = 0
    for a, dest in todo[:args.limit]:
        try:
            img = generate(key, build_prompt(a))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            print(f"  {a['slug']}: generation failed ({str(e)[:110]})", file=sys.stderr)
            continue
        with open(dest, "wb") as fh:
            fh.write(img)
        made += 1
        print(f"  {a['slug']}: {len(img)//1024} KB -> {os.path.relpath(dest, ROOT)}")

    print(f"images: generated {made} of {len(todo)} pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
