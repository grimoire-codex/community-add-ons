import difflib
import html
import re
from html.parser import HTMLParser


# ── Text ─────────────────────────────────────────────────────────────────────

class _MessyHTMLScrubber(HTMLParser):
    """
    Minimal HTML-to-text converter using just the standard library.
    We don't want to drag in BeautifulSoup just for stripping BGG's messy description blocks.
    """

    def __init__(self):
        super().__init__()
        self._parts = []
        self._in_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._in_skip += 1
        # BGG's HTML can be a bit of a mess. Treat block-level tags as paragraph breaks 
        # so we don't end up with mashed together text when stripping tags.
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


def _scrub_html(text):
    """
    Feed messy BGG description HTML through our minimal parser to get 
    clean, readable plain text out the other side.
    """
    if not text:
        return ""
    parser = _MessyHTMLScrubber()
    parser.feed(text)
    return parser.get_text()


# ── Dice ─────────────────────────────────────────────────────────────────────

# Matches the dice notation inside "Dice (Primarily d20)" or "Dice (d6 Pool)".
_DICE_PAREN = re.compile(r"^Dice\s*\((.+?)\)", re.IGNORECASE)
# Matches a dice token like "d20", "2d6", "d100".
_DICE_TOKEN = re.compile(r"\d*d\d+", re.IGNORECASE)


def extract_dice(mechanic):
    """
    Sifts through BGG's noisy mechanic labels ("Dice (Primarily d20)", etc) 
    and distills them down to clean notations ("D20"). If it's a physical supply 
    we track (Jenga towers, cards), we map it. If it's something weird, we drop it.
    """
    stripped = mechanic.strip()

    m = _DICE_PAREN.match(stripped)
    if not m:
        # Check for other physical supplies supported by Grimoire
        lower = stripped.lower()
        
        # Prevent "Unusual Randomizer (not using dice or cards)" from falsely triggering the cards check
        if "not using dice or cards" in lower:
            return None
            
        if "jenga" in lower or "dexterity-based" in lower:
            return "Tumbling Tower (Jenga Tower)"
        if "candle" in lower:
            return "Candles"
        if "poker chip" in lower:
            return "Poker Chips"
        if "timer" in lower:
            return "Timers"
        if "phone" in lower:
            return "Phone"
            
        # Check for card types
        if "tarot" in lower:
            return "Tarot Cards"
        if "playing card" in lower or "standard deck" in lower or "french-suited" in lower:
            return "Playing Cards"
        if re.search(r"\b(card|cards|deck|decks)\b", lower):
            return "Custom Deck"
            
        # Not a dice or supported mechanic - discard it.
        return None

    inner = m.group(1)
    # BGG labels their dice mechanics with verbose, messy strings like "Dice (Primarily d20)".
    # We strip the common prefix here so we don't clutter the UI.
    inner = re.sub(r"^Primarily\s+", "", inner, flags=re.IGNORECASE)

    # Pull the first dice token out of whatever remains ("d20", "2d6", etc.).
    token = _DICE_TOKEN.search(inner)
    if token:
        return token.group(0).upper()

    # We just want the raw dice notation (e.g. "d20", "2d6"). If the parens didn't 
    # hold anything recognisable, we just throw it out.
    return None


def extract_all_dice_and_materials(mechanics_raw):
    """
    Takes a list of raw BGG mechanic strings, passes them through extract_dice,
    and returns a clean, sorted list of mapped supplies.
    Aggressively strips out any phantom dice or cards if the system explicitly
    declares it doesn't use them.
    """
    dice = sorted(list(set(d for d in (extract_dice(m) for m in mechanics_raw) if d)))
    
    if any("not using dice or cards" in m.lower() for m in mechanics_raw):
        dice = [
            d for d in dice 
            if not re.search(r"^\d*D\d+$", d) 
            and "Card" not in d 
            and "Deck" not in d
        ]
        
    return dice


