# Content packs

Catalog content for a character sheet - the spells, classes, species, feats and
backgrounds a character picks from. A sheet describes the *shape* of a spell;
a pack supplies the spells.

| Pack | For sheet | Licence | Entries |
| --- | --- | --- | --- |
| [`dnd-5e-srd`](dnd-5e-srd/) | `dnd-5e-2024` | CC BY 4.0 (SRD 5.2) | 1109 |
| [`draw-steel-core`](draw-steel-core/) | `draw-steel` | Draw Steel Creator License | 1660 |
| [`pf2e-player-core`](pf2e-player-core/) | `pathfinder-2e` | ORC | 1606 |

## How a pack reaches a table

1. A pack is published in `content-packs/index.json` like everything else here.
2. An **admin** installs it from **Characters → Manage sheets → Content →
   Browse content packs**. Packs are server-wide, which is why installing needs
   an admin. Grimoire writes it into `DATA_PATH/character-content/<pack_id>/`,
   checking each file against the digest the index published.
3. From then on, every character on that sheet can pick from it, and a GM can
   import it into their campaign's **ruleset** in a click - which is where a
   table forks entries, adds house rules, and limits a game to the content it
   allows.

A character stores a **reference** to an entry (its id), never a copy, so a
corrected entry reaches every character that picked it.

## Adding a pack

### 1. Check the licence

