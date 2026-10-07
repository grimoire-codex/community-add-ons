# Character sheets

Schema-driven character sheets for Grimoire. A user installs the ones they want
from **Characters → Manage sheets → Browse sheets** and builds characters
against them. A sheet never changes what anyone else sees, so, like
[themes](../themes/README.md), it needs no admin approval.

This page walks through adding one. The complete list of what a sheet can use -
every field type, formula function, layout directive, HTML tag and CSS property
- is the [**character sheet reference**](../docs/character-sheets.md).

| Sheet | System | Licence | Layout | Content pack |
| --- | --- | --- | --- | --- |
| [`dnd-5e-2024`](dnd-5e-2024/) | Dungeons & Dragons 5e (2024) | CC BY 4.0 | Custom | [`dnd-5e-srd`](../content-packs/dnd-5e-srd/) |
| [`draw-steel`](draw-steel/) | Draw Steel | Draw Steel Creator License | Custom, after the printed sheet | [`draw-steel-core`](../content-packs/draw-steel-core/) |
| [`pathfinder-2e`](pathfinder-2e/) | Pathfinder 2e | ORC | Custom | [`pf2e-player-core`](../content-packs/pf2e-player-core/) |
| [`pathfinder-1e`](pathfinder-1e/) | Pathfinder 1e | OGL 1.0a | Custom, after the 2009 sheet | |
| [`call-of-cthulhu-7e`](call-of-cthulhu-7e/) | Call of Cthulhu 7th Edition | Chaosium Fan Material Policy | Custom | |
| [`traveller-2e`](traveller-2e/) | Traveller (Mongoose 2nd Edition) | Traveller Fair Use Policy | Custom, after J. Brannen's spreadsheet | |
| [`cosmere-rpg`](cosmere-rpg/) | Cosmere RPG | Cosmere RPG Fan Content Policy | Custom | |
| [`dungeon-crawler-carl`](dungeon-crawler-carl/) | Dungeon Crawler Carl | - | Custom, after the printed sheet | |
| [`cairn`](cairn/) | Cairn | CC BY-SA 4.0 | Default | |
| [`basic-fantasy`](basic-fantasy/) | Basic Fantasy RPG | CC BY-SA 4.0 | Default | |

The best way to learn the format is to read one of these. `cairn` is the
smallest complete sheet; `dnd-5e-2024` uses nearly everything.

## What a sheet is

Three parts: the **fields** a character has, the **computed** values derived
from them, and the **layout** that draws them.

```json
{
  "$schema": "../../schema/character-sheet.schema.json",
  "id": "cairn",
  "name": "Cairn",
  "version": "1.0.0",
  "system": "Cairn",
  "author": "you",
  "fields": {
    "strength": { "type": "number", "label": "Strength", "min": 0, "max": 20, "default": 10 },
    "hp": { "type": "number", "label": "Hit Protection", "min": 0, "default": 4 }
  },
  "computed": {
    "wounded": { "formula": "hp <= 0 ? 'Wounded' : 'Hale'", "label": "Condition" }
  },
  "layout": [{ "title": "Abilities", "fields": ["strength", "hp", "wounded"] }]
}
```

That is a working sheet. Everything else is optional and adds to it:

