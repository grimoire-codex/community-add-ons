"""
nobleknight.py - Noble Knight Games book scraper.

Noble Knight has no public API, so a lookup takes two requests:

1. Search goes to the JSON API of Zoovu, the hosted search service behind the
   store's own search box, under the store's project ID. It returns names,
   publishers and years, which is enough to pick a result.
2. Fetch reads the chosen product page (/P/<id>/): the "Product Details" block
   is a tidy list of label/value rows (Publisher, Author, Publish Year,
   MFG. Part #, ...), and the description sits in its own element.

Both run only when a person asks for them in Grimoire. Standard library only,
per Grimoire's script rules.
"""

import difflib
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE_URL = "https://www.nobleknight.com"
USER_AGENT = "Grimoire/1 (+https://github.com/hunter-read/grimoire)"
REQUEST_TIMEOUT = 20

# The store's project on Zoovu, from the search plugin config its pages load
# (js.search.zoovu.com/plugin/bundle/51850.js, "siteId").
SEARCH_URL = "https://api.search.zoovu.com/search"
SEARCH_PROJECT_ID = "43167"
# Fetch a generous page and re-rank locally: the store's relevance order puts
# near-misses ("#249 Below the Tomb of Horrors") above exact title matches.
SEARCH_PAGE_SIZE = 40
SEARCH_LIMIT = 15
SEARCH_MIN_SCORE = 0.3
# Product types that are printed books (or boxes of them). Categories are too
# coarse for this - dice bags file under "Role Playing Games" - so the type
# decides. A product with no type is given the benefit of the doubt.
BOOK_TYPES = {
    "Hardcover", "Softcover", "Module", "Magazine", "Box Set", "Ziplock",
    "Parts - Book", "Novel - Softcover", "Novel - Hardcover",
}
NON_BOOK_FACTOR = 0.85

# Every Grimoire install that uses this add-on shares one request pattern, so
# both requests are cached: searches for an hour, parsed product pages for a day.
SEARCH_CACHE_TTL = 3600
PRODUCT_CACHE_TTL = 86400

_PRODUCT_ID = re.compile(r"/P/(\d+)")

# Block-level tags that end a paragraph in the product description.
_BLOCK_TAGS = {"p", "ul", "ol", "div", "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr"}

# The catalogue files titles library-style, with a leading article moved to the
# end of the name: "Gaean Reach, The - Core Rules". Only a trailing article
# directly before the end, a " - " subtitle, a "#" issue number, a "(" or a ":"
# is moved back, so a comma that is part of the real title is left alone.
_INVERTED_ARTICLE = re.compile(r"^(?P<name>[^,]+?), (?P<article>The|A|An)(?=$|\s+[-#(:])")

# Names are listed in one cell. Split on commas, ampersands, semicolons and a
# standalone "and"; the store does not use any of those inside a single name.
_NAME_SEPARATORS = re.compile(r"\s*(?:,|;|&|\band\b)\s*")


