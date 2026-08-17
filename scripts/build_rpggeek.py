#!/usr/bin/env python3
"""
build_rpggeek.py - Bundler for RPGGeek scrapers.

"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "scrapers", "rpggeek", "src")

PARSE_FILE = os.path.join(SRC_DIR, "parse.py")
API_FILE = os.path.join(SRC_DIR, "api.py")
RPGGEEK_SRC = os.path.join(SRC_DIR, "rpggeek.py")
RPGGEEK_SYS_SRC = os.path.join(SRC_DIR, "rpggeek_system.py")

RPGGEEK_OUT = os.path.join(ROOT, "scrapers", "rpggeek", "rpggeek.py")
RPGGEEK_SYS_OUT = os.path.join(ROOT, "scrapers", "rpggeek-system", "rpggeek_system.py")

def build_script(parse_code, api_code, src_path, out_path):
    with open(src_path, "r", encoding="utf-8") as f:
        src_code = f.read()

    # We have to aggressively strip out the local imports, otherwise Python 
    # will try to look for our modular files at runtime and explode.
    api_code = re.sub(r"^from parse import.*$", "", api_code, flags=re.MULTILINE)
    src_code = re.sub(r"^from api import.*$", "", src_code, flags=re.MULTILINE)

    # Just smash them together sequentially. It ain't pretty, and you end up 
    # with some duplicated imports, but it keeps Grimoire happy.
    bundled = (
        f"{parse_code}\n\n"
        f"# --- END OF PARSE LIBRARY ---\n\n"
        f"{api_code.strip()}\n\n"
        f"# --- END OF API LIBRARY ---\n\n"
        f"{src_code.strip()}\n"
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(bundled)
    
    print(f"Built {os.path.relpath(out_path, ROOT)}")

def main():
    if not os.path.exists(PARSE_FILE):
        print(f"Error: Could not find {PARSE_FILE}")
        return 1
    if not os.path.exists(API_FILE):
        print(f"Error: Could not find {API_FILE}")
        return 1

    # Load our heavy-lifting logic and inject it into both scrapers.
    with open(PARSE_FILE, "r", encoding="utf-8") as f:
        parse_code = f.read()
    with open(API_FILE, "r", encoding="utf-8") as f:
        api_code = f.read()

    build_script(parse_code, api_code, RPGGEEK_SRC, RPGGEEK_OUT)
    build_script(parse_code, api_code, RPGGEEK_SYS_SRC, RPGGEEK_SYS_OUT)
    print("RPGGeek scripts bundled successfully.")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
