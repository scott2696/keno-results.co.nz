#!/usr/bin/env python3
"""Export URL lists from sitemap.xml for indexing submission.

    python3 tools/export_urls.py

Writes tools/export/all-urls.txt and tools/export/priority-urls.txt.
See tools/export/README.md for what the split is for.
"""
import os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://keno-results.co.nz/"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def rank(url):
    p = url.replace(SITE, "")
    if p == "":
        return 0
    if p.startswith("news/"):
        return 1
    if p.startswith("blog/"):
        return 2
    if p.startswith(("statistics/", "odds/", "calculator", "number-generator")):
        return 3
    if p.startswith("results/2"):
        return 9          # per-draw pages: sitemap handles these
    return 4


def main():
    tree = ET.parse(os.path.join(ROOT, "sitemap.xml"))
    urls = [u.find("s:loc", NS).text for u in tree.getroot().findall("s:url", NS)]
    out = os.path.join(ROOT, "tools", "export")
    os.makedirs(out, exist_ok=True)

    with open(os.path.join(out, "all-urls.txt"), "w") as fh:
        fh.write("\n".join(urls) + "\n")

    priority = sorted((u for u in urls if rank(u) <= 4), key=lambda u: (rank(u), u))
    with open(os.path.join(out, "priority-urls.txt"), "w") as fh:
        fh.write("\n".join(priority) + "\n")

    print(f"all-urls.txt       {len(urls):4d}")
    print(f"priority-urls.txt  {len(priority):4d} "
          f"({len(urls) - len(priority)} per-draw pages excluded)")


if __name__ == "__main__":
    main()
