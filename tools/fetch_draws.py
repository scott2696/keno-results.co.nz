#!/usr/bin/env python3
"""Fetch NZ Keno (and Lotto/Bullseye) results from MyLotto into the site's feed.

Adapted from the nz_lotto_results.py bundle. Two things differ:

  1. This site stores draw *history*, not just the latest draw, so it backfills
     by draw number and merges with what is already on disk.
  2. Everything is normalised to the site's schema and validated before it is
     written -- numbers become integers, times become ISO 8601 with the correct
     New Zealand offset, and any draw that is not 20 unique values in 1-80 is
     dropped rather than published.

MyLotto's API sets Access-Control-Allow-Origin to their own domain, so a
browser on our domain cannot call it. We pull server-side on a schedule and
write a same-origin JSON file the page can read. Unofficial endpoint -- it can
change without notice, so every failure path here leaves existing data intact.

    python3 tools/fetch_draws.py                  # update keno + other games
    python3 tools/fetch_draws.py --backfill 200   # reach further back
    python3 tools/fetch_draws.py --games keno     # keno only

Stdlib only.
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    from zoneinfo import ZoneInfo
    NZ = ZoneInfo("Pacific/Auckland")
except Exception:                                    # pragma: no cover
    NZ = datetime.timezone(datetime.timedelta(hours=12))

API = "https://pathway.mylotto.co.nz/api/results/v1/results"
UA = {"User-Agent": "keno-results.co.nz/1.0 (+https://keno-results.co.nz/about/)",
      "Accept": "application/json"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "assets", "data")
SOURCE_LABEL = "Lotto NZ (MyLotto)"

RANGE_LO, RANGE_HI, DRAW_SIZE = 1, 80, 20
DELAY = 0.35          # be polite to an API that owes us nothing


def fetch(game, draw=None, timeout=30):
    url = f"{API}/{game}" + (f"/{draw}" if draw else "")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def to_iso(date_str, time_str):
    """'2026-09-05' + '10:01' (NZ local) -> ISO 8601 with the right offset.

    New Zealand switches between +12:00 and +13:00, so the offset has to come
    from the zone rather than be hardcoded.
    """
    if not date_str:
        return None
    hh, mm = 0, 0
    if time_str and ":" in time_str:
        try:
            hh, mm = (int(x) for x in time_str.split(":")[:2])
        except ValueError:
            hh, mm = 0, 0
    try:
        y, mo, d = (int(x) for x in date_str.split("-"))
    except ValueError:
        return None
    return datetime.datetime(y, mo, d, hh, mm, tzinfo=NZ).isoformat()


def normalise_keno(raw):
    """MyLotto keno record -> this site's draw shape, or None if unusable."""
    nums = raw.get("winningNumbers") or []
    try:
        nums = sorted(int(n) for n in nums)
    except (TypeError, ValueError):
        return None

    draw_no = raw.get("drawNumber")
    drawn_at = to_iso(raw.get("drawDate"), raw.get("drawTime"))
    if draw_no is None or drawn_at is None:
        return None

    out = {"id": str(draw_no), "drawnAt": drawn_at, "numbers": nums}
    mult = raw.get("multiplier")
    if mult:
        out["multiplier"] = str(mult)
    return out


def is_valid(d):
    """The same rule the validator and the browser enforce."""
    n = d.get("numbers")
    if not isinstance(n, list) or len(n) != DRAW_SIZE:
        return False
    if len(set(n)) != DRAW_SIZE:
        return False
    return all(isinstance(x, int) and RANGE_LO <= x <= RANGE_HI for x in n)


def load_feed(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data.get("draws"), list):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"game": "Keno NZ", "numberRange": [RANGE_LO, RANGE_HI],
            "drawSize": DRAW_SIZE, "source": None, "retrievedAt": None, "draws": []}


