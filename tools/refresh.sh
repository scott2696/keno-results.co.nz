#!/usr/bin/env bash
# Local alternative to the GitHub Action: fetch, validate, rebuild, publish.
#
#   ./tools/refresh.sh          # fetch + validate + build, leave changes staged
#   ./tools/refresh.sh --push   # also commit and push
#
# Validation gates the publish: if the feed is bad, nothing is written or pushed.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 tools/fetch_draws.py --backfill "${BACKFILL:-40}"
python3 tools/validate_draws.py          # non-zero exit aborts the run

# Editorial pipeline. All best-effort: a failure here must never stop results
# being published, so none of these is allowed to fail the run.
#   watch_news     - what the media is covering (headlines only, never bodies)
#   fetch_official - what Lotto NZ itself has published, which we can source from
python3 tools/watch_news.py     || echo "news watch skipped"
python3 tools/fetch_official.py || echo "official releases skipped"
python3 tools/auto_news.py  || echo "auto-news skipped"
python3 tools/gen_images.py --limit 3 || echo "image generation skipped"

python3 tools/build.py > /dev/null

if [ "${1:-}" = "--push" ]; then
  if [ -z "$(git status --porcelain)" ]; then
    echo "No new draws - nothing to publish."
    exit 0
  fi
  git add -A
  git commit -m "Refresh draw results ($(date -u '+%Y-%m-%d %H:%M UTC'))"
  git push
  echo "published."
else
  git status --short
  echo
  echo "Run with --push to commit and publish."
fi
