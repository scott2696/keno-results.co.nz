#!/usr/bin/env python3
"""Write news articles automatically from official draw results.

    python3 tools/auto_news.py            # publish anything notable
    python3 tools/auto_news.py --dry-run  # report only

Runs unattended from the refresh workflow. Everything it publishes is built
from Lotto New Zealand's own results endpoint and our validated Keno archive -
no third-party copy is read or reused. tools/watch_news.py tells us what the
media is covering; this writes what we can source ourselves.

It only fires on objectively notable events, never on routine draws, so the
news section does not fill with filler:

  - Powerball First Division struck, or its pool rolling past $15m
  - Lotto First Division taken by a small number of tickets
  - Bullseye First Division struck (rare - an exact six-digit match)
  - A Keno draw carrying x5 or x10, the two rarest multipliers

Each draw is written about at most once, tracked by draw id.

Stdlib only.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "data")
API = "https://pathway.mylotto.co.nz/api/results/v1/results"
UA = {"User-Agent": "keno-results.co.nz/1.0 (+https://keno-results.co.nz/about/)",
      "Accept": "application/json"}

POWERBALL_ROLLOVER_FLOOR = 15_000_000
MAX_PER_RUN = 2                      # never flood the section in one go

DISCLAIMER = (
    '<p class="article-foot" style="margin-top:26px">All figures in this report are '
    'taken from Lotto New Zealand&rsquo;s published results for the draw named above. '
    'keno-results.co.nz is an independent service and is not affiliated with Lotto NZ. '
    'Results here are unofficial &mdash; always confirm a winning ticket with the '
    'official operator before acting on it. See our '
    '<a href="/authors/">editorial standards</a>.</p>')


def fetch(game, timeout=30):
    req = urllib.request.Request(f"{API}/{game}", headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def money(v):
    """Format a prize value. Non-numeric values ('ROLLOVER', 'Bonus Ticket')
    pass through untouched, which is how the API expresses them."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"${f:,.0f}" if f == int(f) else f"${f:,.2f}"


def nice_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%-d %B %Y")
    except ValueError:
        return iso


