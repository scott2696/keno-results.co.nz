#!/usr/bin/env python3
"""Read Lotto NZ's own media releases, so we can write from the source.

    python3 tools/fetch_official.py              # refresh the index
    python3 tools/fetch_official.py --full SLUG  # also pull one release's text
    python3 tools/fetch_official.py --list       # show what we hold

Why this exists
---------------
tools/watch_news.py watches Google News and stores headlines only. It tells us
a story is being covered; it can never tell us anything we are allowed to
publish, because everything it sees belongs to a news organisation.

This reads Lotto New Zealand instead - the operator, the primary source, the
people the facts actually come from. That is the one body of writing about
these games we can legitimately source from, and it is what unblocked the
Powerball format story: the rule was never "no sources", it was no third-party
news sites.

The boundary this file must keep
--------------------------------
It stores the official release's title, date, URL and standfirst so an article
can cite and link it. `--full` pulls the release body into .firecrawl/ for
reading - deliberately NOT into src/data/, and never into an article. Facts are
free to use; Lotto NZ's sentences are theirs. Anything published here is
written from scratch, the same rule that applies to everything else on the site.

mylotto.co.nz is a JavaScript app that serves "loading (bootstrapping)" to a
plain fetch, so this goes through Firecrawl with a render wait. The key comes
from the macOS keychain via tools/fc - never from a file in this repo, which is
public and is itself the web root.

Stdlib only (Firecrawl is invoked as a subprocess through tools/fc).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FC = os.path.join(ROOT, "tools", "fc")
OUT = os.path.join(ROOT, "src", "data", "official-releases.json")
WORK = os.path.join(ROOT, ".firecrawl")

INDEX = "https://mylotto.co.nz/media-releases"
RENDER_WAIT = "9000"          # the SPA needs a real render pass

# Releases worth flagging for an article. Everything else is filed but not
# surfaced - winner stories and giveaways are not things we can add to.
NOTABLE = [
    (["overhaul", "change", "changes", "new format", "rule", "rules",
      "prize structure", "division", "divisions", "launch", "replacing"],
     "format", 1),
    (["draw time", "draw times", "schedule", "delay", "delayed"], "schedule", 1),
    (["odds", "probability", "chances"], "odds", 2),
    (["unclaimed", "expire", "deadline", "check your ticket"], "unclaimed", 3),
]
GAMES = ("powerball", "lotto", "keno", "bullseye", "instant kiwi", "strike")


def fc(*args, timeout=240):
    """Run the Firecrawl CLI. Returns stdout, or None if it failed."""
    try:
        r = subprocess.run([FC, *args], capture_output=True, text=True,
                           timeout=timeout, cwd=ROOT)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"warn: firecrawl unavailable ({e})", file=sys.stderr)
        return None
    if r.returncode != 0:
        print(f"warn: firecrawl exit {r.returncode}: {r.stderr.strip()[:200]}",
              file=sys.stderr)
        return None
    return r.stdout


def classify(title, standfirst):
    text = (title + " " + standfirst).lower()
    game = next((g for g in GAMES if g in text), None)
    for words, label, pri in NOTABLE:
        if any(w in text for w in words):
            return game, label, pri
    return game, "general", 5


def parse_index(md):
    """Pull releases out of the index page's markdown.

    Each card renders as one link whose text carries the category, a bold
    title, a dd/mm/yyyy date and a standfirst, all separated by escaped
    newlines. Parsing the card rather than the whole page keeps a layout
    change from silently producing garbage: a card that does not match is
    skipped, not guessed at.
    """
    out = []
    for body, url in re.findall(r"\[(.+?)\]\((https://mylotto\.co\.nz/"
                                r"news-and-press-releases?/[^)]+)\)", md, re.S):
        title = re.search(r"\*\*(.+?)\*\*", body, re.S)
        date = re.search(r"(\d{2})/(\d{2})/(\d{4})", body)
        if not (title and date):
            continue
        d, m, y = date.groups()
        clean = lambda s: re.sub(r"\s+", " ", s.replace("\\", "")).strip()
        tail = body[date.end():]
        standfirst = clean(re.sub(r"\s*Read more\.?\s*$", "", tail))
        t = clean(title.group(1))
        game, topic, pri = classify(t, standfirst)
        out.append({
            "title": t,
            "date": f"{y}-{m}-{d}",
            "url": url,
            "slug": url.rstrip("/").rsplit("/", 1)[-1],
            "standfirst": standfirst,
            "game": game,
            "topic": topic,
            "priority": pri,
        })
    return out


def load():
    try:
        with open(OUT, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "_note": "Lotto NZ's own media releases - the operator, not a news "
                     "site. Titles, dates, links and standfirsts only: enough "
                     "to cite and link a release. Article text is always "
                     "written from scratch from the facts, never adapted from "
                     "Lotto NZ's wording.",
            "source": INDEX,
            "updated": None,
            "releases": [],
        }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--full", metavar="SLUG",
                    help="also fetch one release's text into .firecrawl/ to read")
    ap.add_argument("--list", action="store_true", help="show what we hold")
    args = ap.parse_args()

    store = load()

    if args.list:
        for r in store["releases"]:
            flag = "*" if r["priority"] <= 2 and not r.get("covered") else " "
            print(f" {flag} {r['date']}  [{r['topic']:<9}] {r['title'][:64]}")
            print(f"      {r['url']}")
        return 0

    if args.full:
        rel = next((r for r in store["releases"] if r["slug"] == args.full), None)
        if not rel:
            print(f"no release with slug {args.full!r} - run without --full first",
                  file=sys.stderr)
            return 1
        os.makedirs(WORK, exist_ok=True)
        dest = os.path.join(WORK, f"release-{args.full}.md")
        # Into .firecrawl/, which is gitignored. This is reading material for
        # whoever writes the article, not an input to the site.
        if fc("scrape", rel["url"], "--wait-for", RENDER_WAIT, "--country", "NZ",
              "--only-main-content", "-o", dest) is None:
            return 1
        print(f"{rel['title']}\n  -> {os.path.relpath(dest, ROOT)}")
        print("  facts are usable; the wording is Lotto NZ's - write it fresh.")
        return 0

    md_path = os.path.join(WORK, "media-releases.md")
    os.makedirs(WORK, exist_ok=True)
    if fc("scrape", INDEX, "--wait-for", RENDER_WAIT, "--country", "NZ",
          "--only-main-content", "-o", md_path) is None:
        print("official releases: fetch failed, index left unchanged", file=sys.stderr)
        return 0                       # never fail the refresh run

    try:
        with open(md_path, encoding="utf-8") as fh:
            md = fh.read()
    except OSError:
        return 0

    found = parse_index(md)
    if not found:
        # A layout change should be loud but harmless: keep what we have.
        print("official releases: nothing parsed - page layout may have changed",
              file=sys.stderr)
        return 0

    known = {r["url"]: r for r in store["releases"]}
    added = 0
    for rel in found:
        if rel["url"] in known:
            known[rel["url"]].update({k: rel[k] for k in
                                      ("title", "date", "standfirst", "topic",
                                       "game", "priority")})
            continue
        rel["covered"] = False
        rel["seen"] = datetime.date.today().isoformat()
        store["releases"].append(rel)
        added += 1

    store["releases"].sort(key=lambda r: r["date"], reverse=True)
    store["releases"] = store["releases"][:60]
    store["updated"] = datetime.datetime.now().replace(microsecond=0).isoformat()

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    open_ = [r for r in store["releases"]
             if not r.get("covered") and r["priority"] <= 2]
    print(f"official releases: {len(found)} on the page, {added} new, "
          f"{len(open_)} worth writing about")
    for r in open_[:6]:
        print(f"  [{r['topic']:<9}] {r['date']}  {r['title'][:66]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
