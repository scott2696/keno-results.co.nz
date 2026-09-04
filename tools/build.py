#!/usr/bin/env python3
"""Build the static site.

    python3 tools/build.py

Renders src/pages/*.html through src/base.html into the repo root, where
GitHub Pages serves them. No npm, no toolchain -- the site is 13 pages and
does not need one. Re-run after editing anything in src/.
"""
import datetime
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SITE = "https://keno-results.co.nz"
YEAR = datetime.date.today().year

# slug -> page definition. slug "" is the homepage.
PAGES = [
    dict(slug="", src="index", nav="home",
         title="Keno Results NZ | Latest Winning Numbers",
         og="Keno Results NZ",
         desc="The latest confirmed New Zealand Keno draw - 20 numbers from 1 to 80 - "
              "with a ticket checker and full draw archive.",
         js=["results"], schema=["website", "org"]),
    dict(slug="check", src="check", nav="check",
         title="Check My Keno Numbers | keno-results.co.nz",
         og="Check my Keno numbers",
         desc="Check your Keno ticket against any published New Zealand draw. "
              "Your numbers stay in your browser and are never uploaded.",
         js=["results", "checker"]),
    dict(slug="results", src="results", nav="results",
         title="Keno Draw Archive NZ | keno-results.co.nz",
         og="Keno draw archive",
         desc="Every confirmed New Zealand Keno draw we hold, newest first, "
              "with winning numbers and draw identifiers.",
         js=["results"], schema=["dataset"]),
    dict(slug="statistics", src="statistics", nav="stats",
         title="Keno Number Frequency NZ | keno-results.co.nz",
         og="Keno number frequency",
         desc="How often each Keno number has been drawn. Descriptive history only - "
              "past draws do not predict future ones.",
         js=["results"]),
    dict(slug="how-to-play", src="how-to-play", nav="howto",
         title="How to Play Keno in New Zealand | keno-results.co.nz",
         og="How to play Keno",
         desc="How New Zealand Keno works: 20 numbers drawn from 80, choosing your spots, "
              "how prizes are structured, and what people get wrong.",
         schema=["howto"]),
    dict(slug="odds", src="odds", nav="odds",
         title="Keno Odds NZ - Real Probabilities | keno-results.co.nz",
         og="Keno odds",
         desc="Verified Keno odds for every spot count, calculated from the rules of the "
              "game. Includes the full six-spot breakdown and the formula used.",
         schema=["faq"]),
    dict(slug="about", src="about",
         title="About & Data Sources | keno-results.co.nz",
         og="About this site",
         desc="Who runs keno-results.co.nz, where the results come from, how every draw "
              "is validated before publication, and how to report an error.",
         schema=["org"]),
    dict(slug="lotto-nz", src="lotto-nz",
         title="Lotto NZ Games Explained | keno-results.co.nz",
         og="Lotto NZ games",
         desc="The games Lotto New Zealand runs alongside Keno - Lotto, Powerball, "
              "Bullseye and Instant Kiwi - and how they differ."),
    dict(slug="powerball", src="powerball",
         title="Powerball NZ Explained | keno-results.co.nz",
         og="Powerball NZ",
         desc="How Powerball attaches to a Lotto NZ line, what it does to the odds, "
              "and why a bigger jackpot does not mean a better chance."),
    dict(slug="bullseye", src="bullseye",
         title="Bullseye NZ Explained | keno-results.co.nz",
         og="Bullseye NZ",
         desc="How New Zealand's daily Bullseye game is structured and how it differs "
              "from Keno."),
    dict(slug="instant-kiwi", src="instant-kiwi",
         title="Instant Kiwi Explained | keno-results.co.nz",
         og="Instant Kiwi",
         desc="Why Instant Kiwi scratch tickets work differently from drawn games, and "
              "what their published odds actually describe."),
    dict(slug="privacy-policy", src="privacy-policy",
         title="Privacy Policy | keno-results.co.nz",
         og="Privacy policy",
         desc="What keno-results.co.nz collects, why your Keno numbers never leave your "
              "browser, and your rights under the Privacy Act 2020."),
    dict(slug="404", src="404", path="404.html", robots="noindex, follow", sitemap=False,
         title="Page Not Found | keno-results.co.nz",
         og="Page not found",
         desc="That page has moved or never existed."),
]

