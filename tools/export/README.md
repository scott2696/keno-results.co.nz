# URL exports for indexing submission

Regenerate after any build:

    python3 tools/export_urls.py

## Files

**`priority-urls.txt`** — 49 URLs. Homepage, news, blog, all statistics and odds
pages, the tools, and the guide/legal set. This is the list worth submitting to
a paid indexer.

**`all-urls.txt`** — 272 URLs. Everything in the sitemap, including every
individual draw page.

## Why the two lists differ

The 223 per-draw pages are deliberately excluded from the priority list. They
are near-identical in structure, they are all in `sitemap.xml`, and they grow by
four a day — paying per URL to index them is the fastest way to spend credits
for the least return. Let the sitemap and internal linking carry those.

Submit the priority list. Re-submit only new URLs after that: each new news or
blog post, and any page you materially rewrite.
