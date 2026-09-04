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
         desc="Every confirmed New Zealand Keno draw we hold, newest first, "
              "with winning numbers and draw identifiers.",
         js=["results"], schema=["dataset"]),
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
    dict(slug="news", src="news", nav="news",
         title="Keno News & Analysis NZ | keno-results.co.nz",
         og="Keno news and analysis",
         desc="Analysis drawn from our own New Zealand Keno draw archive - hot and cold "
              "numbers, multiplier data and draw schedule, with the working shown."),
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


def _news():
    try:
        with open(os.path.join(SRC, "data", "news.json"), encoding="utf-8") as fh:
            arts = json.load(fh).get("articles", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return sorted(arts, key=lambda a: a.get("date", ""), reverse=True)


def _pretty_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%-d %B %Y")
    except ValueError:
        return iso


def news_list():
    """Cards for the /news/ index."""
    arts = _news()
    if not arts:
        return ('<div class="empty"><h3>Nothing published yet</h3>'
                '<p>Analysis will appear here.</p></div>')
    items = []
    for a in arts:
        items.append(
            f'<li><a class="news-card" href="/news/{a["slug"]}/">'
            f'<span class="news-meta">'
            f'<span class="news-tag">{html.escape(a.get("tag", "Analysis"))}</span>'
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
    return f'<ul class="news-list">{"".join(items)}</ul>'


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
            headline = f'<span class="rail-bonus">{o["bonus"]}</span>'

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
        for key in ("home", "check", "results", "stats", "howto", "odds", "news", "about", "contact"):
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
                   .replace("{newslist}", news_list()))
               .replace("{year}", str(YEAR)))

        rel = page.get("path") or ("index.html" if not slug else f"{slug}/index.html")
        dest = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(dest) or ROOT, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out)
        written.append(rel)

    # ---- news articles ----
    base_tpl = open(os.path.join(SRC, "base.html"), encoding="utf-8").read()
    for a in _news():
        canonical = f"{SITE}/news/{a['slug']}/"
        ld = {"@context": "https://schema.org", "@graph": [{
            "@type": "NewsArticle",
            "headline": a["title"],
            "description": a["summary"],
            "datePublished": a["date"],
            "dateModified": a["date"],
            "url": canonical,
            "mainEntityOfPage": canonical,
            "publisher": {"@id": SITE + "/#org"},
            "author": {"@id": SITE + "/#org"},
            "isAccessibleForFree": True,
        }, {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "News", "item": SITE + "/news/"},
                {"@type": "ListItem", "position": 3, "name": a["title"], "item": canonical},
            ],
        }]}
        body = (
            '<div class="wrap">'
            '<div class="article-head">'
            f'<span class="news-meta" style="justify-content:center">'
            f'<span class="news-tag">{html.escape(a.get("tag", "Analysis"))}</span>'
            f'<span class="news-date">{_pretty_date(a["date"])}</span></span>'
            f'<h1>{html.escape(a["title"])}</h1>'
            f'<p class="article-lede">{html.escape(a["summary"])}</p>'
            '</div>'
            f'<div class="prose" style="margin-top:34px">{a["body"]}'
            '<p class="article-foot">Figures in this article are computed from the draw '
            'archive this site holds and were correct at the time of writing. '
            'See <a href="/authors/">our editorial standards</a>, or '
            '<a href="/news/">all articles</a>.</p>'
            '</div></div>'
        )
        out = base_tpl
        for key in ("home", "check", "results", "stats", "howto", "odds", "news"):
            out = out.replace("{c_%s}" % key, ' aria-current="page"' if key == "news" else "")
        out = (out
               .replace("{title}", html.escape(a["title"]) + " | keno-results.co.nz")
               .replace("{og_title}", html.escape(a["title"]))
               .replace("{description}", html.escape(a["summary"]))
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
        dest = os.path.join(ROOT, "news", a["slug"], "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(out)
        written.append(f"news/{a['slug']}/index.html")

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
    for a in _news():
        urls.append(f"  <url><loc>{SITE}/news/{a['slug']}/</loc>"
                    f"<lastmod>{a['date']}</lastmod><priority>0.6</priority></url>")
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
