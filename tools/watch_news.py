#!/usr/bin/env python3
"""Watch NZ media for lottery stories and queue the topics.

    python3 tools/watch_news.py

New Zealand's news sites do not publish open APIs, so this reads the Google
News NZ query feed, which aggregates NZ Herald, Stuff, 1News, RNZ and others.

IMPORTANT - what this deliberately does NOT do:

It stores headlines, sources, dates and links only. It never fetches or keeps
article bodies, and nothing it captures is used as source material for what we
publish. Its job is to tell us *what is being covered* so we know a story
exists; the article we then write comes from Lotto NZ's official results.
Re-publishing a competitor's copy is both a copyright problem and duplicate
content, and this site's credibility is the whole product.

Output: src/data/news-queue.json - a list of topics with a 'covered' flag.
Nothing here reaches the site until it is written up and moved into news.json.

Stdlib only.
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "src", "data", "news-queue.json")
UA = {"User-Agent": "keno-results.co.nz/1.0 (+https://keno-results.co.nz/about/)"}

FEED = ("https://news.google.com/rss/search?q="
        + urllib.parse.quote('"Lotto" OR "Powerball" OR "Keno" OR "Bullseye" '
                             'OR "Instant Kiwi" New Zealand')
        + "&hl=en-NZ&gl=NZ&ceid=NZ:en")

# A headline must hit a game or the operator to be worth queueing.
GAMES = ("lotto", "powerball", "keno", "bullseye", "instant kiwi", "strike",
         "mylotto", "lotto nz")

# Story shapes we can actually answer from official data, roughly ranked.
SIGNALS = [
    (["rule", "change", "overhaul", "new format", "shake-up", "shakeup",
      "revamp", "odds rise", "must be won", "must-be-won"], "rules", 1),
    (["jackpot", "rolls over", "rolled over", "rollover", "up for grabs",
      "must go off"], "jackpot", 2),
    (["winner", "won", "claimed", "scooped", "split", "share"], "winner", 3),
    (["sold", "where", "store", "dairy", "supermarket"], "retail", 4),
    (["unclaimed", "expire", "deadline"], "unclaimed", 3),
]


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def classify(title):
    t = title.lower()
    if not any(g in t for g in GAMES):
        return None, 99
    for words, label, pri in SIGNALS:
        if any(w in t for w in words):
            return label, pri
    return "general", 5


def parse(xml):
    out = []
    for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def grab(tag):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S)
            return clean(m.group(1)) if m else ""

        title = grab("title")
        if not title:
            continue
        link, pub, src = grab("link"), grab("pubDate"), grab("source")
        # Google appends " - Source" to titles
        title = re.sub(r"\s+-\s+[^-]{2,30}$", "", title).strip()

        label, pri = classify(title)
        if label is None:
            continue
        out.append({"title": title, "source": src, "published": pub,
                    "link": link, "topic": label, "priority": pri})
    return out


def load_queue():
    try:
        with open(QUEUE, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"_note": "Topics spotted in NZ media. Headlines and links only - no "
                         "article text is stored or reused. Write from official data.",
                "updated": None, "topics": []}


def main():
    try:
        xml = fetch(FEED)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"warn: feed unreachable ({e}); queue left unchanged", file=sys.stderr)
        return 0

    found = parse(xml)
    q = load_queue()
    seen = {t["title"].lower() for t in q["topics"]}

    added = 0
    for item in found:
        if item["title"].lower() in seen:
            continue
        item["covered"] = False
        item["seen"] = datetime.date.today().isoformat()
        q["topics"].append(item)
        seen.add(item["title"].lower())
        added += 1

    # newest and most actionable first, and keep it from growing without bound
    q["topics"].sort(key=lambda t: (t.get("covered", False), t.get("priority", 9),
                                    t.get("seen", "")), reverse=False)
    q["topics"] = q["topics"][:120]
    q["updated"] = datetime.datetime.now().replace(microsecond=0).isoformat()

    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8") as fh:
        json.dump(q, fh, indent=2)
        fh.write("\n")

    open_topics = [t for t in q["topics"] if not t.get("covered")]
    print(f"news watch: {len(found)} relevant headlines, {added} new, "
          f"{len(open_topics)} uncovered")
    for t in open_topics[:8]:
        print(f"  [{t['topic']:<8}] {t['title'][:76]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