# Legacy URLs that must not 404. GitHub Pages cannot issue a server-side 301,
# so these are canonical-tagged meta-refresh stubs -- the standard approach.
REDIRECTS = {
    "keno-tools": "/statistics/",   # was a tools/statistics page
    "stra": "/odds/",               # "strategy" -> the actual arithmetic
}

SCHEMA = {
    "org": lambda: {
        "@type": "Organization",
        "@id": SITE + "/#org",
        "name": "keno-results.co.nz",
        "url": SITE + "/",
        "logo": SITE + "/assets/img/icon-512.png",
        "email": "info@keno-results.co.nz",
        "disambiguatingDescription":
            "An independent Keno results service. Not affiliated with, endorsed by, "
            "or operated by Lotto New Zealand.",
    },
    "website": lambda: {
        "@type": "WebSite",
        "@id": SITE + "/#website",
        "url": SITE + "/",
        "name": "keno-results.co.nz",
        "publisher": {"@id": SITE + "/#org"},
        "inLanguage": "en-NZ",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint",
                       "urlTemplate": SITE + "/check/?numbers={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    },
    "dataset": lambda: {
        "@type": "Dataset",
        "name": "New Zealand Keno draw results",
        "description": "Winning numbers for New Zealand Keno draws. "
                       "Each draw is 20 unique numbers between 1 and 80.",
        "url": SITE + "/results/",
        "variableMeasured": "Winning numbers (20 drawn from 1-80)",
        "creator": {"@id": SITE + "/#org"},
        "isAccessibleForFree": True,
        "license": SITE + "/about/",
    },
    "howto": lambda: {
        "@type": "HowTo",
        "name": "How to play Keno in New Zealand",
        "description": "Choosing your spots, entering a draw and checking a Keno ticket.",
        "step": [
            {"@type": "HowToStep", "name": "Choose how many spots to play",
             "text": "Choose between one and ten numbers. This determines the prize "
                     "structure of your ticket."},
            {"@type": "HowToStep", "name": "Choose your numbers",
             "text": "Mark your own numbers or take a random selection. Neither method "
                     "affects your odds."},
            {"@type": "HowToStep", "name": "Set your stake",
             "text": "Prizes scale with the amount you stake."},
            {"@type": "HowToStep", "name": "Choose how many draws to enter",
             "text": "Enter a single draw, or the same numbers across several "
                     "consecutive draws."},
            {"@type": "HowToStep", "name": "Check your ticket",
             "text": "Compare your numbers against the 20 drawn and count the matches. "
                     "Confirm any win with the official operator."},
        ],
    },
    "faq": lambda: {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question",
             "name": "What are the odds of matching all six numbers on a Keno ticket?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "About 1 in 7,753. Twenty numbers are drawn from "
                                        "80, so the probability is C(20,6) divided by "
                                        "C(80,6)."}},
            {"@type": "Question",
             "name": "Does playing more spots improve my Keno odds?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "No. Playing more spots makes the top prize tier "
                                        "harder to reach, not easier. What it adds is a "
                                        "longer ladder of smaller prize tiers."}},
            {"@type": "Question",
             "name": "Can a system or number-selection strategy improve Keno odds?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "No. Every draw is independent and every "
                                        "combination is equally likely. No selection "
                                        "method changes the probabilities."}},
            {"@type": "Question",
             "name": "Are some Keno numbers due to come up?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "No. Draws have no memory. A number that has not "
                                        "appeared recently is exactly as likely to appear "
                                        "as any other."}},
        ],
    },
}