class ProductPage(HTMLParser):
    """Collects the Product Details rows and the description from a product page.

    ``details`` maps each row's label to ``{"text": ..., "links": [...]}``, where
    ``links`` holds the text of each link in the value (Genre is one link per
    genre). ``description`` is the description as plain text.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.details = {}
        self._description = []
        # One entry per open <div>: the role it plays here, or None.
        self._divs = []
        self._row = None
        self._link = None

    @property
    def description(self):
        text = "".join(self._description)
        lines = [" ".join(line.split()) for line in text.split("\n")]
        text = "\n".join(lines)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def _inside(self, role):
        return role in self._divs

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()

        if tag == "div":
            role = None
            if "info-line" in classes and self._row is None:
                role = "row"
                self._row = {"label": [], "value": [], "links": []}
            elif self._row is not None and "label" in classes:
                role = "label"
            elif self._row is not None and "value" in classes:
                role = "value"
            elif attributes.get("id") == "productDescription":
                role = "description"
            elif self._inside("description"):
                self._description.append("\n\n")
            self._divs.append(role)
            return

        if tag == "a" and self._inside("value"):
            self._link = []

        if self._inside("description"):
            if tag == "br":
                self._description.append("\n")
            elif tag == "li":
                self._description.append("\n• ")
            elif tag in _BLOCK_TAGS:
                self._description.append("\n\n")

    def handle_endtag(self, tag):
        if tag == "div":
            if not self._divs:
                return
            role = self._divs.pop()
            if role == "row":
                self._finish_row()
            elif self._inside("description"):
                self._description.append("\n\n")
            return

        if tag == "a" and self._link is not None:
            self._row["links"].append(_clean("".join(self._link)))
            self._link = None

        if self._inside("description") and tag in _BLOCK_TAGS:
            self._description.append("\n\n")

    def handle_data(self, data):
        if self._inside("label"):
            self._row["label"].append(data)
        elif self._inside("value"):
            self._row["value"].append(data)
            if self._link is not None:
                self._link.append(data)
        if self._inside("description"):
            self._description.append(data)

    def _finish_row(self):
        label = _clean("".join(self._row["label"]))
        # The page lists each row once; keep the first if that ever changes.
        if label and label not in self.details:
            self.details[label] = {
                "text": _clean("".join(self._row["value"])),
                "links": [link for link in self._row["links"] if link],
            }
        self._row = None


def _clean(text):
    return " ".join(text.split())


def uninvert_title(title):
    """"Gaean Reach, The - Core Rules" -> "The Gaean Reach - Core Rules"."""
    return _INVERTED_ARTICLE.sub(lambda m: f"{m['article']} {m['name']}", title, count=1)


def split_names(text):
    return [name for name in _NAME_SEPARATORS.split(text or "") if name]


def product_url(identity):
    return f"{BASE_URL}/P/{identity}/"


def map_fields(page, identity):
    """Turn a parsed product page into Grimoire book fields."""
    details = page.details

    def text(*labels):
        for label in labels:
            value = details.get(label, {}).get("text", "")
            if value:
                return value
        return ""

    fields = {}

    title = text("Title")
    if title:
        fields["title"] = uninvert_title(title)

    if page.description:
        fields["description"] = page.description

    publisher = text("Publisher")
    if publisher:
        fields["publisher"] = publisher

    authors = split_names(text("Author", "Authors"))
    if authors:
        fields["authors"] = authors

    artists = split_names(text("Artist", "Artists"))
    if artists:
        fields["artists"] = artists

    # The Genre row mixes true genres ("RPG - Fantasy") with game systems
    # ("Pathfinder", "Call of Cthulhu") and formats ("Magazine - Role-Playing").
    # Only the "RPG - " entries are genres.
    genres = [
        link[len("RPG - "):].strip()
        for link in details.get("Genre", {}).get("links", [])
        if link.startswith("RPG - ")
    ]
    if genres:
        fields["genres"] = genres

    year = text("Publish Year")
    if re.fullmatch(r"\d{4}", year):
        fields["year"] = int(year)

    # The manufacturer's catalogue number (HG235, PZO90140). "NKG Part #" is the
    # store's own internal id and is deliberately not used.
    product_code = text("MFG. Part #")
    if product_code:
        fields["product_code"] = product_code

    isbn = text("ISBN")
    if isbn:
        fields["isbn"] = isbn

    fields["urls"] = [{"label": "Noble Knight Games", "url": product_url(identity)}]
    return fields


def _cache_path(addon_dir, kind, key):
    if not addon_dir:
        return ""
    cache_dir = os.path.join(addon_dir, "cache", kind)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{key}.json")


def _cache_read(path, ttl):
    if not path or not os.path.isfile(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _cache_write(path, value, ttl):
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(value, fh)
        # Drop expired neighbours so the cache does not grow without bound.
        cache_dir = os.path.dirname(path)
        now = time.time()
        for name in os.listdir(cache_dir):
            entry = os.path.join(cache_dir, name)
            if now - os.path.getmtime(entry) > ttl:
                os.remove(entry)
    except OSError:
        # A cache we cannot write is only a missed optimisation.
        pass


def _get(url, accept):
    """GET ``url``. Returns ``(final_url, text)``; raises HTTPError for a 4xx/5xx."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.geturl(), resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {urllib.parse.urlsplit(url).hostname}: {exc.reason}") from exc


def _normalise(text):
    text = re.sub(r"['\u2019]", "", text.lower()).replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def title_score(query, title):
    """Similarity of ``query`` to ``title``, 0-1.

    Printings and editions are listed as separate products with the detail in
    brackets ("Tomb of Horrors (4th Printing, Green)"), so the title is also
    compared without its bracketed parts; the better of the two counts.

    Plain similarity punishes a longer title that contains the query, ranking
    "Wilderfeast Dice Bag" above "Wilderfeast Core Book". So a title holding
    every word of the query scores at least 0.75, rising as the query covers
    more of it.
    """
    query = _normalise(query)
    words = set(query.split())
    best = 0.0
    for candidate in (title, re.sub(r"\s*\([^)]*\)", "", title)):
        candidate = _normalise(candidate)
        if not candidate:
            continue
        score = difflib.SequenceMatcher(None, query, candidate).ratio()
        if words and words <= set(candidate.split()):
            score = max(score, 0.75 + 0.25 * min(1.0, len(query) / len(candidate)))
        best = max(best, score)
    return best


