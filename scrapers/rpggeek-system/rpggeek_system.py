"""
rpggeek_system.py - game-system scraper entry-point for the rpggeek-system add-on.

Reads from stdin, writes to stdout, per the Grimoire script contract.
The actual work lives in rpggeek_common.py (in the sibling rpggeek/ directory) -
this file resolves the import path and wires up the action dispatch.
"""

import json
import os
import re
import sys


def _load_common(addon_dir):
    """
    rpggeek_common.py lives in the rpggeek/ sibling directory, not here.
    We resolve it relative to addon_dir so both add-ons can share the
    implementation without duplicating ~200 lines of XML parsing.
    """
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
    # Accept a full RPGGeek URL or a bare numeric ID.
    # e.g. "https://rpggeek.com/rpg/79109/dragonbane" or just "79109"
    m = re.search(r"/rpg/(\d+)", identity)
    if m:
        identity = m.group(1)

    common = _load_common(addon_dir)
    token = common.get_token()
    fields, url = common.fetch(identity, "rpg", token, addon_dir)

    # Drop fields that belong to the book target only.
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
