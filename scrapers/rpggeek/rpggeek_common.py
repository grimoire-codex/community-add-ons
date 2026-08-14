"""
rpggeek_common.py - shared implementation for the rpggeek and rpggeek-system scrapers.

Both scrapers hit the BGG XML API v2 (https://rpggeek.com/xmlapi2/). The API is
XML-only, which is why this module exists - the YAML declarative format only speaks
JSON, so we drop down to a script and parse the XML ourselves.

Standard library only: urllib.request, xml.etree.ElementTree, html.parser, difflib.
No third-party dependencies.

NOTE: The BGG API has required a Bearer Token since July 2025. Set BGG_API_TOKEN
in your environment before use. See the README for how to get one.
"""

import difflib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


# ── HTTP ─────────────────────────────────────────────────────────────────────

def get_token():
    """Read BGG_API_TOKEN from the environment. Fail fast with a useful message."""
    token = os.environ.get("BGG_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BGG_API_TOKEN is not set. To use the RPGGeek scraper you need a free "
            "API token from BoardGameGeek - register an application at "
            "https://boardgamegeek.com/account/api and set the token as the "
            "BGG_API_TOKEN environment variable on your Grimoire server."
        )
    return token


def bgg_get(url, token):
    """
    Fetch a URL from the BGG API with auth. Handles the quirky HTTP 202 response
    BGG returns when it's still building a result - retries up to 3 times with a
    short delay before giving up.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Grimoire/1 (+https://github.com/hunter-read/grimoire)",
        },
    )

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                body = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = b""

        if status == 200:
            return body
        if status == 202:
            # BGG queues some requests and returns 202 while processing. Give it
            # a moment and try again - three retries is almost always enough.
            if attempt < 3:
                time.sleep(2)
                continue
            raise RuntimeError(
                "RPGGeek API returned 202 (still processing) after 3 retries. "
                "Try again in a few seconds."
            )
        if status in (401, 403):
            raise RuntimeError(
                f"RPGGeek API returned {status}. Check that BGG_API_TOKEN is correct "
                "and hasn't expired."
            )
        raise RuntimeError(f"RPGGeek API returned HTTP {status} for: {url}")

    # Shouldn't be reachable, but keeps type checkers happy.
    raise RuntimeError("Unexpected state in bgg_get retry loop.")


# ── Text ─────────────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-text converter using the standard library."""

    def __init__(self):
        super().__init__()
        self._parts = []
        self._in_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._in_skip += 1
        # Treat block-level tags as paragraph breaks.
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "hr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._in_skip = max(0, self._in_skip - 1)

    def handle_data(self, data):
        if not self._in_skip:
            self._parts.append(data)

    def get_text(self):
        text = "".join(self._parts)
        # Strip leading whitespace from each line (list indentation artefacts),
        # then collapse runs of blank lines.
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return html.unescape(text).strip()


def strip_html(text):
    """Strip HTML tags and decode entities. Returns plain text."""
    if not text:
        return ""
    parser = _HTMLStripper()
    parser.feed(text)
    return parser.get_text()


# ── Dice ─────────────────────────────────────────────────────────────────────

# Matches the dice notation inside "Dice (Primarily d20)" or "Dice (d6 Pool)".
_DICE_PAREN = re.compile(r"^Dice\s*\((.+?)\)", re.IGNORECASE)
# Matches a dice token like "d20", "2d6", "d100".
_DICE_TOKEN = re.compile(r"\d*d\d+", re.IGNORECASE)


def extract_dice(mechanic):
    """
    Convert a verbose RPGGeek rpgmechanic label into a short dice notation,
    or return None if it isn't a dice mechanic at all.

    Examples:
        "Dice (Primarily d20)"         -> "D20"
        "Dice (Primarily 2d6)"         -> "2D6"
        "Dice (d6 Pool)"               -> "D6"
        "Dice (Primarily d100/percentile)" -> "D100"
        "Diceless"                     -> "Diceless"
        "Class Based (Pilot, ...)"     -> None
        "Skill Based (...)"            -> None
    """
    stripped = mechanic.strip()

    if stripped.lower() == "diceless":
        return "Diceless"

    m = _DICE_PAREN.match(stripped)
    if not m:
        # Not a dice mechanic - discard it.
        return None

    inner = m.group(1)
    # Strip the common "Primarily " prefix BGG uses.
    inner = re.sub(r"^Primarily\s+", "", inner, flags=re.IGNORECASE)

    # Pull the first dice token out of whatever remains ("d20", "2d6", etc.).
    token = _DICE_TOKEN.search(inner)
    if token:
        return token.group(0).upper()

    # The parens had something in them but no recognisable dice notation - skip.
    return None


# ── Fuzzy ranking ────────────────────────────────────────────────────────────

