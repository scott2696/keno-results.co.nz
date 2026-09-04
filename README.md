# keno-results.co.nz

Independent New Zealand Keno results, ticket checker and game guides.
Static site, no build toolchain, served from GitHub Pages.

## Layout

```
src/base.html          page shell (head, header, footer)
src/pages/*.html       page content fragments
src/brand/             original logo artwork (source of truth)
tools/build.py         renders src/ -> repo root
tools/fetch_draws.py   pulls results from MyLotto into the feed
tools/validate_draws.py  feed validator - run before every publish
tools/refresh.sh       fetch + validate + build (+ --push to publish)
assets/css/site.css    design system (tokens, components)
assets/js/             site.js (shared) - results.js - checker.js
assets/data/draws.json the draw feed
```

Generated pages live at the repo root because that is what GitHub Pages
serves. Edit `src/`, never the generated HTML.

## Build

```sh
python3 tools/build.py
```

No npm, no dependencies beyond the Python standard library. Rebuild after
editing anything in `src/`, then commit the generated files.

Pillow is needed only if you regenerate logo or icon artwork.

## The draw feed

`assets/data/draws.json` is the single source of results. Shape:

```json
{
  "game": "Keno NZ",
  "numberRange": [1, 80],
  "drawSize": 20,
  "source": "Name of the upstream provider",
  "retrievedAt": "2026-09-05T22:04:12+12:00",
  "draws": [
    { "id": "2481093",
      "drawnAt": "2026-09-05T22:00:00+12:00",
      "numbers": [4, 9, 11, 17, 22, 23, 29, 35, 38, 41, 46, 52, 55, 57, 61, 64, 68, 73, 76, 79] }
  ]
}
```

`source` is shown to visitors in the provenance strip under every set of
numbers, so it must name a real upstream source.

### Where the data comes from

Results are pulled from MyLotto's results API:

```
GET https://pathway.mylotto.co.nz/api/results/v1/results/keno       # latest
GET https://pathway.mylotto.co.nz/api/results/v1/results/keno/{n}   # draw n
```

That endpoint sends `Access-Control-Allow-Origin: https://mylotto.co.nz`, so a
browser on our domain **cannot** call it directly. We fetch server-side on a
schedule and write a same-origin JSON file the page reads instead - no CORS,
and we are not hammering their API on every pageview.

`tools/fetch_draws.py` normalises their shape into ours: zero-padded strings
become integers, `drawDate` + `drawTime` become ISO 8601 with the correct New
Zealand offset (which alternates between +12:00 and +13:00, so it is taken
from the zone rather than hardcoded), and draw history is merged with what is
already on disk so only missing draws are fetched.

```sh
python3 tools/fetch_draws.py                 # keno + lotto + bullseye
python3 tools/fetch_draws.py --backfill 200  # reach further back
python3 tools/fetch_draws.py --games keno    # keno only
```

Keno draws about 4x/day (10:01, 13:01, 15:01, 18:01 NZ). Lotto and Bullseye
latest draws are written to `assets/data/{game}-results.json` and shown on
those game pages.

> The endpoint is published by the operator but undocumented, so it can change
> without notice. Every failure path leaves existing data intact and the site
> shows its unavailable state. Worth a compliance check on Lotto NZ's terms
> before republishing commercially.

### Automated refresh

`tools/refresh-results.workflow.yml` is a ready-to-use GitHub Action. It runs
after each draw, validates, rebuilds and commits only if something changed.
That is the recommended path: the site is static, so new results have to be
committed to appear, and an Action does not depend on a particular machine
being awake.

**To activate it**, move it into place and push:

```sh
mkdir -p .github/workflows
git mv tools/refresh-results.workflow.yml .github/workflows/refresh-results.yml
git commit -m "Enable scheduled results refresh" && git push
```

Pushing anything under `.github/workflows/` needs a token with the `workflow`
scope. If that push is rejected, either add the scope to your token, or create
the file through GitHub's web UI (Actions -> New workflow) and paste the
contents in - the web editor is not subject to the token scope.

Once enabled, check it under the repo's **Actions** tab; `workflow_dispatch`
lets you trigger a run by hand.

To run it by hand instead:

```sh
./tools/refresh.sh          # fetch, validate, build
./tools/refresh.sh --push   # ...and publish
```

`tools/com.kenoresults.refresh.plist` is a launchd template if you would rather
publish from a Mac. Note the macOS TCC restriction: launchd cannot touch
`~/Documents` unless `/bin/bash` has Full Disk Access, which is a good reason to
prefer the Action.

### Validation is not optional

```sh
python3 tools/validate_draws.py            # exits non-zero on any problem
```

Every draw must be exactly 20 unique integers in 1-80, with a valid id and
ISO 8601 timestamp. The browser re-checks the same rules and silently drops
anything that fails, so bad data cannot reach a visitor.

This exists for a specific reason: the previous version of this site
published results containing numbers from 81 to 90 for a game drawn from
1 to 80, while its own guide correctly described the 1-80 range. Run the
validator in CI before any deploy.

