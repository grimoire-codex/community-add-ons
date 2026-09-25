#!/usr/bin/env python3
"""Validate this repo's contents and regenerate its four index files.

  index.json            add-ons (scrapers) — installed by an admin
  templates/index.json  note templates — browsed and downloaded by a GM
  themes/index.json     colour themes — installed per user
  character-sheets/index.json  character sheets — installed per user
  content-packs/index.json     content packs — installed server-wide by an admin

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
SHEET_DIR = ROOT / "character-sheets"
PACK_DIR = ROOT / "content-packs"
SHEET_INDEX_PATH = SHEET_DIR / "index.json"
PACK_INDEX_PATH = PACK_DIR / "index.json"
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
        for optional in ("description", "homepage", "author", "grimoire_min_version"):
            if optional in data:
                entry[optional] = data[optional]

        if "script" in data:
            script_path = manifest_path.parent / data["script"]["entry"]
            if not script_path.is_file():
                errors.append(f"{rel}: script '{data['script']['entry']}' not found")
                continue
            entry["script_sha256"] = sha256(script_path)

        changelog_path = manifest_path.parent / "changelog.yml"
        if changelog_path.is_file():
            try:
                changelog_data = yaml.safe_load(changelog_path.read_text())
                entry["changelog"] = changelog_data
            except yaml.YAMLError as exc:
                errors.append(f"{rel}: invalid changelog YAML: {exc}")

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
        for optional in ("system", "category", "description", "author", "grimoire_min_version"):
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


def discover_sheets() -> list[pathlib.Path]:
    """Every character sheet, as character-sheets/<id>/<id>.json."""
    if not SHEET_DIR.is_dir():
        return []
    found = []
    for entry in sorted(SHEET_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        candidate = entry / f"{entry.name}.json"
        if candidate.is_file():
            found.append(candidate)
    return found


def _sidecar(data: dict, directory: pathlib.Path, key: str, extension: str):
    """The sibling file a sheet keeps its layout or stylesheet in.

    Named explicitly via ``key``, or found by convention as ``<id><extension>``.
    Returns ``(path, error)`` — the path is None when the sheet has no such
    file, which is not an error; a *named* file that is missing is.
    """
    named = data.get(key)
    if named:
        candidate = directory / str(named)
        if not candidate.is_file():
            return None, f"{key} '{named}' not found"
        return candidate, ""

    conventional = directory / f"{data['id']}{extension}"
    return (conventional if conventional.is_file() else None), ""


def build_sheets() -> tuple[dict, list[str]]:
    """Validate every character sheet and build the catalogue Grimoire browses.

    Sheets follow themes rather than add-ons: a user installs one into their own
    account, nothing executes, and no admin approves it. The index carries the
    file's digest, which Grimoire verifies on download.

    A sheet describing a licensed game must carry that licence's required
    credit in `attribution`, which Grimoire renders verbatim. Several open
    licences mandate exact wording, so the check here is only that it is
    present — getting it *right* is the author's job, and the per-sheet README
    is where the wording is recorded.
    """
    schema = json.loads((ROOT / "schema" / "character-sheet.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    sheets = []

    for sheet_path in discover_sheets():
        rel = sheet_path.relative_to(ROOT).as_posix()
        try:
            data = json.loads(sheet_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        # `$schema` is an editor affordance, not part of the document.
        data.pop("$schema", None)

        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if schema_errors:
            for err in schema_errors:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                errors.append(f"{rel}: {loc}: {err.message}")
            continue

        if data["id"] != sheet_path.parent.name:
            errors.append(
                f"{rel}: id '{data['id']}' does not match directory "
                f"'{sheet_path.parent.name}'"
            )
            continue

        # A select field without options renders as an empty dropdown, which the
        # app rejects on install — catch it here instead, where the author is.
        for field_name, definition in data["fields"].items():
            if definition.get("type") == "select" and not definition.get("options"):
                errors.append(f"{rel}: select field '{field_name}' has no options")

        # Licensed content must credit its source. A sheet naming a licence but
        # no attribution is the easy mistake, and the one that matters.
        if data.get("license") and not data.get("attribution"):
            errors.append(
                f"{rel}: 'license' is set but 'attribution' is missing — "
                "a licensed sheet must carry the credit Grimoire displays"
            )

        # A sheet's layout and stylesheet may live in sibling files rather than
        # being inlined as JSON strings — HTML embedded in JSON has to be
        # escaped, which makes it unreadable and all but unmaintainable. Named
        # explicitly, or found by convention as `<id>.html` / `<id>.css`.
        directory = sheet_path.parent
        layout_file, layout_error = _sidecar(data, directory, "layout_file", ".html")
        styles_file, styles_error = _sidecar(data, directory, "styles_file", ".css")
        for problem in (layout_error, styles_error):
            if problem:
                errors.append(f"{rel}: {problem}")
        if layout_error or styles_error:
            continue

        entry = {
            "id": data["id"],
            "name": data["name"],
            "version": data["version"],
            "path": rel,
            "sha256": sha256(sheet_path),
            "custom_layout": bool(data.get("layout_html") or layout_file),
            "field_count": len(data["fields"]),
        }
        if layout_file:
            entry["layout_path"] = layout_file.relative_to(ROOT).as_posix()
            entry["layout_sha256"] = sha256(layout_file)
        if styles_file:
            entry["styles_path"] = styles_file.relative_to(ROOT).as_posix()
            entry["styles_sha256"] = sha256(styles_file)
        for optional in (
            "system", "description", "author", "homepage",
            "license", "license_url", "attribution", "grimoire_min_version",
        ):
            if data.get(optional):
                entry[optional] = data[optional]
        sheets.append(entry)

    index = {
        "version": 1,
        "generated": dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "sheets": sorted(sheets, key=lambda s: s["id"]),
    }

    index_schema = json.loads(
        (ROOT / "schema" / "character-sheet-index.schema.json").read_text()
    )
    for err in jsonschema.Draft202012Validator(index_schema).iter_errors(index):
        errors.append(f"character-sheets/index.json: {err.message}")

    return index, errors


def build_content_packs() -> tuple[dict, list[str]]:
    """Validate every content pack and build the catalogue Grimoire browses.

    A pack is several files - `_meta.json` plus one per content type - so its
    index entry carries a digest per file rather than one for the pack. Grimoire
    downloads each and checks it, the same rule a sheet and its sibling
    layout/stylesheet follow.

    This used to validate only, on the reasoning that an admin installs a pack
    by copying a directory onto the server. That left the SRD sitting in this
    repo with no way to reach anyone, so packs are published like everything
    else here.
    """
    index: dict = {
        "$schema": "../schema/content-pack-index.schema.json",
        "version": 1,
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "packs": [],
    }
    errors: list[str] = []
    if not PACK_DIR.is_dir():
        return index, errors

    schema = json.loads((ROOT / "schema" / "content-pack.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)

    for directory in sorted(p for p in PACK_DIR.iterdir() if p.is_dir()):
        meta_path = directory / "_meta.json"
        rel = meta_path.relative_to(ROOT).as_posix()
        if not meta_path.is_file():
            errors.append(f"{directory.relative_to(ROOT)}: no _meta.json")
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        for err in validator.iter_errors(meta):
            errors.append(f"{rel}: {err.message}")
        if meta.get("pack_id") and meta["pack_id"] != directory.name:
            errors.append(
                f"{rel}: pack_id {meta['pack_id']!r} does not match the "
                f"directory {directory.name!r}"
            )

        files = [
            {
                "name": "_meta.json",
                "path": rel,
                "sha256": sha256(meta_path),
                "bytes": meta_path.stat().st_size,
            }
        ]
        content_types: list[str] = []
        total = 0

        for content_file in sorted(directory.glob("*.json")):
            if content_file.name == "_meta.json":
                continue
            crel = content_file.relative_to(ROOT).as_posix()
            try:
                entries = json.loads(content_file.read_text())
            except json.JSONDecodeError as exc:
                errors.append(f"{crel}: invalid JSON: {exc}")
                continue
            if not isinstance(entries, list):
                errors.append(f"{crel}: must be an array of entries")
                continue

            seen: set[str] = set()
            for position, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    errors.append(f"{crel}: entry {position} is not an object")
                    continue
                entry_id = entry.get("_id")
                if not isinstance(entry_id, str) or not entry_id.strip():
                    errors.append(f"{crel}: entry {position} has no '_id'")
                    continue
                if entry_id in seen:
                    errors.append(f"{crel}: defines {entry_id!r} twice")
                seen.add(entry_id)

            content_types.append(content_file.stem)
            total += len(entries)
            files.append(
                {
                    "name": content_file.name,
                    "path": crel,
                    "sha256": sha256(content_file),
                    "bytes": content_file.stat().st_size,
                }
            )

        entry = {
            "pack_id": meta.get("pack_id", directory.name),
            "schema_id": meta.get("schema_id", ""),
            "name": meta.get("name", directory.name),
            "files": files,
            "entry_count": total,
            "content_types": content_types,
        }
        for key in ("version", "description", "license", "license_url",
                    "attribution", "source_url"):
            if meta.get(key):
                entry[key] = meta[key]
        index["packs"].append(entry)

    index_schema = json.loads(
        (ROOT / "schema" / "content-pack-index.schema.json").read_text()
    )
    for err in jsonschema.Draft202012Validator(index_schema).iter_errors(index):
        errors.append(f"content-packs/index.json: {err.message}")

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
    sheet_index, sheet_errors = build_sheets()
    pack_index, pack_errors = build_content_packs()
    errors = errors + template_errors + theme_errors + sheet_errors + pack_errors
    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"Validated {len(index['addons'])} add-on(s), "
        f"{len(template_index['templates'])} note template(s), "
        f"{len(theme_index['themes'])} theme(s), and "
        f"{len(sheet_index['sheets'])} character sheet(s), and "
        f"{len(pack_index['packs'])} content pack(s)."
    )

    targets = [
        (INDEX_PATH, index, "addons"),
        (TEMPLATE_INDEX_PATH, template_index, "templates"),
        (THEME_INDEX_PATH, theme_index, "themes"),
        (SHEET_INDEX_PATH, sheet_index, "sheets"),
        (PACK_INDEX_PATH, pack_index, "packs"),
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