def fuzzy_score(a, b):
    """Simple fuzzy ratio between two strings. 1.0 is a perfect match."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ── BGG XML helpers ──────────────────────────────────────────────────────────

def _attr(element, path, attrib="value", default=None):
    """
    Find a child element by path and return one of its attribute values.
    BGG's XML stores almost everything in `value` attributes rather than
    element text, which is a bit quirky but consistent.
    """
    node = element.find(path)
    if node is None:
        return default
    return node.get(attrib, default)


def _links(element, link_type):
    """Return a list of `value` attributes for all <link type="…"> children."""
    return [
        link.get("value")
        for link in element.findall("link")
        if link.get("type") == link_type and link.get("value")
    ]


# ── Search ───────────────────────────────────────────────────────────────────

def search(query, item_type, token, limit=15):
    """
    Search RPGGeek for items of the given type. Returns a list of candidate
    dicts ready to hand back to Grimoire as search results.

    item_type should be "rpgitem" (books) or "rpg" (game systems).
    """
    encoded = urllib.parse.quote(query)
    url = f"https://rpggeek.com/xmlapi2/search?query={encoded}&type={item_type}"

    raw = bgg_get(url, token)
    root = ET.fromstring(raw)

    candidates = []
    for item in root.findall("item"):
        item_id = item.get("id")
        name = _attr(item, "name")
        year = _attr(item, "yearpublished") or ""
        if not item_id or not name:
            continue
        score = fuzzy_score(query, name)
        year_label = f" ({year})" if year else ""
        candidates.append({
            "identity": item_id,
            "label": f"{name}{year_label}",
            "score": score,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:limit]


# ── Fetch ────────────────────────────────────────────────────────────────────

def fetch(identity, item_type, token, addon_dir):
    """
    Fetch the full record for a single RPGGeek item. Returns a Grimoire-shaped
    `fields` dict. Caches the raw response in addon_dir/cache/ for 24 hours to
    avoid hammering the API on repeated opens of the same item.
    """
    cache_path = _cache_path(addon_dir, item_type, identity)
    raw = _cache_read(cache_path)

    if raw is None:
        url = f"https://rpggeek.com/xmlapi2/thing?id={identity}&type={item_type}"
        raw = bgg_get(url, token)
        _cache_write(cache_path, raw)

    root = ET.fromstring(raw)
    item = root.find("item")
    if item is None:
        raise RuntimeError(
            f"RPGGeek returned no item for id={identity} type={item_type}. "
            "The ID may be wrong, or the item may have been removed."
        )

    name_node = item.find("name[@type='primary']")
    title = name_node.get("value", "") if name_node is not None else ""

    description_raw = ""
    desc_node = item.find("description")
    if desc_node is not None and desc_node.text:
        description_raw = desc_node.text

    year_raw = _attr(item, "yearpublished")
    year = int(year_raw) if year_raw and year_raw.isdigit() else None

    publishers = _links(item, "rpgpublisher")
    designers = _links(item, "rpgdesigner")
    artists = _links(item, "rpgartist")
    genres = _links(item, "rpggenre")
    families = _links(item, "rpgfamily")

    # Only keep mechanics that are actually dice-related, and strip the verbose
    # label down to short notation ("D20", "D6", "Diceless").
    mechanics_raw = _links(item, "rpgmechanic")
    dice = [d for d in (extract_dice(m) for m in mechanics_raw) if d]

    fields = {
        "description": strip_html(description_raw),
        "year": year,
        "genres": genres,
        "dice_materials": dice,
        "system_family": families[0] if families else None,
        "publishers": [{"name": p, "url": ""} for p in publishers],
        # book-specific fields
        "title": title,
        "publisher": publishers[0] if publishers else None,
        "authors": designers,
        "artists": artists,
    }

    source_url = _item_url(identity, item_type)
    fields["urls"] = [{"label": "RPGGeek", "url": source_url}]

    return fields, source_url


def _item_url(identity, item_type):
    slug = {"rpgitem": "rpgitem", "rpg": "rpg"}.get(item_type, "rpgitem")
    return f"https://rpggeek.com/{slug}/{identity}"


# ── Cache ─────────────────────────────────────────────────────────────────────

_CACHE_TTL = 86400  # 24 hours


def _cache_path(addon_dir, item_type, identity):
    cache_dir = os.path.join(addon_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{item_type}_{identity}.xml")


def _cache_read(path):
    """Return cached bytes if the file exists and is less than TTL seconds old."""
    try:
        age = time.time() - os.path.getmtime(path)
        if age < _CACHE_TTL:
            with open(path, "rb") as f:
                return f.read()
    except OSError:
        pass
    return None


def _cache_write(path, data):
    try:
        with open(path, "wb") as f:
            f.write(data)
    except OSError:
        # Cache write failures are non-fatal - we already have the data.
        pass
