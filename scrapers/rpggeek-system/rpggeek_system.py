"""
rpggeek_system.py - game-system scraper entry-point.

Just like the book scraper, we farm out the heavy XML parsing to `rpggeek_common.py`.
This file just resolves the messy import path and sets up the system-specific fetching.
"""

import json
import os
import re
import sys


def _load_common(addon_dir):
    # FIXME: We have to hack the sys.path here to share the XML parsing logic 
    # across both scrapers without duplicating 200 lines of code. Not ideal, 
    # but it avoids a maintenance nightmare if the BGG API changes.
    common_dir = os.path.join(os.path.dirname(addon_dir.rstrip("/\\")), "rpggeek")
    if common_dir not in sys.path:
        sys.path.insert(0, common_dir)
    import rpggeek_common
    return rpggeek_common


def search(query, addon_dir):
    common = _load_common(addon_dir)
    token = common.get_token()
    candidates = common.search(query, "rpg", token)
    return {"results": candidates}


def fetch(identity, addon_dir):
    # Grimoire users might paste a full URL or just the ID. 
    # We handle both so they don't have to manually strip the URL.
    m = re.search(r"/rpg/(\d+)", identity)
    if m:
        identity = m.group(1)

    common = _load_common(addon_dir)
    token = common.get_token()
    fields, url = common.fetch(identity, "rpg", token, addon_dir)

    # Grimoire's schema strictly rejects payloads containing fields the target 
    # doesn't support. We scrub the book-specific fields here before returning.
    for key in ("title", "publisher", "authors", "artists"):
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
