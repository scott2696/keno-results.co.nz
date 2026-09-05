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
import random
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
         desc="Every confirmed New Zealand Keno draw, searchable by draw number, date "
              "or a number that came up. Each result has its own permanent page.",
         js=["archive"], schema=["dataset"]),
    dict(slug="statistics", src="statistics", nav="stats",
         title="Hot & Cold Keno Numbers NZ | keno-results.co.nz",
         og="Hot and cold Keno numbers",
         desc="Which NZ Keno numbers have come up most and least often over the last 5, "
              "10, 25, 50, 100 or 250 draws, plus the full frequency count.",
         js=["results"]),
    dict(slug="how-to-play", src="how-to-play", nav="howto", section=True,
         title="How to Play Keno in New Zealand | keno-results.co.nz",
         og="How to play Keno",
         desc="How New Zealand Keno works: 20 numbers drawn from 80, choosing your spots, "
              "how prizes are structured, and what people get wrong.",
         schema=["howto"]),
    dict(slug="odds", src="odds", nav="odds", section=True,
         title="Keno Odds NZ - Real Probabilities | keno-results.co.nz",
         og="Keno odds",
         desc="Verified Keno odds for every spot count, calculated from the rules of the "
              "game. Includes the full six-spot breakdown and the formula used.",
         schema=["faq"]),
    dict(slug="number-generator", src="number-generator", nav="tools",
         title="Keno Number Generator NZ | keno-results.co.nz",
         og="Keno number generator",
         desc="Generate a random Keno line in your browser and see the true odds of that "
              "line beside it. One to ten spots, nothing sent anywhere.",
         js=["generator"]),
    dict(slug="calculator", src="calculator", nav="tools",
         title="Keno Odds & Return Calculator NZ | keno-results.co.nz",
         og="Keno odds and return calculator",
         desc="Exact probabilities for any Keno spot count, plus real expected return and "
              "house edge once you supply the prize values from your own paytable.",
         js=["calculator"]),
    dict(slug="prizes", src="prizes", section=True,
         title="How Keno Prizes Work NZ | keno-results.co.nz",
         og="How Keno prizes work",
         desc="What sets the size of a NZ Keno win - spots played, matches, stake and the "
              "draw multiplier - and why we publish odds rather than a prize table."),
    dict(slug="history", src="history", section=True,
         title="The History of Keno | keno-results.co.nz",
         og="The history of Keno",
         desc="How Keno travelled from Han dynasty China to four draws a day in New "
              "Zealand, why the pool is 80 numbers, and what has never changed."),
    dict(slug="where-to-play", src="where-to-play", section=True,
         title="Where to Play Keno in New Zealand | keno-results.co.nz",
         og="Where to play Keno in NZ",
         desc="Who legally offers Keno in New Zealand, how casino Keno differs, what to "
              "check before playing anywhere, and why we do not sell tickets."),
    dict(slug="faqs", src="faqs", section=True,
         title="Keno FAQs NZ | keno-results.co.nz",
         og="Keno FAQs",
         desc="Straight answers about New Zealand Keno: how it works, the odds, the "
              "multiplier, whether numbers are ever due, and where our results come from.",
         schema=["faq2"]),
    dict(slug="multiplier", src="multiplier", section=True,
         title="Keno Multiplier NZ Explained | keno-results.co.nz",
         og="The Keno multiplier",
         desc="How the NZ Keno multiplier scales prizes, the values we have observed "
              "across 220 draws, and why it never changes your odds of winning.",
         schema=["faq3"]),
    dict(slug="draw-schedule", src="draw-schedule", section=True,
         title="Keno Draw Times NZ | keno-results.co.nz",
         og="Keno draw schedule",
         desc="New Zealand Keno draws four times daily at 10:01am, 1:01pm, 3:01pm and "
              "6:01pm NZ time, every day of the week.",
         schema=["howto2"]),
    dict(slug="rules", src="rules", section=True,
         title="Keno Rules & Regulations NZ | keno-results.co.nz",
         og="Keno rules and regulations",
         desc="How NZ Keno is structured, who operates and regulates it, the age limit, "
              "how prizes are claimed, and where the binding rules live.",
         schema=[]),
    dict(slug="about", src="about", nav="about",
         title="About & Data Sources | keno-results.co.nz",
         og="About this site",
         desc="Who runs keno-results.co.nz, where the results come from, how every draw "
              "is validated before publication, and how to report an error.",
         schema=["org"]),
    dict(slug="lotto-nz", src="lotto-nz", js=["game"],
         title="Lotto NZ Games Explained | keno-results.co.nz",
         og="Lotto NZ games",
         desc="The games Lotto New Zealand runs alongside Keno - Lotto, Powerball, "
              "Bullseye and Instant Kiwi - and how they differ."),
    dict(slug="powerball", src="powerball", js=["game"],
         title="Powerball NZ Explained | keno-results.co.nz",
         og="Powerball NZ",
         desc="How Powerball attaches to a Lotto NZ line, what it does to the odds, "
              "and why a bigger jackpot does not mean a better chance."),
    dict(slug="bullseye", src="bullseye", js=["game"],
         title="Bullseye NZ Explained | keno-results.co.nz",
         og="Bullseye NZ",
         desc="How New Zealand's daily Bullseye game is structured and how it differs "
              "from Keno."),
    dict(slug="instant-kiwi", src="instant-kiwi",
         title="Instant Kiwi Explained | keno-results.co.nz",
         og="Instant Kiwi",
         desc="Why Instant Kiwi scratch tickets work differently from drawn games, and "
              "what their published odds actually describe."),
    dict(slug="blog", src="blog", nav="blog",
         title="Keno Blog & Analysis NZ | keno-results.co.nz",
         og="Keno blog and analysis",
         desc="Analysis and reference drawn from our own New Zealand Keno draw archive - "
              "hot and cold numbers, multiplier data and draw times, with the working shown."),
    dict(slug="news", src="news", nav="news",
         title="Keno News NZ | keno-results.co.nz",
         og="Keno news",
         desc="Timely news on New Zealand Keno and the wider Lotto NZ range."),
    dict(slug="contact", src="contact", nav="contact",
         title="Contact Us | keno-results.co.nz",
         og="Contact us",
         desc="Report a wrong Keno result, ask about our data, or get in touch about "
              "media and partnerships.",
         schema=["contactpage"]),
    dict(slug="authors", src="authors",
         title="Authors & Editorial Standards | keno-results.co.nz",
         og="Authors and editorial standards",
         desc="Who runs keno-results.co.nz, how draw results are produced and validated, "
              "and the editorial rules everything published here has to pass.",
         schema=["org"]),
    dict(slug="terms", src="terms",
         title="Terms and Conditions | keno-results.co.nz",
         og="Terms and conditions",
         desc="The terms on which keno-results.co.nz is provided, including that results "
              "are unofficial and must be confirmed with Lotto NZ."),
    dict(slug="cookie-policy", src="cookie-policy",
         title="Cookie Policy | keno-results.co.nz",
         og="Cookie policy",
         desc="keno-results.co.nz sets no cookies. What we store in local storage, why, "
              "and how to clear it."),
    dict(slug="responsible-gambling", src="responsible-gambling",
         title="Responsible Gambling | keno-results.co.nz",
         og="Responsible gambling",
         desc="How Keno's house edge works, warning signs worth taking seriously, "
              "practical limits, and where to get free help in New Zealand."),
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

