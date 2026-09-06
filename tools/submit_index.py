#!/usr/bin/env python3
"""Send newly published URLs to RalfyIndex for indexing.

    python3 tools/submit_index.py             # submit whatever is new
    python3 tools/submit_index.py --dry-run   # show what would go, send nothing
    python3 tools/submit_index.py --baseline  # adopt the current sitemap as
                                              # already-submitted, send nothing
    python3 tools/submit_index.py --status    # check credentials only

What counts as new
------------------
The sitemap is the authoritative list of what this site wants indexed, so the
delta between it and src/data/indexed.json is exactly the set worth sending -
the day's draw pages and any article published since the last run. Nothing is
sent twice, because a URL is only recorded once it has actually been accepted.

The first run adopts the whole sitemap as a baseline rather than submitting 273
URLs at once. Pass --baseline explicitly to re-adopt after a bulk change.

Where it sits in the pipeline
-----------------------------
After validate_draws.py and after the build, so a feed that failed validation
can never have its pages advertised. Best-effort throughout: a network failure
or a bad response leaves indexed.json untouched and exits 0, so the results
still publish. Submitting is not worth breaking a build over, and an unrecorded
URL simply goes again next run.

Credentials come from the macOS keychain (service `ralfyindex-api`) or the
RALFY_API_KEY environment variable, so the key is never in this repo - which is
public, and is itself the web root.

Stdlib only.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITEMAP = os.path.join(ROOT, "sitemap.xml")
STATE = os.path.join(ROOT, "src", "data", "indexed.json")
CONFIG = os.path.join(ROOT, "src", "data", "indexing.json")
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# What is worth paying a credit for. Submission costs one credit per URL, so
# four draw pages a day is ~1,460 credits a year - most of a plan spent on
# dated archive pages nobody searches for by number minutes after the draw.
# Those are discovered from the sitemap perfectly well; what actually benefits
# from being indexed in five rather than five hundred minutes is an article,
# and there are a couple a month. The default reflects that, and any of it can
# be turned back on in src/data/indexing.json.
DEFAULT_KINDS = {"article": True, "page": True, "draw": False}

# Which non-article pages are worth a credit. Everything outside this list is
# still in the sitemap and still gets indexed - it just is not worth paying to
# hurry along. The legal pages in particular gain nothing from being crawled
# five minutes sooner, and they change once a year.
DEFAULT_PAGE_PREFIXES = ["odds", "faqs"]


def kind_of(url, page_prefixes=None):
    """article (blog/news), draw (a dated result), page (worth submitting),
    or other (real, indexable, just not worth a credit)."""
    path = url.replace("https://keno-results.co.nz", "").strip("/")
    if path.startswith(("blog/", "news/")) and path.count("/") >= 1:
        return "article"
    if path.startswith("results/2"):
        return "draw"
    prefixes = DEFAULT_PAGE_PREFIXES if page_prefixes is None else page_prefixes
    head = path.split("/")[0]
    return "page" if head in prefixes else "other"

API_BASE = "https://api.ralfyindex.com"
STATUS_URL = API_BASE + "/status"


def api_key():
    env = os.environ.get("RALFY_API_KEY")
    if env:
        return env.strip()
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "ralfyindex-api", "-w"],
            capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def config():
    """Endpoint and payload shape, kept out of the code so it can be filled in
    without a patch. The submit endpoint is not published anywhere public - it
    only appears in the dashboard once you are signed in - and guessing it with
    a live key is how a key gets revoked, so it stays empty until pasted."""
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def post(url, payload, timeout=30):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "keno-results.co.nz/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    try:
        return r.status if hasattr(r, "status") else 200, json.loads(body)
    except json.JSONDecodeError:
        return 200, {"raw": body[:400]}


def accepted_ok(body):
    """True only if the API actually took the batch.

    RalfyIndex answers a bad key with HTTP 200 and {"errorCode":1,...}, so
    success has to be read from the body rather than the status line."""
    if not isinstance(body, dict):
        return False
    if body.get("errorCode"):
        return False
    if "error" in body or "message" in body and "status" not in body:
        return False
    return body.get("status") in ("ok", "success", True) or "creditsUsed" in body


def sitemap_urls():
    try:
        tree = ET.parse(SITEMAP)
    except (OSError, ET.ParseError):
        return []
    return [u.find("s:loc", NS).text for u in tree.getroot().findall("s:url", NS)
            if u.find("s:loc", NS) is not None]


def load_state():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"_note": "URLs already sent to RalfyIndex. A URL is recorded "
                         "only once the API has accepted it, so a failed run "
                         "simply retries next time.",
                "updated": None, "submitted": {}}


def save_state(state):
    state["updated"] = datetime.datetime.now().replace(microsecond=0).isoformat()
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--baseline", action="store_true",
                    help="record the current sitemap as sent, submit nothing")
    ap.add_argument("--status", action="store_true", help="check credentials only")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    key = api_key()
    if not key:
        print("index: no key in the keychain ('ralfyindex-api') or RALFY_API_KEY; "
              "skipping", file=sys.stderr)
        return 0

    if args.status:
        try:
            code, body = post(STATUS_URL, {"apikey": key})
            ok = accepted_ok(body)
            print(f"index: status {code} {json.dumps(body)}"
                  f"  -> credentials {'OK' if ok else 'REJECTED'}")
            if not ok:
                return 1
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"index: status check failed ({e})", file=sys.stderr)
        return 0

    urls = sitemap_urls()
    if not urls:
        print("index: no sitemap yet; nothing to do", file=sys.stderr)
        return 0

    state = load_state()
    sent = state["submitted"]
    today = datetime.date.today().isoformat()

    # First run, or an explicit re-adopt: take the sitemap as the starting point
    # instead of firing 273 URLs at the API in one go.
    if args.baseline or not sent:
        for u in urls:
            sent.setdefault(u, today)
        save_state(state)
        print(f"index: baseline adopted, {len(urls)} URLs marked as already sent")
        return 0

    cfg_all = config()
    kinds = dict(DEFAULT_KINDS)
    kinds.update(cfg_all.get("submit") or {})
    kinds.setdefault("other", False)
    prefixes = cfg_all.get("pagePrefixes") or DEFAULT_PAGE_PREFIXES

    new_all = [u for u in urls if u not in sent]
    fresh, skipped = [], {}
    for u in new_all:
        k = kind_of(u, prefixes)
        if kinds.get(k, True):
            fresh.append(u)
        else:
            skipped[k] = skipped.get(k, 0) + 1
            # Record it anyway: it is a deliberate skip, not a failure, and
            # leaving it unrecorded would re-offer it on every future run.
            sent[u] = today

    if skipped:
        save_state(state)
        print("index: skipped " + ", ".join(f"{n} {k}" for k, n in skipped.items())
              + " (not worth a credit; the sitemap covers discovery)")
    if not fresh:
        print("index: nothing new worth submitting")
        return 0

    batch = fresh[:args.limit]
    print(f"index: {len(fresh)} new URL(s)" +
          (f", submitting the first {len(batch)}" if len(batch) < len(fresh) else ""))
    for u in batch[:8]:
        print("   " + u)
    if len(batch) > 8:
        print(f"   ... and {len(batch) - 8} more")

    cfg = config()
    endpoint = (cfg.get("endpoint") or "").strip()
    if args.dry_run or not endpoint:
        if not endpoint:
            print("\nindex: no submit endpoint configured, so nothing was sent.\n"
                  "       Paste the indexing example from "
                  "https://ralfyindex.com/dashboard/apikey into\n"
                  "       src/data/indexing.json - endpoint, and urlsField if the\n"
                  "       URL list is not called 'urls'. Credentials already work:\n"
                  "       tools/submit_index.py --status returns ok.",
                  file=sys.stderr)
        return 0

    field = cfg.get("urlsField") or "urls"
    size = int(cfg.get("batchSize") or 100)
    accepted = 0
    for i in range(0, len(batch), size):
        chunk = batch[i:i + size]
        payload = {"apikey": key, field: chunk}
        payload.update(cfg.get("extra") or {})
        try:
            code, body = post(endpoint, payload)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print(f"index: submit failed ({str(e)[:140]}); "
                  f"{len(chunk)} URL(s) left unrecorded and will retry",
                  file=sys.stderr)
            break
        # This API answers a rejected key with HTTP 200 and an errorCode in the
        # body, so the status line alone is not evidence of anything. Without
        # this check a dead key would look like a clean run and the URLs would
        # be marked submitted having never been sent.
        if not accepted_ok(body):
            print(f"index: API rejected the batch -> {json.dumps(body)[:200]}\n"
                  f"       {len(chunk)} URL(s) left unrecorded and will retry",
                  file=sys.stderr)
            break
        # Only record what the API actually took.
        for u in chunk:
            sent[u] = today
        accepted += len(chunk)
        print(f"   accepted {len(chunk)} -> {json.dumps(body)[:160]}")

    if accepted:
        save_state(state)
    print(f"index: {accepted} URL(s) submitted and recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