def extract_edition(name, family):
    """
    BGG bakes editions directly into the system name (e.g. "Dungeons & Dragons 5th Edition").
    We try to smartly isolate the edition by subtracting the system family from the name.
    If that trick fails (because they don't share text), we fall back to sweeping for 
    common edition regex patterns.
    """
    if not name:
        return None
        
    if family and family.lower() in name.lower():
        pattern = re.compile(re.escape(family), re.IGNORECASE)
        diff = pattern.sub("", name).strip()
        
        # Clean up any wrapping parens
        if diff.startswith("(") and diff.endswith(")"):
            diff = diff[1:-1].strip()
            
        # Clean up leading dashes or colons
        diff = diff.lstrip(" :-").strip()
        
        # Clean up double spaces
        diff = " ".join(diff.split())
        
        if diff:
            return diff

    # Fallback: scan for common edition keywords
    patterns = [
        re.compile(r"\b(\d+(?:\.\d+)?e)\b", re.IGNORECASE),
        re.compile(r"\b(\d+(?:st|nd|rd|th)?(?:\s+\w+)?\s+(?:edition|ed\.?))\b", re.IGNORECASE),
        re.compile(r"\b((?:revised|anniversary|adventure|starter|core)\s+edition)\b", re.IGNORECASE)
    ]
    
    for p in patterns:
        m = p.search(name)
        if m:
            return m.group(1).strip()
            
    return None


# ── Fuzzy ranking ────────────────────────────────────────────────────────────

def _score_fuzzy_match(a, b):
    """
    Simple fuzzy ratio scoring so we don't need to import external libraries like thefuzz.
    Perfect for ranking API search results that might have slightly mangled titles.
    """
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ── BGG XML helpers ──────────────────────────────────────────────────────────

def _grab_attr(element, path, attrib="value", default=None):
    """
    BGG's XML is quirky - it stores almost everything in `value` attributes 
    rather than element text. This grabs a child node and pulls that value safely.
    """
    node = element.find(path)
    if node is None:
        return default
    return node.get(attrib, default)


def _grab_links(element, link_type):
    """
    Grabs all the values for a specific `<link type="...">` tag. 
    BGG uses these for everything from genres to mechanics.
    """
    return [
        link.get("value")
        for link in element.findall("link")
        if link.get("type") == link_type and link.get("value")
    ]


def _grab_links_with_id(element, link_type):
    """
    Same as _grab_links, but pulls the internal BGG ID as well.
    Useful when we actually need to make follow-up queries against specific entities.
    """
    return [
        (link.get("id"), link.get("value"))
        for link in element.findall("link")
        if link.get("type") == link_type and link.get("value")
    ]


# --- END OF PARSE LIBRARY ---

import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET



# ── HTTP ─────────────────────────────────────────────────────────────────────

def get_token():
    """
    Fail fast if the BGG_API_TOKEN environment variable isn't set.
    The API bounces unauthenticated requests immediately, so there's no point
    trying to parse XML if we don't have the key.
    """
    token = os.environ.get("BGG_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BGG_API_TOKEN is not set. To use the RPGGeek scraper you need a free "
            "API token from BoardGameGeek - register an application at "
            "https://boardgamegeek.com/account/api and set the token as the "
            "BGG_API_TOKEN environment variable on your Grimoire server."
        )
    return token


