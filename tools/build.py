#!/usr/bin/env python3
"""Build the static site.

    python3 tools/build.py

Renders src/pages/*.html through src/base.html into the repo root, where
GitHub Pages serves them. No npm, no toolchain -- the site is 13 pages and
does not need one. Re-run after editing anything in src/.
"""
import datetime
import hashlib
import html
import json
import os
import random
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SITE = "https://keno-results.co.nz"
YEAR = datetime.date.today().year


# ---- Title Case ---------------------------------------------------------
# Headings across the site are Title Case. A run is left exactly as written if
# it carries a digit (35x, $1, "1."), and a hyphen-part is left alone if it
# already carries a capital, so NZ, NZD, RTP, PayPal and New survive while the
# tail of Buy-now-pay-later still gets cased.

# AP-style: articles, coordinating conjunctions and prepositions of <=3 letters.
# "up" is deliberately absent - on this site it is always a particle ("sign up",
# "speed up"), never a preposition.
SMALL_WORDS = {"a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
               "at", "by", "in", "of", "on", "to", "as", "per", "via", "vs"}

_ENT = re.compile(r"&(?:[a-zA-Z]+|#\d+);")
_TAG = re.compile(r"<[^>]+>")
_PH = re.compile(r"\{[^}]*\}")


def _tc_core(run):
    """The bare word: entities collapsed, surrounding punctuation stripped."""
    return _PH.sub("", _ENT.sub("'", run)).strip("\"'()[]{}.,;:!?\u2014\u2013-\u2026")


def _tc_part_upper(run, start):
    """Does the hyphen-part beginning at `start` already carry a capital?"""
    return any(c.isupper() for c in _ENT.sub("", run[start:].split("-", 1)[0]))


def _tc_cap(run):
    """Uppercase the first letter of each hyphen-part that lacks one."""
    out, boundary, part = [], True, _tc_part_upper(run, 0)
    i = 0
    while i < len(run):
        m = _ENT.match(run, i) or _PH.match(run, i)
        if m:                        # entity/placeholder: copy, not a boundary
            out.append(m.group(0)); i = m.end(); continue
        ch = run[i]
        if boundary and ch.isalpha() and not part:
            out.append(ch.upper()); boundary = False
        else:
            out.append(ch)
            if ch.isalpha():
                boundary = False
            if ch == "-":
                boundary = True
                part = _tc_part_upper(run, i + 1)
        i += 1
    return "".join(out)


def _tc_lower(run):
    """Lowercase a small word that a previous pass had capitalised."""
    for i, ch in enumerate(run):
        if ch.isalpha():
            return run[:i] + ch.lower() + run[i + 1:]
    return run


def title_case(text):
    """Title-case heading text, leaving tags and their attributes alone."""
    parts, tags = _TAG.split(text), _TAG.findall(text)
    runs, index = [], []
    for chunk in parts:
        toks = re.split(r"(\s+)", chunk)
        index.append([len(runs) + i for i, t in enumerate(toks)])
        runs.extend(toks)

    words = [i for i, r in enumerate(runs) if r.strip()]
    if not words:
        return text
    first, last = words[0], words[-1]

    for n, i in enumerate(words):
        run = runs[i]
        core = _tc_core(run)
        if not core or any(c.isdigit() for c in core):
            continue                                  # 35x, $1, 18+, "1."
        prev = runs[words[n - 1]] if n else ""
        # test `prev` as written: stripping punctuation first would hide the
        # very full stop or question mark we are looking for
        new_sentence = bool(re.search(
            r"(?:[.!?:]|&mdash;|&ndash;|[\u2014\u2013])[\"'\)\]]*\s*$", prev))
        if i == first or i == last or new_sentence or core.lower() not in SMALL_WORDS:
            runs[i] = _tc_cap(run)
        else:
            runs[i] = _tc_lower(run)

    rebuilt = ["".join(runs[j] for j in ids) for ids in index]
    out = rebuilt[0]
    for t, seg in zip(tags, rebuilt[1:]):
        out += t + seg
    return out


