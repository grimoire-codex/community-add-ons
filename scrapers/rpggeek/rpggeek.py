"""
rpggeek.py - book scraper entry-point for the rpggeek add-on.

Reads from stdin, writes to stdout, per the Grimoire script contract.
The actual work lives in rpggeek_common.py - this file just wires up the
action dispatch and handles top-level error formatting.
"""

import json
import sys

import rpggeek_common as common


def search(query, addon_dir):
    token = common.get_token()
    candidates = common.search(query, "rpgitem", token)
    return {"results": candidates}


def fetch(identity, addon_dir):
    # Accept a full RPGGeek URL or a bare numeric ID.
    # e.g. "https://rpggeek.com/rpgitem/386173/dragonbane-mirth-and-mayhem-roleplaying"
    #   or just "386173"
    import re
    m = re.search(r"/rpgitem/(\d+)", identity)
    if m:
        identity = m.group(1)

    token = common.get_token()
    fields, url = common.fetch(identity, "rpgitem", token, addon_dir)

    # Drop fields that don't belong on the book target.
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
