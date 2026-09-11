#!/usr/bin/env python3
"""The supplied keyword sets, and a coverage audit against the built pages.

Match is deliberately generous: lowercase, punctuation stripped, and a phrase
counts as present if its words appear in order within a short window, so
"fast payout casino NZ" is satisfied by "fast payout casinos in NZ". If a term
fails even that, it genuinely is not on the page.
"""
import re, sys, os

KW = {
"online-casinos": {
 1: ["online casinos nz", "best online casino nz", "online casino new zealand",
     "nz online casinos", "online casino real money nz", "best online casinos nz 2026",
     "top online casinos nz", "real money casino nz", "nz casino sites", "casino online nz"],
 2: ["best casino sites nz", "safe online casinos nz", "trusted online casinos nz",
     "new online casinos nz", "online casinos that accept nzd", "nzd online casino",
     "online gambling nz", "best online gambling sites nz", "casino sites new zealand"],
 3: ["best online casino nz reddit", "which online casino pays out the most nz",
     "best online casino for kiwis", "best online casino nz low deposit",
     "online casino nz sign up bonus", "best rated online casino new zealand",
     "most trusted online casino nz", "online casino nz real money no deposit",
     "are online casinos safe nz", "best online casino nz for beginners"],
},
"licensed-online-casinos": {
 1: ["licensed online casinos nz", "legal online casinos nz", "is online gambling legal in nz",
     "are online casinos legal in new zealand", "online gambling laws new zealand"],
 2: ["online casino gambling act 2026", "nz online casino licence",
     "regulated online casinos new zealand", "dia licensed online casino",
     "new zealand online casino licence list", "legal online casino nz 2027"],
 3: ["which online casinos are licensed in nz", "when do online casinos become legal in nz",
     "how many online casino licences nz", "department of internal affairs online casino licence",
     "is it legal to gamble online in new zealand", "offshore casinos nz legal status",
     "unlicensed online casinos nz", "nz online casino licence holders list",
     "do i pay tax on casino winnings nz", "is gambling tax free in new zealand"],
},
"casino-bonus": {
 1: ["casino bonus nz", "best casino bonuses nz", "casino sign up bonus nz",
     "1 deposit casino nz"],
 2: ["online casino bonus new zealand", "welcome bonus casino nz",
     "1 dollar deposit casino nz", "5 deposit casino nz", "10 deposit casino nz",
     "casino bonus codes nz"],
 3: ["no wagering casino bonus nz", "low wagering bonus nz", "what does 35x wagering mean",
     "how do casino wagering requirements work", "reload bonus casino nz",
     "cashback casino bonus nz", "best welcome bonus online casino nz",
     "1 deposit casino nz free spins", "minimum deposit casino bonus nz",
     "are casino bonuses worth it nz"],
},
"no-deposit-bonus": {
 1: ["no deposit bonus nz", "free spins no deposit nz", "no deposit bonus codes nz",
     "casino no deposit bonus new zealand", "no deposit casino nz"],
 2: ["free spins no deposit nz 2026", "no deposit sign up bonus nz",
     "50 free spins no deposit nz", "20 free spins no deposit nz",
     "new no deposit bonus nz", "real money no deposit bonus nz",
     "no deposit free spins on registration nz"],
 3: ["100 free spins no deposit nz", "25 free spins no deposit nz", "5 no deposit bonus nz",
     "10 no deposit bonus nz", "no deposit bonus keep what you win nz",
     "can you withdraw no deposit bonus winnings nz",
     "free spins no deposit no card details nz", "no deposit bonus max cashout explained",
     "no deposit bonus wagering requirements nz", "how to claim a no deposit bonus",
     "are no deposit bonuses legit", "no deposit bonus pokies nz",
     "exclusive no deposit bonus codes nz", "best no deposit bonus nz 2026",
     "free chip no deposit casino nz"],
},
"casino-payout-percentages": {
 1: ["casino payout percentage", "best payout online casino nz", "highest rtp casinos nz",
     "rtp meaning casino", "what is rtp in pokies"],
 2: ["highest rtp pokies nz", "best rtp slots nz", "online casino payout percentage nz",
     "highest paying online casino nz", "return to player explained"],
 3: ["which online casino has the best payout nz", "average rtp online casino nz",
     "house edge vs rtp", "loosest online pokies nz", "how is casino rtp calculated",
     "what is a good rtp percentage", "payout rates online casinos new zealand",
     "does rtp matter in the short term", "blackjack rtp vs pokies rtp"],
},
"fast-payout-casinos": {
 1: ["fast payout casinos nz", "instant withdrawal casino nz",
     "fastest paying online casino nz", "how long do casino withdrawals take nz"],
 2: ["quick withdrawal casino nz", "same day payout casino nz", "instant payout casino nz",
     "casinos with fast withdrawals nz", "withdrawal times online casino nz"],
 3: ["fastest withdrawal method online casino nz", "instant withdrawal casino nz bank transfer",
     "crypto instant withdrawal casino nz", "why is my casino withdrawal pending",
     "casino withdrawal pending time nz", "fast payout casino nz no verification delay",
     "online casino payout time new zealand", "instant withdrawal pokies nz",
     "casino that pays out instantly nz", "how to speed up casino withdrawal"],
},
"casino-payment-methods": {
 1: ["casino payment methods nz", "online casino deposit methods nz", "paysafecard casino nz",
     "casinos that accept poli nz", "paypal casino nz"],
 2: ["neosurf casino nz", "skrill casino nz", "neteller casino nz", "apple pay casino nz",
     "bank transfer casino nz", "crypto casino nz", "bitcoin casino nz", "visa casino nz",
     "mastercard casino nz", "casinos that accept nzd"],
 3: ["can you use paypal at online casinos nz", "best payment method for online casino nz",
     "poli payments casino nz", "minimum deposit online casino nz",
     "online casino that accepts prepaid card nz", "deposit with phone bill casino nz",
     "casino deposit no fees nz", "which casinos accept apple pay nz",
     "nzd deposits no conversion fee casino", "casino withdrawal to bank account nz"],
},
"online-pokies": {
 1: ["online pokies nz", "online pokies real money nz", "best online pokies nz",
     "free pokies nz", "pokies online new zealand", "real money pokies nz"],
 2: ["play pokies online nz", "new pokies nz", "best pokie sites nz", "jackpot pokies nz",
     "mobile pokies nz", "free online pokies no download"],
 3: ["best paying pokies nz", "megaways pokies nz", "progressive jackpot pokies nz",
     "online pokies 1 deposit nz", "are online pokies legal in nz",
     "how do online pokies work", "online pokies free spins no deposit nz",
     "highest rtp online pokies nz", "free pokies no download no registration nz",
     "which online pokies pay the most nz", "online pokies with bonus buy nz"],
},
"live-casino": {
 1: ["live casino nz", "live dealer casino nz", "best live casino nz", "live roulette nz",
     "live blackjack nz"],
 2: ["live baccarat nz", "live casino real money nz", "evolution gaming casinos nz",
     "crazy time nz", "lightning roulette nz"],
 3: ["best live casino sites new zealand", "live casino minimum bet nz",
     "live dealer blackjack online nz real money", "how does live casino work",
     "live casino vs rng games", "live casino with nzd tables",
     "best live roulette site nz", "monopoly live nz", "live casino app nz"],
},
"new-casinos-nz": {
 1: ["new online casinos nz", "new casinos nz", "newest online casinos nz",
     "new casino sites nz", "new online casino nz real money"],
 2: ["brand new online casinos nz 2026", "latest online casinos nz", "new pokie sites nz",
     "new casino sites with free spins nz", "upcoming online casinos nz"],
 3: ["new online casinos nz no deposit bonus", "newly licensed online casinos nz",
     "are new online casinos safe nz", "best new casino sites nz 2026",
     "new online casino free spins no deposit nz", "new nz casinos accepting nzd",
     "new casino no wagering bonus nz", "newest pokie sites new zealand",
     "what to check before joining a new casino", "new crypto casinos nz",
     "new casinos launching new zealand"],
},
"crypto-casinos-nz": {
 1: ["crypto casino nz", "bitcoin casino nz", "crypto casinos new zealand",
     "best crypto casino nz", "bitcoin gambling nz"],
 2: ["ethereum casino nz", "usdt casino nz", "litecoin casino nz", "crypto pokies nz",
     "instant withdrawal crypto casino nz", "anonymous casino nz", "dogecoin casino nz"],
 3: ["best bitcoin casino nz 2026", "are crypto casinos legal in nz",
     "how to deposit bitcoin at an online casino nz", "crypto casino no deposit bonus nz",
     "fastest crypto withdrawal casino nz", "crypto casino with nzd conversion",
     "do you pay tax on crypto casino winnings nz", "provably fair casino explained",
     "crypto casino welcome bonus nz", "bitcoin pokies nz",
     "how to withdraw crypto from an online casino nz", "crypto casino minimum deposit nz",
     "crypto vs bank transfer casino withdrawals"],
},
"how-we-rate-casinos": {
 1: ["how to choose an online casino nz", "how to tell if an online casino is legit",
     "what makes an online casino safe", "online casino review methodology",
     "casino licensing explained", "responsible gambling nz", "gambling helpline nz",
     "how to check if a casino is licensed nz"],
},
}


