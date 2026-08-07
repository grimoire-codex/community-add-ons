#!/usr/bin/env python3
"""Validate every add-on in this repo and regenerate index.json.

Run with --check to verify the committed index is up to date (what CI does on a
PR); run with no arguments to rewrite it.

    python3 scripts/build_index.py           # regenerate
    python3 scripts/build_index.py --check   # fail if stale or invalid
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema is required: pip install jsonschema")

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADDON_DIRS = ("scrapers", "plugins", "templates")
INDEX_PATH = ROOT / "index.json"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover() -> list[pathlib.Path]:
    """Every add-on manifest, as <...>/<name>/<name>.yml.

    Add-ons may be nested in grouping folders, so templates can be filed by
    system (``templates/draw-steel/ds-encounter/ds-encounter.yml``) rather than
    all sitting flat. A directory holding ``<its own name>.yml`` is an add-on;
    anything else is treated as a grouping folder and descended into.
    """
    found = []

    def walk(directory: pathlib.Path) -> None:
        manifest = directory / f"{directory.name}.yml"
        if manifest.is_file():
            found.append(manifest)
            return
        children = sorted(p for p in directory.iterdir() if p.is_dir())
        if not children:
            print(f"  ! {directory.relative_to(ROOT)}: expected {manifest.name}")
            return
        for child in children:
            walk(child)

    for group in ADDON_DIRS:
        base = ROOT / group
        if not base.is_dir():
            continue
        for entry in sorted(p for p in base.iterdir() if p.is_dir()):
            walk(entry)
    return found


def build() -> tuple[dict, list[str]]:
    schema = json.loads((ROOT / "schema" / "addon.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    addons = []

    for manifest_path in discover():
        rel = manifest_path.relative_to(ROOT).as_posix()
        try:
            data = yaml.safe_load(manifest_path.read_text())
        except yaml.YAMLError as exc:
            errors.append(f"{rel}: invalid YAML: {exc}")
            continue

        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if schema_errors:
            for err in schema_errors:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                errors.append(f"{rel}: {loc}: {err.message}")
            continue

        # The id is the install directory name, so it must match on disk.
        if data["id"] != manifest_path.parent.name:
            errors.append(
                f"{rel}: id '{data['id']}' does not match directory "
                f"'{manifest_path.parent.name}'"
            )
            continue

        entry = {
            "id": data["id"],
            "name": data["name"],
            "kind": data["kind"],
            "version": data["version"],
            "path": rel,
            "requires_script": "script" in data,
            "sha256": sha256(manifest_path),
        }
        # `target` selects which fields a scraper may write; a note-template has
        # no mapping step, so emitting it there would be meaningless noise.
        if data["kind"] != "note-template":
            entry["target"] = data.get("target", "game-system")
        for optional in ("description", "homepage", "grimoire_min_version"):
            if optional in data:
                entry[optional] = data[optional]

        if "script" in data:
            script_path = manifest_path.parent / data["script"]["entry"]
            if not script_path.is_file():
                errors.append(f"{rel}: script '{data['script']['entry']}' not found")
                continue
            entry["script_sha256"] = sha256(script_path)

        if data["kind"] == "note-template":
            # The markdown body is the whole payload of a template add-on, so it
            # is digested and verified on install exactly like a script is.
            body_name = data.get("body", f"{data['id']}.md")
            body_path = manifest_path.parent / body_name
            if not body_path.is_file():
                errors.append(f"{rel}: template body '{body_name}' not found")
                continue
            entry["body_sha256"] = sha256(body_path)
            for optional in ("system", "category"):
                if optional in data:
                    entry[optional] = data[optional]

        addons.append(entry)

    index = {
        "version": 1,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "addons": sorted(addons, key=lambda a: a["id"]),
    }

    index_schema = json.loads((ROOT / "schema" / "index.schema.json").read_text())
    for err in jsonschema.Draft202012Validator(index_schema).iter_errors(index):
        errors.append(f"index.json: {err.message}")

    return index, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed index is current instead of rewriting it",
    )
    args = parser.parse_args()

    index, errors = build()
    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"Validated {len(index['addons'])} add-on(s).")

    if args.check:
        if not INDEX_PATH.is_file():
            print("index.json is missing — run: python3 scripts/build_index.py")
            return 1
        committed = json.loads(INDEX_PATH.read_text())
        # `generated` is a timestamp; it always differs and is not meaningful drift.
        if committed.get("addons") != index["addons"]:
            print("index.json is stale — run: python3 scripts/build_index.py")
            return 1
        print("index.json is up to date.")
        return 0

    INDEX_PATH.write_text(json.dumps(index, indent=2) + "\n")
    print(f"Wrote {INDEX_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
