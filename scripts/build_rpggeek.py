#!/usr/bin/env python3
"""
build_rpggeek.py - Bundler for RPGGeek scrapers.

"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "scrapers", "rpggeek", "src")

COMMON_FILE = os.path.join(SRC_DIR, "rpggeek_common.py")
RPGGEEK_SRC = os.path.join(SRC_DIR, "rpggeek.py")
RPGGEEK_SYS_SRC = os.path.join(SRC_DIR, "rpggeek_system.py")

RPGGEEK_OUT = os.path.join(ROOT, "scrapers", "rpggeek", "rpggeek.py")
RPGGEEK_SYS_OUT = os.path.join(ROOT, "scrapers", "rpggeek-system", "rpggeek_system.py")

def build_script(common_code, src_path, out_path):
    with open(src_path, "r", encoding="utf-8") as f:
        src_code = f.read()

    # We have to aggressively strip out the local import, otherwise Python 
    # will try to look for rpggeek_common.py at runtime and explode.
    src_code = re.sub(r"^from rpggeek_common import.*$", "", src_code, flags=re.MULTILINE)

    # Just smash them together. It ain't pretty, and you end up with some 
    # duplicated imports, but it keeps Grimoire happy.
    bundled = f"{common_code}\n\n# --- END OF COMMON LIBRARY ---\n\n{src_code.strip()}\n"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(bundled)
    
    print(f"Built {os.path.relpath(out_path, ROOT)}")

def main():
    if not os.path.exists(COMMON_FILE):
        print(f"Error: Could not find {COMMON_FILE}")
        return 1

    # Load our heavy-lifting XML logic once and inject it into both scrapers.
    with open(COMMON_FILE, "r", encoding="utf-8") as f:
        common_code = f.read()

    build_script(common_code, RPGGEEK_SRC, RPGGEEK_OUT)
    build_script(common_code, RPGGEEK_SYS_SRC, RPGGEEK_SYS_OUT)
    print("RPGGeek scripts bundled successfully.")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
