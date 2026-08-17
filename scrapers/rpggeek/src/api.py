import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from parse import _MessyHTMLScrubber, _scrub_html, extract_all_dice_and_materials, extract_edition, _score_fuzzy_match, _grab_attr, _grab_links, _grab_links_with_id

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