**Everything in a pack must be covered by the licence it names.** A pack is
rules content in bulk, and most rules content is not redistributable. Read
[Licensing](#licensing) below before writing one.

### 2. Make sure the sheet declares the content

A pack can only supply what its sheet's
[`content_types`](../docs/character-sheets.md#content-types) declare. The
sheet decides the shape - which properties a spell has, which are searched and
filtered on, what the one-line summary shows - and the pack fills it in.

**Every property a pack carries must be declared there.** Undeclared properties
are dropped when the pack loads, so they are never stored, searched or read by a
formula. Adding a property to a pack therefore usually means adding its
declaration to the sheet in the same PR.

### 3. Make the directory

```
content-packs/
└── my-game-srd/
    ├── _meta.json    # required - the pack
    ├── spell.json    # one file per content type
    ├── class.json
    └── species.json
```

The directory name is the `pack_id`. Each content file is named after the
content type it holds: `spell.json` holds entries of the sheet's `spell` type.

### 4. Write `_meta.json`

```json
{
  "pack_id": "dnd-5e-srd",
  "schema_id": "dnd-5e-2024",
  "name": "D&D 5e SRD 5.2",
  "version": "1.0.0",
  "description": "Every species, background, feat, spell and item in SRD 5.2.",
  "license": "CC-BY-4.0",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "attribution": "…the licence's exact required wording…",
  "source": "srd",
  "source_url": "https://www.dndbeyond.com/srd"
}
```

| Key | Required | What it is |
| --- | --- | --- |
| `pack_id` | yes | Lowercase letters, digits, single `-` or `_`. Must match the directory |
| `schema_id` | yes | The sheet the content is for. **Not** a hard reference: a pack may be installed before anyone installs the sheet, and install order does not matter |
| `name` | yes | Shown in the catalogue and on every entry's credit |
| `version` | | Semver. Grimoire offers an installed pack's update when this rises |
| `description` | | One or two sentences for the catalogue |
| `license`, `license_url`, `attribution` | | The content's licence. `attribution` is shown verbatim and is **required** once `license` is set - the index build and the server's loader both refuse a pack without it |
| `source` | | A short label every entry is tagged with, so "Fireball (srd)" is distinguishable from a table's own house version. Defaults to the `pack_id` |
| `source_url` | | Where the content came from |

Validated by
[`schema/content-pack.schema.json`](../schema/content-pack.schema.json).

### 5. Write the content files

Each content file is a JSON array of entries. Each entry needs an `_id`, and the
remaining keys are the properties its content type declares:

```json
[
  { "_id": "fireball", "name": "Fireball", "level": 3, "school": "Evocation",
    "description": "A bright streak flashes from your pointing finger…" },
  { "_id": "magic-missile", "name": "Magic Missile", "level": 1, "school": "Evocation",
    "_source": "srd-errata" }
]
```

| Key | What it is |
| --- | --- |
| `_id` | Required. **Unique across the whole pack**, not only within one file: a character stores a pick as the id alone, so an ancestry trait and the ability it grants cannot both be `human-detect-the-supernatural`. Never change a published id - characters that picked it would show it as missing |
| `_source` | Overrides the pack's `source` for this entry |
| anything else | A property the content type declares, coerced to its declared type: a `number` property given `"3"` is stored as `3`, and a list given to a `text` property is turned into text |

Rules of thumb:

- **Text is plain text.** Separate paragraphs with a blank line. Markdown and
  HTML are shown as typed.
- **Give every property a formula or a pick reads.** A class's `hit_die`, a
  background's `feat_id`, a species' `speed`: if an entry lacks one, the sheet
  falls back to the player typing it, which works but defeats the point.
- **Lists of ids** that an `on_pick` rule grants - a species' `trait_ids` - can
  be a real list, or comma-separated text if the sheet declares the property as
  `text`.
- Up to 20,000 entries per content type and 32 MiB per file.

### 6. Try it locally

Copy the directory into your own Grimoire's `DATA_PATH/character-content/`, then
**Settings → Add-ons → Character content packs → Reload from disk**. Install the
sheet, create a character, and pick from the catalog. A pack that will not load
is left out of the list, with the reason in the server log.

The pack is indexed against an installed copy of its sheet, so install the sheet
before reloading. Loaded with no copy installed, entries are stored as written,
undeclared properties and all, until the next reload.

### 7. Build the index and open a PR

```bash
python3 scripts/build_index.py
```

This checks `_meta.json` against its schema, that `pack_id` matches the
directory, that every entry has an `_id` and none repeats within a file, and
records each file's digest in `content-packs/index.json`. Commit the index with
the pack; CI fails if it is stale.

Add the pack to the table above, and give it a `README.md` recording where the
content came from and how it was converted. A pack generated from another
dataset should keep its converter under [`scripts/`](../scripts/) so it can be
regenerated - the existing packs do.

## Updating a published pack

Raise `version` and rebuild the index; an admin sees the update under
**Browse content packs** and installs it. Characters pick up corrections at
once, because they reference entries rather than copy them.

A ruleset that imported the pack keeps its **own copy** of the entries - that is
what makes it editable - so it does not change until its GM imports the pack
again and chooses **Replace it**.

Removing an entry never breaks a character: the sheet shows the pick as not
installed, and it reads correctly again if the entry returns.

## Homebrew without a pack

A table's own content does not need to be a pack, or to come through this
repository. A GM can write entries into a **ruleset** by hand, or import a
ruleset document - the same entries, grouped by content type, in one file:

```json
{
  "$schema": "grimoire://ruleset/v1",
  "name": "Our House Rules",
  "schema_id": "dnd-5e-2024",
  "version": "1.0.0",
  "entries": {
    "feat": [{ "_id": "lucky-break", "name": "Lucky Break", "description": "…" }]
  }
}
```

**Characters → Manage sheets → Content → Import a document** takes it as JSON
or YAML, and **Export** writes one from any ruleset. A pack is the right home
for content many tables share under an open licence; a ruleset is the right home
for one table's.

## Licensing

**Everything in a pack must be covered by the licence it names.** The 5e pack
is SRD 5.2 only - nine species, four backgrounds, the SRD feats, spells, class
features, equipment and magic items - because it carries the SRD's CC BY 4.0
attribution. Content from a rulebook outside the SRD cannot go in it however
familiar it is: the Player's Handbook's other backgrounds, feats and species are
not open content. Check each entry against the source document, not against
memory; an earlier version of this pack got that wrong, and Grimoire's test
suite now checks the pack against the SRD's lists.

Its spells, class features, equipment and magic items are converted from
[Open5e](https://github.com/open5e/open5e-api)'s SRD 5.2 data by
`scripts/srd-5e/import_open5e.py`. Open5e expands a generic magic item into a
copy per weapon or armour; the script folds those back into the one entry the
SRD prints.

The Draw Steel pack is MCDM's text, converted from [Forge Steel](https://forgesteel.net/)'s
data under the Draw Steel Creator License. Forge Steel's GPL-3.0 covers its code,
not MCDM's text, so it is credited rather than licensed from. The pack takes only
the core book, *Draw Steel: Heroes* - Forge Steel also carries third-party and
community books the Creator License does not cover.

The Pathfinder pack is converted from the Foundry VTT pf2e system, which records
each item's book and licence. It takes only items from *Pathfinder Player Core*
marked ORC, and carries Paizo's attribution for that book verbatim. Anything
Player Core points at from an OGL book - the dwarf's Clan Dagger is from the
Core Rulebook - is left out rather than brought in with it. It is **rules text
only**: Paizo keeps its world (deities, places, planes, organisations) as
Reserved Material, so colour text and anything naming the setting is stripped.

A pack carrying licensed content must set `license`, `license_url` and
`attribution`. Grimoire renders `attribution` **verbatim** wherever the content
is browsed or used, and copies it onto any ruleset the pack is imported into, so
credit follows the content rather than stopping at the pack.

Several licences mandate exact wording. Reproduce it character for character and
record where it came from, so the next person can check it.

Do not include artwork, page scans, or logos from any published book.
