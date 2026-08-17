"""
rpggeek_system.py - game-system scraper entry-point.

Just like the book scraper, we farm out the heavy XML parsing to `rpggeek_common.py`.
This file simply hooks into the system-specific endpoint and scrubs out the 
fields that Grimoire's game-system schema doesn't care about.
"""

import json
import os
import re
import sys

from rpggeek_common import get_token, _common_search, _common_fetch


def search(query, addon_dir):
    token = get_token()
    candidates = _common_search(query, "rpg", token)
    return {"results": candidates}


def fetch(identity, addon_dir):
    # Grimoire users might paste a full URL or just the ID. 
    # We handle both so they don't have to manually strip the URL.
    m = re.search(r"/rpg/(\d+)", identity)
    if m:
        identity = m.group(1)

    token = get_token()
    fields, url = _common_fetch(identity, "rpg", token, addon_dir)

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
