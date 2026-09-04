# keno-results.co.nz

Independent New Zealand Keno results, ticket checker and game guides.
Static site, no build toolchain, served from GitHub Pages.

## Layout

```
src/base.html          page shell (head, header, footer)
src/pages/*.html       page content fragments
src/brand/             original logo artwork (source of truth)
tools/build.py         renders src/ -> repo root
tools/validate_draws.py  feed validator - run before every publish
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
numbers, so it must name a real upstream source. The feed currently ships
**empty**: the site shows an honest "no confirmed draw yet" state rather
than placeholder numbers. Point it at a real feed to bring the site live.

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

## Conventions

- Tokens are declared in full on `:root`; dark mode redefines tokens only.
  Never style a component inside a `@media` or `[data-theme]` block.
- Matched balls carry state through fill **and** border, never colour alone.
- The orange `--live` token means one thing: a draw is in progress. Nothing else.
- Statistics are presented in number order with no ranking or "hot/cold"
  styling, because frequency history does not predict future draws.
- We publish odds, never prize amounts. Prizes depend on stake and on the
  operator's current schedule.

## Legacy URLs

`/keno-tools/` and `/stra/` are canonical-tagged meta-refresh stubs
(GitHub Pages cannot issue server-side 301s). `/stra/` points at `/odds/`
deliberately - the old "strategy" framing implied influence over a random
draw.
