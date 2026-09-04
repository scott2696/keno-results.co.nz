#!/usr/bin/env python3
"""Validate the Keno draw feed.

Run this at ingest, before anything is published. It exists because the
previous site published numbers in the range 1-90 for a game that draws
1-80 -- the single fault that most damaged the site's credibility.

    python3 tools/validate_draws.py [path]

Exit 0 = every draw is publishable. Exit 1 = do not publish.
"""
import json
import sys
from datetime import datetime

RANGE_LO, RANGE_HI, DRAW_SIZE = 1, 80, 20


def check_draw(d, i):
    """Return a list of problems with one draw. Empty list means it's good."""
    errs = []
    where = f"draws[{i}]"

    did = d.get("id")
    if not isinstance(did, str) or not did.strip():
        errs.append(f"{where}: missing or non-string 'id'")
    else:
        where = f"draw {did}"

    when = d.get("drawnAt")
    if not isinstance(when, str):
        errs.append(f"{where}: missing 'drawnAt'")
    else:
        try:
            datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            errs.append(f"{where}: 'drawnAt' is not ISO 8601: {when!r}")

    nums = d.get("numbers")
    if not isinstance(nums, list):
        errs.append(f"{where}: 'numbers' must be a list")
        return errs

    if len(nums) != DRAW_SIZE:
        errs.append(f"{where}: has {len(nums)} numbers, expected {DRAW_SIZE}")

    bad_type = [n for n in nums if not isinstance(n, int) or isinstance(n, bool)]
    if bad_type:
        errs.append(f"{where}: non-integer values {bad_type}")

    out_of_range = sorted({n for n in nums if isinstance(n, int) and not RANGE_LO <= n <= RANGE_HI})
    if out_of_range:
        errs.append(
            f"{where}: {len(out_of_range)} value(s) outside {RANGE_LO}-{RANGE_HI}: {out_of_range} "
            f"-- impossible in NZ Keno"
        )

    dupes = sorted({n for n in nums if nums.count(n) > 1})
    if dupes:
        errs.append(f"{where}: duplicate numbers {dupes}")

    return errs


def main(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"FAIL  no such file: {path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"FAIL  {path} is not valid JSON: {e}")
        return 1

    errs = []
    if data.get("drawSize") != DRAW_SIZE:
        errs.append(f"feed: drawSize is {data.get('drawSize')!r}, expected {DRAW_SIZE}")
    if data.get("numberRange") != [RANGE_LO, RANGE_HI]:
        errs.append(f"feed: numberRange is {data.get('numberRange')!r}, expected [{RANGE_LO}, {RANGE_HI}]")

    draws = data.get("draws")
    if not isinstance(draws, list):
        errs.append("feed: 'draws' must be a list")
        draws = []

    seen_ids = {}
    for i, d in enumerate(draws):
        if not isinstance(d, dict):
            errs.append(f"draws[{i}]: not an object")
            continue
        errs.extend(check_draw(d, i))
        did = d.get("id")
        if isinstance(did, str):
            if did in seen_ids:
                errs.append(f"draw {did}: duplicate id (also at index {seen_ids[did]})")
            seen_ids[did] = i

    if data.get("draws") and not data.get("source"):
        errs.append("feed: draws are present but 'source' is null -- "
                    "the provenance strip cannot name a source")

    if errs:
        print(f"FAIL  {len(errs)} problem(s) in {path}\n")
        for e in errs:
            print(f"  - {e}")
        print("\nNothing published. Fix the feed and re-run.")
        return 1

    n = len(draws)
    if n == 0:
        print(f"OK    {path}: valid, but empty. The site will show its "
              f"'no confirmed draw' state.")
    else:
        print(f"OK    {path}: {n} draw(s), all {DRAW_SIZE} unique numbers "
              f"in {RANGE_LO}-{RANGE_HI}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "assets/data/draws.json"))
