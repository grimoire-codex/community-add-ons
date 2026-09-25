# Content packs

Catalog content for a character sheet — the spells, classes, species, feats and
backgrounds a character picks from. A sheet describes the *shape* of a spell;
a pack supplies the spells.

A pack is published in `content-packs/index.json` like everything else here, and
an admin installs one from **Characters → Manage sheets → Rulesets → Browse
content packs**. Grimoire writes it into the server's
`DATA_PATH/character-content/`, checking each file against the digest the index
published. Copying a directory there by hand still works and is loaded on
startup - the filesystem is the source of truth either way.

From there a GM imports the pack into their campaign's **ruleset** in a click,
and the table plays with it.

```
content-packs/
└── dnd-5e-srd/
    ├── _meta.json    # required — the pack
    ├── spell.json    # one file per content type
    ├── class.json
    └── species.json
```

Run `python3 scripts/build_index.py` after editing one; it validates every pack
and regenerates `content-packs/index.json`, and CI checks that the committed
index is current.

## `_meta.json`

```json
{
  "pack_id": "dnd-5e-srd",
  "schema_id": "dnd-5e-2024",
  "name": "D&D 5e SRD 5.2",
  "version": "1.0.0",
  "license": "CC-BY-4.0",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "attribution": "…the licence's exact required wording…",
  "source": "srd"
}
```

`pack_id` must match the directory name. `schema_id` names the character sheet
the content is for — it is **not** a hard reference, so a pack may be installed
before anyone installs the sheet, and install order does not matter.

`source` is the short label each entry is tagged with, so a table browsing its
catalog can tell "Fireball (srd)" from its own house version.

Validated by
[`schema/content-pack.schema.json`](../schema/content-pack.schema.json).

## Content files

One file per content type, named after it — `spell.json` holds entries of type
`spell`. Each is an array of objects, and each object needs an `_id` unique
within that file:

```json
[
  { "_id": "fireball", "name": "Fireball", "level": 3, "school": "Evocation" },
  { "_id": "magic-missile", "name": "Magic Missile", "level": 1 }
]
```

The remaining keys are whatever the sheet's content type declares. Fields the
sheet does not declare are dropped on load rather than rejected, so a pack can
carry extra detail for a sheet that has not caught up.

That cuts both ways: a property the sheet's rules *read* - a class's
`skill_options`, a background's `feat_id` - must be declared by the sheet, or
it is dropped before any rule sees it. Add the property to the pack and the
declaration to the sheet together.

An entry may override the pack's `source` with its own `_source`.

## Licensing

This matters more here than anywhere else in the repo: a pack is rules content,
in bulk, and most of it is not redistributable. **Check what the game actually
permits before writing one.**

A pack carrying licensed content must set `license`, `license_url` and
`attribution`. Grimoire renders `attribution` **verbatim** wherever the content
is browsed or used, and copies it onto any ruleset the pack is imported into, so
credit follows the content rather than stopping at the pack. Validation fails if
you set a `license` without one — and the server's loader refuses the pack too.

Several licences mandate exact wording. Reproduce it character for character and
record where it came from, so the next person can check it.

Do not include artwork, page scans, or logos from any published book.
