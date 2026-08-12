#!/usr/bin/env python3
"""Validate this repo's contents and regenerate its three index files.

  index.json            add-ons (scrapers) — installed by an admin
  templates/index.json  note templates — browsed and downloaded by a GM
  themes/index.json     colour themes — installed per user

Run with --check to verify the committed indexes are up to date (what CI does
on a PR); run with no arguments to rewrite them.

    python3 scripts/build_index.py           # regenerate
    python3 scripts/build_index.py --check   # fail if stale or invalid

Note templates carry their folder path, so Grimoire can render the repo's
directory tree in its browser. A folder may hold a `_folder.yml` giving its
display name; without one the directory name is used.
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
ADDON_DIRS = ("scrapers", "plugins")
TEMPLATE_DIR = ROOT / "templates"
THEME_DIR = ROOT / "themes"
INDEX_PATH = ROOT / "index.json"
TEMPLATE_INDEX_PATH = TEMPLATE_DIR / "index.json"
THEME_INDEX_PATH = THEME_DIR / "index.json"
# Optional per-folder metadata (display name), not an add-on itself.
FOLDER_META = "_folder.yml"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover() -> list[pathlib.Path]:
    """Every add-on manifest, as <dir>/<name>/<name>.yml."""
    found = []
    for group in ADDON_DIRS:
        base = ROOT / group
        if not base.is_dir():
            continue
        for addon_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            manifest = addon_dir / f"{addon_dir.name}.yml"
            if manifest.is_file():
                found.append(manifest)
            else:
                print(f"  ! {addon_dir.relative_to(ROOT)}: expected {manifest.name}")
    return found


def discover_templates() -> list[pathlib.Path]:
    """Every note-template manifest under templates/, at any folder depth.

    A directory holding ``<its own name>.yml`` is a template; anything else is
    a grouping folder and is descended into. That lets templates be filed by
    system (``templates/draw-steel/ds-encounter/``) without the layout being
    baked into the format.
    """
    found: list[pathlib.Path] = []

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

    if TEMPLATE_DIR.is_dir():
        for entry in sorted(p for p in TEMPLATE_DIR.iterdir() if p.is_dir()):
            walk(entry)
    return found


def folder_display_name(directory: pathlib.Path) -> str:
    """A folder's display name from its ``_folder.yml``, else its directory name."""
    meta = directory / FOLDER_META
    if meta.is_file():
        try:
            data = yaml.safe_load(meta.read_text()) or {}
            name = str(data.get("name") or "").strip()
            if name:
                return name
        except yaml.YAMLError:
            pass
    return directory.name


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
            "target": data.get("target", "game-system"),
            "version": data["version"],
            "path": rel,
            "requires_script": "script" in data,
            "sha256": sha256(manifest_path),
        }
        for optional in ("description", "homepage", "grimoire_min_version"):
            if optional in data:
                entry[optional] = data[optional]

        if "script" in data:
            script_path = manifest_path.parent / data["script"]["entry"]
            if not script_path.is_file():
                errors.append(f"{rel}: script '{data['script']['entry']}' not found")
                continue
            entry["script_sha256"] = sha256(script_path)

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