def write_atomic(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def update_keno(backfill):
    path = os.path.join(DATA, "draws.json")
    feed = load_feed(path)
    have = {d.get("id"): d for d in feed["draws"] if isinstance(d, dict)}
    before = len(have)

    try:
        latest = fetch("keno")
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        print(f"warn: could not reach MyLotto ({e}); existing data left untouched",
              file=sys.stderr)
        return 1

    top = latest.get("drawNumber")
    if not isinstance(top, int):
        print("warn: latest draw has no usable drawNumber; nothing written", file=sys.stderr)
        return 1

    added, skipped, failed = 0, 0, 0
    for n in range(top, max(top - backfill, 0), -1):
        key = str(n)
        if key in have:
            skipped += 1
            continue
        try:
            raw = latest if n == top else fetch("keno", n)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            print(f"  draw {n}: fetch failed ({e})", file=sys.stderr)
            failed += 1
            if n != top:
                time.sleep(DELAY)
            continue

        d = normalise_keno(raw)
        if d and is_valid(d):
            have[key] = d
            added += 1
        else:
            bad = sorted(int(x) for x in (raw.get("winningNumbers") or []) if str(x).isdigit())
            out_of_range = [v for v in bad if not RANGE_LO <= v <= RANGE_HI]
            reason = f"{len(bad)} numbers" + (f", out of range {out_of_range}" if out_of_range else "")
            print(f"  draw {n}: rejected by validation ({reason})", file=sys.stderr)
            failed += 1
        if n != top:
            time.sleep(DELAY)

    draws = sorted(have.values(), key=lambda d: d["drawnAt"], reverse=True)
    feed.update(
        game="Keno NZ",
        numberRange=[RANGE_LO, RANGE_HI],
        drawSize=DRAW_SIZE,
        source=SOURCE_LABEL,
        sourceUrl="https://mylotto.co.nz/results/keno",
        retrievedAt=datetime.datetime.now(NZ).replace(microsecond=0).isoformat(),
        draws=draws,
    )
    write_atomic(path, feed)
    print(f"keno: {before} -> {len(draws)} draws "
          f"(+{added} new, {skipped} already held, {failed} failed/rejected)")
    return 0


def update_other(games):
    """Latest Lotto/Powerball and Bullseye draw, for the secondary game pages."""
    label = {"lotto": "Lotto & Powerball", "bullseye": "Bullseye"}
    for game in games:
        try:
            raw = fetch(game)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
            print(f"warn: {game} fetch failed ({e}); leaving existing file", file=sys.stderr)
            continue

        if game == "lotto":
            lotto = raw.get("lotto") or {}
            win = lotto.get("lottoWinningNumbers") or {}
            pb = raw.get("powerBall") or {}
            strike = raw.get("strike") or {}
            extras = []
            if win.get("bonusBalls"):
                extras.append({"label": "Bonus", "value": str(win["bonusBalls"])})
            if pb.get("powerballWinningNumber"):
                extras.append({"label": "Powerball", "value": str(pb["powerballWinningNumber"])})
            if strike.get("strikeWinningNumbers"):
                extras.append({"label": "Strike", "value": " ".join(strike["strikeWinningNumbers"])})
            rec = {"drawNumber": lotto.get("drawNumber"),
                   "drawnAt": to_iso(lotto.get("drawDate"), lotto.get("drawTime")),
                   "numbers": [int(n) for n in win.get("numbers", []) if str(n).isdigit()],
                   "extras": extras}
        else:
            num = (raw.get("bullseyeWinningNumbers") or {}).get("numbers")
            rec = {"drawNumber": raw.get("drawNumber"),
                   "drawnAt": to_iso(raw.get("drawDate"), raw.get("drawTime")),
                   "numbers": [str(num)] if num else [],
                   "singleNumber": True, "extras": []}

        if rec["drawNumber"] is None or not rec["numbers"]:
            print(f"warn: {game} response missing numbers; skipped", file=sys.stderr)
            continue

        rec.update(game=game, gameLabel=label[game], source=SOURCE_LABEL,
                   sourceUrl=f"https://mylotto.co.nz/results/{game}",
                   retrievedAt=datetime.datetime.now(NZ).replace(microsecond=0).isoformat())
        write_atomic(os.path.join(DATA, f"{game}-results.json"), rec)
        print(f"{game}: draw {rec['drawNumber']}, {len(rec['numbers'])} number(s)")
        time.sleep(DELAY)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backfill", type=int, default=120,
                    help="how many draws back to try to fill (default 120, ~30 days)")
    ap.add_argument("--games", nargs="+", default=["keno", "lotto", "bullseye"],
                    choices=["keno", "lotto", "bullseye"])
    args = ap.parse_args()

    rc = 0
    if "keno" in args.games:
        rc |= update_keno(args.backfill)
    others = [g for g in args.games if g != "keno"]
    if others:
        update_other(others)
    return rc


if __name__ == "__main__":
    sys.exit(main())
