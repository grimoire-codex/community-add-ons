"""
rpggeek.py - book scraper entry-point.

The BGG XML API is messy, so we offload all the heavy lifting to `rpggeek_common.py`.
This file just wires up the search/fetch actions for books and handles the top-level
error wrapping so Grimoire doesn't choke on a raw stack trace.
"""

import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import rpggeek_common as common


def search(query, addon_dir):
    token = common.get_token()
    candidates = common.search(query, "rpgitem", token)
    return {"results": candidates}


def fetch(identity, addon_dir):
    # Grimoire users might paste a full URL or just the ID. 
    # We handle both so they don't have to manually strip the URL.
    import re
    m = re.search(r"/rpgitem/(\d+)", identity)
    if m:
        identity = m.group(1)

    token = common.get_token()
    fields, url = common.fetch(identity, "rpgitem", token, addon_dir)

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