def build_templates() -> tuple[dict, list[str]]:
    """Validate every note template and build the catalogue Grimoire browses.

    Templates are *not* add-ons: nobody installs them into a server. A GM
    browses this catalogue and downloads a copy into their own campaign, so the
    index carries the folder path (for the browser's tree) and the body's
    digest (so a download can be verified).
    """
    schema = json.loads((ROOT / "schema" / "note-template.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    templates = []
    folders: dict[str, str] = {}

    for manifest_path in discover_templates():
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

        if data["id"] != manifest_path.parent.name:
            errors.append(
                f"{rel}: id '{data['id']}' does not match directory "
                f"'{manifest_path.parent.name}'"
            )
            continue

        body_name = data.get("body", f"{data['id']}.md")
        body_path = manifest_path.parent / body_name
        if not body_path.is_file():
            errors.append(f"{rel}: template body '{body_name}' not found")
            continue

        # The folder path relative to templates/, minus the template's own
        # directory — this is what the browser renders as its tree.
        folder = manifest_path.parent.parent.relative_to(TEMPLATE_DIR).as_posix()
        if folder == ".":
            folder = ""
        # Record a display name for this folder and each of its ancestors.
        if folder:
            parts = folder.split("/")
            for depth in range(len(parts)):
                key = "/".join(parts[: depth + 1])
                folders.setdefault(key, folder_display_name(TEMPLATE_DIR / key))

        entry = {
            "id": data["id"],
            "name": data["name"],
            "version": data["version"],
            "folder": folder,
            "path": rel,
            "body_path": (manifest_path.parent / body_name)
            .relative_to(ROOT)
            .as_posix(),
            "sha256": sha256(manifest_path),
            "body_sha256": sha256(body_path),
        }
        for optional in ("system", "category", "description", "grimoire_min_version"):
            if optional in data:
                entry[optional] = data[optional]

        templates.append(entry)

    index = {
        "version": 1,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "folders": [
            {"path": path, "name": name} for path, name in sorted(folders.items())
        ],
        "templates": sorted(templates, key=lambda t: (t["folder"], t["id"])),
    }

    index_schema = json.loads(
        (ROOT / "schema" / "note-template-index.schema.json").read_text()
    )
    for err in jsonschema.Draft202012Validator(index_schema).iter_errors(index):
        errors.append(f"templates/index.json: {err.message}")

    return index, errors


def discover_themes() -> list[pathlib.Path]:
    """Every theme file, as themes/<id>/<id>.json."""
    if not THEME_DIR.is_dir():
        return []
    found = []
    for entry in sorted(THEME_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        candidate = entry / f"{entry.name}.json"
        if candidate.is_file():
            found.append(candidate)
    return found


def build_themes() -> tuple[dict, list[str]]:
    """Validate every theme and build the catalogue Grimoire browses.

    Themes are neither add-ons nor templates: nobody installs one into a
    server, and nothing executes. A user browses this catalogue and downloads a
    copy into their own account, so the index carries the file's digest and
    Grimoire verifies it on download.
    """
    schema = json.loads((ROOT / "schema" / "theme.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    themes = []

    for theme_path in discover_themes():
        rel = theme_path.relative_to(ROOT).as_posix()
        try:
            data = json.loads(theme_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if schema_errors:
            for err in schema_errors:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                errors.append(f"{rel}: {loc}: {err.message}")
            continue

        if data["id"] != theme_path.parent.name:
            errors.append(
                f"{rel}: id '{data['id']}' does not match directory "
                f"'{theme_path.parent.name}'"
            )
            continue

        # A theme ships either a flat `tokens` map or a `variants` block with a
        # palette per colour mode. Normalise to the list of modes it covers, so
        # the catalogue can show one row reading "light & dark".
        variants = data.get("variants") or {}
        modes = [m for m in ("light", "dark") if variants.get(m)]
        if not modes:
            if not data.get("tokens"):
                errors.append(f"{rel}: a theme must set at least one token")
                continue
            modes = [data["mode"]]

        entry = {
            "id": data["id"],
            "name": data["name"],
            "version": data["version"],
            "mode": data["mode"],
            "modes": modes,
            "path": rel,
            "sha256": sha256(theme_path),
        }
        for optional in ("app_mode", "author", "description", "homepage", "grimoire_min_version"):
            if data.get(optional):
                entry[optional] = data[optional]
        themes.append(entry)

    index = {
        "version": 1,
        "generated": dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "themes": sorted(themes, key=lambda t: t["id"]),
    }

    index_schema = json.loads((ROOT / "schema" / "theme-index.schema.json").read_text())
    for err in jsonschema.Draft202012Validator(index_schema).iter_errors(index):
        errors.append(f"themes/index.json: {err.message}")

    return index, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed indexes are current instead of rewriting them",
    )
    args = parser.parse_args()

    index, errors = build()
    template_index, template_errors = build_templates()
    theme_index, theme_errors = build_themes()
    errors = errors + template_errors + theme_errors
    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"Validated {len(index['addons'])} add-on(s), "
        f"{len(template_index['templates'])} note template(s), and "
        f"{len(theme_index['themes'])} theme(s)."
    )

    targets = [
        (INDEX_PATH, index, "addons"),
        (TEMPLATE_INDEX_PATH, template_index, "templates"),
        (THEME_INDEX_PATH, theme_index, "themes"),
    ]

    if args.check:
        for path, built, key in targets:
            rel = path.relative_to(ROOT)
            if not path.is_file():
                print(f"{rel} is missing — run: python3 scripts/build_index.py")
                return 1
            committed = json.loads(path.read_text())
            # `generated` is a timestamp; it always differs and is not
            # meaningful drift. `folders` is derived, so it is compared too.
            stale = committed.get(key) != built[key] or committed.get(
                "folders"
            ) != built.get("folders")
            if stale:
                print(f"{rel} is stale — run: python3 scripts/build_index.py")
                return 1
            print(f"{rel} is up to date.")
        return 0

    for path, built, _ in targets:
        path.write_text(json.dumps(built, indent=2) + "\n")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