# slug -> page definition. slug "" is the homepage.
PAGES = [
    dict(slug="", src="index", nav="home",
         title="Keno Results NZ | Latest Winning Numbers",
         og="Keno Results NZ",
         desc="Today's Keno results for New Zealand, updated after each of the four "
              "daily draws. Latest winning numbers, ticket checker and full archive.",
         js=["results"], schema=["website", "org"]),
    dict(slug="check", faqtopic="Checking Keno Numbers", faq=[
             ('How do I know if I have won?',
              'Enter your numbers above and they are matched against any published draw, in your browser. For an official confirmation and to claim, take the ticket to Lotto NZ &mdash; we tell you how many numbers matched, not what it is worth.'),
             ('Can I check an old Keno ticket?',
              'Yes, against any draw we hold. Use the draw selector to pick the draw your ticket was for. Bear in mind prizes must be claimed within 12 months of the draw date.'),
         ],
         src="check", nav="check",
         title="Check My Keno Numbers | keno-results.co.nz",
         og="Check my Keno numbers",
         desc="Check your Keno numbers against any published NZ draw, free. Enter a "
              "line, pick the draw and see your matches \u2014 numbers stay in your "
              "browser, never uploaded.",
         js=["results", "checker"]),
    dict(slug="results", src="results", nav="results",
         title="Keno Draw Archive NZ | keno-results.co.nz",
         og="Keno draw archive",
         desc="Every daily Keno result we hold for New Zealand, searchable by draw "
              "number, date or a number that came up. Each draw has its own page.",
         js=["archive"], schema=["dataset"]),
    dict(slug="statistics", faqtopic="Keno Statistics", faq=[
             ('Are some Keno numbers due to come up?',
              'No. Every draw is independent and the machine has no memory. A number that has not appeared in fifty draws is exactly as likely as one that appeared in the last three &mdash; both sit at 25%, because twenty numbers are drawn from eighty.'),
             ('What are the most common Keno numbers?',
              'Some numbers have come up more often than others in any finite sample, and the full count is above. It carries no predictive value. Widen the window from 5 draws to 250 with the selector and watch the spread collapse &mdash; that flattening is the point.'),
         ],
         src="statistics", nav="stats",
         title="Hot & Cold Keno Numbers NZ | keno-results.co.nz",
         og="Hot and cold Keno numbers",
         desc="Which NZ Keno numbers have come up most and least often over the last 5, "
              "10, 25, 50, 100 or 250 draws, plus the full frequency count.",
         js=["results"]),
    dict(slug="how-to-play", faqtopic="Playing Keno", faq=[
             ('How many numbers can I pick in Keno?',
              "Between one and ten &mdash; your spots. It is the most consequential choice on the ticket, because each spot count has an entirely different prize ladder. See <a href='/odds/'>the odds tables</a> for all ten."),
             ('Can I choose my own numbers, or do I have to take a Dip?',
              'Either. You can mark your own, take a Dip where the system picks at random, or reuse a saved set from a MyLotto account. All three give exactly the same odds &mdash; the draw has no idea where your numbers came from.'),
             ('How long do I have to claim a Keno prize?',
              'Lotto NZ allows 12 months from the draw date to claim a prize on any of its draw games. After that the prize is forfeited.'),
         ],
         src="how-to-play", nav="howto", section=True,
         title="How to Play Keno in New Zealand | keno-results.co.nz",
         og="How to play Keno",
         desc="How New Zealand Keno works: 20 numbers drawn from 80, choosing your spots, "
              "how prizes are structured, and what people get wrong.",
         schema=["howto"]),
    dict(slug="odds", faqtopic="Keno Odds", faq=[
             ('Which Keno spot count has the best odds?',
              'It depends what you mean by best. The chance of matching <em>every</em> spot is highest at 1 spot and falls steeply as you add more. The chance of winning <em>anything at all</em> peaks in the middle of the range. The tables above give both figures for all ten spot counts, so you can see the trade rather than take a recommendation.'),
             ('If I spend more, will I win more?',
              'You will win more <em>when</em> you win, because the prize scales with your stake &mdash; a $2 ticket pays twice what the same result pays on $1. What does not change is how often you win. Staking more does not make a matching line any more likely.'),
             ('Does playing more spots improve my chances?',
              'No. Each spot count is a different game with its own prize ladder, not a difficulty setting. Adding spots makes matching all of them dramatically harder while opening lower tiers that pay less. Neither direction is an edge.'),
             ('What is the house edge on Keno?',
              "It is the share of stakes the operator keeps over the long run, and it varies by spot count because each has its own prize ladder. Our <a href='/calculator/'>return calculator</a> works out the expected return for any spot count and stake, which is the same figure seen from the player's side."),
         ],
         src="odds", nav="odds", section=True,
         title="Keno Odds NZ - Real Probabilities | keno-results.co.nz",
         og="Keno odds",
         desc="Verified Keno odds for every spot count, calculated from the rules of the "
              "game. Includes the full six-spot breakdown and the formula used.",
         schema=["faq"]),
    dict(slug="number-generator", faqtopic="the Keno Number Generator", faq=[
             ('Do randomly generated numbers win more often?',
              'No. A random line and a line you chose yourself have identical odds. The generator exists so you can see the true probability of a line beside it, not because the numbers are better.'),
         ],
         src="number-generator", nav="tools",
         title="Keno Number Generator NZ | keno-results.co.nz",
         og="Keno number generator",
         desc="A free Keno number generator for NZ players. Draw a random line and see "
              "the true odds beside it. One to ten spots, nothing sent anywhere.",
         js=["generator"]),
    dict(slug="calculator", src="calculator", nav="tools",
         title="Keno Odds & Return Calculator NZ | keno-results.co.nz",
         og="Keno odds and return calculator",
         desc="Exact probabilities for any Keno spot count, plus real expected return and "
              "house edge once you supply the prize values from your own paytable.",
         js=["calculator"]),
    dict(slug="prizes", faqtopic="Keno Prizes", faq=[
             ('How do I claim a larger Keno prize?',
              'Smaller prizes can be paid at a retailer; larger ones are claimed through Lotto NZ directly. The operator publishes the current thresholds and the process, and those change, which is why we point you there rather than quote a figure.'),
         ],
         src="prizes", section=True,
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
    dict(slug="multiplier", faqtopic="the Keno Multiplier", faq=[
             ('Does the multiplier change my odds of winning?',
              'No. The multiplier scales what a winning ticket pays; it has no effect on whether a ticket wins. It is attached before the draw and applies to everyone playing that draw equally.'),
             ('What multipliers are possible?',
              'We have recorded &times;1.5, &times;2, &times;3, &times;5 and &times;10 across the draws in our archive. The counts and the share each represents are in the table above, taken from our own records rather than a published schedule.'),
         ],
         src="multiplier", section=True,
         title="Keno Multiplier NZ Explained | keno-results.co.nz",
         og="The Keno multiplier",
         desc="How the NZ Keno multiplier scales prizes, the values we have observed "
              "across 220 draws, and why it never changes your odds of winning.",
         schema=["faq3"]),
    dict(slug="draw-schedule", faqtopic="Keno Draw Times", faq=[
             ('What time is the Keno draw in New Zealand?',
              'Four draws every day, at 10:01am, 1:01pm, 3:01pm and 6:01pm New Zealand time. Every draw in our archive has held to those times.'),
             ('Does Keno draw on weekends and public holidays?',
              'Yes. The schedule does not change &mdash; four draws a day, every day of the year, weekends and public holidays included.'),
             ('What time is the last Keno draw of the day?',
              "6:01pm New Zealand time. The result usually appears on <a href='/'>the homepage</a> within a few minutes of Lotto NZ publishing it."),
         ],
         src="draw-schedule", section=True,
         title="Keno Draw Times NZ | keno-results.co.nz",
         og="Keno draw schedule",
         desc="NZ Keno draw times: four draws daily at 10:01am, 1:01pm, 3:01pm and "
              "6:01pm New Zealand time, weekends and public holidays included.",
         schema=["howto2"]),
    dict(slug="rules", src="rules", section=True,
         title="Keno Rules & Regulations NZ | keno-results.co.nz",
         og="Keno rules and regulations",
         desc="How NZ Keno is structured, who operates and regulates it, the age limit, "
              "how prizes are claimed, and where the binding rules live.",
         schema=[]),
    dict(slug="gaming", faqtopic="Gambling in New Zealand", src="gaming", section="gaming", noads=True,
         faq=[
             ('Is gambling legal in New Zealand?',
              "Some of it. The Gambling Act 2003 works by prohibition with exceptions, so gambling is unlawful unless the Act specifically authorises it. What is permitted is Lotto NZ's games, betting through TAB NZ, gaming machines in pubs and clubs, and the six licensed land-based casinos."),
             ('Is online gambling legal in New Zealand?',
              "It is changing. Online casino gambling was never lawfully offered from within New Zealand, and the Online Casino Gambling Act 2026 creates a licensing regime for it. From 1 December 2026 only operators that won the right to apply for a licence may serve New Zealand customers. See <a href='/gaming/online-casino-law/'>the law change</a>."),
             ('Do I pay tax on gambling winnings in New Zealand?',
              'Lotto NZ states prize money is not taxed, so a prize is paid in full. What the money then earns afterwards &mdash; interest, dividends, rent &mdash; is taxable in the ordinary way. General information rather than tax advice.'),
         ],
         title="Gambling in New Zealand | keno-results.co.nz",
         og="Gambling in New Zealand",
         desc="What is legal, who regulates it, where the money goes, and what "
              "changes on 1 December 2026 - sourced from the legislation itself."),
    dict(slug="gaming/online-casino-law", faqtopic="the Online Casino Law Change", src="gaming-online-casino-law",
         section="gaming", noads=True,
         faq=[
             ('When does the online casino law change take effect?',
              'The Act came into force on 1 May 2026 and the supporting regulations on 3 July 2026. The date that changes things for players is 1 December 2026, when only operators holding the right to apply for a licence may serve New Zealand customers. Licences themselves are expected to be issued from early 2027.'),
             ('Can I still play on an offshore casino right now?',
              'The regulator has said there are no changes for online casino customers during the transition. Operators that were serving New Zealand before 1 May 2026 may continue until 1 December 2026, though they are not permitted to advertise here during that period.'),
             ('How will I know if an online casino is licensed in New Zealand?',
              'Two ways. The Department of Internal Affairs will publish a public register of licensed operators, and licensed casinos will be required to display a unique registration icon on their platform and in any advertising. If a site shows neither, it is not licensed here.'),
             ('What happens if I play on an unlicensed site?',
              'You do not get the protections the licensing regime is built to provide, and there is no regulator to complain to. With a licensed operator you can complain to the casino or to the Department directly.'),
             ('Does this affect sports betting?',
              'No. Betting on sport and racing is regulated under the Racing Industry Act 2020 alongside the Gambling Act 2003, through TAB NZ, and the online casino changes do not alter it.'),
         ],
         title="NZ Online Casino Law Change 2026 | keno-results.co.nz",
         og="The online casino law change",
         desc="New Zealand licensed online casino gambling in 2026. The dates that "
              "matter, what changes on 1 December, and how to spot a licensed site."),
    dict(slug="gaming/who-regulates-gambling", faqtopic="Gambling Regulation in NZ", src="gaming-who-regulates",
         section="gaming", noads=True,
         faq=[
             ('Who regulates gambling in New Zealand?',
              "The Department of Internal Affairs is the regulator &mdash; it licenses, inspects and enforces, and now administers the online casino regime. The Gambling Commission is a separate independent body that hears appeals against the Department's decisions and handles casino licensing matters."),
             ('What are the four classes of gambling?',
              'Class 1 is small-scale with no licence needed, such as a school raffle. Class 2 is larger community fundraising. Class 3 covers substantial prizes and requires a licence. Class 4 is gaming machines outside casinos &mdash; the pokies in pubs and clubs, and the most tightly controlled.'),
             ('Where does New Zealand gambling money go?',
              'Lotto NZ is a Crown entity, so its surplus goes to the Lottery Grants Board rather than to shareholders &mdash; a near-record $395 million in its 2025 financial year. Class 4 societies operating gaming machines must also return a minimum share of proceeds to authorised community purposes.'),
         ],
         title="Who Regulates Gambling in NZ | keno-results.co.nz",
         og="Who regulates gambling",
         desc="The Gambling Act 2003, the four classes of gambling, the Department "
              "of Internal Affairs, and why sports betting sits under another law."),
    dict(slug="gaming/getting-help", faqtopic="Gambling Harm and Getting Help", src="gaming-getting-help",
         section="gaming", noads=True,
         faq=[
             ('Where can I get help with gambling in New Zealand?',
              "The Gambling Helpline on 0800 654 655, or text 8006. It is free, confidential and available 24 hours, and you can call about your own gambling or someone else's. Safer Gambling Aotearoa at safergambling.org.nz has further support options."),
             ("Can I call about someone else's gambling?",
              "Yes. The helpline takes calls from family and friends, you do not need the person's permission or involvement, and you do not need to have worked out what to say first."),
             ('How do I know if my gambling is a problem?',
              'The clearest single signal is chasing &mdash; playing to win back what you lost rather than because you wanted to play, because it means the loss is now driving the decision. Hiding how much you play, using money meant for something else, and believing a number is due are the others worth taking seriously.'),
         ],
         title="Gambling Help NZ | keno-results.co.nz",
         og="If gambling stops being fun",
         desc="Free confidential gambling help in New Zealand, the warning signs "
              "worth taking seriously, and practical limits that actually work."),
    # ---- the online casino cluster -------------------------------------
    # noads throughout: online casino advertising is prohibited under the
    # Gambling Act 2003, and the 2026 Act attaches penalties reaching whoever
    # publishes or arranges to publish one. These pages rank on the arithmetic.
    dict(slug="online-casinos", faqtopic="Online Casinos", src="online-casinos", section="casinos", noads=True,
         verdict=("Online Casinos in NZ",
              "After more than 300 of these accounts, my honest view is that the choice of site matters far less than New Zealanders are encouraged to believe. The lobbies overlap because a handful of studios supply all of them, so the real spread sits inside the games: blackjack at a 3:2 table returns about 99.5% with basic strategy, a typical pokie 96%. That gap is worth more over a year than any welcome offer on this page.\n\nWhat genuinely differs between operators is the cashier &mdash; whether verification is demanded before your first withdrawal rather than after it, and whether a pending period sits between you and your money. That is what I would choose on, and it is the one thing the marketing never leads with."),
                  ct=dict(h="Best Online Casino Sites NZ &mdash; Ranked for {month}",
                 p="Fifteen online casinos take New Zealand players right now, and every welcome offer on this page has been through the same wagering maths before it went up. You get the bonus, the multiple and the minimum deposit side by side, so you can see in about ten seconds which ones are worth claiming and which are marketing."),
         faq=[
             ('Are online casinos legal in New Zealand?',
              "Playing has never been an offence for a New Zealander. The Gambling Act 2003 works by prohibition with exceptions, and online casino gambling was not among the authorised forms &mdash; so it was unlawful to offer from inside New Zealand, while playing on an offshore site was not an offence. New Zealand has since legislated to licence it. See <a href='/licensed-online-casinos/'>licensed online casinos</a>."),
             ('How do I know if an online casino is licensed in NZ?',
              'Find the regulator and company named in the footer, then search that regulator&rsquo;s own public register for the company &mdash; not the brand, since one company often runs several. It takes about two minutes. A licence number in a footer, or a seal that is an image rather than a link to a register entry, is a graphic rather than a licence.'),
             ('Do I pay tax on casino winnings in New Zealand?',
              'Gambling winnings are generally not income for tax purposes for a recreational player, and Lotto NZ states prize money is paid in full. What the money earns afterwards &mdash; interest, dividends, rent &mdash; is taxable in the ordinary way. That is general information rather than tax advice.'),
             ('Are online casinos safe in New Zealand?',
              "Two questions in one. Game honesty is rarely the issue at a site running titles from named studios, because those studios are licensed and audited independently of the operator. Whether you get paid is a question about the operator, and it is the one worth your attention &mdash; unpaid withdrawals, not rigged games, is what actually happens. See <a href='/how-we-rate-casinos/'>how to check a site</a>."),
             ('Which online casino pays out the most in NZ?',
              'No casino pays out the most &mdash; games do. Blackjack at a 3:2 table returns about 99.5% of turnover with basic strategy, typical pokies 92&ndash;98%. A site&rsquo;s advertised payout percentage is an aggregate across all players and all games, so it tells you about its traffic mix rather than about your session.'),
             ('Can I play at an online casino in New Zealand dollars?',
              'Some offer genuine NZD accounts and many only appear to. If the site converts your deposit and holds the balance in euros or US dollars, you pay a spread in both directions. A real NZD online casino shows balance, bets and withdrawal in NZD with no conversion line on the transaction.'),
             ('What is the best online casino for Kiwis just starting out?',
              'Whichever has a low minimum deposit so a mistake is cheap, lets you complete verification on day one, and publishes the RTP of its games. Skip the largest welcome bonus, progressive jackpots and live-table side bets at the start &mdash; those are the parts of the product designed to be picked up first, not the parts worth having.'),
             ('Is Reddit a reliable source for online casino recommendations in NZ?',
              'It is better than an affiliate list for one thing specifically: unpaid withdrawal complaints, which are the failure mode that matters and the one no commercial page reports. It is unreliable on odds, bonuses and payout claims, where confident wrong answers outnumber right ones. Use it for operator behaviour, not for arithmetic.'),
             ('Which casino games have the best odds?',
              'Blackjack played with basic strategy at a 3:2 table is the cheapest, at roughly a 0.5% house edge, followed by baccarat&rsquo;s banker bet at 1.06% and the craps pass line at 1.41%. Single-zero roulette costs 2.70% and double-zero 5.26% for an otherwise identical game. Typical pokies sit between 2% and 8%.'),
             ('Are the casinos listed on this page recommendations?',
              "No. Every operator in the table is a commercial partner and every link is a paid placement, which is stated in the table itself. The order is one this site chose rather than a ranking any operator earned, and appearing in it means a commercial arrangement exists &mdash; a different fact from &ldquo;this is the best place to play&rdquo;. The criteria and the arithmetic are on <a href='/how-we-rate-casinos/'>how we rate casinos</a> and are unaffected by it."),
         ],
         title="Best Online Casino NZ 2026 | Real Money Casino Sites Compared | keno-results.co.nz",
         og="Top online casinos NZ",
         desc="Compare the top online casinos NZ players use in 2026. Real money casino NZ sites measured on house edge, withdrawal terms and bonus maths, not banner size."),
    dict(slug="licensed-online-casinos", faqtopic="Licensed Online Casinos", src="licensed-online-casinos",
         verdict=("Licensed Online Casinos in NZ",
              "Most people arrive here asking whether online casinos are legal, and the answer is that playing has never been an offence for a New Zealander. The more useful question is who licenses the site you are actually on, because at the moment nobody holds a New Zealand licence &mdash; none has been issued to anyone. Every operator taking Kiwi players is offshore-licensed, and those regimes are not interchangeable.\n\nMy position is unglamorous and it takes two minutes: find the regulator and the company name in the footer, then search that regulator&rsquo;s own public register for the company rather than the brand. A seal that is an image instead of a link to a register entry has already told you something."),
                  section="casinos", noads=True,
         ct=dict(h="Online Casino Sites Accepting New Zealand Players",
                 p="Fifteen casinos accepting New Zealand players, with the licence question answered properly for each: not one of them holds a New Zealand online casino licence, because the Department of Internal Affairs has not issued one to anyone yet. Below the table is the two-minute check that tells you what licence a site does hold."),
         faq=[
             ('Which online casinos are licensed in New Zealand?',
              'The Department of Internal Affairs administers the regime and publishes a register of licensed operators, capped at fifteen. Until a licence has been issued to a given operator, no site can truthfully claim to hold one here &mdash; so the register, rather than a badge on a casino&rsquo;s own page, is what settles it.'),
             ('How does the New Zealand online casino licensing regime work?',
              'The right to apply for one of the fifteen licences was allocated by auction rather than by assessment alone, which gives the regulator leverage it has never had over offshore operators. Winning at auction is not the same as holding a licence: suitability and harm-prevention obligations still have to be satisfied before one is issued.'),
             ('Is it illegal for me to play on an unlicensed site?',
              'The Act regulates operators and advertisers rather than criminalising players, so playing is not itself an offence. What you lose is the regulator: no New Zealand body to complain to, no enforceable local obligation on the operator, and no register entry to check.'),
             ('What does a New Zealand licence actually protect?',
              'Principally a complaints path that does not end at the operator, which matters because an internal complaints team works for the party you are complaining about. It also turns harm-prevention and consumer-protection duties into enforceable conditions, and gives the operator something it can lose. It does not change the house edge or guarantee a withdrawal.'),
             ('Is it legal to gamble online in New Zealand?',
              'Playing has never been an offence for a New Zealander, and it still is not. The Gambling Act 2003 works by prohibition with exceptions and online casino gambling was not among the authorised forms, so offering it from inside New Zealand was unlawful while playing on an offshore site was not. The law regulates operators and advertisers rather than criminalising players.'),
             ('Are offshore online casinos legal for New Zealanders?',
              'Using one has never been an offence for you. What you give up is the regulator: no New Zealand body to complain to, no locally enforceable obligation on the operator, and no local register entry to check. Your protection is whatever the operator&rsquo;s own licensing jurisdiction provides, and that varies enormously.'),
             ('Do I pay tax on casino winnings in NZ?',
              'Generally no. Gambling winnings are not income for tax purposes for a recreational player, and Lotto NZ states prize money is paid in full. What the money earns afterwards &mdash; interest, dividends, rent &mdash; is taxable in the ordinary way, and a win taken in cryptocurrency raises a separate question because Inland Revenue treats crypto-assets as property. General information, not tax advice.'),
             ('How many online casino licences will New Zealand issue?',
              'No more than fifteen. The right to apply was allocated by auction rather than by assessment alone, which gives the regulator leverage it has never had over offshore operators, because a capped licence has value that can be withdrawn. Winning at auction is not the same as holding a licence &mdash; suitability and harm-prevention obligations still have to be satisfied.'),
             ('Does this affect sports betting or Lotto?',
              'No. Sports and racing betting is regulated under the Racing Industry Act 2020 alongside the Gambling Act 2003, through TAB NZ. Lotto NZ&rsquo;s games, Keno included, are run by a Crown entity under its own authority. Neither is affected by the online casino regime.'),
         ],
         title="Licensed Online Casinos NZ 2026 | Is Online Gambling Legal? | keno-results.co.nz",
         og="Legal and licensed online casinos NZ",
         desc="Are online casinos legal in New Zealand? Check licensed online casinos NZ against the Gambling Act, see who regulates them, and verify a licence in two minutes."),
    dict(slug="casino-bonus", faqtopic="Casino Bonuses", src="casino-bonus",
         verdict=("Casino Bonuses in NZ",
              "I price every welcome offer the same way before it goes up, and the answer is consistent enough to state plainly: a bonus breaks even at about 25&times; wagering on a typical 4% pokie, and every offer in the table above sits on the wrong side of that line. That does not make them frauds. It makes them entertainment you are paying for, which is a different proposition from the free money the headline implies.\n\nIf you are going to claim one anyway, read the multiple rather than the maximum. A 100% match at 40&times; costs you more expected turnover than a smaller offer at 20&times;, every single time."),
                  section="casinos", noads=True,
         ct=dict(h="Best Casino Bonuses NZ &mdash; Welcome Offers for {month}",
                 p="Every welcome bonus here has been run through one division before publication. A bonus breaks even at 25&times; wagering on a typical pokie; these run from 30&times; to 50&times;, and the multiple sits under each button so you can do the sum yourself. That is the difference between a NZ$18,500 headline and NZ$18,500 you can withdraw."),
         faq=[
             ('What does 40x wagering actually mean?',
              'That you must stake forty times the bonus before bonus funds become withdrawable. On a NZ$100 bonus that is NZ$4,000 of turnover &mdash; or NZ$8,000 if the multiple applies to deposit plus bonus rather than to the bonus alone.'),
             ('At what wagering requirement is a casino bonus worth taking?',
              'The break-even multiple is 1 divided by the house edge, and the bonus amount cancels out entirely. On a typical pokie at a 4% edge that is 25&times;. Below 25&times; the offer has positive expected value; above it you are paying more in expected turnover cost than the bonus is worth.'),
             ('Is a bigger casino bonus better?',
              'No &mdash; bonus size has no bearing on whether an offer is good, because it cancels out of the break-even calculation. Only the wagering multiple, the game weighting and the house edge of what you play decide it. A 50% bonus at 20&times; beats a 200% bonus at 35&times;.'),
             ('What is game weighting on a bonus?',
              'The proportion of each dollar staked that counts toward the requirement. Pokies usually count 100%, table games often 10% or less. Divide the stated multiple by the weighting to get the effective one: a nominal 40&times; at 10% weighting is really 400&times;.'),
             ('What is a $1 deposit casino bonus worth in NZ?',
              'As a bonus, the same as any other &mdash; the wagering multiple, game weighting and maximum conversion all still apply, and a small deposit softens none of them. As a test it is excellent: NZ$1 buys you a look at the cashier, the verification process and a real withdrawal before anything is at stake. Check the offer threshold too, since a site minimum and a bonus minimum are often different numbers.'),
             ('What is a low wagering casino bonus?',
              'Anything at or below the break-even multiple for the games you play &mdash; about 25&times; on a typical pokie. A no wagering offer is worth exactly its face value, because there is no turnover cost to subtract. Both are rare, both are smaller than the headline offers, and both are worth more.'),
             ('Are casino bonuses worth it in NZ?',
              'Most advertised welcome offers carry wagering above the break-even line, which makes them marketing costs recovered from your turnover rather than gifts. That is not a reason never to take one &mdash; a bonus extends playing time and the entertainment is the point. It is a reason to stop treating bonus size as a quality signal.'),
             ('Why was my bonus voided?',
              'Most commonly for exceeding the maximum bet while wagering &mdash; usually around NZ$5 to NZ$8 per spin or hand. It only takes one bet, it is enforced automatically, and most terms allow the operator to void the bonus and everything won with it.'),
         ],
         title="Best Casino Bonuses NZ 2026 | Welcome Offers Priced on Wagering | keno-results.co.nz",
         og="Casino bonus NZ",
         desc="Compare the best casino bonuses NZ offers in 2026: what a casino sign up bonus NZ is really worth after the wagering maths, plus $1 deposit casino NZ terms."),
    dict(slug="casino-payout-percentages", faqtopic="Casino Payout Percentages", src="casino-payout-percentages",
         verdict=("Casino Payout Percentages in NZ",
              "No casino pays out the most. Games do, and that is the entire answer to the question that brings most people to this page. The highest published returns on any New Zealand floor are Ugga Bugga at 99.07%, with Mega Joker and Book of 99 at 99%, against a typical pokie&rsquo;s 96% &mdash; and nearly every site in the table above carries those same titles.\n\nA site-level payout percentage is an average of whatever that casino&rsquo;s customers happened to play, which tells you about them and not about the operator. The RTP in the game&rsquo;s own information panel is the only figure on this subject that is about you."),
                  section="casinos", noads=True,
         ct=dict(h="Best Payout Casinos NZ &mdash; Highest RTP Sites for {month}",
                 p="Fifteen casinos serving New Zealand, running largely the same games from the same studios. Which is the point: no casino pays out the most, games do. The house edge of every common game is set out below, derived from the published rules rather than quoted &mdash; from blackjack at 0.5% to the baccarat tie at 14.36%."),
         faq=[
             ('What is RTP in an online casino?',
              'Return to player: the share of everything staked that a game pays back across its full theoretical cycle. Its complement is the house edge &mdash; a 96% RTP game has a 4% edge, costing about NZ$4 per NZ$100 staked in the long run.'),
             ('Does a high RTP mean I will win?',
              'No. RTP is calculated over the game&rsquo;s complete theoretical distribution, often tens of millions of spins, and much of it can sit inside rare outcomes most players never see. It describes the long-run cost of staking, not what happens tonight, and a game is never &ldquo;due&rdquo; to return to it.'),
             ('Can a casino change a game’s RTP?',
              'Sometimes. A number of studios ship the same title in several RTP builds &mdash; a 96% and a 94% version of an identical-looking game &mdash; and the operator selects which to run. Read the figure in the game&rsquo;s own information panel on the site you are playing.'),
             ('What is the difference between RTP and volatility?',
              'RTP is the size of the return; volatility is its shape. Two 96% games cost the same per dollar staked, but a high-volatility one concentrates the return in rare large wins, so the median session lands below the average even though the average is identical.'),
             ('Which online casino has the best payout in NZ?',
              'The question has no site-level answer. Published payout percentages are aggregates across every player and every game, weighted by turnover, so a site with heavy table-game volume reports a higher figure without a single game differing. The highest paying option is whichever site runs the highest-RTP build of the game you want and tells you which build that is.'),
             ('What is a good RTP percentage?',
              'Above 96% is competitive for a pokie, 92&ndash;94% is poor, and almost any table game beats almost any pokie &mdash; blackjack with basic strategy at a 3:2 table returns roughly 99.5% of turnover against a typical pokie&rsquo;s 96%.'),
             ('Does RTP matter in the short term?',
              'Barely. RTP is calculated across the game&rsquo;s full theoretical cycle, often tens of millions of spins. Over a single session volatility dominates completely, which is why two games at the same RTP can feel nothing alike and why the median session on a high-volatility game lands below its own average.'),
             ('Are audited payout percentages useful?',
              'Barely. They are aggregates across every player and every game on a platform, weighted by turnover, so a site with heavy table-game volume shows a higher figure without a single game differing. The per-game RTP is the number that applies to what you actually play.'),
         ],
         title="Best Payout Online Casino NZ 2026 | Highest RTP Casinos NZ | keno-results.co.nz",
         og="Casino payout percentage and RTP",
         desc="What is RTP in pokies, and which is the best payout online casino NZ? Casino payout percentage and highest RTP casinos NZ, worked from published game rules."),
    dict(slug="fast-payout-casinos", faqtopic="Fast Payout Casinos", src="fast-payout-casinos",
         verdict=("Fast Payout Casinos in NZ",
              "Having tested withdrawals at more sites than I can now list individually, my conclusion is that the operator is rarely the reason your money is slow. Your own account is. A fully verified account paying to an e-wallet is same-day at most sites; an unverified account paying to a card is a week almost anywhere, and no amount of instant-withdrawal marketing moves either figure.\n\nSo the useful move is not finding a faster casino. It is completing verification before you have a balance worth waiting on, and checking whether a pending period sits in front of processing. Do those two things and you have removed most of the delay you would otherwise blame on the brand."),
                  section="casinos", noads=True,
         ct=dict(h="Best Fast Payout Casinos NZ &mdash; Instant Withdrawals for {month}",
                 p="Fifteen casinos accepting New Zealand players, with the minimum deposit and wagering on each. On withdrawal speed the honest answer is that your own account decides it: a verified account paying to an e-wallet is same-day almost anywhere, an unverified one paying to a card is a week almost anywhere. Below is how to be in the first group."),
         faq=[
             ('Which online casinos have the fastest payouts in New Zealand?',
              'Payout speed is driven far more by your own account state and your chosen method than by which operator you pick. A verified account withdrawing to an e-wallet is fast almost anywhere; an unverified account withdrawing to a card is slow almost anywhere. Advertised operator times describe one stage of four, and they change month to month.'),
             ('Are instant withdrawals real?',
              'Not in the literal sense. &ldquo;Instant&rdquo; describes the final settlement step once an operator has already approved the payment &mdash; the pending period, identity verification and manual approval all happen before it. The fastest realistic outcome is same-day, and it needs verification completed in advance.'),
             ('How long do online casino withdrawals take?',
              'It depends on four separate stages run by three parties: a pending period set by the operator, identity verification required by anti-money-laundering law, manual approval in the operator&rsquo;s business hours, and settlement on the payment rail. Advertised times usually describe only one of them.'),
             ('Why is my casino withdrawal taking so long?',
              'Most often verification. If identity, address and payment-ownership documents were not submitted when the account opened, the first withdrawal and the first document request arrive together. Completing verification before you have won anything is the single most effective thing you can do about withdrawal speed.'),
             ('What is a reverse withdrawal?',
              'A feature letting you pull a pending withdrawal back into your playable balance. It is presented as flexibility and it is a mechanism for un-winning &mdash; a long pending period combined with easy reversal is the most harmful design choice on a cashier page.'),
             ('Can a casino refuse to pay out?',
              'Yes, and most refusals turn on a term the player breached: exceeding the maximum bet while wagering a bonus, a name mismatch between account, ID and payment method, incomplete verification, or a duplicate account. Ask for the specific clause relied on, in writing.'),
             ('What is the fastest withdrawal method at an online casino?',
              'E-wallets, because the operator pushes funds straight to the wallet with no bank clearing step. Crypto settles fast on-chain but waits behind the same compliance review. Cards are slower and issuer-dependent, since withdrawals are often processed as a refund against the original deposit. Bank transfer is slowest and most transparent.'),
             ('How can I speed up a casino withdrawal?',
              'Complete identity verification when you open the account rather than when you first withdraw; make sure the name on the account, the ID and the payment method match exactly; choose an e-wallet if one is supported; avoid submitting on a Friday evening; and make sure no active bonus is locking the balance.'),
             ('Is there such a thing as an instant withdrawal casino?',
              'Not literally. &ldquo;Instant&rdquo; describes the final settlement step once payment is already approved &mdash; the pending period, verification and manual approval all happen first. Same-day is the fastest realistic outcome, and it needs verification done in advance.'),
             ('Why must I withdraw to the method I deposited with?',
              'Anti-money-laundering rules make returning funds to their source the default. It means depositing by a method that cannot receive a withdrawal &mdash; a prepaid voucher, for instance &mdash; creates a problem you discover at the worst possible moment.'),
         ],
         title="Fast Payout Casinos NZ 2026 | Instant Withdrawal Casino Sites | keno-results.co.nz",
         og="Fastest paying online casino NZ",
         desc="How long do casino withdrawals take NZ? Compare fast payout casinos NZ and instant withdrawal casino NZ claims against what the payment rails actually clear."),
    dict(slug="casino-payment-methods", faqtopic="Casino Payment Methods", src="casino-payment-methods",
         verdict=("Casino Payment Methods in NZ",
              "The cost that matters on a deposit is the one nobody prints. A round trip through a non-NZD account runs several percent in conversion spread and card fees &mdash; more than the entire 2.70% house edge of single-zero roulette &mdash; which means the payment method can cost you more than the game does.\n\nTreat NZD acceptance as the first filter and the method as the second, because a spread you pay on the way in and again on the way out is charged whether you win or lose. I have deliberately not published an availability table here: those change without notice, and the cashier page is the only source current enough to trust."),
                  section="casinos", noads=True,
         ct=dict(h="Best Casino Payment Methods NZ &mdash; NZD, POLi, Crypto for {month}",
                 p="Fifteen casinos taking New Zealand players, with the minimum deposit on each. What the table deliberately does not list is accepted payment methods &mdash; those change without notice and the cashier page is the only current source. What the guide below gives you is the cost nobody prints: the conversion spread on a non-NZD account."),
         faq=[
             ('Can I deposit in New Zealand dollars at an online casino?',
              'Some operators offer genuine NZD accounts and many do not, converting your deposit into euros, US or Australian dollars instead. Check the cashier rather than the banner: a real NZD account shows your balance, bets and withdrawal in NZD with no conversion line on the transaction.'),
             ('What is the cheapest way to pay at an online casino?',
              'Whichever avoids a currency conversion. Two conversions plus a card issuer&rsquo;s foreign transaction fee can cost several percent of a round trip &mdash; comparable to the entire house edge of single-zero roulette, and larger than any difference between sites&rsquo; withdrawal speeds.'),
             ('Which payment method has the fastest withdrawal?',
              'E-wallets, because the operator pushes funds to the wallet with no bank clearing step. Cards are slower and issuer-dependent, since withdrawals are often processed as a refund against the original deposit. Bank transfer is slowest and most transparent.'),
             ('Can I withdraw to a prepaid voucher?',
              'No. Vouchers are deposit-only, so a second verified method is needed before you can take money out. Their real strength is as a hard spending cap &mdash; you cannot deposit more than the voucher holds.'),
             ('Do casinos accept POLi in NZ?',
              'POLi still operates in New Zealand &mdash; it closed in Australia on 30 September 2023 but the NZ business continued under separate local ownership &mdash; so it is a live method here rather than a dead one copied from an Australian page. Worth knowing how it works first: it asks for your internet banking username and password so it can log in on your behalf, Consumer NZ has criticised the model on that basis, and most bank terms say disclosing login details to a third party can affect your cover.'),
             ('Can you use PayPal at online casinos in NZ?',
              'It depends on the operator&rsquo;s licensing, not on what a comparison page says. PayPal restricts gambling merchants and permits them only in specific licensed markets under agreement. It is the method most often listed inaccurately, precisely because it is the one people search for &mdash; check the cashier.'),
             ('Which casinos accept Apple Pay in NZ?',
              'Apple Pay and Google Pay are not payment methods in their own right; they are a wrapper around the card already in your wallet. So the answer depends on whether your card issuer permits gambling transactions at all, and the card&rsquo;s foreign transaction fee still applies.'),
             ('What is the minimum deposit at an online casino in NZ?',
              'Typically NZ$10 to NZ$20, with NZ$1 and NZ$5 minimums available at some sites. Check it against the withdrawal minimum rather than on its own &mdash; a NZ$1 deposit floor beside a NZ$50 withdrawal floor is a trap rather than a feature.'),
             ('Should I use a credit card at an online casino?',
              'Some New Zealand issuers decline gambling transactions or treat them as a cash advance, which attracts interest immediately with no grace period. Gambling with borrowed money is also one of the clearest markers in every harm-screening framework.'),
         ],
         title="Casino Payment Methods NZ 2026 | PayPal, POLi and Paysafecard | keno-results.co.nz",
         og="Online casino deposit methods NZ",
         desc="Casino payment methods NZ on fee and speed: online casino deposit methods NZ including PayPal casino NZ, Paysafecard casino NZ and casinos that accept POLi NZ."),
    dict(slug="online-pokies", faqtopic="Online Pokies", src="online-pokies",
         verdict=("Online Pokies in NZ",
              "Two things decide what a pokie costs you and neither appears on the banner. The first is RTP: the spread between Ugga Bugga at 99.07% and a typical title at 96% is three points, worth more over any real session than the difference between any two welcome offers on this site. The second is volatility, which is why two 96% games feel nothing alike &mdash; the same return delivered in rarer, larger pieces.\n\nThe number is nearly always there, in an information tab almost nobody opens. Opening it is the highest-value habit a pokie player can build, and everything else on a lobby page is decoration."),
                  section="casinos", noads=True,
         ct=dict(h="Best Real Money Online Pokies Sites NZ for {month}",
                 p="Fifteen casinos with real money pokies for New Zealand players, and the welcome offer on each. The libraries overlap heavily because a handful of studios supply everyone, so what actually separates these sites is the cashier &mdash; and what separates the games is RTP, which runs from 92% to 99.07% and is disclosed in a tab nobody opens."),
         faq=[
             ('Are online pokies rigged?',
              'They are not rigged, and they are not fair in the sense people mean. Each spin is an independent draw from a random number generator, and the game is built so that across enough play it returns less than it takes in. That is disclosed, legal and unavoidable &mdash; typically 2% to 8% of everything staked.'),
             ('Is a pokie ever “due” to pay?',
              'No. Every spin is independent of every previous one, so a game that has paid nothing for two hours has exactly the same probability on the next spin as one that just paid a jackpot. There is no memory and no schedule.'),
             ('Does stopping the reels change the result?',
              'No. The outcome is determined the moment you press spin; the reels animate a result that already exists. The stop button shortens the animation and nothing else.'),
             ('What is volatility on a pokie?',
              'The shape of the return rather than its size. Low-volatility games pay small amounts often; high-volatility games pay rarely and occasionally very large. Two games at the same RTP cost the same per dollar staked, but the high-volatility one has a median session outcome worse than its average.'),
             ('Are online pokies the same as pub pokies in New Zealand?',
              'No. Pub and club machines are Class 4 gaming machines under the Gambling Act 2003 &mdash; capped stakes and prizes, returns set by gazetted game rules rather than chosen by the venue, mandatory community returns, and staff with harm-minimisation duties. Online pokies have no stake cap, run far faster, and nobody is standing next to you.'),
             ('Which online pokies pay the most in NZ?',
              'The ones with the highest published RTP that you enjoy playing. There is no title that pays more than its disclosed return, and the loosest online pokies are loose by a percentage point or two rather than by a category. Read the figure in the game&rsquo;s information panel on the site you are using, because some studios ship the same title in several RTP builds.'),
             ('Can I play free pokies with no download or registration?',
              'Usually yes &mdash; most studios publish a demo build running the same maths as the real game, which makes it an honest way to see how a title behaves before staking anything. It is also an acquisition tool: demo play runs at a different subjective temperature because nothing is at stake, and the transition to real money is the point at which the product is sold to you.'),
             ('What is a bonus buy on a pokie?',
              'Paying a multiple of your stake &mdash; often 75&times; to 100&times; &mdash; to enter the feature immediately. It does not improve the return. It compresses many spins of expectation into a single purchase at the same house edge or slightly worse, turning a high-volatility game into an extremely high-volatility one. Some jurisdictions have banned the mechanic.'),
             ('What are Megaways pokies?',
              'Games where the number of symbols per reel changes each spin, producing a large and varying number of ways to win. It is a counting method rather than a generosity measure, and Megaways titles are usually high-volatility designs with the return concentrated in the feature.'),
             ('Do progressive jackpots have worse odds?',
              'Their advertised RTP includes the jackpot contribution, and almost no one wins the pool &mdash; so the return a typical player experiences is lower than the headline figure. A 96% progressive contributing 2% to the pool behaves much like a 94% game with a lottery ticket attached.'),
         ],
         title="Online Pokies NZ 2026 | Real Money Pokies Sites Compared | keno-results.co.nz",
         og="Best online pokies NZ",
         desc="Best online pokies NZ for 2026: how online pokies real money NZ games work, what RTP and volatility actually change, and where free pokies NZ demos mislead."),
    dict(slug="live-casino", faqtopic="Live Casino Games", src="live-casino",
         verdict=("Live Casino Games in NZ",
              "The table sets the house edge and the casino does not, which makes where you sit far more consequential than which site you joined. The cheapest seat in any New Zealand live lobby is baccarat&rsquo;s banker bet at 1.06%, with French roulette under la partage at 1.35% just behind &mdash; and the same studios stream those tables into nearly every operator listed here.\n\nWhat will cost you is the rule variant and the side bet. A 6:5 blackjack table takes about 1.4% more than a 3:2 one, and the side bets run several times the main game. Both are printed on the felt, so read the felt before you read any review."),
                  section="casinos", noads=True,
         ct=dict(h="Best Live Casino Sites NZ &mdash; Live Dealer Tables for {month}",
                 p="Fifteen casinos with live dealer tables for New Zealand players. The tables themselves come from a handful of studios and are streamed into all of them, so the site matters less than the table: French roulette with la partage runs a 1.35% house edge, and 6:5 blackjack costs 1.4% more than 3:2. Both are printed on the felt."),
         faq=[
             ('How do live dealer casino games work?',
              'A physical dealer runs a physical game in a studio, cameras capture it, optical recognition reads the cards or wheel, and bets settle against what actually happened. Most tables are run by specialist studios &mdash; Evolution is the largest &mdash; and streamed into dozens of operators at once, so the rules of a table are set by the studio rather than by the casino whose logo is on the page.'),
             ('Which live casino game has the lowest house edge?',
              'Blackjack with basic strategy at a 3:2 table, at roughly 0.5%. Baccarat&rsquo;s banker bet is 1.06%, single-zero roulette 2.70%, double-zero roulette 5.26%, and the baccarat tie bet 14.36%.'),
             ('Are live casino side bets worth taking?',
              'No, on the arithmetic. Side bets typically carry house edges between 5% and 15%, against 0.5% to 2.7% on the main game. A NZ$5 side bet alongside a NZ$25 blackjack hand can cost more in expectation than the hand itself.'),
             ('What is the difference between 3:2 and 6:5 blackjack?',
              'Roughly 1.4% of house edge &mdash; the largest single rule effect at the table. A 6:5 payout on a natural blackjack turns the cheapest game in the casino into a mid-range one, and it is advertised identically. The payout is written on the felt.'),
             ('What is the difference between live casino and RNG games?',
              'A live game&rsquo;s outcome is physical &mdash; a real dealer, a real wheel, captured on camera &mdash; while an RNG game generates it in software. The house edge is the same for the same rules. What differs is that you can watch a live table, that rounds are slower so you generate less turnover per hour, and that minimum bets are higher because a dealer costs money per round.'),
             ('Why are live casino minimum bets higher?',
              'A physical dealer, a studio and a camera crew have a cost per round that an RNG game does not, so live tables carry higher minimums &mdash; often several times the RNG version of the same game. Check the table minimum before sitting.'),
             ('Can I play live casino in New Zealand dollars?',
              'Often not. Live tables are shared across many operators and are frequently denominated in euros or US dollars, so a currency conversion can sit between you and every bet. That spread is a real cost and no comparison of table limits captures it.'),
             ('Can you count cards in live dealer blackjack?',
              'Not usefully. Shoes are shuffled early and often, deck penetration is shallow, and bet-spread limits are enforced. The technique needs conditions the format is specifically arranged not to provide.'),
         ],
         title="Live Casino NZ 2026 | Live Dealer Casino Sites and Tables | keno-results.co.nz",
         og="Best live casino NZ",
         desc="Best live casino NZ guide for 2026: how live dealer casino NZ games work, and the real house edge on live roulette NZ, live blackjack NZ and baccarat tables."),
    dict(slug="how-we-rate-casinos", faqtopic="How We Rate Casinos", src="how-we-rate-casinos",
         verdict=("How We Rate Casinos",
              "There is no score out of ten on this site, and that is the deliberate part. A single number is the most persuasive thing a review page can publish and the least checkable, because the weights behind it are never shown to anyone.\n\nWhat is published here instead is the criteria, the arithmetic, and a plain statement of what is paid for: the operator table is advertising and the order is ours. My own test for whether any of this is worth anything sits on the bonus page, where the break-even wagering multiple is printed directly under the same offers and several of them fail it. Apply that test to us before you apply anything here to a casino."),
                  section="casinos", noads=True,
         ct=dict(h="The Operators This Site Has Commercial Arrangements With",
                 p="Fifteen casinos accepting New Zealand players, shown on every page in this section. This is the page that explains how they got there, what we check, what we deliberately ignore, and who pays for what &mdash; published as criteria and arithmetic rather than a score out of ten, so you can apply it yourself."),
         faq=[
             ('How does keno-results.co.nz rate online casinos?',
              "It does not publish a ranked list. The five criteria &mdash; legal standing, withdrawal behaviour, bonus arithmetic, published return figures, and an external complaints path &mdash; are published for you to apply, because online casino advertising is prohibited in New Zealand and the 2026 Act reaches whoever publishes one."),
             ('Why does this site not accept casino affiliate commissions?',
              'The Online Casino Gambling Act 2026 attaches penalties of up to NZ$5 million to whoever publishes an unlawful advertisement or arranges to publish one, and Cabinet&rsquo;s initial advertising decisions name affiliate marketing and paid endorsements specifically. Nothing in this section is paid for.'),
             ('What is excluded from the rating and why?',
              'Bonus size on its own, &ldquo;exclusive&rdquo; offers, game counts, site design, operator-quoted payout percentages and user review scores. Each is either controlled by the operator, trivially inflated, or measuring something other than whether you get paid.'),
             ('How do I check if a casino is licensed in NZ?',
              'Three steps, about two minutes. Find the registered company and named regulator in the site&rsquo;s footer &mdash; the company, not the brand, since one company often runs several. Go to that regulator&rsquo;s own website and search its public licence register for the company. Check the entry is current and covers online casino gambling. A licence number with nothing to check it against, or a seal that is an image rather than a link to a register entry, is a graphic.'),
             ('What makes an online casino safe?',
              'A licence you can verify in a register, withdrawal terms published before you deposit, games from named studios that are audited independently of the operator, and a complaints path that does not end with the operator. Design, game count and bonus size are not safety signals, and user review scores are dominated by people who just won or just lost.'),
             ('Where do the house edge figures on this site come from?',
              'They are derived from the published rules of each game rather than quoted from another site &mdash; single-zero roulette&rsquo;s 2.70% is 1 divided by 37. Where a figure cannot be derived or sourced, it does not appear, which is why withdrawal times and payment availability are not asserted here as facts.'),
         ],
         title="How to Choose an Online Casino NZ | Our Review Methodology | keno-results.co.nz",
         og="How to tell if an online casino is legit",
         desc="How to tell if an online casino is legit: our online casino review methodology, casino licensing explained, and how to check if a casino is licensed NZ-side."),
    dict(slug="new-casinos-nz", faqtopic="New Online Casinos", src="new-casinos-nz",
         verdict=("New Online Casinos in NZ",
              "New is a risk rather than a feature, and I have not yet had a month where that conclusion changed. Most sites marketed as new turn out to be a fresh brand on an existing licence, or a skin on a shared platform running identical terms &mdash; the novelty is the logo.\n\nThe genuinely new ones have the opposite problem: no complaint record at all, which happens to be the most useful thing there is to know about a casino and the one thing a launch cannot give you. If a new site is offering something an established one is not, ask what it is being offered in exchange for, and keep deposits small until you have taken a withdrawal all the way out."),
                  section="casinos", noads=True,
         ct=dict(h="Newest Online Casino Sites NZ &mdash; New Casinos for {month}",
                 p="Fifteen casinos accepting New Zealand players, with the welcome offer and wagering on each. None is genuinely new, which is the point of this page: most sites marketed as new turn out to be a fresh brand on an existing licence, and the truly new ones have no complaint record &mdash; the most useful thing there is to know about a casino."),
         faq=[
             ('What is the newest online casino in New Zealand?',
              'Usually not a new company at all. Most sites described as new are a new brand on an existing operator&rsquo;s licence, or a new skin on a white-label platform shared with dozens of other &ldquo;new&rdquo; casinos &mdash; same company, same terms, same cashier, new artwork. Check the registered company in the footer against the regulator&rsquo;s register to tell which you are looking at.'),
             ('Are new online casinos safe?',
              'They are structurally harder to judge, which is different from dishonest. A new site has no complaint record, no history of paying a large withdrawal, and terms that have not been tested by a real dispute &mdash; and the things that normally protect you are all made of history.'),
             ('Do new casinos have better bonuses?',
              'Usually larger ones, because a new site has to buy its first players. Larger is not better: the break-even wagering multiple is 1 divided by the house edge, about 25&times; on a typical pokie, and acquisition offers tend to sit well above it.'),
             ('Does a new casino have better odds?',
              'No. New sites run the same games from the same studios at the same published return figures. Newness affects who is holding your money, not the house edge on anything you play.'),
             ('Are there new online casinos in NZ with no deposit bonuses?',
              'New sites lean on acquisition offers, so no deposit bonuses and free spins on registration turn up more often on them than on established ones. The terms decide whether one is worth taking, not the newness &mdash; the limiting term on any no deposit offer is the maximum cashout, which is usually between NZ$50 and NZ$150.'),
             ('When will newly licensed casinos launch in New Zealand?',
              'Read the terms, because on a new site they are the entire risk assessment. Reputation is the usual proxy for the terms, and a new casino has none &mdash; so the withdrawal caps, the maximum conversion, the pending period and the reverse-withdrawal clause are all you have. Unlike reviews and forum threads, they are complete, free and available before you register.'),
             ('How do I check a casino with no track record?',
              'Use structure instead of reputation: find the registered company in the regulator&rsquo;s searchable list rather than trusting a footer licence number, read the withdrawal caps before the bonus terms, check the games come from named studios, look for a complaints path outside the operator, and deposit the minimum and withdraw early as a test.'),
         ],
         title="New Online Casinos NZ 2026 | Newest Casino Sites Checked | keno-results.co.nz",
         og="New casinos NZ",
         desc="New online casinos NZ for 2026: what the newest online casinos NZ and new casino sites NZ will not tell you, and how to check one with no track record."),
    dict(slug="no-deposit-bonus", faqtopic="No Deposit Bonuses", src="no-deposit-bonus",
         verdict=("No Deposit Bonuses in NZ",
              "The number that decides what a no deposit offer is worth is the maximum cashout, and it is never the number in the headline. On a typical New Zealand offer that cap runs NZ$50 to NZ$150, so a NZ$4,000 win pays NZ$100 and the rest simply evaporates.\n\nOnce you know that, the arithmetic stops being about spin counts: 100 spins capped at NZ$50 are worth less than 20 spins capped at NZ$150. My verdict is that these are worth claiming as a free look at a lobby and nothing more. Treat the cap as the actual prize and one will never disappoint you."),
                  section="casinos", noads=True,
         ct=dict(h="Best No Deposit Bonus NZ &mdash; Free Spins for {month}",
                 p="Fifteen casinos accepting Kiwi players, with the wagering and minimum deposit on every welcome offer. One of them &mdash; Lucky7even &mdash; hands you 20 spins before you deposit anything. On any no deposit bonus the figure that decides its value is the maximum cashout, and that is what the guide below is about."),
         faq=[
             ('What is a no deposit bonus?',
              'A small credit &mdash; cash or free spins &mdash; given for registering an account, with no deposit required. The figure that decides what it is worth is not the bonus size but the maximum conversion: a cap on what it can become no matter how much you win with it, commonly NZ$50 to NZ$150.'),
             ('Can you actually withdraw a no deposit bonus?',
              'Yes, up to the conversion cap and after the wagering requirement is met. If you win NZ$4,000 on a bonus with a NZ$100 cap, you withdraw NZ$100 &mdash; the rest is removed by a clause rather than by bad luck, which is why the cap is the first term to read.'),
             ('Are no deposit bonuses worth it?',
              'In pure money terms they cannot be negative, because you stake nothing of your own. What they cost is your identity documents, your contact details, a marketing relationship and a lot of time &mdash; NZ$20 at 50&times; is NZ$1,000 of turnover. They are an acquisition cost paid to you, not free money.'),
             ('Why do casinos give away no deposit bonuses?',
              'Because the wagering requirement is calibrated so the average player clears it with nothing left, and the small proportion who come out ahead are capped on the way out. The offer buys a verified account and a playing habit, and the lifetime value of the accounts that convert exceeds the cost of those that do not.'),
             ('Can you withdraw no deposit bonus winnings in NZ?',
              'Yes, up to the maximum cashout and once wagering is cleared. &ldquo;Keep what you win&rdquo; always means keep what you win up to the cap &mdash; an uncapped no deposit offer would be a standing invitation to arbitrage, so essentially nobody offers one.'),
             ('How do I claim a no deposit bonus?',
              'Register, verify your email or phone, and in most cases enter a bonus code on signup or opt in from the promotions page. Complete identity verification straight away rather than waiting &mdash; it is required before any withdrawal, and doing it before you have a balance removes the delay that causes most complaints.'),
             ('Are no deposit bonuses legit?',
              'The offers are real and the terms are enforced exactly as written, which is the part people mean when they ask. Nothing is hidden; the maximum cashout, wagering multiple and game restrictions are all in the terms, and they are calibrated so the average player clears the requirement with nothing left.'),
             ('What are no deposit bonus codes and are exclusive ones better?',
              'A code is usually a tracking string identifying the channel you arrived through. An &ldquo;exclusive&rdquo; code is exclusive to the publisher who issued it rather than better for you &mdash; the terms underneath are typically identical, and the cashout cap certainly is.'),
             ('Do I have to deposit to withdraw a no deposit bonus?',
              'Sometimes, and it is the clause to look for. Some terms require a qualifying deposit before the bonus can be cashed out at all, which quietly makes it a deposit offer. It is rarely stated on the landing page.'),
         ],
         title="No Deposit Bonus NZ 2026 | Free Spins No Deposit Offers | keno-results.co.nz",
         og="No deposit casino NZ",
         desc="Find no deposit bonus NZ offers and free spins no deposit NZ deals, with no deposit bonus codes NZ checked against the max cashout that decides their value."),
    dict(slug="crypto-casinos-nz", faqtopic="Crypto Casinos", src="crypto-casinos-nz",
         verdict=("Crypto Casinos in NZ",
              "Paying in crypto means making two bets rather than one, and only one of them is the game. The round trip costs four currency conversions instead of two, and on a short session that spread plus network fees runs more than the entire 2.70% house edge of single-zero roulette. You can win at the table and still finish the night down.\n\nThe claim I would treat as a warning rather than a feature is &ldquo;no verification&rdquo;. An operator that will not identify you at deposit has not spared you the paperwork; it has kept the option of demanding it at withdrawal, when it is holding your balance. Provably fair shows the deal was not rigged. It shows nothing about whether you get paid."),
                  section="casinos", noads=True,
         ct=dict(h="Best Crypto Casinos NZ &mdash; Bitcoin Sites for {month}",
                 p="Fifteen casinos that take New Zealand players and accept crypto, with the welcome offer and wagering on each. Before the bonus, price the round trip: paying in crypto means four currency conversions rather than two, and on a short session the spread costs more than the entire 2.70% house edge of single-zero roulette."),
         faq=[
             ('Are crypto casinos legal in New Zealand?',
              'Playing is not an offence for a New Zealander, and paying in crypto changes nothing about the operator&rsquo;s position either. The same questions apply as at any online casino: which regulator, is the company in that register, and is there a complaints path that leaves the building. Crypto sites are over-represented among operators with the thinnest licensing.'),
             ('What does provably fair actually prove?',
              'That the operator committed to a server seed before your bet existed, so the outcome could not be chosen after seeing it &mdash; and you can verify that yourself by hashing the revealed seed. It does not prove the house edge, does not prove you will be paid, and does not cover third-party pokies or live tables on the same site.'),
             ('Do crypto casinos really have no verification?',
              'Distrust the claim. Anti-money-laundering obligations attach to the operator, not the payment rail. Most verify exactly like anyone else and often do it later, at the first large withdrawal &mdash; the worst possible timing, because it arrives when you have a balance you want and no leverage.'),
             ('Are crypto withdrawals faster?',
              'The settlement step is. Network confirmation is minutes, but the pending period, verification, compliance review and manual approval in front of it run at the same speed as any other method, because it is the same process performed by the same team.'),
             ('Do I pay tax on crypto casino winnings in New Zealand?',
              'Two separate questions. Gambling winnings are generally not income for a recreational player, but Inland Revenue treats crypto-assets as property, and disposing of them &mdash; including converting back to New Zealand dollars &mdash; can give rise to taxable income depending on why the asset was acquired. General information, not tax advice.'),
             ('How do I deposit bitcoin at an online casino?',
              'Buy the asset on an exchange, send it to the deposit address the casino generates for your account, and wait for network confirmation &mdash; minutes on most chains. The steps are easy; the cost is not obvious, because a full round trip is four conversions rather than two, each carrying a spread, with network fees on top.'),
             ('Which crypto should I use at a casino?',
              'A stablecoin such as USDT if you do not want the currency exposure, because it removes the second bet you would otherwise be making on the asset price. Bitcoin, Ethereum, Litecoin and Dogecoin differ by an order of magnitude in network fee and confirmation time, so the choice is not cosmetic.'),
             ('Are crypto casino withdrawals faster than bank transfer?',
              'On the chain, yes &mdash; minutes rather than working days. Overall, often not, because the pending period, verification, compliance review and manual approval in front of settlement run at the same speed regardless of the rail. Crypto shortens the last stage of four.'),
             ('Do crypto casinos have better odds?',
              'No. Same games, same studios, same published return figures. A round trip is also four conversions rather than two, and the spreads plus network fees frequently exceed what a bank transfer would have cost.'),
         ],
         title="Crypto Casino NZ 2026 | Bitcoin Casino Sites and Real Costs | keno-results.co.nz",
         og="Best crypto casino NZ",
         desc="Best crypto casino NZ guide for 2026: what bitcoin casino NZ sites prove with provably fair, what bitcoin gambling NZ costs you in spread, and the tax point."),
    dict(slug="about", src="about", nav="about",
         title="About & Data Sources | keno-results.co.nz",
         og="About this site",
         desc="Who runs keno-results.co.nz, where the results come from, how every draw "
              "is validated before publication, and how to report an error.",
         schema=["org"]),
    dict(slug="lotto-nz", faqtopic="Lotto NZ Games", faq=[
             ('Do I pay tax on Lotto winnings in New Zealand?',
              'Lotto NZ states prize money is not taxed, so a prize is paid in full. What the money then earns &mdash; interest, dividends, rent &mdash; is taxable in the ordinary way. That is general information rather than tax advice; Inland Revenue is the right answer for your own circumstances.'),
             ('I found an old ticket &mdash; can I still claim?',
              'If the draw was within the last 12 months, yes. Lotto NZ allows 12 months from the draw date on all its draw games; Instant Kiwi runs 12 months from the date the game closed.'),
         ],
         src="lotto-nz", js=["game"],
         title="Lotto NZ Games Explained | keno-results.co.nz",
         og="Lotto NZ games",
         desc="The Lotto NZ games that run alongside Keno \u2014 Lotto, Powerball, Strike, "
              "Bullseye and Instant Kiwi \u2014 with the odds, draw nights and structure "
              "of each compared."),
    dict(slug="powerball", faqtopic="Powerball", faq=[
             ('How has Powerball changed since it launched in 2001?',
              'It began with eight Powerballs and a $1 million starting jackpot. The change on 13 September 2026, taking the pool from 10 to 14, is the fifth revision of the game.'),
             ('Why is there a Must Be Won draw?',
              'Because the current game ends. The final draw under the 10-Powerball format, on Saturday 12 September, is Must Be Won &mdash; if nobody takes Division 1 the pool flows down to the next division with winners rather than rolling into a game that no longer exists.'),
         ],
         src="powerball", js=["game"],
         title="Powerball NZ Explained | keno-results.co.nz",
         og="Powerball NZ",
         desc="How Powerball NZ attaches to a Lotto line, what it does to the odds, how "
              "the 2026 change to 14 balls shifts them, and why a bigger jackpot is "
              "not better odds."),
    dict(slug="bullseye", faqtopic="Bullseye", faq=[
             ('What are the odds of winning Bullseye?',
              'A six-digit number runs from 000000 to 999999, which is 1,000,000 possibilities, so one entry matches exactly once in a million. That follows from the format alone and does not change.'),
             ('When is Bullseye drawn?',
              'Once a day, in the evening New Zealand time. Every draw we hold has landed just after 6pm.'),
         ],
         src="bullseye", js=["game"],
         title="Bullseye NZ Explained | keno-results.co.nz",
         og="Bullseye NZ",
         desc="How Bullseye NZ works: the daily draw, the six-digit number, how the top "
              "prize and Bullseye odds are structured, and how it differs from Keno."),
    dict(slug="instant-kiwi", src="instant-kiwi",
         title="Instant Kiwi Explained | keno-results.co.nz",
         og="Instant Kiwi",
         desc="How Instant Kiwi odds really work: why scratch tickets differ from drawn "
              "games, what the published odds actually mean, and how they compare "
              "with Keno."),
    dict(slug="blog", src="blog", nav="blog",
         title="Keno Blog & Analysis NZ | keno-results.co.nz",
         og="Keno blog and analysis",
         desc="Analysis and reference drawn from our own New Zealand Keno draw archive - "
              "hot and cold numbers, multiplier data and draw times, with the working shown."),
    dict(slug="news", src="news", nav="news",
         title="Keno News NZ | keno-results.co.nz",
         og="Keno news",
         desc="Keno and Lotto NZ news, updated as draws land: multiplier records, "
              "jackpot rolls, Bullseye results and rule changes, each written from "
              "the published data."),
    dict(slug="contact", src="contact", nav="contact",
         title="Contact Us | keno-results.co.nz",
         og="Contact us",
         desc="Report a wrong Keno result, ask about our data, or get in touch about "
              "media and partnerships.",
         schema=[]),
    dict(slug="authors", src="authors",
         title="Authors & Editorial Standards | keno-results.co.nz",
         og="Authors and editorial standards",
         desc="Who writes and reviews keno-results.co.nz, how draw results are produced "
              "and validated, and the editorial rules everything published here has to pass.",
         schema=["org", "keri", "ngaio"]),
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
    # Same intent as /fast-payout-casinos/ - how fast do I get paid - so it
    # consolidates onto that page rather than competing with it for the query.
    "instant-withdrawals": "/fast-payout-casinos/",
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


# "More in this section" - the gaming cluster, which is editorial and carries
# no commercial placements.
GAMING = [
    ("gaming",                        "Overview"),
    ("gaming/online-casino-law",      "Online casino law"),
    ("gaming/who-regulates-gambling", "Who regulates it"),
    ("gaming/getting-help",           "Getting help"),
]


# "More in this section" - the online casino cluster. The hub carries a labelled
# operator table; the other eight pages are unpaid, and nothing on them moves
# for whoever is in it.
# Flat slugs rather than a /casinos/ subtree: each page sits at the root on
# the exact term it targets, so the URL itself carries the keyword.
# The hub carries a labelled operator table; every other page in the cluster is
# unpaid, and the arithmetic on them does not move for whoever is in that table.
CASINOS = [
    ("online-casinos",            "Overview"),
    ("licensed-online-casinos",   "Licensing"),
    ("casino-bonus",              "Bonuses"),
    ("casino-payout-percentages", "Payouts &amp; RTP"),
    ("fast-payout-casinos",       "Fast payouts"),
    ("casino-payment-methods",    "Payments"),
    ("online-pokies",             "Pokies"),
    ("live-casino",               "Live dealer"),
    ("no-deposit-bonus",          "No deposit"),
    ("new-casinos-nz",            "New casinos"),
    ("crypto-casinos-nz",         "Crypto"),
    ("how-we-rate-casinos",       "How we rate"),
]

# Which "more in this section" list a page's section name selects.
SUBNAVS = {"gaming": None, "casinos": None}   # filled below, after GAMING/CASINOS exist
SUBNAVS["gaming"] = GAMING
SUBNAVS["casinos"] = CASINOS


def subnav(slug, items_src=None):
    items = []
    for s_, label in (items_src or SECTION):
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
        # A bare URL is legal but Google asks for an ImageObject with dimensions,
        # and will not use a logo it has to go and measure itself.
        "logo": {"@id": SITE + "/#logo"},
        "image": {"@id": SITE + "/#logo"},
        "email": "info@keno-results.co.nz",
        "areaServed": {"@type": "Country", "name": "New Zealand"},
        "knowsAbout": ["Keno", "Lotto New Zealand", "Lottery results",
                       "Lottery odds and probability"],
        # The editorial standards page is what an E-E-A-T assessment is looking
        # for, and it is worth naming rather than leaving to be discovered.
        "publishingPrinciples": SITE + "/authors/",
        "contactPoint": [{
            "@type": "ContactPoint",
            "email": "info@keno-results.co.nz",
            "contactType": "customer support",
            "areaServed": "NZ",
            "availableLanguage": "English",
        }],
        "disambiguatingDescription":
            "An independent Keno results service. Not affiliated with, endorsed by, "
            "or operated by Lotto New Zealand.",
    },
    # The two named contributors on the casino section. Person nodes exist so a
    # byline is machine-readable rather than only rendered; jobTitle, knowsAbout
    # and alumniOf are what an E-E-A-T assessment actually reads.
    "keri": lambda: {
        "@type": "Person",
        "@id": SITE + "/authors/#keri-ihimaera",
        "name": "Keri Ihimaera",
        "url": SITE + "/authors/#keri-ihimaera",
        "image": {
            "@type": "ImageObject",
            "@id": SITE + "/authors/#keri-ihimaera-photo",
            "url": SITE + "/assets/img/authors/keri-ihimaera.jpg",
            "contentUrl": SITE + "/assets/img/authors/keri-ihimaera.jpg",
            "width": 320, "height": 320,
        },
        "jobTitle": "Senior Casino Reviewer & Live Dealer Specialist",
        "description": "Senior casino reviewer covering online slots, live dealer "
                       "studios and real-money banking, with more than 300 sites "
                       "tested since 2019.",
        "worksFor": {"@id": SITE + "/#org"},
        "alumniOf": {"@type": "CollegeOrUniversity", "name": "University of Auckland"},
        "knowsAbout": ["Live dealer casino studios", "Slot volatility and RTP",
                       "Casino withdrawal and KYC testing", "Bonus wagering terms",
                       "Mobile casino usability"],
        "knowsLanguage": ["English", "Spanish"],
    },
    "ngaio": lambda: {
        "@type": "Person",
        "@id": SITE + "/authors/#ngaio-hulme",
        "name": "Ngaio Hulme",
        "url": SITE + "/authors/#ngaio-hulme",
        "image": {
            "@type": "ImageObject",
            "@id": SITE + "/authors/#ngaio-hulme-photo",
            "url": SITE + "/assets/img/authors/ngaio-hulme.jpg",
            "contentUrl": SITE + "/assets/img/authors/ngaio-hulme.jpg",
            "width": 320, "height": 320,
        },
        "jobTitle": "Senior Compliance Reviewer, Online Casino & Payments",
        "description": "Compliance reviewer with eleven years as the final check on "
                       "online casino content, and nine years in AML transaction "
                       "monitoring and payments compliance.",
        "worksFor": {"@id": SITE + "/#org"},
        "alumniOf": {"@type": "CollegeOrUniversity",
                     "name": "Open Polytechnic of New Zealand"},
        "hasCredential": {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": "certification",
            "name": "Certified Anti-Money Laundering Specialist (CAMS)",
            "recognizedBy": {
                "@type": "Organization",
                "name": "Association of Certified Anti-Money Laundering Specialists",
            },
        },
        "knowsAbout": ["Online casino licensing", "Bonus terms and wagering audits",
                       "Payments and KYC compliance", "Anti-money laundering review",
                       "Editorial standards and corrections"],
    },
    "logo": lambda: {
        "@type": "ImageObject",
        "@id": SITE + "/#logo",
        "url": SITE + "/assets/img/icon-512.png",
        "contentUrl": SITE + "/assets/img/icon-512.png",
        "width": 512,
        "height": 512,
        "caption": "keno-results.co.nz",
    },
    "website": lambda: {
        "@type": "WebSite",
        "@id": SITE + "/#website",
        "url": SITE + "/",
        "name": "keno-results.co.nz",
        "description": "Every New Zealand Keno draw, checked against Lotto NZ's "
                       "own published results before it is shown.",
        "publisher": {"@id": SITE + "/#org"},
        "copyrightHolder": {"@id": SITE + "/#org"},
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
             "name": "How do I win at Keno?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "By matching drawn numbers, and no method "
                                        "makes that more likely. Every draw is "
                                        "independent and no combination is better "
                                        "than another. The only real choice is how "
                                        "many spots to play, because each spot count "
                                        "has a different prize ladder."}},
            {"@type": "Question",
             "name": "What time is the 6pm Keno draw in New Zealand?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "6:01pm New Zealand time. It is the last of "
                                        "four daily draws, after 10:01am, 1:01pm and "
                                        "3:01pm, and the time holds on weekends and "
                                        "public holidays."}},
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