def breadcrumbs(page):
    if not page["slug"]:
        return None
    label = re.sub(r"\s*\|.*$", "", page["og"])
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": label,
             "item": f"{SITE}/{page['slug']}/"},
        ],
    }


def build():
    base = open(os.path.join(SRC, "base.html"), encoding="utf-8").read()
    written = []

    for page in PAGES:
        slug = page["slug"]
        body = open(os.path.join(SRC, "pages", page["src"] + ".html"), encoding="utf-8").read()

        canonical = SITE + "/" if not slug else f"{SITE}/{slug}/"
        if page.get("path"):
            canonical = f"{SITE}/{page['path']}"

        graph = [SCHEMA[k]() for k in page.get("schema", [])]
        crumbs = breadcrumbs(page)
        if crumbs:
            graph.append(crumbs)
        head_extra = ""
        if graph:
            blob = json.dumps({"@context": "https://schema.org", "@graph": graph},
                              indent=None, separators=(",", ":"))
            head_extra = f'<script type="application/ld+json">{blob}</script>'

        scripts = "".join(
            f'<script src="/assets/js/{name}.js" defer></script>' for name in page.get("js", []))

        nav = page.get("nav")
        out = base
        for key in ("home", "check", "results", "stats", "howto", "odds"):
            out = out.replace("{c_%s}" % key, ' aria-current="page"' if nav == key else "")

        out = (out
               .replace("{title}", html.escape(page["title"]))
               .replace("{og_title}", html.escape(page["og"]))
               .replace("{description}", html.escape(page["desc"]))
               .replace("{canonical}", canonical)
               .replace("{robots}", page.get("robots", "index, follow, max-image-preview:large"))
               .replace("{site}", SITE)
               .replace("{head_extra}", head_extra)
               .replace("{scripts}", scripts)
               .replace("{content}", body.rstrip())
               .replace("{year}", str(YEAR)))

        rel = page.get("path") or ("index.html" if not slug else f"{slug}/index.html")
        dest = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(dest) or ROOT, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out)
        written.append(rel)

    # ---- legacy redirect stubs ----
    for old, new in REDIRECTS.items():
        dest = os.path.join(ROOT, old, "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f"""<!DOCTYPE html>
<html lang="en-NZ">
<head>
<meta charset="utf-8">
<title>Moved to {new}</title>
<link rel="canonical" href="{SITE}{new}">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={new}">
</head>
<body><p>This page has moved to <a href="{new}">{SITE}{new}</a>.</p></body>
</html>
""")
        written.append(f"{old}/index.html (-> {new})")

    # ---- sitemap ----
    today = datetime.date.today().isoformat()
    urls = []
    for page in PAGES:
        if page.get("sitemap") is False:
            continue
        loc = SITE + "/" if not page["slug"] else f"{SITE}/{page['slug']}/"
        prio = "1.0" if not page["slug"] else ("0.9" if page["slug"] in ("check", "results") else "0.7")
        urls.append(f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod>"
                    f"<priority>{prio}</priority></url>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + "\n".join(urls) + "\n</urlset>\n")
    written.append("sitemap.xml")

    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    written.append("robots.txt")

    with open(os.path.join(ROOT, "site.webmanifest"), "w", encoding="utf-8") as fh:
        json.dump({
            "name": "keno-results.co.nz",
            "short_name": "Keno Results",
            "description": "New Zealand Keno results and ticket checker.",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#FBFCFB",
            "theme_color": "#0B7A43",
            "icons": [
                {"src": "/assets/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/assets/img/icon-512.png", "sizes": "512x512", "type": "image/png",
                 "purpose": "any maskable"},
            ],
        }, fh, indent=2)
    written.append("site.webmanifest")

    print(f"built {len(written)} files:")
    for w in written:
        print("  " + w)
    return 0


if __name__ == "__main__":
    sys.exit(build())