def norm(t):
    t = re.sub(r"<[^>]+>", " ", t).lower()
    t = (t.replace("&mdash;", " ").replace("&ndash;", " ").replace("&rsquo;", "'")
          .replace("&amp;", "&").replace("&ldquo;", " ").replace("&rdquo;", " ")
          .replace("&nbsp;", " ").replace("&times;", "x").replace("&divide;", "/"))
    # strip currency marks so "$1 deposit casino NZ" satisfies "1 deposit casino nz",
    # and split "nz$20" into tokens the same way the keyword list would be written
    t = t.replace("nz$", " ").replace("$", " ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t)


def present(words, text):
    """All words in order inside a window of len(words)+4 tokens."""
    toks = text.split()
    idx, n = 0, len(words)
    for i, tk in enumerate(toks):
        if tk == words[0] or tk == words[0] + "s":
            j, k = i, 0
            while j < len(toks) and k < n and j - i <= n + 4:
                if toks[j] == words[k] or toks[j] == words[k] + "s" or toks[j] + "s" == words[k]:
                    k += 1
                j += 1
            if k == n:
                return True
    return False


def audit(root="."):
    rows, tot_hit, tot_all = [], 0, 0
    for slug, tiers in KW.items():
        f = os.path.join(root, slug, "index.html")
        raw = open(f, encoding="utf-8").read()
        main = re.search(r"<main id=\"main\">(.*)</main>", raw, re.S).group(1)
        head = re.search(r"<title>(.*?)</title>", raw, re.S).group(1) + " " + \
               (re.search(r'name="description" content="(.*?)"', raw, re.S) or
                re.match("", "")).group(1)
        text = norm(head + " " + main)
        miss = []
        hit = all_ = 0
        for tier, terms in tiers.items():
            for t in terms:
                all_ += 1
                if present(norm(t).split(), text):
                    hit += 1
                else:
                    miss.append((tier, t))
        tot_hit += hit; tot_all += all_
        rows.append((slug, hit, all_, miss))
    return rows, tot_hit, tot_all


if __name__ == "__main__":
    rows, h, a = audit(sys.argv[1] if len(sys.argv) > 1 else ".")
    show = "-v" in sys.argv
    for slug, hit, all_, miss in rows:
        print("%-27s %3d/%-3d  %3.0f%%" % (slug, hit, all_, 100 * hit / all_))
        if show:
            for tier, t in miss:
                print("      miss T%d  %s" % (tier, t))
    print("\nTOTAL %d/%d  %.0f%%" % (h, a, 100 * h / a))