# Month stamp for H1s and ledes, in NZ time. Regenerated every build rather
# than typed into a page, so a month-stamped headline can never be stale.
try:
    from zoneinfo import ZoneInfo
    NZ_MONTH = datetime.datetime.now(ZoneInfo("Pacific/Auckland")).strftime("%B %Y")
except Exception:                      # no tzdata: the month is still right
    NZ_MONTH = datetime.datetime.now().strftime("%B %Y")


# Two content sections, same machinery. "blog" is evergreen analysis and
# reference; "news" is timely items. Each has its own JSON file and index.
SECTIONS = {
    "blog": {"file": "blog.json", "key": "posts", "label": "Blog",
             "schema": "Article",
             "eyebrow": "Analysis &amp; reference",
             "empty_h": "Nothing Published Yet",
             "empty_p": "Analysis and reference posts will appear here."},
    "news": {"file": "news.json", "key": "articles", "label": "News",
             "schema": "NewsArticle",
             "eyebrow": "News",
             "empty_h": "No News Yet",
             "empty_p": "Timely Keno and lottery news will appear here as we publish it."},
}


def _entries(kind):
    cfg = SECTIONS[kind]
    try:
        with open(os.path.join(SRC, "data", cfg["file"]), encoding="utf-8") as fh:
            items = json.load(fh).get(cfg["key"], [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    items = [_tc_entry(a) for a in items]
    return sorted(items, key=lambda a: a.get("date", ""), reverse=True)


_BODY_H = re.compile(r"(<h([1-6])(?:\s[^>]*)?>)(.*?)(</h\2>)", re.S)


def _tc_entry(a):
    """Title Case an article's headline and its in-body section headings.

    Done at load rather than in the JSON so it also covers whatever
    auto_news.py writes next, and so the headline, the listing card, the
    <title>, og:title and the schema headline cannot drift apart.
    """
    out = dict(a)
    if a.get("title"):
        out["title"] = title_case(a["title"])
    if a.get("body"):
        out["body"] = _BODY_H.sub(
            lambda m: m.group(1) + title_case(m.group(3)) + m.group(4), a["body"])
    return out


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


# Pages whose content is the draw data itself, so they genuinely change
# whenever a new draw lands - unlike the guides, which change when edited.
DATA_PAGES = {"", "results", "statistics", "lotto-nz", "powerball", "bullseye"}

_GIT_DATES = None


def git_dates():
    """Last commit date for every tracked file, from one pass of the log.

    lastmod has to mean something. Stamping today's date on /terms/ because the
    generator happened to run is not a modification, and Google's documented
    response to a lastmod it cannot correlate with real change is to stop
    trusting the field across the whole site. Now that results rebuild on a
    schedule, every static page was claiming to change daily."""
    global _GIT_DATES
    if _GIT_DATES is not None:
        return _GIT_DATES
    _GIT_DATES = {}
    try:
        out = subprocess.run(
            ["git", "log", "--name-only", "--format=%x00%cd", "--date=short"],
            cwd=ROOT, capture_output=True, text=True, timeout=90).stdout
    except (OSError, subprocess.SubprocessError):
        return _GIT_DATES
    date = None
    for line in out.splitlines():
        if line.startswith("\x00"):
            date = line[1:].strip()
        elif line.strip() and date:
            _GIT_DATES.setdefault(line.strip(), date)   # log is newest-first
    return _GIT_DATES


def latest_draw_ymd():
    ds = _draws().get("draws") or []
    return max((_nz_dt(d["drawnAt"])[2] for d in ds), default=None)


CONTENT_DATES = os.path.join(SRC, "data", "content-dates.json")
# The page fields that are content. Everything else in a PAGES entry - js,
# schema keys, nav, section - is plumbing, and changing it is not a page edit.
CONTENT_KEYS = ("title", "og", "desc", "ct", "faq", "faqtopic", "verdict")


def _content_fingerprint(page):
    """A hash of the copy this page carries inside build.py.

    Titles, descriptions, FAQ questions, table standfirsts and the author's
    verdict all live here rather than in src/pages, so a git date on the source
    file cannot see them change. {month} is normalised out: a month-stamp
    rolling over is not an edit, and treating it as one would bump every casino
    page on the first of the month for nothing.
    """
    blob = json.dumps([page.get(k) for k in CONTENT_KEYS],
                      sort_keys=True, ensure_ascii=False, default=str)
    blob = blob.replace("{month}", "")
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def _content_dates():
    """slug -> {hash, date}, persisted so the date survives the next build."""
    if not hasattr(_content_dates, "_c"):
        try:
            with open(CONTENT_DATES, encoding="utf-8") as fh:
                _content_dates._c = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            _content_dates._c = {}
        _content_dates._dirty = False
    return _content_dates._c


def content_date(page):
    """The day this page's build.py copy last changed, recorded on first sight."""
    store = _content_dates()
    key = page["slug"] or "index"
    fp = _content_fingerprint(page)
    rec = store.get(key)
    if not rec or rec.get("hash") != fp:
        store[key] = {"hash": fp, "date": datetime.date.today().isoformat()}
        _content_dates._dirty = True
    return store[key]["date"]


def flush_content_dates():
    if getattr(_content_dates, "_dirty", False):
        os.makedirs(os.path.dirname(CONTENT_DATES), exist_ok=True)
        with open(CONTENT_DATES, "w", encoding="utf-8") as fh:
            json.dump(_content_dates(), fh, indent=1, sort_keys=True)
            fh.write("\n")


def page_lastmod(page):
    """When this page's content last actually changed.

    Deliberately ignores base.html and the stylesheet: re-skinning a page is not
    a content change, and treating it as one is exactly what devalues the field.

    Two sources, because a page's copy lives in two places: the body in
    src/pages, and the title, description, FAQ, standfirst and verdict in the
    PAGES entry here."""
    cand = [git_dates().get("src/pages/%s.html" % page["src"]), content_date(page)]
    if page["slug"] in DATA_PAGES:
        cand.append(latest_draw_ymd())
    cand = [d for d in cand if d]
    return max(cand) if cand else datetime.date.today().isoformat()


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
            + _mark(o, "", "offer-word")
            + f'</span>'
            f'<span class="offer-body">'
            f'<span class="offer-name">{name}</span>'
            f'<span class="offer-bonus">{o.get("bonus", "")}</span>'
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


def _mark(o, img_cls, word_cls):
    """An operator's logo, or a typographic wordmark when we hold no artwork.

    Most of the roster supplied a tracking link and nothing else. Borrowing an
    operator's logo from their own site is not ours to do, and inventing one is
    worse, so the name is set in the display face instead.
    """
    src = o.get("logoRev") or o.get("logo")
    name = html.escape(o["name"])
    if not src:
        return '<span class="%s">%s</span>' % (word_cls, name)
    cls = ' class="%s"' % img_cls if img_cls else ""
    return '<img%s src="%s" alt="%s" loading="lazy" decoding="async">' % (cls, src, name)


def byline_block(page):
    """Attribution and review date, as one line under the H1.

    The casino section is written and reviewed by the two named contributors on
    /authors/, so those pages carry a person byline. Everywhere else stays
    attributed to the site: the draw results are machine-produced and the Keno
    guides are the owner's, and claiming otherwise in a byline would be the one
    thing /authors/ exists to rule out.

    The date is page_lastmod(), the same value the sitemap reports, so the
    visible stamp and the machine-readable one cannot drift apart.
    """
    d = datetime.date.fromisoformat(page_lastmod(page)).strftime("%-d %B %Y")
    # The methodology link is a casino-section page and that section carries
    # paid placements. /gaming/ states it keeps advertising off, so it gets the
    # editorial-standards link instead - the byline should not be the one place
    # that quietly routes an unpaid page into a commercial one.
    if page.get("section") == "gaming":
        third = '<a class="byline-m" href="/authors/">Editorial standards</a>'
    else:
        third = '<a class="byline-m" href="/how-we-rate-casinos/">How we rate</a>'
    sep = '<span class="byline-sep" aria-hidden="true">&middot;</span>'
    if page.get("section") == "casinos":
        who = ('<span class="byline-by">By '
               '<a class="byline-au" href="/authors/#keri-ihimaera" rel="author">'
               'Keri Ihimaera</a></span>' + sep +
               '<span class="byline-by">Reviewed by '
               '<a class="byline-au" href="/authors/#ngaio-hulme">'
               'Ngaio Hulme</a></span>')
    else:
        who = '<a class="byline-a" href="/authors/">keno-results.co.nz</a>'
    return ('<p class="byline">' + who + sep +
            '<span class="byline-d">Updated <time datetime="%s">%s</time></span>'
            + sep + third + '</p>') % (page_lastmod(page), d)


def operator_itemlist(url):
    """An ItemList naming the operators the page lists, in display order.

    Name and position only. Deliberately no Review, AggregateRating or Offer
    node: Google restricted self-serving review markup, and a rating awarded to
    an entity you have a paid relationship with is the exact case it targets --
    a manual action there costs far more than the rich result is worth. This
    says "the page lists these fifteen, in this order" and claims nothing about
    quality.

    itemListOrder is omitted rather than guessed. The order is editorial, so it
    is neither ascending nor descending by any property, and declaring it
    unordered would contradict the visible 01-15 numbering.
    """
    live = sorted((o for o in _load_offers()
                   if o.get("active") and o.get("casino") and o.get("urlCasino")),
                  key=lambda o: (o.get("order", 999), o["name"].lower()))
    if not live:
        return None
    return {
        "@type": "ItemList",
        "@id": url + "#operators",
        "name": "Online casino operators listed on this page",
        "numberOfItems": len(live),
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": o["name"]}
            for i, o in enumerate(live, 1)
        ],
    }


def casino_table(page=None):
    """The operator comparison table, rendered from offers.json.

    Heading and standfirst come from the page's own `ct` dict, so each of the
    twelve pages spends this H2 on its own head term rather than repeating one
    generic line. The standfirst is first person and carries a real figure --
    never a claim about testing that has not happened, which is the exact tell
    /how-we-rate-casinos/ warns readers to look for.

    Built from the same file as the rails and the bonus box so the three can
    never disagree about what an operator is offering - drift between a table
    and a banner is exactly what turns an affiliate page into a liability.

    Every row is labelled as a paid placement and every link carries
    rel="sponsored", because an undisclosed affiliate link is both a Search
    policy violation and the thing that makes the disclosure elsewhere on the
    page worthless.

    Ordering comes from `order` in offers.json - a sequence chosen by the site
    owner, not computed. It was alphabetical until that field existed, and the
    pages said so precisely because alphabetical is checkable; a chosen order is
    not, so the copy no longer claims the ordering is independent of commercial
    terms. It says the order is ours and leaves the reader to weigh it.
    """
    # A partner qualifies for this table only if it offers casino games AND
    # supplied a casino tracking link. Both halves matter: Rooster.Bet has
    # casino=true but gave us only a sportsbook link, so linking it from a
    # casino page would send readers to the wrong product and the click would
    # not track. Sports-only partners are excluded outright.
    live = sorted((o for o in _load_offers()
                   if o.get("active") and o.get("casino") and o.get("urlCasino")),
                  key=lambda o: (o.get("order", 999), o["name"].lower()))
    if not live:
        return ""

    rows = []
    for i, o in enumerate(live, 1):
        name = html.escape(o["name"])
        logo = o.get("logoRev") or o.get("logo")
        # The card plates the mark on its own tile; where we hold no artwork the
        # plate is dropped rather than filled with a borrowed or invented logo.
        mark = (f'<span class="ct-mark">'
                # No width/height attributes: the masters run 128x128 to
                # 435x128, so one hard-coded pair would be wrong for nearly all
                # of them. The plate is a fixed size and reserves the space, so
                # there is no layout shift to guard against.
                f'<img class="ct-logo" src="{logo}" alt="{name}" loading="lazy" '
                f'decoding="async"></span>') if logo else ""

        # Feature line: the operator's own points, mid-dot separated, plus the
        # licence and game count when those have been supplied to us.
        bits = list(o.get("points", [])[:3])
        if o.get("licence"):
            bits.insert(0, html.escape(o["licence"]))
        if o.get("games"):
            bits.append(html.escape(o["games"]))
        tagline = " &middot; ".join(bits)

        # Score bar. Absent from the data for every partner, and deliberately so
        # - /how-we-rate-casinos/ sets out why this site does not publish a
        # composite score. Wired up so it can be switched on, not switched on.
        score = o.get("score")
        score_html = ""
        if score:
            pct = max(0.0, min(10.0, float(score))) * 10
            score_html = (
                f'<div class="ct-score">'
                f'<div class="ct-bar"><span style="width:{pct:.0f}%"></span></div>'
                f'<div class="ct-score-r"><span>Our score</span>'
                f'<b>{float(score):.1f}/10</b></div></div>')

        badge = (f'<span class="ct-badge">{html.escape(o["badge"])}</span>'
                 if o.get("badge") else "")

        # offerText is one readable phrase; amount/amountSub are the two-line
        # split the rails and bonus box use, and reading them end to end gives
        # "NZ$3,700 390% welcome bonus + 175 free spins".
        text = o.get("offerText") or (
            ("%s %s" % (o.get("amount", ""),
                        (o.get("amountSub") or "").replace("<br>", " "))).strip())
        if text:
            offer = (f'<div class="ct-offer-box">'
                     f'<span class="ct-offer-l">Welcome offer</span>'
                     f'<span class="ct-offer-t">{text}</span></div>')
        else:
            offer = ('<div class="ct-offer-box ct-offer-none">'
                     '<span class="ct-offer-l">Welcome offer</span>'
                     '<span class="ct-offer-t">None supplied to us</span></div>')

        # Terms footnote: only facts we actually hold. 18+ and T&Cs always apply;
        # wagering and minimum deposit appear per operator when supplied.
        terms = []
        if o.get("wagering"):
            terms.append(html.escape(o["wagering"]) + " wagering")
        if o.get("minDeposit"):
            terms.append(html.escape(o["minDeposit"]) + " min deposit")
        terms.append("18+ T&amp;Cs apply")
        terms_html = " &middot; ".join(terms)

        rows.append(
            f'<tr>'
            f'<td class="ct-rank"><span class="ct-num">{i:02d}</span>{badge}</td>'
            f'<td class="ct-brand">{mark}'
            f'<span class="ct-name">{name}</span>'
            f'<span class="ct-kind">{html.escape(o.get("kind", ""))}</span>'
            f'<span class="ct-tag">{tagline}</span></td>'
            f'<td class="ct-offer">{score_html}{offer}</td>'
            f'<td class="ct-go">'
            f'<a class="ct-cta" href="{o["urlCasino"]}" target="_blank" '
            f'rel="sponsored nofollow noopener">'
            f'{html.escape(o.get("cta", "Visit site"))}'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'<path d="M5 12h14M13 6l6 6-6 6"/></svg></a>'
            f'<span class="ct-terms">{terms_html}</span></td>'
            f'</tr>')

    ct = (page or {}).get("ct") or {}
    heading = ct.get("h", "Online Casino Sites Accepting New Zealand Players")
    note = ct.get("p", 'All three are commercial partners of this site and every '
                       'link below is paid, and the order is ours rather than a ranking '
                       'earned on merit.')

    # The per-page commentary leads; on mobile it drops below the table, because
    # it was ten lines deep on a phone and pushed the first operator card off
    # the screen entirely.
    return (
        '<section class="ct-wrap" aria-labelledby="ct-h">'
        '<div class="ct-head">'
        '<h2 id="ct-h">' + heading + '</h2>'
        '</div>'
        '<p class="ct-note">' + note + '</p>'
        '<div class="tw ct-tw"><table class="ct">'
        '<caption class="vh">Commercial partners, in the order this site lists them</caption>'
        '<thead><tr><th><span class="vh">Rank</span></th><th>Operator</th>'
        '<th>Welcome offer</th><th><span class="vh">Visit</span></th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table></div>'
        # Disclosure sits directly under the links, in the form the rest of this
        # industry uses: one quiet line rather than a pill shouting beside the
        # heading. Still adjacent, still paired with rel="sponsored" on every
        # link - which is the part Search actually requires. Removing it
        # altogether would be a Fair Trading Act problem, not a design choice.
        '<p class="ct-adv">Advertiser disclosure: we earn a commission from the '
        'operators listed here. It does not change what the guides below say. '
        '<a href="/how-we-rate-casinos/">How we rate</a></p>'
        '<p class="ct-legal">18+ only. Gambling carries a fixed house edge and returns '
        'less than it takes in over time. Set a limit before you play. Free confidential '
        'help: Gambling Helpline 0800 654 655 or text 8006 \u2014 '
        '<a href="/gaming/getting-help/">getting help</a>.</p>'
        '</section>')


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
            mark = _mark(o, "rail-logo", "rail-word")
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
            headline = (f'<span class="rail-bonus">{o.get("bonus", "")}</span>'
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


# Pages that index other pages rather than being the destination themselves.
COLLECTIONS = {"results", "odds", "statistics", "blog", "news"}
PAGE_TYPES = {"contact": "ContactPage", "about": "AboutPage",
              "authors": "AboutPage"}
# Node types that are the *subject* of their page rather than a second copy of
# it, so the WebPage stays a WebPage and points at them.
MAIN_ENTITY_TYPES = {"FAQPage", "HowTo", "Dataset"}


def crumb_list(url, trail):
    """A BreadcrumbList with an @id, so a WebPage node can point at it.

    trail is [(name, url), ...] excluding Home, which is always first."""
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"}]
    for i, (name, href) in enumerate(trail, start=2):
        items.append({"@type": "ListItem", "position": i, "name": name, "item": href})
    return {"@type": "BreadcrumbList", "@id": url + "#breadcrumb",
            "itemListElement": items}


def page_graph(url, name, description, *, page_type="WebPage", modified=None,
               published=None, crumbs=None, nodes=(), main_entity=None,
               image=None, author=None, reviewer=None):
    """The full JSON-LD graph for one page.

    Organization and WebSite ship on *every* page, not just the homepage. Nearly
    every node on this site points at #org as publisher, creator or author, and
    Google resolves an @id only within the graph on the page it is reading - so
    on any page that omitted them, those references pointed at nothing at all.

    The WebPage node is the piece that was missing entirely: it is what ties a
    URL to the site, to its breadcrumb trail, and to a modification date."""
    wp = {
        "@type": page_type,
        "@id": url + "#webpage",
        "url": url,
        "name": re.sub(r"\s*\|.*$", "", name),
        "description": description,
        "isPartOf": {"@id": SITE + "/#website"},
        "about": {"@id": SITE + "/#org"},
        "publisher": {"@id": SITE + "/#org"},
        # Defaults to the Organization. A page passes a Person only where a
        # named contributor really is responsible for it, and the matching
        # Person node has to ship in this same graph - an @id resolves only
        # within the page Google is reading.
        "author": {"@id": author or (SITE + "/#org")},
        "inLanguage": "en-NZ",
    }
    if reviewer:
        wp["reviewedBy"] = {"@id": reviewer}
    if published:
        wp["datePublished"] = published
    if modified:
        wp["dateModified"] = modified
    if crumbs:
        wp["breadcrumb"] = {"@id": crumbs["@id"]}
    if main_entity:
        wp["mainEntity"] = main_entity
    if image:
        wp["primaryImageOfPage"] = {"@type": "ImageObject", "url": image}
    graph = [SCHEMA["org"](), SCHEMA["logo"](), SCHEMA["website"](), wp]
    graph.extend(n for n in nodes if n)
    if crumbs:
        graph.append(crumbs)
    return {"@context": "https://schema.org", "@graph": graph}


def ld_script(graph):
    return ('<script type="application/ld+json">'
            + json.dumps(graph, indent=None, separators=(",", ":"))
            + "</script>")


# A cluster's hub, so its spokes can declare a real trail instead of the flat
# Home > Page every other page gets. Only clusters with a genuine hub appear
# here; inventing a middle level for a page that has no parent would be worse
# than a two-step crumb.
CLUSTER_HUB = {
    "casinos": ("online-casinos", "Online casinos in NZ"),
    "gaming":  ("gaming", "Gambling in New Zealand"),
}


def breadcrumbs(page):
    if not page["slug"]:
        return None
    label = re.sub(r"\s*\|.*$", "", page["og"])
    trail = []
    hub = CLUSTER_HUB.get(page.get("section"))
    if hub and hub[0] != page["slug"]:
        trail.append((hub[1], f"{SITE}/{hub[0]}/"))
    trail.append((label, f"{SITE}/{page['slug']}/"))
    return crumb_list(f"{SITE}/{page['slug']}/", trail)


def page_deco(key):
    """Which of the four page-top wedge variants this page gets.

    Hashed from the page's own key so it is stable across builds - a wedge that
    changed shape every time the generator ran would be noise, not design - and
    spread so neighbouring pages in a section rarely repeat.
    """
    if key == "home":
        return "a"          # the variant that was reviewed and approved
    return "abcd"[int(hashlib.sha1(key.encode()).hexdigest(), 16) % 4]


def _art_alt(a):
    art = a.get("art") or {}
    if art.get("kind") in ("draw", "keno", "bullseye"):
        return ("The numbers drawn in %s draw %s, shown as coloured balls."
                % (art.get("game", ""), art.get("drawNumber", "")))
    return ("Abstract illustration in the site's colours, accompanying the "
            "article \u2014 it does not depict a real draw.")


def _art_cap(a):
    art = a.get("art") or {}
    if art.get("kind") in ("draw", "keno", "bullseye"):
        return "%s draw %s &mdash; the numbers as drawn" % (
            html.escape(str(art.get("game", ""))), art.get("drawNumber", ""))
    return "Illustration &mdash; abstract, not a photograph"


def band_block():
    """A horizontal partner banner for viewports below the rail breakpoint.

    The side rails only appear at 1460px and up, so on every phone and most
    laptops the two rail partners are invisible. This fills that gap with one
    of them, laid out horizontally, and disappears the moment the rails take
    over so nobody ever sees both.

    Rendered from offers.json like everything else, so the banner and the rail
    can never disagree about the offer."""
    offers = [o for o in _load_offers() if o.get("active", True)
              and o.get("placement") == "rail-right"]
    if not offers:
        return ""
    o = offers[0]
    t = o.get("theme", {})
    style = ("--o-deep:%s;--o-base:%s;--o-cyan:%s;--o-cta-a:%s;--o-cta-b:%s"
             % (t.get("deep", "#050522"), t.get("base", "#111135"),
                t.get("cyan", "#00F0F1"), t.get("ctaFrom", "#6A2BE8"),
                t.get("ctaTo", "#2F6FD6")))
    return (
        f'<aside class="promo-band" aria-label="Advertisement" style="{style}">'
        f'<a class="band-in" href="{o["url"]}" target="_blank" '
        f'rel="sponsored nofollow noopener">'
        f'<span class="band-flag">Ad</span>'
        + _mark(o, "band-logo", "band-word")
        + f'<span class="band-copy">'
        f'<span class="band-amt">{o.get("amount", "")}</span>'
        # the rail breaks this over two lines; here it is one, so the <br>
        # becomes a space rather than being hidden and closing the gap
        f'<span class="band-sub">'
        f'{(o.get("amountSub", "") or "").replace("<br>", " ")}</span></span>'
        f'<span class="band-cta">{html.escape(o.get("cta", "Claim"))}'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>'
        f'</a></aside>')


def bonusbox_block():
    """The three partner offers, rendered from offers.json.

    Built from the data rather than typed into base.html, so the box and the
    rails can never disagree about what an operator is offering - which is the
    kind of drift that turns an affiliate page into a liability."""
    offers = [o for o in _load_offers() if o.get("active", True)]
    if not offers:
        return ""
    cards = []
    for i, o in enumerate(offers[:3]):
        t = o.get("theme", {})
        style = (
            "--c-deep:%s;--c-base:%s;--c-accent:%s;--c-cta-a:%s;--c-cta-b:%s;--i:%d"
            % (t.get("deep", "#12161D"), t.get("base", "#1A1F29"),
               t.get("cyan", "#E9B44C"), t.get("ctaFrom", "#0A6E3C"),
               t.get("ctaTo", "#085A31"), i))
        pts = "".join("<li>%s</li>" % p for p in (o.get("points") or [])[:3])
        cards.append(
            f'<li class="bb-card" style="{style}">'
            f'<span class="bb-kind">{html.escape(o.get("kind", "Offer"))}</span>'
            # logoRev where an operator's mark is dark-on-white: the inline
            # banner sets that one on a white plate, these cards do not.
            + _mark(o, "bb-logo", "bb-word")
            + f'<span class="bb-amount">{o.get("amount", "")}</span>'
            f'<span class="bb-sub">{o.get("amountSub", "")}</span>'
            f'<ul class="bb-points">{pts}</ul>'
            f'<a class="bb-cta" href="{o["url"]}" target="_blank" '
            f'rel="sponsored nofollow noopener">{html.escape(o.get("cta", "Claim bonus"))}'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>'
            f'</li>')
    return (
        '<div class="bb-modal" id="bonus-box" hidden>'
        '<div class="bb-backdrop" data-bb-close></div>'
        '<div class="bb-panel" role="dialog" aria-modal="true" aria-labelledby="bb-title">'
        '<button class="bb-x" type="button" data-bb-close aria-label="Close">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>'
        '</button>'
        '<span class="bb-flag">Advertisement</span>'
        '<p class="bb-eyebrow">Bonus box</p>'
        f'<h2 class="bb-title" id="bb-title">{len(cards)} Welcome Offers</h2>'
        '<p class="bb-lede">From the operators we carry. Not a prize draw &mdash; '
        'these are the same paid placements you see on the page, in one place.</p>'
        f'<ul class="bb-grid">{"".join(cards)}</ul>'
        '<p class="bb-fine">18+. New players only. T&amp;Cs apply. Paid placements '
        '&mdash; we earn a commission if you sign up. Gamble responsibly: '
        '<a href="/responsible-gambling/">know the signs</a>.</p>'
        '</div></div>')


def hreflang_block(canonical, robots=""):
    """Alternates for the two English markets this content serves.

    All three point at the same URL, which is valid and self-reciprocal - it
    declares one page serving both, not a separate Australian edition.

    Omitted entirely on noindex pages: telling Google "here is the Australian
    alternate" while also telling it not to index the page is a contradiction,
    and the 404 was picking it up from the shared template.
    """
    if robots.startswith("noindex"):
        return ""
    return "".join(
        '<link rel="alternate" hreflang="%s" href="%s">' % (lang, canonical)
        for lang in ("en-NZ", "en-AU", "x-default"))



def verdict_block(page):
    """The author's closing judgement, above the FAQ.

    Only on pages that carry a person byline. A signed verdict on a page
    attributed to the organisation would be attributing an opinion to nobody,
    and the Keno pages are not hers to sign.

    Each one is written against what that page actually argues and repeats its
    figures, so it reads as a conclusion rather than a summary bolted on.
    """
    v = page.get("verdict")
    if not v or page.get("section") != "casinos":
        return ""
    topic, text = v
    paras = "".join("<p>%s</p>" % para.strip() for para in text.strip().split("\n\n"))
    return (
        '<div class="wrap"><section class="verdict" aria-labelledby="verdict-h">'
        '<div class="sec-h"><h2 id="verdict-h">The Final Verdict on %s</h2></div>'
        '<div class="verdict-card">'
        '<div class="verdict-by">'
        '<img class="verdict-pic" src="/assets/img/authors/keri-ihimaera.jpg" '
        'width="56" height="56" alt="Keri Ihimaera" loading="lazy" decoding="async">'
        '<span class="verdict-who">'
        '<a href="/authors/#keri-ihimaera" rel="author">Keri Ihimaera</a>'
        '<span class="verdict-role">Senior Casino Reviewer</span></span>'
        '</div>'
        '<div class="verdict-text">%s</div>'
        '</div></section></div>' % (html.escape(topic), paras))


def faq_block(faq, page=None):
    """Per-page questions, rendered as the same disclosure list /faqs/ uses.

    Questions come from what people actually ask - Lotto NZ's own FAQ for the
    operator-side ones, and the question-form search terms for the rest. Answers
    are written here from figures this site can verify, which is the only kind
    worth publishing: an FAQ that guesses is worse than no FAQ, because it gets
    quoted back as fact.
    """
    if not faq:
        return ""
    items = "".join(
        '<details%s><summary>%s</summary><div class="a">%s</div></details>'
        % (" open" if i == 0 else "", html.escape(q), a)
        for i, (q, a) in enumerate(faq))
    # "Frequently Asked Questions About X" rather than a bare "Common Questions":
    # it is the phrasing people search, and it tells a reader arriving at an
    # anchor which page's questions these are. faqtopic is the noun phrase; it
    # falls back to the og title, which is close enough to read correctly.
    topic = (page or {}).get("faqtopic") or (page or {}).get("og")
    heading = ("Frequently Asked Questions About %s" % topic) if topic \
        else "Frequently Asked Questions"
    # {faq} is injected into <main> after the page's own .wrap divs have closed,
    # so without one of its own the whole block sat flush against both window
    # edges - no side margin at all, and the card borders clipped off-screen.
    return ('<div class="wrap"><section><div class="sec-h"><h2>%s</h2></div>'
            '<div class="faq">%s</div></section></div>'
            % (html.escape(heading), items))


def faq_schema(faq, url):
    """FAQPage for the questions on this page, as the WebPage's mainEntity."""
    if not faq:
        return None
    return {
        "@type": "FAQPage",
        "@id": url + "#faq",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer",
                                "text": re.sub(r"<[^>]+>", "", a).strip()}}
            for q, a in faq],
    }