## Affiliate offers

The offer strip under the latest draw is data-driven from `src/data/offers.json`:

```json
{ "name": "CrownSlots",
  "logo": "/assets/img/partners/crownslots.jpg",
  "url":  "https://crownslotslink.com/...",
  "bonus": "Welcome bonus <b>390% up to NZ$3,700</b> + 175 free spins",
  "cta": "Claim bonus",
  "active": true }
```

`placement` is `inline` (under the latest draw) or `rail` (the sticky vertical
card on the right, shown from 1360px). Add an entry to run another placement;
set `active: false` to pull one without deleting it. With no active offers,
both the strip and the rail render as nothing.

A rail offer may carry a `theme` block so the card uses the operator's own
colours rather than ours:

```json
"theme": { "deep": "#050522", "base": "#111135", "raised": "#1D1D4C",
           "violet": "#8254FF", "cyan": "#00F0F1",
           "ctaFrom": "#6A2BE8", "ctaTo": "#2F6FD6", "style": "space" }
```

These are emitted as inline custom properties. `style: "space"` adds a
deterministic star field. Note the CTA stops are *deepened* from the partner's
own gradient: SpinJo's violet-to-cyan fails contrast badly with a white label
(1.43:1), so the card uses violet-to-blue at 4.81:1 while keeping the identity.

Set `logo` to a file in `assets/img/partners/` when the partner supplies one;
without it the name is set as a wordmark, split on an internal capital.

Rendering is handled by `offers_block()` in `tools/build.py`, and `{offers}` is
the placeholder in a page's source. It currently appears only on the homepage.

Non-negotiables, all enforced in the renderer:

- `rel="sponsored nofollow noopener"` on every offer link.
- An explicit **Advertisement** label above, and a disclosure line below stating
  it is paid, that we are not affiliated, and that we may earn a commission.
- 18+ and "terms apply" in the card itself.
- The strip sits **below** the draw card, never inside or beside the numbers.
  Its palette is deliberately the partner's, not ours, so it cannot be mistaken
  for editorial content or for data.

Bonus copy is display text and is not verified by us. Confirm it matches the
partner's current NZ-facing offer before launch, and re-check when it changes.

## Promotional slots

The content column is 980px, centred, leaving room either side. Four slots are
built into `src/base.html`, all empty by default:

| Slot | Where | Notes |
|---|---|---|
| `.promo-top` | full width, above the page title | ~970x90 leaderboard |
| `.promo-mid` | in-flow, between sections | add to a page in `src/pages/` |
| `.promo-bottom` | full width, above the footer | ~970x90 |
| `.promo-rail left` / `right` | sticky side rails | 160px wide, only shown above 1400px |

Drop markup straight in:

```html
<div class="promo-top">
  <a href="..." rel="sponsored noopener"><img src="/assets/img/promo.png" alt="..."></a>
</div>
```

Every slot collapses to nothing while empty (`:empty { display:none }`), so an
unfilled position never leaves a hole or reserves dead space. The rails are
`position:fixed` and disappear below 1400px rather than crowding the content.

`--wrap` (column width) and `--rail` (rail width) are both tokens in
`assets/css/site.css` if you want different proportions.

Use `rel="sponsored"` on paid links, and keep anything that could be mistaken
for a result clear of the draw components - the provenance strip's credibility
depends on nothing beside it looking like data.

## Conventions

- Tokens are declared in full on `:root`; dark mode redefines tokens only.
  Never style a component inside a `@media` or `[data-theme]` block.
- Matched balls carry state through fill **and** border, never colour alone.
- The orange `--live` token means one thing: a draw is in progress. Nothing else.
- Balls are coloured by decade (`--b1`..`--b8`, 1-10 through 71-80). This is
  the lottery convention and does real work: you can find a number by its
  colour. Every fill carries ink numerals at 6.7:1+ and a tonal ring, so the
  same palette holds on both grounds without a per-theme variant.
- Because hue is spent on identity, *state* cannot use it. Picked and matched
  balls are marked with a solid accent ring plus a lift, and matched adds a
  tick badge - readable on all eight fills.
- Hot/cold uses its own `--hot` / `--cold` semantic tokens, deliberately not
  the brand accent and not `--live`; they colour the rate pill, not the ball.
  The full frequency list stays in number order (not sorted by count) so it
  reads as a record rather than a ranking.
- Hot/cold is presented with an explicit caveat: it is descriptive, not
  predictive. Widening the draw window visibly narrows the spread toward the
  25% baseline, which is the honest demonstration of why. Keep that framing.
- We publish odds, never prize amounts. Prizes depend on stake and on the
  operator's current schedule.

## Legacy URLs

`/keno-tools/` and `/stra/` are canonical-tagged meta-refresh stubs
(GitHub Pages cannot issue server-side 301s). `/stra/` points at `/odds/`
deliberately - the old "strategy" framing implied influence over a random
draw.
