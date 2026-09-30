"""Month-stamped titles and H1s in the "Primary Keyword [Month Year]: Secondary" format.

seo_titles.json maps an output path (e.g. "casino-reviews/rivo/index.html") to
{"title": ..., "h1": ...}, both carrying a {{month}} token. apply() runs on each
finished page just before it is written, so the builder's own templates stay
untouched and a monthly roll is a change to the month the builder passes in.

The title is swapped everywhere the old one appears (<title>, og:title,
twitter:title, JSON-LD), and the H1's inner HTML is replaced while the tag's
attributes are kept. sync_schema() then makes the structured data agree with
the page: WebPage-type names and Article-type headlines follow <title>, and
og:/twitter:title follow it too.
"""
import html
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    DATA = json.load(open(os.path.join(_HERE, "seo_titles.json"), encoding="utf-8"))
except FileNotFoundError:
    DATA = {}

# Node types whose "name" is the page's name, and types whose "headline" is.
_PAGE_TYPES = {"WebPage", "CollectionPage", "AboutPage", "ContactPage", "FAQPage",
               "ItemPage", "ProfilePage", "SearchResultsPage", "MedicalWebPage"}
_HEADLINE_TYPES = _PAGE_TYPES | {"Article", "NewsArticle", "BlogPosting", "Review",
                                 "TechArticle", "Report"}
_LD = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)


def _types(node):
    t = node.get("@type")
    return set(t) if isinstance(t, list) else {t}


def _walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from _walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v)


def sync_schema(doc, modified=None):
    """Point schema names/headlines and social titles at the page's <title>.

    modified: optional ISO date; any older dateModified is raised to it so the
    structured data never claims an earlier change than the sitemap does.
    """
    m = re.search(r"<title>(.*?)</title>", doc, re.S)
    if not m:
        return doc
    title = html.unescape(m.group(1)).strip()

    def fix(block):
        raw = block.group(2)
        try:
            data = json.loads(raw)
        except ValueError:
            return block.group(0)
        changed = False
        for node in _walk(data):
            ts = _types(node)
            if ts & _PAGE_TYPES and "name" in node and node["name"] != title:
                node["name"] = title
                changed = True
            if ts & _HEADLINE_TYPES and "headline" in node and node["headline"] != title:
                node["headline"] = title
                changed = True
            if modified and isinstance(node.get("dateModified"), str) \
                    and node["dateModified"][:10] < modified:
                node["dateModified"] = modified + node["dateModified"][10:]
                changed = True
        if not changed:
            return block.group(0)
        if "\n" in raw.strip():
            out = "\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        else:
            out = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return block.group(1) + out.replace("</", "<\\/") + block.group(3)

    doc = _LD.sub(fix, doc)
    esc = html.escape(title)
    doc = re.sub(r'(<meta property="og:title" content=")[^"]*(")',
                 lambda k: k.group(1) + esc + k.group(2), doc)
    doc = re.sub(r'(<meta name="twitter:title" content=")[^"]*(")',
                 lambda k: k.group(1) + esc + k.group(2), doc)
    return doc


def apply(doc, rel, month, modified=None):
    e = DATA.get(rel.replace(os.sep, "/"))
    if not e:
        return doc
    m = re.search(r"<title>(.*?)</title>", doc, re.S)
    if m and e.get("title"):
        old = m.group(1)
        new_plain = e["title"].replace("{{month}}", month)
        new_html = html.escape(new_plain, quote=False)
        old_plain = html.unescape(old)
        doc = doc.replace("<title>%s</title>" % old, "<title>%s</title>" % new_html)
        doc = doc.replace('content="%s"' % old, 'content="%s"' % html.escape(new_plain))
        doc = doc.replace('content="%s"' % html.escape(old_plain), 'content="%s"' % html.escape(new_plain))
        for o in {old_plain, json.dumps(old_plain)[1:-1], json.dumps(old_plain, ensure_ascii=False)[1:-1]}:
            doc = doc.replace('"%s"' % o, '"%s"' % json.dumps(new_plain, ensure_ascii=False)[1:-1])
    if e.get("h1"):
        new_h1 = e["h1"].replace("{{month}}", month)
        doc = re.sub(r"(<h1\b[^>]*>).*?(</h1>)", lambda k: k.group(1) + new_h1 + k.group(2),
                     doc, count=1, flags=re.S)
    return sync_schema(doc, modified)