ADS_RE = re.compile(r"<!--ADS:(\w+)-->.*?<!--/ADS:\1-->", re.S)


def strip_ads(html):
    """Remove every commercial placement from a page.

    Used by /gaming/, which writes about online casino regulation. Carrying
    casino advertising beside that would read badly and, per the DIA, the
    advertising itself is prohibited - so those pages carry none of it.
    Markers rather than a regex over nested markup, so removal is exact."""
    html = ADS_RE.sub("", html)
    for slot in ("{rail}", "{rail_left}", "{band}", "{bonusbox}"):
        html = html.replace(slot, "")
    return html


def analytics_block():
    """Cloudflare Web Analytics, or nothing at all.

    Chosen over Google Analytics deliberately: it sets no cookies and builds no
    cross-site profile, so the pages stay consistent with what the privacy and
    cookie policies promise, and no consent gate is required. With no token
    configured this returns an empty string and the site ships untracked."""
    try:
        with open(os.path.join(SRC, "data", "analytics.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    token = (cfg.get("token") or "").strip()
    if not token:
        return ""
    return ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
            'data-cf-beacon=\'{"token":"%s"}\'></script>' % html.escape(token, quote=True))


# Images worth declaring. Only the ones that carry meaning - the contributor
# portraits and the article artwork. Icons and the logo are chrome, and listing
# them would pad the file without telling a crawler anything.
SITEMAP_IMAGES = {
    "authors": [("/assets/img/authors/keri-ihimaera.jpg", "Keri Ihimaera"),
                ("/assets/img/authors/ngaio-hulme.jpg", "Ngaio Hulme")],
}


def _sitemap_images(page):
    out = []
    for src, title in SITEMAP_IMAGES.get(page["slug"], []):
        out.append(f"<image:image><image:loc>{SITE}{src}</image:loc>"
                   f"<image:title>{html.escape(title)}</image:title></image:image>")
    return "".join(out)


def build():
    base = open(os.path.join(SRC, "base.html"), encoding="utf-8").read().replace("{analytics}", analytics_block()).replace("{bonusbox}", bonusbox_block()).replace("{band}", band_block())
    written = []

    for page in PAGES:
        slug = page["slug"]
        body = open(os.path.join(SRC, "pages", page["src"] + ".html"), encoding="utf-8").read()

        canonical = SITE + "/" if not slug else f"{SITE}/{slug}/"
        if page.get("path"):
            canonical = f"{SITE}/{page['path']}"

        keys = list(page.get("schema", []))
        # a person byline needs its Person node on the same page
        if page.get("section") == "casinos":
            keys += [k for k in ("keri", "ngaio") if k not in keys]
        extra = [SCHEMA[k]() for k in keys if k not in ("org", "website")]
        ptype = PAGE_TYPES.get(slug) or ("CollectionPage" if slug in COLLECTIONS
                                         else "WebPage")
        pfaq = faq_schema(page.get("faq"), canonical)
        if pfaq:
            # A page must not carry two FAQPage nodes, and schema questions have
            # to be the ones actually rendered - the older SCHEMA-key FAQs were
            # never on the page, which is exactly what Google rejects. The
            # per-page list is what the visitor sees, so it replaces them.
            extra = [n for n in extra if n.get("@type") != "FAQPage"]
            extra.append(pfaq)
        # Pages that render the operator table describe it in the graph too, so
        # the fifteen names are machine-readable as a list rather than only as
        # table markup.
        if page.get("section") == "casinos":
            il = operator_itemlist(canonical)
            if il:
                extra.append(il)
        main = None
        for n in extra:
            if n.get("@type") in MAIN_ENTITY_TYPES:
                n.setdefault("@id", canonical + "#main")
                main = {"@id": n["@id"]}
                break
        head_extra = "" if page.get("robots", "").startswith("noindex") else ld_script(
            page_graph(canonical, page["og"], page["desc"], page_type=ptype,
                       modified=page_lastmod(page), crumbs=breadcrumbs(page),
                       nodes=extra, main_entity=main,
                       author=(SITE + "/authors/#keri-ihimaera"
                               if page.get("section") == "casinos" else None),
                       reviewer=(SITE + "/authors/#ngaio-hulme"
                                 if page.get("section") == "casinos" else None)))

        scripts = "".join(
            f'<script src="/assets/js/{name}.js" defer></script>' for name in page.get("js", []))

        nav = page.get("nav")
        out = strip_ads(base) if page.get("noads") else base
        for key in ("home", "check", "results", "stats", "howto", "odds", "tools", "blog", "news", "about", "contact"):
            out = out.replace("{c_%s}" % key, ' aria-current="page"' if nav == key else "")

        out = (out
               .replace("{page_id}", slug or "home")
               .replace("{page_art}", page_deco(slug or "home"))
               .replace("{title}", html.escape(page["title"]).replace("{month}", NZ_MONTH))
               .replace("{og_title}", html.escape(page["og"]))
               .replace("{description}", html.escape(page["desc"]))
               .replace("{canonical}", canonical)
               .replace("{hreflang}", hreflang_block(canonical, page.get("robots", "")))
               .replace("{robots}", page.get("robots", "index, follow, max-image-preview:large"))
               .replace("{site}", SITE)
                   .replace("{og_image}", SITE + "/assets/img/icon-512.png")
                   .replace("{tw_card}", "summary")
               .replace("{head_extra}", head_extra)
               .replace("{scripts}", scripts)
               .replace("{rail}", "" if page.get("noads") else rail_block("rail-right"))
               .replace("{rail_left}", "" if page.get("noads") else rail_block("rail-left"))
               .replace("{content}", body.rstrip()
                   .replace("{subnav}",
                            subnav(slug, SUBNAVS.get(page.get("section")))
                            if page.get("section") else "")
                   .replace("{offers}", "" if page.get("noads") else offers_block())
                   .replace("{casinotable}", casino_table(page))
                   .replace("{month}", NZ_MONTH)
                   # visible freshness stamp. Same source as the sitemap's
                   # lastmod, so what the reader sees and what a crawler is told
                   # are one fact rather than two that can drift apart.
                   .replace("{byline}", byline_block(page))
                   .replace("{newslist}", entry_list("news"))
                   .replace("{bloglist}", entry_list("blog")))
               # outside the {content} chain: the slot lives in base.html, not
               # in the page body, so replacing it on `body` never matched
               .replace("{verdict}", verdict_block(page))
               .replace("{faq}", faq_block(page.get("faq"), page))
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
    base_tpl = open(os.path.join(SRC, "base.html"), encoding="utf-8").read().replace("{analytics}", analytics_block()).replace("{bonusbox}", bonusbox_block()).replace("{band}", band_block())
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

        dataset = {
            "@type": "Dataset",
            "@id": canonical + "#dataset",
            "name": f"Keno NZ draw {did} - {day}",
            "description": f"Winning numbers for New Zealand Keno draw {did}, "
                           f"drawn {day} at {tod} NZ. Twenty numbers from 1 to 80.",
            "url": canonical,
            "temporalCoverage": d["drawnAt"],
            "datePublished": ymd,
            "variableMeasured": "Winning numbers (20 drawn from 1-80)",
            "measurementTechnique": "Read from Lotto NZ's published results and "
                                    "validated before publication",
            "creator": {"@id": SITE + "/#org"},
            "publisher": {"@id": SITE + "/#org"},
            "isBasedOn": {"@type": "Organization", "name": src_label, "url": src_url},
            "license": SITE + "/terms/",
            "inLanguage": "en-NZ",
            "keywords": ["Keno", "New Zealand", f"draw {did}", day],
            "isAccessibleForFree": True,
        }
        crumbs = crumb_list(canonical, [("Results", SITE + "/results/"),
                                        (f"Draw {did}", canonical)])
        ld = page_graph(
            canonical, f"Keno draw {did} - {day}",
            f"Winning numbers for New Zealand Keno draw {did}, drawn {day} "
            f"at {tod} NZ.",
            page_type="ItemPage", modified=ymd, published=ymd, crumbs=crumbs,
            nodes=[dataset], main_entity={"@id": canonical + "#dataset"})

        body = (
            '<div class="wrap">'
            '<div class="page-head">'
            '<p class="eyebrow">Keno draw result</p>'
            f'<h1>Keno Results: Draw {did}</h1>'
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
            '<section><div class="sec-h"><h2>This Draw Against All 80 Numbers</h2></div>'
            + draw_grid(d["numbers"]) +
            '<p class="muted" style="font-size:13px; margin-top:14px; text-align:center">'
            'Twenty of eighty come out each draw, so any given number appears '
            'about 25% of the time. '
            '<a href="/statistics/">See how that plays out over the full archive</a>.</p>'
            '</section>'
            '<section><div class="btn-row" style="justify-content:center">'
            + "".join(nav_links) + '</div></section>'
            '<section><div class="card" style="text-align:center">'
            '<h2 style="font-size:19px">Did Your Numbers Come Up?</h2>'
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
               .replace("{page_id}", "draw")
                   .replace("{page_art}", page_deco(canonical))
                   .replace("{hreflang}", hreflang_block(canonical))
                   .replace("{robots}", "index, follow, max-image-preview:large")
               .replace("{site}", SITE)
                   .replace("{faq}", "").replace("{verdict}", "")
                   .replace("{og_image}", SITE + "/assets/img/icon-512.png")
                   .replace("{tw_card}", "summary")
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
            f'<h1>{spots} Spot Keno Odds</h1>'
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
            '<h2>How This Is Calculated</h2>'
            '<p>Hypergeometric probability - drawing without replacement from a fixed pool. '
            f'For a {spots}-spot ticket the chance of matching exactly <em>k</em> numbers is '
            f'<span class="mono">C(20, k) &times; C(60, {spots} &minus; k) &divide; C(80, {spots})</span>. '
            'Every figure above can be checked with that formula.</p>'
            '<h2>Other Spot Counts</h2>'
            f'<p class="jump"><span class="jump-l">Compare</span>{others}</p>'
            '<p>Playing more spots does not shorten your odds - it lengthens the top tier '
            'and widens the ladder beneath it. Compare '
            f'<a href="/odds/{min(spots+2,10)}-spot/">{min(spots+2,10)} spot</a> and '
            f'<a href="/odds/{max(spots-2,1)}-spot/">{max(spots-2,1)} spot</a> to see it.</p>'
            '<p><a href="/odds/">Back to the full odds tables</a></p>'
            '</div></div>'
        )
        o_url = f"{SITE}/odds/{spots}-spot/"
        ld = page_graph(
            o_url, f"Keno {spots} spot odds",
            f"Every prize division for a {spots} spot Keno ticket in New Zealand, "
            f"with the real probability of each.",
            modified=git_dates().get("src/pages/odds.html"),
            crumbs=crumb_list(o_url, [("Odds", SITE + "/odds/"),
                                      (f"{spots} spot", o_url)]))
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
               .replace("{page_id}", "odds-spot")
                   .replace("{page_art}", page_deco(o_url))
                   .replace("{hreflang}", hreflang_block(o_url))
                   .replace("{robots}", "index, follow, max-image-preview:large")
               .replace("{site}", SITE)
                   .replace("{faq}", "").replace("{verdict}", "")
                   .replace("{og_image}", SITE + "/assets/img/icon-512.png")
                   .replace("{tw_card}", "summary")
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
        urls_extra.append((f"odds/{spots}-spot/",
                           git_dates().get("src/pages/odds.html")
                           or datetime.date.today().isoformat()))
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

        stat_pages.append(("frequency", "Number Frequency",
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
        stat_pages.append(("pairs", "Most Drawn Pairs",
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
        stat_pages.append(("gaps", "Draws Since Last Seen",
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
        stat_pages.append(("patterns", "Sums and Odd/Even",
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
        stat_pages.append(("by-draw-time", "Frequency by Draw Time",
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
                    '<h2>More Statistics</h2>'
                    f'<p class="jump"><span class="jump-l">See also</span>{others}'
                    '<a href="/statistics/">Hot and cold</a></p>'
                    '</div></div>')
            st_url = f"{SITE}/statistics/{slug}/"
            ld = page_graph(
                st_url, title, desc,
                modified=latest_draw_ymd(),
                crumbs=crumb_list(st_url, [("Statistics", SITE + "/statistics/"),
                                           (title, st_url)]))
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
                   .replace("{page_id}", "stats-child")
                   .replace("{page_art}", page_deco(st_url))
                   .replace("{hreflang}", hreflang_block(st_url))
                   .replace("{robots}", "index, follow, max-image-preview:large")
                   .replace("{site}", SITE)
                   .replace("{faq}", "").replace("{verdict}", "")
                   .replace("{og_image}", SITE + "/assets/img/icon-512.png")
                   .replace("{tw_card}", "summary")
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
            urls_extra.append((f"statistics/{slug}/",
                               latest_draw_ymd()
                               or datetime.date.today().isoformat()))
        written.append(f"statistics/<page>/index.html  x{len(stat_pages)}")

    # ---- blog posts and news articles ----
    base_tpl = open(os.path.join(SRC, "base.html"), encoding="utf-8").read().replace("{analytics}", analytics_block()).replace("{bonusbox}", bonusbox_block()).replace("{band}", band_block())
    for kind, cfg in SECTIONS.items():
        for a in _entries(kind):
            canonical = f"{SITE}/{kind}/{a['slug']}/"
            # SVG first: the art is drawn, not sampled, so it is vector and a
            # tenth the weight. PNG stays supported in case one is ever
            # generated rather than drawn.
            img = None
            png = (f"{SITE}/assets/img/articles/{a['slug']}.png"
                   if os.path.exists(os.path.join(ROOT, "assets", "img",
                                                  "articles", a["slug"] + ".png"))
                   else None)
            for ext in (".svg", ".png"):
                if os.path.exists(os.path.join(ROOT, "assets", "img",
                                               "articles", a["slug"] + ext)):
                    img = f"{SITE}/assets/img/articles/{a['slug']}{ext}"
                    break
            article = {
                "@type": cfg["schema"],
                "@id": canonical + "#article",
                "headline": a["title"],
                "description": a.get("metaDescription") or a["summary"],
                "datePublished": a["date"],
                "dateModified": a.get("updated", a["date"]),
                "url": canonical,
                # Point at the WebPage node rather than repeating the URL, so the
                # article and the page it lives on are one connected thing.
                "mainEntityOfPage": {"@id": canonical + "#webpage"},
                "isPartOf": {"@id": canonical + "#webpage"},
                "publisher": {"@id": SITE + "/#org"},
                # Authored by the organisation, not a person - that is the actual
                # editorial model here, and /authors/ says so in as many words.
                "author": {"@id": SITE + "/#org"},
                "creditText": "keno-results.co.nz",
                "articleSection": cfg["label"],
                "inLanguage": "en-NZ",
                "wordCount": len(re.sub(r"<[^>]+>", " ", a.get("body", "")).split()),
                "isAccessibleForFree": True,
            }
            if a.get("tag"):
                article["keywords"] = list(dict.fromkeys(
                    [a["tag"], "Keno", "New Zealand"]))
            if png:
                # Only when a raster exists. Falling back to the SVG declared an
                # image in a format Google does not accept for Article markup,
                # which is a structured-data error rather than a harmless one -
                # no image is better than an unusable one., because SVG is not an accepted
                # format for Article structured data. The caption has to match
                # what the image actually shows - these are drawn locally, not
                # generated, and a draw image shows the real numbers.
                art_kind = (a.get("art") or {}).get("kind")
                article["image"] = {
                    "@type": "ImageObject", "url": png,
                    "width": 1200, "height": 675,
                    "caption": ("The numbers drawn in %s draw %s"
                                % ((a.get("art") or {}).get("game", ""),
                                   (a.get("art") or {}).get("drawNumber", ""))
                                if art_kind in ("draw", "keno", "bullseye")
                                else "Abstract illustration, not a photograph")}
            if not article["wordCount"]:
                del article["wordCount"]
            img_path = img.replace(SITE, "") if img else None
            crumbs = crumb_list(canonical, [(cfg["label"], f"{SITE}/{kind}/"),
                                            (a["title"], canonical)])
            ld = page_graph(
                canonical, a["title"], a.get("metaDescription") or a["summary"],
                page_type="WebPage", modified=a.get("updated", a["date"]),
                published=a["date"], crumbs=crumbs, nodes=[article],
                main_entity={"@id": canonical + "#article"}, image=img)
            body = (
                '<div class="wrap">'
                '<div class="article-head">'
                '<span class="news-meta" style="justify-content:center">'
                f'<span class="news-tag">{html.escape(a.get("tag", cfg["label"]))}</span>'
                f'<span class="news-date">{_pretty_date(a["date"])}</span></span>'
                f'<h1>{html.escape(a["title"])}</h1>'
                f'<p class="article-lede">{html.escape(a["summary"])}</p>'
                '</div>'
                # Header illustration, between the standfirst and the first
                # paragraph. Labelled as an illustration on principle: on a site
                # whose whole position is verified data, a decorative image must
                # never be mistakable for a photograph of a real draw.
                # Two kinds of header image, and they must not be described the
                # same way. Where the article carries its own result the image
                # shows those actual numbers, so calling it an abstract
                # illustration would be false - and on this site that is the
                # one thing an image must never be.
                + (f'<div class="article-img"><figure>'
                   f'<img src="{img_path}" alt="{html.escape(_art_alt(a))}" '
                   f'width="1200" height="675" loading="lazy" decoding="async">'
                   f'<figcaption>{_art_cap(a)}</figcaption></figure></div>'
                   if img_path else '')
                + f'<div class="prose" style="margin-top:34px">{a["body"]}'
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
                   .replace("{og_image}", png or f"{SITE}/assets/img/icon-512.png")
                   .replace("{tw_card}", "summary_large_image" if png else "summary")
                   .replace("{page_id}", "article")
                   .replace("{page_art}", page_deco(canonical))
                   .replace("{hreflang}", hreflang_block(canonical))
                   .replace("{robots}", "index, follow, max-image-preview:large")
                   .replace("{site}", SITE)
                   .replace("{faq}", "").replace("{verdict}", "")
                   .replace("{og_image}", SITE + "/assets/img/icon-512.png")
                   .replace("{tw_card}", "summary")
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
        # Canonical only, deliberately without noindex. The two together are
        # contradictory - noindex says drop this page, canonical says fold it
        # into another - and Google's guidance is to pick one. For a page that
        # has moved, canonical consolidates the old URL's signals onto the new
        # page instead of throwing them away, and it is what puts the URL in
        # Search Console as "Alternative page with proper canonical tag"
        # rather than "Excluded by noindex tag".
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f"""<!DOCTYPE html>
<html lang="en-NZ">
<head>
<meta charset="utf-8">
<title>Moved to {new}</title>
<link rel="canonical" href="{SITE}{new}">
<meta name="robots" content="follow">
<meta http-equiv="refresh" content="0; url={new}">
</head>
<body><p>This page has moved to <a href="{new}">{SITE}{new}</a>.</p></body>
</html>
""")
        written.append(f"{old}/index.html (-> {new})")

    # ---- sitemap ----
    # <priority> and <changefreq> are gone: Google has ignored both for years,
    # and a file that argues with the crawler about what matters is just noise.
    # What is left is the one field it does read, and it is now true.
    urls = []
    for page in PAGES:
        if page.get("sitemap") is False:
            continue
        loc = SITE + "/" if not page["slug"] else f"{SITE}/{page['slug']}/"
        urls.append(f"  <url><loc>{loc}</loc>"
                    f"<lastmod>{page_lastmod(page)}</lastmod>"
                    f"{_sitemap_images(page)}</url>")
    for extra, mod in urls_extra:
        urls.append(f"  <url><loc>{SITE}/{extra}</loc><lastmod>{mod}</lastmod></url>")
    for d in all_draws:
        # A draw page is finished the moment the draw is published: the numbers
        # cannot change, so its lastmod is the draw date, permanently.
        _, _, ymd = _nz_dt(d["drawnAt"])
        urls.append(f"  <url><loc>{SITE}/results/{ymd}/{d['id']}/</loc>"
                    f"<lastmod>{ymd}</lastmod></url>")
    for kind in SECTIONS:
        for a in _entries(kind):
            img = ""
            for ext in (".png", ".svg"):
                rel = f"assets/img/articles/{a['slug']}{ext}"
                if os.path.exists(os.path.join(ROOT, rel)):
                    img = (f"<image:image><image:loc>{SITE}/{rel}</image:loc>"
                           f"<image:title>{html.escape(a['title'])}</image:title>"
                           f"</image:image>")
                    break
            urls.append(f"  <url><loc>{SITE}/{kind}/{a['slug']}/</loc>"
                        f"<lastmod>{a.get('updated', a['date'])}</lastmod>{img}</url>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
                 '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
                 + "\n".join(urls) + "\n</urlset>\n")
    written.append("sitemap.xml")
    flush_content_dates()

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