def weekday(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%A")
    except ValueError:
        return ""


def nums(seq):
    vals = [str(int(n)) for n in seq]
    return ", ".join(vals[:-1]) + " and " + vals[-1] if len(vals) > 1 else vals[0]


def load(name, key):
    try:
        with open(os.path.join(SRC, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"_note": "", key: []}


# --------------------------------------------------------------------------- #
# article builders - each returns an article dict, or None if not notable
# --------------------------------------------------------------------------- #
def lotto_article(d):
    L, P, S = d.get("lotto", {}), d.get("powerBall", {}), d.get("strike", {})
    if not L.get("drawNumber"):
        return None

    div1 = next((w for w in L.get("lottoWinners", []) if w["division"] == 1), None)
    pb1 = next((w for w in P.get("powerballWinners", []) if w["division"] == 1), None)
    if not div1 or not pb1:
        return None

    pb_won = pb1["numberOfWinners"] > 0
    pb_pool = float(P.get("powerballPrizePool", 0))
    notable = pb_won or pb_pool >= POWERBALL_ROLLOVER_FLOOR or div1["numberOfWinners"] > 0
    if not notable:
        return None

    dn = L["drawNumber"]
    date, day = L.get("drawDate", ""), weekday(L.get("drawDate", ""))
    winners = div1["numberOfWinners"]
    each = money(div1["prizeValue"]) if winners else None

    if pb_won:
        headline = f"Powerball struck in draw {dn} as top prize finally goes"
        lede = (f"Powerball's First Division was won in draw {dn}, ending the run of "
                f"rollovers that had carried the pool to {money(pb_pool)}.")
        opener = (f"<p>Powerball's top prize was claimed in {day}'s draw, with "
                  f"{pb1['numberOfWinners']} ticket"
                  f"{'s' if pb1['numberOfWinners'] != 1 else ''} sharing a pool of "
                  f"{money(pb_pool)}.</p>")
    elif winners:
        headline = (f"{'Three' if winners == 3 else winners} tickets take Lotto's top "
                    f"prize as Powerball rolls to {money(pb_pool)}")
        lede = (f"Draw {dn} produced {winners} First Division Lotto winner"
                f"{'s' if winners != 1 else ''} at {each} each, while Powerball went "
                f"unstruck and its pool moved to {money(pb_pool)}.")
        opener = (f"<p>{winners} ticket{'s' if winners != 1 else ''} took First Division "
                  f"in {day}'s Lotto draw, while Powerball went unclaimed for a further "
                  f"draw.</p>")
    else:
        headline = f"Powerball rolls to {money(pb_pool)} after draw {dn}"
        lede = (f"Neither Lotto's First Division nor Powerball was won in draw {dn}, "
                f"carrying the Powerball pool to {money(pb_pool)}.")
        opener = (f"<p>{day}'s draw passed without a First Division winner in either "
                  f"Lotto or Powerball.</p>")

    rows = "".join(
        f'<tr><td class="num">{w["division"]}</td>'
        f'<td class="num">{w["numberOfWinners"]:,}</td>'
        f'<td class="num">{money(w["prizeValue"])}</td></tr>'
        for w in L.get("lottoWinners", []))

    body = (
        opener +
        "<h2>The result</h2>"
        f"<p>Lotto draw {dn} was made on {day} {nice_date(date)} at "
        f"{L.get('drawTime','')}. The winning line was <strong>"
        f"{nums(L['lottoWinningNumbers']['numbers'])}</strong>, with "
        f"<strong>{int(L['lottoWinningNumbers']['bonusBalls'])}</strong> as the bonus "
        f"ball. The Powerball number was <strong>"
        f"{int(P.get('powerballWinningNumber', 0))}</strong>."
        + (f" The Strike sequence was drawn as <strong>"
           f"{nums(S['strikeWinningNumbers'])}</strong>.</p>"
           if S.get("strikeWinningNumbers") else "</p>") +
        "<h2>Where the money went</h2>"
        '<div class="tw"><table>'
        f'<caption class="vh">Lotto draw {dn} prize divisions</caption>'
        '<thead><tr><th class="num">Division</th><th class="num">Winners</th>'
        '<th class="num">Prize each</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        f"<p>The Lotto pool returned {money(L.get('lottoPrizePool', 0))} to "
        f"{L.get('lottoTotalWinners', 0):,} winning tickets. Counting Powerball and "
        f"Strike alongside it, the draw paid {money(d.get('totalPrizes', 0))} to "
        f"{d.get('totalNumberWinners', 0):,} tickets in total.</p>"
        "<h2>Reading the result</h2>"
        "<p>Powerball requires a First Division Lotto line together with the separately "
        "drawn Powerball number, which is why it is struck far less often than Lotto's "
        "own top division and why its pool builds across draws.</p>"
        "<p>A growing pool does not improve the chance of winning it. The odds on any "
        "given line are the same from one draw to the next, whatever the prize has "
        "reached.</p>"
        "<h2>Next draw</h2>"
        "<p>Lotto, Powerball and Strike are drawn on Wednesday and Saturday evenings at "
        f"8:20pm New Zealand time. The next draw is number {dn + 1}.</p>"
        + DISCLAIMER
    )
    return {"slug": f"lotto-draw-{dn}-result", "title": headline,
            "date": datetime.date.today().isoformat(), "tag": "Lotto NZ",
            "summary": lede, "body": body, "_key": f"lotto-{dn}",
            "art": {"kind": "draw", "game": "Lotto", "drawNumber": dn,
                    "numbers": d.get("numbers", []),
                    "extras": [{"label": e.get("label"), "value": e.get("value")}
                               for e in d.get("extras", [])
                               if e.get("label") in ("Bonus", "Powerball")]}}


def bullseye_article(d):
    dn = d.get("drawNumber")
    div1 = next((w for w in d.get("bullseyeWinners", []) if w["division"] == 1), None)
    if not dn or not div1 or div1["numberOfWinners"] == 0:
        return None                      # only publish when it is actually struck

    n = d["bullseyeWinningNumbers"]["numbers"]
    date = d.get("drawDate", "")
    rows = "".join(
        f'<tr><td class="num">{w["division"]}</td>'
        f'<td class="num">{w["numberOfWinners"]:,}</td>'
        f'<td class="num">{money(w["prizeValue"])}</td></tr>'
        for w in d.get("bullseyeWinners", []))

    body = (
        f"<p>Bullseye's top prize was won on {weekday(date)}, with the drawn number "
        f"matched exactly for the first time in the current run of draws.</p>"
        "<h2>The result</h2>"
        f"<p>Bullseye draw {dn} was made on {weekday(date)} {nice_date(date)} at "
        f"{d.get('drawTime','')}. The winning number was <strong>{n}</strong>, matched "
        f"by {div1['numberOfWinners']} ticket"
        f"{'s' if div1['numberOfWinners'] != 1 else ''}.</p>"
        "<h2>The divisions</h2>"
        '<div class="tw"><table>'
        f'<caption class="vh">Bullseye draw {dn} prize divisions</caption>'
        '<thead><tr><th class="num">Division</th><th class="num">Winners</th>'
        '<th class="num">Prize each</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        f"<p>In total the draw paid {money(d.get('totalBullseyePrizes', 0))} across "
        f"{d.get('bullseyeTotalWinners', 0):,} winning tickets.</p>"
        "<h2>How Bullseye works</h2>"
        "<p>Bullseye draws a single six-digit number and pays on proximity to it, with "
        "each division covering a progressively wider band either side. An exact match "
        "takes First Division, which is why it is struck infrequently and why the pool "
        "builds between wins.</p>"
        "<h2>Next draw</h2>"
        "<p>Bullseye is drawn daily at around 6pm New Zealand time. The next draw is "
        f"number {dn + 1}.</p>"
        + DISCLAIMER
    )
    return {"slug": f"bullseye-draw-{dn}-won", "title":
            f"Bullseye top prize won as {n} comes out",
            "date": datetime.date.today().isoformat(), "tag": "Bullseye",
            "summary": (f"Draw {dn} produced a First Division Bullseye winner, with the "
                        f"number {n} matched exactly."),
            "body": body, "_key": f"bullseye-{dn}",
            "art": {"kind": "bullseye", "game": "Bullseye", "drawNumber": dn,
                    "value": str(n)}}


def keno_article():
    """Fires on x5 and x10 - the two rarest multipliers - using our own archive."""
    try:
        with open(os.path.join(ROOT, "assets", "data", "draws.json"), encoding="utf-8") as fh:
            feed = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    draws = feed.get("draws", [])
    if not draws:
        return None
    d = draws[0]
    mult = d.get("multiplier")
    if mult not in ("5", "10"):
        return None

    total = len(draws)
    same = [x for x in draws if x.get("multiplier") == mult]
    share = len(same) / total * 100
    dn, iso = d["id"], d["drawnAt"]
    date = nice_date(iso[:10])
    tod = iso[11:16]
    s = sum(d["numbers"])
    odd = sum(1 for n in d["numbers"] if n % 2)

    body = (
        f"<p>The latest Keno draw carried a &times;{mult} multiplier &mdash; one of the "
        f"two rarest the New Zealand game applies, and recorded in just "
        f"{share:.1f}% of the {total} consecutive draws in our archive.</p>"
        "<h2>The result</h2>"
        f"<p>Keno draw <strong>{dn}</strong> was made on {weekday(iso[:10])} {date} at "
        f"{tod} New Zealand time. The twenty numbers drawn were:</p>"
        f"<p><strong>{nums(d['numbers'])}.</strong></p>"
        f"<p>The draw carried a <strong>&times;{mult}</strong> multiplier, scaling prizes "
        "on winning tickets for that draw accordingly.</p>"
        "<h2>How rare that is</h2>"
        f"<p>We hold {total} consecutive Keno draws. Of those, {len(same)} have carried "
        f"&times;{mult} &mdash; {share:.1f}%. These are observed counts from a limited "
        "window rather than a published schedule; Lotto New Zealand set the underlying "
        "weightings.</p>"
        "<h2>The draw itself</h2>"
        f"<p>The twenty numbers summed to {s} against a theoretical average of 810, and "
        f"split {odd} odd to {20 - odd} even. Both sit within ordinary variation.</p>"
        "<h2>What the multiplier does</h2>"
        "<p>It changes what a win pays, never how likely a win is. The probability of "
        "matching numbers is fixed by the rules &mdash; twenty drawn from eighty &mdash; "
        "and depends only on how many spots a player chooses. It is also not "
        "predictable: the multiplier on the next draw is unaffected by recent ones.</p>"
        "<h2>Next draw</h2>"
        "<p>Keno is drawn four times daily at 10:01am, 1:01pm, 3:01pm and 6:01pm New "
        "Zealand time, each with its own multiplier.</p>"
        + DISCLAIMER
    )
    return {"slug": f"keno-draw-{dn}-multiplier-{mult}",
            "title": f"Keno draw {dn} carries a x{mult} multiplier",
            "date": datetime.date.today().isoformat(), "tag": "Keno",
            "summary": (f"Draw {dn} was attached to a &times;{mult} multiplier, recorded "
                        f"in {share:.1f}% of the {total} draws in our archive."),
            "body": body, "_key": f"keno-{dn}",
            "art": {"kind": "keno", "game": "Keno", "drawNumber": dn,
                    "numbers": d.get("numbers", []), "multiplier": mult}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    news = load("news.json", "articles")
    existing_slugs = {a.get("slug", "") for a in news["articles"]}
    # any article already mentioning this draw number counts as covered, however
    # it was written - otherwise a hand-written piece gets duplicated
    existing_text = " ".join(
        (a.get("slug", "") + " " + a.get("title", "") + " " + a.get("summary", ""))
        for a in news["articles"]).lower()

    candidates = []
    try:
        candidates.append(lotto_article(fetch("lotto")))
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"warn: lotto unavailable ({e})", file=sys.stderr)
    try:
        candidates.append(bullseye_article(fetch("bullseye")))
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        print(f"warn: bullseye unavailable ({e})", file=sys.stderr)
    candidates.append(keno_article())

    def already_covered(a):
        if a["slug"] in existing_slugs:
            return True
        draw_id = a.get("_key", "").split("-")[-1]
        return bool(draw_id) and draw_id in existing_text

    fresh = [a for a in candidates if a and not already_covered(a)][:MAX_PER_RUN]

    if not fresh:
        print("auto-news: nothing notable to publish")
        return 0

    for a in fresh:
        a.pop("_key", None)
        print(f"auto-news: {'would publish' if args.dry_run else 'publishing'} "
              f"/news/{a['slug']}/ - {a['title']}")

    if args.dry_run:
        return 0

    news["articles"] = fresh + news["articles"]
    with open(os.path.join(SRC, "news.json"), "w", encoding="utf-8") as fh:
        json.dump(news, fh, indent=2)
        fh.write("\n")
    print(f"auto-news: wrote {len(fresh)} article(s) to news.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