def _fetch_with_retries(url, token):
    """
    Fetch a URL from the BGG API with auth headers.
    
    BGG has a quirky habit of returning HTTP 202 (Accepted) if a record isn't
    cached on their end and needs to be queued. We sleep and retry a few times
    to wait it out, otherwise we'd throw errors on perfectly valid IDs.
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
            # BGG sometimes queues heavy requests and kicks back a 202 Accepted while processing. 
            # We just sleep and retry. Three attempts is usually enough to wait out the queue.
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


# ── Cache ─────────────────────────────────────────────────────────────────────

_CACHE_TTL = 86400  # 24 hours


def _cache_path(addon_dir, item_type, identity):
    cache_dir = os.path.join(addon_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{item_type}_{identity}.xml")


def _cache_read(path):
    """
    Returns the cached XML blob if it exists and hasn't gone stale. 
    Saves us waiting on BGG's slow endpoints.
    """
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


# ── Search ───────────────────────────────────────────────────────────────────

def _common_search(query, item_type, token, limit=15):
    """
    Hits the BGG search endpoint and scores the results against the user's query.
    We cap it at 15 items to keep the Grimoire search UI snappy.
    """
    encoded = urllib.parse.quote(query)
    url = f"https://rpggeek.com/xmlapi2/search?query={encoded}&type={item_type}"

    raw = _fetch_with_retries(url, token)
    root = ET.fromstring(raw)

    candidates = []
    for item in root.findall("item"):
        item_id = item.get("id")
        name = _grab_attr(item, "name")
        year = _grab_attr(item, "yearpublished") or ""
        if not item_id or not name:
            continue
        score = _score_fuzzy_match(query, name)
        year_label = f" ({year})" if year else ""
        candidates.append({
            "identity": item_id,
            "label": f"{name}{year_label}",
            "score": score,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:limit]


# ── Fetch ────────────────────────────────────────────────────────────────────

def _common_fetch(identity, item_type, token, cache_dir):
    """
    Pulls down the massive XML blob for a specific item, extracts everything 
    Grimoire cares about, and shapes it into our expected dictionary format.
    Caches the raw XML to avoid hammering BGG if the user re-opens the same item.
    """
    cache_path = _cache_path(cache_dir, item_type, identity)
    raw = _cache_read(cache_path)

    if raw is None:
        if item_type == "rpg":
            # RPG systems (like D&D 5e) aren't classified as "things" by BGG, they are "families"
            url = f"https://rpggeek.com/xmlapi2/family?id={identity}&type={item_type}"
        else:
            url = f"https://rpggeek.com/xmlapi2/thing?id={identity}&type={item_type}"
            
        raw = _fetch_with_retries(url, token)

    root = ET.fromstring(raw)
    item = root.find("item")
    
    if item is None:
        raise RuntimeError(f"RPGGeek returned no item for id={identity} type={item_type}. The ID may be wrong, or the item may have been removed.")

    # Only write to the cache if we actually got a valid item back!
    # Otherwise, if BGG hiccups or we send a bad request, we permanently cache the failure.
    if cache_path:
        _cache_write(cache_path, raw)

    name_node = item.find("name[@type='primary']")
    title = name_node.get("value", "") if name_node is not None else ""

    description_raw = ""
    desc_node = item.find("description")
    if desc_node is not None and desc_node.text:
        description_raw = desc_node.text

    year_raw = _grab_attr(item, "yearpublished")
    year = int(year_raw) if year_raw and year_raw.isdigit() else None

    publishers_raw = _grab_links_with_id(item, "rpgpublisher")
    publishers_data = [name for pub_id, name in publishers_raw]
    
    designers = _grab_links(item, "rpgdesigner")
    artists = _grab_links(item, "rpgartist")
    genres = _grab_links(item, "rpggenre")
    families = _grab_links(item, "rpgfamily")

    mechanics_raw = _grab_links(item, "rpgmechanic")
    dice = extract_all_dice_and_materials(mechanics_raw)

    system_family = families[0] if families else None
    edition = extract_edition(title, system_family)

    fields = {
        "description": _scrub_html(description_raw),
        "year": year,
        "genres": genres,
        "dice_materials": dice,
        "system_family": system_family,
        "edition": edition,
        "publishers": publishers_data,
        # book-specific fields
        "title": title,
        "publisher": publishers_raw[0][1] if publishers_raw else None,
        "authors": designers,
        "artists": artists,
    }

    source_url = _item_url(identity, item_type)
    fields["urls"] = [{"label": "RPGGeek", "url": source_url}]

    return fields, source_url


def _item_url(identity, item_type):
    slug = {"rpgitem": "rpgitem", "rpg": "rpg"}.get(item_type, "rpgitem")
    return f"https://rpggeek.com/{slug}/{identity}"

# --- END OF API LIBRARY ---

"""
rpggeek.py - book scraper entry-point.

The BGG XML API is messy, so we offload all the heavy lifting to `rpggeek_common.py`.
This file just wires up the search/fetch actions for books and handles the top-level
error wrapping so Grimoire doesn't choke on a raw stack trace.
"""

import json
import os
import sys




def search(query, addon_dir):
    token = get_token()
    candidates = _common_search(query, "rpgitem", token)
    return {"results": candidates}


def fetch(identity, addon_dir):
    identity = str(identity).strip()

    token = get_token()
    fields, url = _common_fetch(identity, "rpgitem", token, addon_dir)

    # Grimoire's schema strictly rejects payloads containing fields the target 
    # doesn't support. Since we share the fetch logic with game-systems, we have 
    # to scrub the system-specific fields here before returning.
    for key in ("dice_materials", "system_family", "edition", "publishers"):
        fields.pop(key, None)

    return {"fields": fields, "url": url}


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