| To | Use | Reference |
| --- | --- | --- |
| Hold a name, a score, a note, a choice | `text`, `number`, `textarea`, `checkbox`, `select`, `multiselect` fields | [Fields](../docs/character-sheets.md#fields) |
| Hold a table of rows - gear, weapons | a `list` field with `columns` | [`list` columns](../docs/character-sheets.md#list-columns) |
| Work out a modifier, a total, a DC | `computed` formulas | [Formulas](../docs/character-sheets.md#formulas), [Functions](../docs/character-sheets.md#function-reference) |
| Pick spells or a class from a catalog | `content_ref` / `content_list` fields, plus `content_types` | [Catalog fields](../docs/character-sheets.md#catalog-fields-content_ref-and-content_list), [Content types](../docs/character-sheets.md#content-types) |
| Fill in values from a pick | `default_from` and `on_pick` | [`default_from`](../docs/character-sheets.md#default_from), [`on_pick`](../docs/character-sheets.md#what-a-pick-does-on_pick) |
| Hide a field until it applies | `visible_if` | [`visible_if`](../docs/character-sheets.md#visible_if) |
| Warn about an illegal build | `validators` | [Validators](../docs/character-sheets.md#validators) |
| Look like the printed sheet | a custom HTML layout and stylesheet | [Custom HTML layout](../docs/character-sheets.md#custom-html-layout), [Stylesheet](../docs/character-sheets.md#stylesheet) |

## Adding a sheet

### 1. Check the licence first

Before writing anything, read what the game permits - see
[Licensing](#licensing) below. It decides whether the sheet can carry rules text,
whether it can follow the printed sheet's look, and what credit it must show.

### 2. Make the directory

A sheet is a directory named after its `id`, holding a JSON file of the same
name. A sheet with a custom layout keeps its HTML and CSS beside it:

```
character-sheets/
└── my-game/
    ├── my-game.json    # required - fields, computed values, content types
    ├── my-game.html    # optional - the custom layout, as real HTML
    ├── my-game.css     # optional - its stylesheet, as real CSS
    └── README.md       # optional, but the right home for licence wording
```

The `id` is lowercase letters, digits and single `-` or `_`. Characters store
it, so **never rename a published sheet** - publish a new id instead.

The sheet file in this repository is **JSON**. (Grimoire's paste box also takes
YAML, which is handier while drafting.)

Keep a custom layout in **sibling `.html` and `.css` files** rather than inlining
it as `layout_html` / `styles` strings. HTML embedded in a JSON string has to be
escaped, which turns a readable layout into one unbroken line of `\"` and `\n`.
The files are found by convention as `<id>.html` and `<id>.css`, or named
explicitly with `layout_file` and `styles_file`. Grimoire folds them back into
one document when the sheet is installed, each verified against its own digest.

### 3. Write the fields and formulas

Start with the fields and computed values and leave out the layout: with no
layout, Grimoire draws every field in declaration order, which is enough to
check the arithmetic. Add `"$schema": "../../schema/character-sheet.schema.json"`
at the top for editor completion.

### 4. Try it in Grimoire

**Characters → Manage sheets → Paste a sheet** takes three boxes: the sheet
JSON (or YAML), the layout HTML, and the stylesheet. Pasting runs the full
install-time validation - every formula parsed, every layout tag and CSS
property checked - and names the problem if anything fails. Then create a
character on it and fill it in.

Pasting it again replaces your copy, so you can iterate: edit, paste, reload the
character.

### 5. Build the index

```bash
python3 scripts/build_index.py
```

This checks every sheet against the JSON Schema, that its `id` matches its
directory, that a licensed sheet carries `attribution`, and that its layout and
stylesheet files exist, then regenerates `character-sheets/index.json`. Commit
the index with the sheet; CI runs `build_index.py --check` and fails if it is
stale.

`build_index.py` does **not** run Grimoire's own validator - it cannot tell a
formula that will not parse or a CSS property that is not allowed. Pasting the
sheet (step 4) does. So does Grimoire's test suite: with the `grimoire`
repository checked out beside this one,

```bash
python3 -m pytest backend/tests/test_bundled_sheets.py
```

loads every sheet here through the real validator, computes an empty character
on it, checks its licence and credit, and checks its layout and stylesheet
files.

### 6. Add a README and open a PR

The sheet's own `README.md` records where its licence wording came from, what
it covers and anything a maintainer should know. Add the sheet to the table
above and to the one in the [repository README](../README.md#character-sheets),
then open a PR.

### Updating a published sheet

Bump `version` on every change and rebuild the index. Never remove or rename a
field that characters already store: the character keeps the value, and it
still travels in an export, but nothing on the sheet shows a field the sheet no
longer declares - not even **All values**. Adding fields is always safe, and so
is fixing a formula: computed values are never stored, so the correction reaches
every existing character.

## What belongs in a sheet

A sheet holds a character's **record** and its **arithmetic**. It does not run
the game's character creation procedure - careers, lifepaths, priority tables,
random rolls. Those stay at the table with the book, and the sheet holds what
they produced.

Four rules keep sheets working for everyone:

1. **The record and the arithmetic, never the procedure.**
2. **Everything automatic is a suggestion.** The player can override any
   computed value and type over any `default_from`, and a validator warns but
   never blocks saving. Write the formula for the ordinary case and let the
   table handle the exceptions.
3. **Nothing in the engine is about one game.** If a game needs something the
   format cannot express, the answer is a general capability in Grimoire that
   other games could use too - open an issue rather than working around it.
4. **Every sheet works with no content installed.** `ref()` reads as empty, a
   `default_from` falls back to its `default`, a pick with nothing behind it
   does nothing, and `allow_freeform` lets the player type entries in.

## Licensing

Most TTRPG rules text is **not** freely redistributable. Before writing a sheet
that reproduces any, check what the game actually permits.

A sheet that carries licensed content must set `license`, `license_url`, and
`attribution`. Grimoire renders `attribution` **verbatim** wherever the sheet is
browsed or used, and the index build fails if you set a `license` without one.

Several licences mandate exact wording. Reproduce it character for character -
do not paraphrase, and record the source in the sheet's README so the next
person can check it:

```json
"license": "CC-BY-SA-4.0",
"license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
"attribution": "Cairn is © Yochai Gal, licensed under CC BY-SA 4.0. See cairnrpg.com."
```

**A sheet's structure is not its content.** Field names and layout are generally
fine; pages of rules text are generally not. When a game has no open licence,
ship the structure and leave the content to the player. The Traveller sheet is
that case: Mongoose's Fair Use Policy permits non-commercial spreadsheets that
automate the rules, with its notice, but not its rules text, so the sheet has no
content pack and every list is the player's to fill.

**Check what a fan policy says about software and about the publisher's look.**
Some policies permit fan character sheets, including web-based ones that
calculate values, but exclude downloadable apps; some forbid imitating the
publisher's own sheet - its "trade dress" - so a sheet follows the printed one's
content and order but not its fonts, textures or page frame. Chaosium's Fan
Material Policy does both; see the Call of Cthulhu sheet's README.

Do not include artwork, page scans, or logos from any published book.