def search_candidates(document, query):
    """Ranked Grimoire candidates from a Zoovu search response."""
    candidates = []
    seen = set()
    for group in document.get("searchResults") or []:
        # Other groups hold product lines and categories, not products.
        if not isinstance(group, dict) or group.get("type") != "products":
            continue
        # Each result is a list of variants (one per condition) of one product;
        # the first is the head, and they all share its product page.
        for variants in group.get("results") or []:
            head = variants[0] if isinstance(variants, list) and variants else variants
            if not isinstance(head, dict):
                continue
            match = _PRODUCT_ID.search(head.get("link") or "")
            identity = match.group(1) if match else str(head.get("groupId") or "")
            title = uninvert_title(_clean(html.unescape(head.get("name") or "")))
            if not identity.isdigit() or not title or identity in seen:
                continue
            seen.add(identity)

            points = {
                point.get("key"): _clean(str(point.get("value") or ""))
                for point in head.get("dataPoints") or []
                if isinstance(point, dict)
            }
            # "Wilderfeast Core Book — Horrible Guild (2025), Hardcover": the
            # year and format are what tell printings and editions apart.
            label = title
            if points.get("Publisher"):
                label += f" \u2014 {points['Publisher']}"
            if points.get("Publish Year"):
                label += f" ({points['Publish Year']})"
            if points.get("Product Types"):
                label += f", {points['Product Types']}"

            score = title_score(query, title)
            # Grimoire is filling in a book, so dice, card singles, boxed games
            # and the like sort below an equally good title match that is one.
            product_type = points.get("Product Types")
            if product_type and product_type not in BOOK_TYPES:
                score *= NON_BOOK_FACTOR

            candidates.append(
                {
                    "identity": identity,
                    "label": label,
                    "score": round(score, 3),
                    "url": product_url(identity),
                }
            )

    # Stable sort, so equal scores keep the store's relevance order.
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return [c for c in candidates if c["score"] >= SEARCH_MIN_SCORE][:SEARCH_LIMIT]


def search(query, addon_dir):
    query = " ".join(str(query).split())
    if not query:
        return {"results": []}

    key = hashlib.sha256(query.lower().encode("utf-8")).hexdigest()[:32]
    cache_path = _cache_path(addon_dir, "search", key)
    document = _cache_read(cache_path, SEARCH_CACHE_TTL)
    if document is None:
        params = urllib.parse.urlencode(
            {"projectId": SEARCH_PROJECT_ID, "query": query, "limit": SEARCH_PAGE_SIZE}
        )
        try:
            _, body = _get(f"{SEARCH_URL}?{params}", "application/json")
            document = json.loads(body)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Noble Knight search returned HTTP {exc.code}") from exc
        except ValueError as exc:
            raise RuntimeError("Noble Knight search returned something other than JSON") from exc
        if not isinstance(document, dict):
            raise RuntimeError("Noble Knight search returned an unexpected response")
        _cache_write(cache_path, document, SEARCH_CACHE_TTL)

    return {"results": search_candidates(document, query)}


def fetch(identity, addon_dir):
    identity = str(identity).strip()
    if not identity.isdigit():
        raise RuntimeError(
            "That is not a Noble Knight product ID - paste a nobleknight.com/P/... link"
        )

    cache_path = _cache_path(addon_dir, "products", identity)
    fields = _cache_read(cache_path, PRODUCT_CACHE_TTL)
    if fields is None:
        try:
            final_url, body = _get(product_url(identity), "text/html")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise RuntimeError(f"Noble Knight has no product with ID {identity}") from exc
            raise RuntimeError(f"Noble Knight returned HTTP {exc.code}") from exc
        page = ProductPage()
        page.feed(body)
        page.close()
        # An unknown ID redirects to the home page with a 200, so a missing
        # product is recognised by the missing Product Details block.
        if "/P/" not in final_url or "Title" not in page.details:
            raise RuntimeError(f"Noble Knight has no product with ID {identity}")
        fields = map_fields(page, identity)
        _cache_write(cache_path, fields, PRODUCT_CACHE_TTL)

    return {"fields": fields, "url": product_url(identity)}


def main():
    req = json.load(sys.stdin)
    action = req.get("action")
    addon_dir = req.get("addon_dir", "")

    try:
        if action == "search":
            out = search(req.get("query", ""), addon_dir)
        elif action == "fetch":
            out = fetch(req.get("identity", ""), addon_dir)
        else:
            out = {"error": f"Unknown action: {action!r}"}
    except RuntimeError as exc:
        out = {"error": str(exc)}
    except Exception as exc:
        out = {"error": f"Unexpected error: {exc}"}

    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