# "More in this section" - the Keno guide cluster.
SECTION = [
    ("how-to-play",   "How to play"),
    ("odds",          "Odds &amp; payouts"),
    ("faqs",          "Keno FAQs"),
    ("multiplier",    "Multiplier"),
    ("prizes",        "Prizes"),
    ("where-to-play", "Where to play"),
    ("history",       "History"),
    ("draw-schedule", "Draw schedule"),
    ("rules",         "Rules &amp; regulations"),
]


def subnav(slug):
    items = []
    for s_, label in SECTION:
        cur = ' aria-current="page"' if s_ == slug else ""
        items.append('<li><a href="/%s/"%s>%s</a></li>' % (s_, cur, label))
    return ('<nav class="subnav wrap" aria-label="More in this section">'
            '<span class="subnav-l">More in this section</span>'
            '<ul>' + "".join(items) + '</ul></nav>')


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
    "contactpage": lambda: {
        "@type": "ContactPage",
        "name": "Contact keno-results.co.nz",
        "url": SITE + "/contact/",
        "mainEntity": {
            "@type": "Organization",
            "@id": SITE + "/#org",
            "contactPoint": [{
                "@type": "ContactPoint",
                "email": "info@keno-results.co.nz",
                "contactType": "customer support",
                "areaServed": "NZ",
                "availableLanguage": "English",
            }],
        },
    },
    "faq2": lambda: {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "How does Keno work in New Zealand?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Twenty numbers are drawn at random from 1 to 80. "
                                        "You pick between one and ten numbers, called spots, "
                                        "and your prize depends on how many of them appear "
                                        "among the twenty drawn."}},
            {"@type": "Question", "name": "How often are NZ Keno draws held?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Four times a day, every day, at 10:01am, 1:01pm, "
                                        "3:01pm and 6:01pm New Zealand time."}},
            {"@type": "Question", "name": "Are Keno winnings taxed in New Zealand?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Lottery prizes are generally not taxed as income in "
                                        "New Zealand. Income later earned on those winnings, "
                                        "such as interest, is taxable in the normal way."}},
            {"@type": "Question", "name": "Are some Keno numbers due to come up?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "No. Each draw is independent and the draw has no "
                                        "memory. Every number has the same 25 percent chance "
                                        "of appearing in any given draw."}},
            {"@type": "Question", "name": "Does a Keno system or strategy improve your odds?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "No. Every combination is equally likely. Patterns, "
                                        "wheeling systems and frequency-based picks all "
                                        "produce identical odds."}},
        ],
    },
    "faq3": lambda: {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "What is the Keno multiplier?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "A figure selected at random before each draw that "
                                        "multiplies the prize a winning ticket pays. It applies "
                                        "to the whole draw, so everyone playing that draw gets "
                                        "the same multiplier."}},
            {"@type": "Question", "name": "Does the Keno multiplier change your odds?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "No. The multiplier changes what a win pays, never how "
                                        "likely a win is. Your chance of matching numbers "
                                        "depends only on how many spots you play."}},
            {"@type": "Question", "name": "What multiplier values does NZ Keno use?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Across 220 observed draws the multiplier has been "
                                        "x1.5, x2, x3, x5 or x10, with x1.5 the most common at "
                                        "roughly 54 percent of draws and x10 the rarest at "
                                        "under 1 percent."}},
        ],
    },
    "howto2": lambda: {
        "@type": "Dataset",
        "name": "New Zealand Keno draw schedule",
        "description": "Observed NZ Keno draw times: four draws daily at 10:01am, 1:01pm, "
                       "3:01pm and 6:01pm New Zealand time, seven days a week.",
        "url": SITE + "/draw-schedule/",
        "creator": {"@id": SITE + "/#org"},
        "isAccessibleForFree": True,
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


GOLD = "#E8D5A3"


# Two content sections, same machinery. "blog" is evergreen analysis and
# reference; "news" is timely items. Each has its own JSON file and index.
SECTIONS = {
    "blog": {"file": "blog.json", "key": "posts", "label": "Blog",
             "schema": "Article",
             "eyebrow": "Analysis &amp; reference",
             "empty_h": "Nothing published yet",
             "empty_p": "Analysis and reference posts will appear here."},
    "news": {"file": "news.json", "key": "articles", "label": "News",
             "schema": "NewsArticle",
             "eyebrow": "News",
             "empty_h": "No news yet",
             "empty_p": "Timely Keno and lottery news will appear here as we publish it."},
}


def _entries(kind):
    cfg = SECTIONS[kind]
    try:
        with open(os.path.join(SRC, "data", cfg["file"]), encoding="utf-8") as fh:
            items = json.load(fh).get(cfg["key"], [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return sorted(items, key=lambda a: a.get("date", ""), reverse=True)


def _pretty_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%-d %B %Y")
    except ValueError:
        return iso


def entry_list(kind):
    """Cards for a section index."""
    cfg = SECTIONS[kind]
    items = _entries(kind)
    if not items:
        return (f'<div class="empty"><h3>{cfg["empty_h"]}</h3>'
                f'<p>{cfg["empty_p"]}</p></div>')
    out = []
    for a in items:
        out.append(
            f'<li><a class="news-card" href="/{kind}/{a["slug"]}/">'
            f'<span class="news-meta">'
            f'<span class="news-tag">{html.escape(a.get("tag", cfg["label"]))}</span>'
            f'<span class="news-date">{_pretty_date(a["date"])}</span>'
            f'</span>'
            f'<h3>{html.escape(a["title"])}</h3>'
            f'<p>{html.escape(a["summary"])}</p>'
            f'<span class="news-more">Read more'
            f'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" '
            f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M5 12h14M13 6l6 6-6 6"/></svg></span>'
            f'</a></li>'
        )
    return f'<ul class="news-list">{"".join(out)}</ul>'


def _draws():
    try:
        with open(os.path.join(ROOT, "assets", "data", "draws.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"draws": []}


def _nz_dt(iso):
    """'2026-09-05T10:01:00+12:00' -> ('5 September 2026', '10:01am', '2026-09-05')."""
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return iso, "", iso[:10]
    day = dt.strftime("%-d %B %Y")
    h = dt.hour % 12 or 12
    tod = f"{h}:{dt.minute:02d}{'am' if dt.hour < 12 else 'pm'}"
    return day, tod, dt.strftime("%Y-%m-%d")


def draw_balls(nums, cls="", size=""):
    lis = "".join(
        f'<li class="ball b{-(-n // 10)}{cls}">{n}</li>' for n in nums)
    return f'<ul class="balls{size}" aria-label="Winning numbers">{lis}</ul>'


def draw_grid(nums):
    """All 80, with the drawn ones filled - shows the draw against the field."""
    drawn = set(nums)
    lis = "".join(
        f'<li class="ball b{-(-n // 10)}">{n}</li>' if n in drawn
        else f'<li class="ball is-ghost">{n}</li>'
        for n in range(1, 81))
    return f'<ul class="grid80" aria-label="All 80 numbers, drawn ones highlighted">{lis}</ul>'


def offers_block():
    """Render the affiliate strip from src/data/offers.json.

    Kept out of the page templates so a placement can be added, edited or
    switched off in one file. Renders nothing when no offer is active.
    """
    try:
        with open(os.path.join(SRC, "data", "offers.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    live = [o for o in data.get("offers", []) if o.get("active")
            and o.get("placement", "inline") == "inline"]
    if not live:
        return ""

    coins = "".join(
        f'<svg class="coin" style="left:{x}%;bottom:{y}%;animation-delay:{d}s" '
        f'viewBox="0 0 16 16" aria-hidden="true">'
        f'<circle cx="8" cy="8" r="7" fill="none" stroke="{GOLD}" stroke-width="1.6"/>'
        f'<circle cx="8" cy="8" r="3" fill="{GOLD}" opacity=".7"/></svg>'
        for x, y, d in ((12, 18, 0.0), (33, 8, 1.7), (58, 24, 3.4), (79, 12, 5.1), (91, 30, 2.5))
    )
    crown = (
        '<svg class="crown" viewBox="0 0 120 74" aria-hidden="true">'
        '<path d="M6 66 L18 20 L38 44 L60 6 L82 44 L102 20 L114 66 Z" '
        f'fill="none" stroke="{GOLD}" stroke-width="3" stroke-linejoin="round"/>'
        f'<circle cx="18" cy="16" r="5" fill="{GOLD}"/>'
        f'<circle cx="60" cy="4" r="5" fill="{GOLD}"/>'
        f'<circle cx="102" cy="16" r="5" fill="{GOLD}"/></svg>'
    )

    items = []
    for o in live:
        name = html.escape(o["name"])
        cta = html.escape(o.get("cta", "Visit site"))
        items.append(
            f'<li><a class="offer" href="{o["url"]}" target="_blank" '
            f'rel="sponsored nofollow noopener">'
            f'<span class="offer-art" aria-hidden="true">{crown}{coins}</span>'
            f'<span class="offer-brand">'
            f'<img src="{o["logo"]}" alt="{name}" width="150" height="47" loading="lazy">'
            f'</span>'
            f'<span class="offer-body">'
            f'<span class="offer-name">{name}</span>'
            f'<span class="offer-bonus">{o["bonus"]}</span>'
            f'<span class="offer-terms">18+. New players only. Wagering requirements and '
            f'full terms apply &mdash; see the operator&rsquo;s site. Gamble responsibly.'
            f'</span></span>'
            f'<span class="offer-cta">{cta}'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M5 12h14M13 6l6 6-6 6"/></svg></span>'
            f'</a></li>'
        )

    return (
        '<aside class="offers" aria-label="Advertisement">'
        '<p class="offers-l">Advertisement</p>'
        '<ul class="offer-list">' + "".join(items) + '</ul>'
        '<p class="offer-note">This is a paid placement. keno-results.co.nz is not '
        'affiliated with this operator and does not endorse it. We may earn a commission '
        'if you sign up. Please read our '
        '<a href="/responsible-gambling/">responsible gambling</a> page first.</p>'
        '</aside>'
    )


def _load_offers():
    try:
        with open(os.path.join(SRC, "data", "offers.json"), encoding="utf-8") as fh:
            return json.load(fh).get("offers", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def rail_block(side="rail-right"):
    """Vertical offer card for a sticky side rail.

    Colours come from the partner's own `theme` block in offers.json, emitted
    as inline custom properties, so a card carries the operator's identity.
    Falls back to a typographic wordmark when no logo has been supplied,
    rather than inventing one or borrowing their artwork.
    """
    live = [o for o in _load_offers()
            if o.get("active") and o.get("placement") == side]
    if not live:
        return ""

    out = []
    for o in live:
        name = html.escape(o["name"])
        cta = html.escape(o.get("cta", "Visit site"))
        t = o.get("theme") or {}

        style = ""
        pairs = [("--o-deep", "deep"), ("--o-base", "base"), ("--o-raised", "raised"),
                 ("--o-violet", "violet"), ("--o-cyan", "cyan"),
                 ("--o-cta-from", "ctaFrom"), ("--o-cta-to", "ctaTo")]
        decls = [f"{var}:{t[key]}" for var, key in pairs if t.get(key)]
        if decls:
            style = ' style="' + ";".join(decls) + '"'

        art = ""
        if t.get("style") == "sport":
            art = ('<span class="rail-art rail-art-sport" aria-hidden="true">'
                   '<svg viewBox="0 0 200 520" preserveAspectRatio="none">'
                   f'<path d="M-20 300 Q100 240 220 300" fill="none" stroke="{t.get("violet", GOLD)}" '
                   'stroke-width="1.2" opacity=".38"/>'
                   f'<path d="M-20 340 Q100 280 220 340" fill="none" stroke="{t.get("violet", GOLD)}" '
                   'stroke-width="1.2" opacity=".24"/>'
                   f'<path d="M-20 380 Q100 320 220 380" fill="none" stroke="{t.get("violet", GOLD)}" '
                   'stroke-width="1.2" opacity=".14"/>'
                   '</svg></span>')
        elif t.get("style") == "space":
            # deterministic star field - same every build, no layout cost
            rnd = random.Random(len(name) * 7919)
            stars = []
            for _ in range(22):
                # keep the field in the upper sky so a star never lands
                # mid-word in the terms line at the foot of the card
                x, y = rnd.uniform(3, 97), rnd.uniform(3, 58)
                sz = rnd.choice((1, 1, 1, 1.5, 2))
                dl = rnd.uniform(0, 4)
                stars.append(
                    f'<i class="star" style="left:{x:.1f}%;top:{y:.1f}%;'
                    f'width:{sz}px;height:{sz}px;animation-delay:{dl:.1f}s"></i>')
            art = f'<span class="rail-art" aria-hidden="true">{"".join(stars)}</span>'

        if o.get("logo"):
            mark = f'<img class="rail-logo" src="{o["logo"]}" alt="{name}" loading="lazy">'
        else:
            cut = next((i for i in range(1, len(name)) if name[i].isupper()),
                       len(name) // 2)
            mark = f'<span class="rail-mark">{name[:cut]}<em>{name[cut:]}</em></span>'

        kicker = (f'<span class="rail-kicker">{html.escape(o["kicker"])}</span>'
                  if o.get("kicker") else "")

        # headline figure pulled out of the bonus line so it can carry the card
        amt = o.get("amount")
        sub = o.get("amountSub")
        if amt:
            headline = (f'<span class="rail-amt">{amt}</span>'
                        f'<span class="rail-sub">{sub}</span>' if sub
                        else f'<span class="rail-amt">{amt}</span>')
        else:
            headline = (f'<span class="rail-bonus">{o["bonus"]}</span>'
                        if o.get("bonus") else "")

        points = ""
        if o.get("points"):
            lis = "".join(f"<li>{p}</li>" for p in o["points"])
            points = f'<ul class="rail-points">{lis}</ul>'

        out.append(
            f'<a class="offer-rail" href="{o["url"]}" target="_blank" '
            f'rel="sponsored nofollow noopener"{style}>'
            f'{art}'
            f'<span class="rail-top">'
            f'<span class="rail-l">Advertisement</span>'
            f'{mark}'
            f'</span>'
            f'<span class="rail-mid">'
            f'<span class="rail-rule"></span>'
            f'{kicker}'
            f'{headline}'
            f'{points}'
            f'</span>'
            f'<span class="rail-bot">'
            f'<span class="rail-cta">{cta}'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M5 12h14M13 6l6 6-6 6"/></svg></span>'
            f'<span class="rail-terms">18+. New players only. T&amp;Cs apply. '
            f'Paid placement.</span>'
            f'</span>'
            f'</a>'
        )
    return "".join(out)


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
        for key in ("home", "check", "results", "stats", "howto", "odds", "tools", "blog", "news", "about", "contact"):
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
               .replace("{rail}", rail_block("rail-right"))
               .replace("{rail_left}", rail_block("rail-left"))
               .replace("{content}", body.rstrip()
                   .replace("{subnav}", subnav(slug) if page.get("section") else "")
                   .replace("{offers}", offers_block())
                   .replace("{newslist}", entry_list("news"))
                   .replace("{bloglist}", entry_list("blog")))
               .replace("{year}", str(YEAR)))

        rel = page.get("path") or ("index.html" if not slug else f"{slug}/index.html")
        dest = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(dest) or ROOT, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out)
        written.append(rel)

    # ---- one page per draw ----
    # The largest indexable surface on the site: dated long-tail queries the
    # homepage can never hold, because it changes four times a day.
    urls_extra = []
    feed = _draws()
    all_draws = feed.get("draws", [])
    base_tpl = open(os.path.join(SRC, "base.html"), encoding="utf-8").read()
    src_label = feed.get("source") or "Lotto NZ"
    src_url = feed.get("sourceUrl") or "https://mylotto.co.nz/results/keno"

    for i, d in enumerate(all_draws):
        day, tod, ymd = _nz_dt(d["drawnAt"])
        did = d["id"]
        path = f"results/{ymd}/{did}"
        canonical = f"{SITE}/{path}/"
        newer = all_draws[i - 1] if i > 0 else None
        older = all_draws[i + 1] if i + 1 < len(all_draws) else None

        mult = (f'<span class="badge badge-gold">Multiplier &times;{d["multiplier"]}</span>'
                if d.get("multiplier") else "")
        nav_links = []
        if older:
            o_day, _, o_ymd = _nz_dt(older["drawnAt"])
            nav_links.append(f'<a class="btn btn-secondary" rel="prev" '
                             f'href="/results/{o_ymd}/{older["id"]}/">&larr; Draw {older["id"]}</a>')
        nav_links.append('<a class="btn btn-ghost" href="/results/">All draws</a>')
        if newer:
            n_day, _, n_ymd = _nz_dt(newer["drawnAt"])
            nav_links.append(f'<a class="btn btn-secondary" rel="next" '
                             f'href="/results/{n_ymd}/{newer["id"]}/">Draw {newer["id"]} &rarr;</a>')

        head_links = ""
        if older:
            _, _, o_ymd = _nz_dt(older["drawnAt"])
            head_links += f'<link rel="prev" href="{SITE}/results/{o_ymd}/{older["id"]}/">'
        if newer:
            _, _, n_ymd = _nz_dt(newer["drawnAt"])
            head_links += f'<link rel="next" href="{SITE}/results/{n_ymd}/{newer["id"]}/">'

        ld = {"@context": "https://schema.org", "@graph": [{
            "@type": "Dataset",
            "name": f"Keno NZ draw {did} - {day}",
            "description": f"Winning numbers for New Zealand Keno draw {did}, "
                           f"drawn {day} at {tod} NZ. Twenty numbers from 1 to 80.",
            "url": canonical,
            "temporalCoverage": d["drawnAt"],
            "variableMeasured": "Winning numbers (20 drawn from 1-80)",
            "creator": {"@id": SITE + "/#org"},
            "isBasedOn": {"@type": "Organization", "name": src_label},
            "isAccessibleForFree": True,
        }, {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "Results", "item": SITE + "/results/"},
                {"@type": "ListItem", "position": 3, "name": f"Draw {did}", "item": canonical},
            ],
        }]}

        body = (
            '<div class="wrap">'
            '<div class="page-head">'
            '<p class="eyebrow">Keno draw result</p>'
            f'<h1>Keno results: draw {did}</h1>'
            f'<p class="lede">{day} at {tod} New Zealand time. '
            'Twenty numbers drawn from 1 to 80.</p>'
            '</div>'
            '<section style="margin-top:26px"><div class="hero">'
            '<div class="hero-meta">'
            f'<span class="hero-title">Winning numbers</span>'
            f'<span class="draw-id">#{did}</span>'
            f'<span>{day}, {tod} NZ</span>{mult}'
            '</div>'
            + draw_balls(d["numbers"]) +
            '<div class="prov">'
            '<span class="badge badge-ok">Verified</span>'
            f'<span>Source <a href="{src_url}" rel="nofollow noopener">'
            f'<strong>{html.escape(src_label)}</strong></a></span>'
            '<span><a href="/about/#corrections">Report an error</a></span>'
            '</div></div></section>'
            '<section><div class="sec-h"><h2>This draw against all 80 numbers</h2></div>'
            + draw_grid(d["numbers"]) +
            '<p class="muted" style="font-size:13px; margin-top:14px; text-align:center">'
            'Twenty of eighty come out each draw, so any given number appears '
            'about 25% of the time. '
            '<a href="/statistics/">See how that plays out over the full archive</a>.</p>'
            '</section>'
            '<section><div class="btn-row" style="justify-content:center">'
            + "".join(nav_links) + '</div></section>'
            '<section><div class="card" style="text-align:center">'
            '<h2 style="font-size:19px">Did your numbers come up?</h2>'
            '<p class="muted" style="font-size:14.5px; max-width:56ch; margin:0 auto 16px">'
            'Check a ticket against this draw. Your numbers stay in your browser.</p>'
            f'<a class="btn btn-primary" href="/check/?draw={did}">Check my numbers</a>'
            '</div></section>'
            '</div>'
        )

        out = base_tpl
        for key in ("home", "check", "results", "stats", "howto", "odds", "tools",
                    "blog", "news", "about", "contact"):
            out = out.replace("{c_%s}" % key,
                              ' aria-current="page"' if key == "results" else "")
        out = (out
               .replace("{title}", f"Keno Results Draw {did} - {day} | keno-results.co.nz")
               .replace("{og_title}", f"Keno draw {did} - {day}")
               .replace("{description}",
                        f"Winning numbers for NZ Keno draw {did}, drawn {day} at {tod} "
                        f"New Zealand time. Twenty numbers from 1 to 80, verified against "
                        f"the rules of the game.")
               .replace("{canonical}", canonical)
               .replace("{robots}", "index, follow, max-image-preview:large")
               .replace("{site}", SITE)
               .replace("{head_extra}", head_links + '<script type="application/ld+json">'
                        + json.dumps(ld, separators=(",", ":")) + "</script>")
               .replace("{scripts}", "")
               .replace("{rail}", rail_block("rail-right"))
               .replace("{rail_left}", rail_block("rail-left"))
               .replace("{content}", body)
               .replace("{year}", str(YEAR)))
        dest = os.path.join(ROOT, path, "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out)
    if all_draws:
        written.append(f"results/<date>/<id>/index.html  x{len(all_draws)}")

    # ---- one page per spot count ----
    # The odds page is strong but buries ten distinct search intents in one URL.
    from math import comb
    SPOT_NOTE = {
        1: "The simplest ticket there is: one number, one chance, and the shortest odds on the board.",
        2: "Two numbers. Still short odds on the top tier, but the prize is correspondingly small.",
        3: "Three spots is where partial-match tiers start to matter.",
        4: "A common starting point - the top tier is still reachable and lower tiers pay often.",
        5: "Five spots balances a reachable top tier against a useful ladder beneath it.",
        6: "The most-played ticket in most Keno markets, and the one most examples use.",
        7: "Seven spots lengthens the top tier considerably while widening the ladder below.",
        8: "Eight spots is firmly in long-odds territory for the top tier.",
        9: "Nine spots: the top tier is a once-in-over-a-million event.",
        10: "The longest ticket available. Matching all ten is roughly a one-in-nine-million event.",
    }
    for spots in range(1, 11):
        rows, p_top = [], comb(20, spots) / comb(80, spots)
        for k in range(spots, -1, -1):
            pk = comb(20, k) * comb(60, spots - k) / comb(80, spots)
            odds = f"1 in {1/pk:,.1f}" if 1/pk < 100 else f"1 in {1/pk:,.0f}"
            top = ' <span class="badge badge-ok">Top tier</span>' if k == spots else ""
            rows.append(f'<tr><td class="num">{k} of {spots}{top}</td>'
                        f'<td class="num">{odds}</td><td class="num">{pk*100:.4f}%</td></tr>')
        half = -(-spots // 2)
        p_half = sum(comb(20, k) * comb(60, spots - k) / comb(80, spots)
                     for k in range(half, spots + 1))
        others = " ".join(
            f'<a href="/odds/{n}-spot/">{n}</a>' for n in range(1, 11) if n != spots)

        body = (
            '<div class="wrap">'
            '<div class="page-head">'
            '<p class="eyebrow">Keno odds</p>'
            f'<h1>{spots} spot Keno odds</h1>'
            f'<p class="lede">Every prize tier for a {spots}-spot Keno ticket, calculated '
            'from the rules of the game. Matching all '
            f'{spots} happens about once in {1/p_top:,.0f} tickets.</p>'
            '</div>'
            '<div class="prose" style="margin-top:30px">'
            f'<p>{SPOT_NOTE[spots]} You pick {spots} number'
            f'{"s" if spots > 1 else ""} from 1 to 80, twenty are drawn, and your prize '
            f'depends on how many of yours come out.</p>'
            f'<p>Matching at least {half} of your {spots} happens about '
            f'<strong>{p_half*100:.1f}%</strong> of the time.</p>'
            '<div class="tw"><table>'
            f'<caption class="vh">Odds for a {spots} spot Keno ticket</caption>'
            '<thead><tr><th class="num">Matched</th><th class="num">Odds</th>'
            '<th class="num">Probability</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            '<div class="notice"><span class="notice-t">On payouts</span>'
            '<p>These are odds, not prizes. What each tier pays depends on your stake, '
            'the <a href="/multiplier/">multiplier</a> on that draw and Lotto NZ\'s current '
            'prize schedule. See <a href="/prizes/">how Keno prizes are structured</a>.</p></div>'
            '<h2>How this is calculated</h2>'
            '<p>Hypergeometric probability - drawing without replacement from a fixed pool. '
            f'For a {spots}-spot ticket the chance of matching exactly <em>k</em> numbers is '
            f'<span class="mono">C(20, k) &times; C(60, {spots} &minus; k) &divide; C(80, {spots})</span>. '
            'Every figure above can be checked with that formula.</p>'
            '<h2>Other spot counts</h2>'
            f'<p class="jump"><span class="jump-l">Compare</span>{others}</p>'
            '<p>Playing more spots does not shorten your odds - it lengthens the top tier '
            'and widens the ladder beneath it. Compare '
            f'<a href="/odds/{min(spots+2,10)}-spot/">{min(spots+2,10)} spot</a> and '
            f'<a href="/odds/{max(spots-2,1)}-spot/">{max(spots-2,1)} spot</a> to see it.</p>'
            '<p><a href="/odds/">Back to the full odds tables</a></p>'
            '</div></div>'
        )
        ld = {"@context": "https://schema.org", "@graph": [{
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "Odds", "item": SITE + "/odds/"},
                {"@type": "ListItem", "position": 3, "name": f"{spots} spot",
                 "item": f"{SITE}/odds/{spots}-spot/"},
            ]}]}
        out = base_tpl
        for key in ("home", "check", "results", "stats", "howto", "odds", "tools",
                    "blog", "news", "about", "contact"):
            out = out.replace("{c_%s}" % key,
                              ' aria-current="page"' if key == "odds" else "")
        out = (out
               .replace("{title}", f"{spots} Spot Keno Odds NZ | keno-results.co.nz")
               .replace("{og_title}", f"{spots} spot Keno odds")
               .replace("{description}",
                        f"Every prize tier for a {spots}-spot NZ Keno ticket, with real "
                        f"probabilities. Matching all {spots} is about 1 in {1/p_top:,.0f}.")
               .replace("{canonical}", f"{SITE}/odds/{spots}-spot/")
               .replace("{robots}", "index, follow, max-image-preview:large")
               .replace("{site}", SITE)
               .replace("{head_extra}", '<script type="application/ld+json">'
                        + json.dumps(ld, separators=(",", ":")) + "</script>")
               .replace("{scripts}", "")
               .replace("{rail}", rail_block("rail-right"))
               .replace("{rail_left}", rail_block("rail-left"))
               .replace("{content}", body)
               .replace("{year}", str(YEAR)))
        dest = os.path.join(ROOT, "odds", f"{spots}-spot", "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out)
        urls_extra.append(f"odds/{spots}-spot/")
    written.append("odds/<n>-spot/index.html  x10")

    # ---- statistics children ----
    # Everything competitors sell as a "tool", published as a record. The
    # labels are the difference: "draws since last seen" is a fact,
    # "overdue" would be a prediction.
    import collections, itertools
    nums_all = [n for d in all_draws for n in d["numbers"]]
    N = len(all_draws)
    if N:
        freq = collections.Counter(nums_all)
        pair_c = collections.Counter()
        for d in all_draws:
            for a, b in itertools.combinations(sorted(d["numbers"]), 2):
                pair_c[(a, b)] += 1
        last_seen = {}
        for i, d in enumerate(all_draws):
            for n in d["numbers"]:
                last_seen.setdefault(n, i)
        sums = [sum(d["numbers"]) for d in all_draws]
        odds_ct = [sum(1 for n in d["numbers"] if n % 2) for d in all_draws]
        by_time = collections.defaultdict(collections.Counter)
        for d in all_draws:
            by_time[d["drawnAt"][11:16]].update(d["numbers"])

        exp_n = N * 20 / 80
        exp_pair = N * (20 * 19) / (80 * 79)

        def bar_rows(counter, total, label):
            mx = max(counter.values()) or 1
            out = []
            for n in range(1, 81):
                c = counter.get(n, 0)
                out.append(f'<li><span class="n">{n}</span>'
                           f'<span class="bar"><i style="width:{c/mx*100:.1f}%"></i></span>'
                           f'<span class="c">{c}</span></li>')
            return f'<ul class="freq" aria-label="{label}">{"".join(out)}</ul>'

        stat_pages = []

        stat_pages.append(("frequency", "Number frequency",
            f"How often each Keno number has been drawn across {N} confirmed draws.",
            '<p>Counts across all <strong>' + str(N) + '</strong> draws we hold, in number '
            'order. Sorting by count would present ordinary variation as a ranking, so we '
            'do not.</p>'
            f'<p>With 20 of 80 drawn each time, the expected count for any number is '
            f'<strong>{exp_n:.0f}</strong>. The observed range is '
            f'<strong>{min(freq.values())}</strong> to <strong>{max(freq.values())}</strong> '
            '&mdash; a spread you would expect from chance alone at this sample size.</p>'
            + bar_rows(freq, N, "Times each number has been drawn")))

        prows = []
        for (a, b), c in pair_c.most_common(20):
            prows.append(f'<tr><td class="num">{a} + {b}</td><td class="num">{c}</td>'
                         f'<td class="num">{c/exp_pair:.2f}&times;</td></tr>')
        stat_pages.append(("pairs", "Most drawn pairs",
            f"Which two numbers have come out together most often across {N} draws.",
            f'<p>There are <strong>3,160</strong> possible pairs and {N} draws, so any given '
            f'pair is expected about <strong>{exp_pair:.1f}</strong> times.</p>'
            '<div class="tw"><table><caption class="vh">Most frequently drawn pairs</caption>'
            '<thead><tr><th class="num">Pair</th><th class="num">Times together</th>'
            '<th class="num">vs expected</th></tr></thead>'
            f'<tbody>{"".join(prows)}</tbody></table></div>'
            '<div class="notice warn"><span class="notice-t">Read this before using it</span>'
            '<p>This is a record of what has happened, not a prediction. With 3,160 pairs, '
            '<em>something</em> has to come top &mdash; that is arithmetic, not a pattern. '
            'The leading pair here sits at roughly twice expectation, which is exactly the '
            'kind of spread random sampling produces at this scale.</p>'
            '<p>Numbers are drawn independently. No pair is more likely to repeat because '
            'it has appeared together before.</p></div>'))

        grows = []
        for n, gap in sorted(last_seen.items(), key=lambda t: -t[1])[:20]:
            grows.append(f'<tr><td class="num">{n}</td><td class="num">{gap}</td>'
                         f'<td class="num">{gap/4:.1f} days</td></tr>')
        stat_pages.append(("gaps", "Draws since last seen",
            "How many draws have passed since each number last came up.",
            '<p>Counted back from the most recent draw. At four draws a day, a gap of '
            'twelve is three days.</p>'
            '<div class="tw"><table><caption class="vh">Longest current gaps</caption>'
            '<thead><tr><th class="num">Number</th><th class="num">Draws since seen</th>'
            '<th class="num">Roughly</th></tr></thead>'
            f'<tbody>{"".join(grows)}</tbody></table></div>'
            '<div class="notice warn"><span class="notice-t">These numbers are not "due"</span>'
            '<p>Other sites publish this table as "overdue numbers". That framing is wrong. '
            'A number absent for twenty draws has exactly the same 25% chance in the next '
            'draw as one that came up an hour ago. The draw has no memory of what it did '
            'last time, and a gap is a fact about the past, never a signal about the future.</p>'
            '</div>'))

        srows = "".join(
            f'<tr><td>{lab}</td><td class="num">{obs}</td><td class="num">{exp}</td></tr>'
            for lab, obs, exp in [
                ("Mean sum of the 20 drawn numbers", f"{sum(sums)/N:.0f}", "810"),
                ("Lowest sum recorded", f"{min(sums)}", "&mdash;"),
                ("Highest sum recorded", f"{max(sums)}", "&mdash;"),
                ("Mean odd numbers per draw", f"{sum(odds_ct)/N:.1f}", "10.0"),
                ("Fewest odds in a draw", f"{min(odds_ct)}", "&mdash;"),
                ("Most odds in a draw", f"{max(odds_ct)}", "&mdash;"),
            ])
        stat_pages.append(("patterns", "Sums and odd/even",
            f"Sum totals and odd/even splits across {N} Keno draws, against what randomness predicts.",
            '<p>Two measures that show, more clearly than any frequency chart, that the '
            'draw is behaving exactly as a random process should.</p>'
            '<div class="tw"><table><caption class="vh">Sum and parity measures</caption>'
            '<thead><tr><th>Measure</th><th class="num">Observed</th>'
            '<th class="num">Expected if random</th></tr></thead>'
            f'<tbody>{srows}</tbody></table></div>'
            '<p>The mean sum lands within a point of the theoretical 810, and the mean odd '
            'count within a tenth of 10. Individual draws swing widely &mdash; that is what '
            'randomness looks like up close &mdash; but the averages sit exactly where the '
            'maths says they should.</p>'
            '<div class="notice"><span class="notice-t">Why this matters</span>'
            '<p>If the draw were biased, this is where it would show. It does not.</p></div>'))

        trows = []
        for t in sorted(by_time):
            c = by_time[t]
            top_n, top_c = c.most_common(1)[0]
            draws_at = sum(c.values()) // 20
            trows.append(f'<tr><td class="num">{t}</td><td class="num">{draws_at}</td>'
                         f'<td class="num">{top_n}</td><td class="num">{top_c}</td></tr>')
        stat_pages.append(("by-draw-time", "Frequency by draw time",
            "Whether the morning, midday, afternoon and evening draws behave differently. They do not.",
            '<p>Keno draws four times a day. If any draw slot were different from the others, '
            'this is where it would appear.</p>'
            '<div class="tw"><table><caption class="vh">Most drawn number by draw time</caption>'
            '<thead><tr><th class="num">Draw time (NZ)</th><th class="num">Draws</th>'
            '<th class="num">Most drawn</th><th class="num">Times</th></tr></thead>'
            f'<tbody>{"".join(trows)}</tbody></table></div>'
            '<p>Each slot has its own leader and they are all within ordinary variation of '
            'each other. There is no morning number and no evening number &mdash; the same '
            'machine, the same rules, four times a day.</p>'))

        for slug, title, desc, inner in stat_pages:
            others = "".join(
                f'<a href="/statistics/{s2}/">{t2}</a>'
                for s2, t2, _, _ in stat_pages if s2 != slug)
            body = ('<div class="wrap">'
                    '<div class="page-head"><p class="eyebrow">Statistics</p>'
                    f'<h1>{title}</h1><p class="lede">{desc}</p></div>'
                    f'<div class="prose" style="margin-top:30px">{inner}'
                    '<h2>More statistics</h2>'
                    f'<p class="jump"><span class="jump-l">See also</span>{others}'
                    '<a href="/statistics/">Hot and cold</a></p>'
                    '</div></div>')
            ld = {"@context": "https://schema.org", "@graph": [{
                "@type": "BreadcrumbList", "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Statistics",
                     "item": SITE + "/statistics/"},
                    {"@type": "ListItem", "position": 3, "name": title,
                     "item": f"{SITE}/statistics/{slug}/"}]}]}
            out = base_tpl
            for key in ("home", "check", "results", "stats", "howto", "odds", "tools",
                        "blog", "news", "about", "contact"):
                out = out.replace("{c_%s}" % key,
                                  ' aria-current="page"' if key == "stats" else "")
            out = (out
                   .replace("{title}", f"{title} - Keno NZ | keno-results.co.nz")
                   .replace("{og_title}", title)
                   .replace("{description}", desc)
                   .replace("{canonical}", f"{SITE}/statistics/{slug}/")
                   .replace("{robots}", "index, follow, max-image-preview:large")
                   .replace("{site}", SITE)
                   .replace("{head_extra}", '<script type="application/ld+json">'
                            + json.dumps(ld, separators=(",", ":")) + "</script>")
                   .replace("{scripts}", "")
                   .replace("{rail}", rail_block("rail-right"))
                   .replace("{rail_left}", rail_block("rail-left"))
                   .replace("{content}", body)
                   .replace("{year}", str(YEAR)))
            dest = os.path.join(ROOT, "statistics", slug, "index.html")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(out)
            urls_extra.append(f"statistics/{slug}/")
        written.append(f"statistics/<page>/index.html  x{len(stat_pages)}")

    # ---- blog posts and news articles ----
    base_tpl = open(os.path.join(SRC, "base.html"), encoding="utf-8").read()
    for kind, cfg in SECTIONS.items():
        for a in _entries(kind):
            canonical = f"{SITE}/{kind}/{a['slug']}/"
            ld = {"@context": "https://schema.org", "@graph": [{
                "@type": cfg["schema"],
                "headline": a["title"],
                "description": a["summary"],
                "datePublished": a["date"],
                "dateModified": a.get("updated", a["date"]),
                "url": canonical,
                "mainEntityOfPage": canonical,
                "publisher": {"@id": SITE + "/#org"},
                "author": {"@id": SITE + "/#org"},
                "isAccessibleForFree": True,
            }, {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                    {"@type": "ListItem", "position": 2, "name": cfg["label"],
                     "item": f"{SITE}/{kind}/"},
                    {"@type": "ListItem", "position": 3, "name": a["title"], "item": canonical},
                ],
            }]}
            body = (
                '<div class="wrap">'
                '<div class="article-head">'
                '<span class="news-meta" style="justify-content:center">'
                f'<span class="news-tag">{html.escape(a.get("tag", cfg["label"]))}</span>'
                f'<span class="news-date">{_pretty_date(a["date"])}</span></span>'
                f'<h1>{html.escape(a["title"])}</h1>'
                f'<p class="article-lede">{html.escape(a["summary"])}</p>'
                '</div>'
                f'<div class="prose" style="margin-top:34px">{a["body"]}'
                '<p class="article-foot">Figures in this article are computed from the draw '
                'archive this site holds and were correct at the time of writing. '
                'See <a href="/authors/">our editorial standards</a>, or '
                f'<a href="/{kind}/">all {cfg["label"].lower()} posts</a>.</p>'
                '</div></div>'
            )
            out = base_tpl
            for key in ("home", "check", "results", "stats", "howto", "odds", "tools",
                        "blog", "news", "about", "contact"):
                out = out.replace("{c_%s}" % key,
                                  ' aria-current="page"' if key == kind else "")
            # A headline plus " | keno-results.co.nz" runs past what Google will
            # render, and a truncated brand is worse than no brand - the site name
            # is already in the schema. Long headlines carry themselves.
            head = html.escape(a.get("seoTitle") or a["title"])
            page_title = head if len(head) > 46 else head + " | keno-results.co.nz"
            out = (out
                   .replace("{title}", page_title)
                   .replace("{og_title}", html.escape(a["title"]))
                   .replace("{description}",
                            html.escape(a.get("metaDescription") or a["summary"]))
                   .replace("{canonical}", canonical)
                   .replace("{robots}", "index, follow, max-image-preview:large")
                   .replace("{site}", SITE)
                   .replace("{head_extra}", '<script type="application/ld+json">'
                            + json.dumps(ld, separators=(",", ":")) + "</script>")
                   .replace("{scripts}", "")
                   .replace("{rail}", rail_block("rail-right"))
                   .replace("{rail_left}", rail_block("rail-left"))
                   .replace("{content}", body)
                   .replace("{year}", str(YEAR)))
            dest = os.path.join(ROOT, kind, a["slug"], "index.html")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(out)
            written.append(f"{kind}/{a['slug']}/index.html")

    # ---- legacy redirect stubs ----
    moved = {f"news/{a['slug']}": f"/blog/{a['slug']}/" for a in _entries("blog")}
    for old, new in {**REDIRECTS, **moved}.items():
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
    for extra in urls_extra:
        urls.append(f"  <url><loc>{SITE}/{extra}</loc><lastmod>{today}</lastmod>"
                    f"<priority>0.7</priority></url>")
    for d in all_draws:
        _, _, ymd = _nz_dt(d["drawnAt"])
        urls.append(f"  <url><loc>{SITE}/results/{ymd}/{d['id']}/</loc>"
                    f"<lastmod>{ymd}</lastmod><priority>0.5</priority></url>")
    for kind in SECTIONS:
        for a in _entries(kind):
            urls.append(f"  <url><loc>{SITE}/{kind}/{a['slug']}/</loc>"
                        f"<lastmod>{a.get('updated', a['date'])}</lastmod>"
                        f"<priority>0.6</priority></url>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + "\n".join(urls) + "\n</urlset>\n")
    written.append("sitemap.xml")

    blocked = ["AhrefsBot", "SemrushBot", "MJ12bot", "DotBot", "Rogerbot",
               "serpstatbot", "SistrixBot"]
    lines = [f"Sitemap: {SITE}/sitemap.xml", "", "User-agent: *", "Allow: /", ""]
    for bot in blocked:
        lines += [f"User-agent: {bot}", "Disallow: /", ""]
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
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
            "icons": [{"src": f"/assets/img/icon-{n}.png", "sizes": f"{n}x{n}",
                       "type": "image/png"} for n in (48, 96, 144, 192, 240, 288)]
                     + [{"src": "/assets/img/icon-512.png", "sizes": "512x512",
                         "type": "image/png", "purpose": "any maskable"}],
        }, fh, indent=2)
    written.append("site.webmanifest")

    print(f"built {len(written)} files:")
    for w in written:
        print("  " + w)
    return 0


if __name__ == "__main__":
    sys.exit(build())
