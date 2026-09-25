# Character sheets

Schema-driven character sheets for Grimoire. A user installs the ones they want
and builds characters against them — a sheet never changes what anyone else
sees, so, like [themes](../themes/README.md), it needs no admin approval.

Each sheet is a directory named after its `id`, holding a JSON file of the same
name — plus, for a sheet with a custom layout, its HTML and CSS beside it:

```
character-sheets/
├── cairn/
│   ├── cairn.json    # required — the sheet
│   └── README.md     # optional, but the right home for licence wording
└── dnd-5e-2024/
    ├── dnd-5e-2024.json   # fields, computed values, content types
    ├── dnd-5e-2024.html   # the layout, as real HTML
    ├── dnd-5e-2024.css    # the stylesheet, as real CSS
    └── README.md
```

A sheet with a custom layout should keep it in **sibling `.html` and `.css`
files** rather than inlining it. HTML embedded in a JSON string has to be
escaped, which turns a readable layout into one unbroken line of `\"` and `\n`
— unwritable, and worse to review. The files are found by convention as
`<id>.html` and `<id>.css`, or named explicitly with `layout_file` and
`styles_file`. Grimoire folds them back into one document when the sheet is
installed, each verified against its own digest.

Run `python3 scripts/build_index.py` after adding or editing one; CI checks that
`character-sheets/index.json` is current.

Everything here is validated by
[`schema/character-sheet.schema.json`](../schema/character-sheet.schema.json).
Point your editor at it for completion and inline errors.

## What a sheet is

Three parts: the **fields** a character has, the **computed** values derived from
them, and the **layout** that draws them.

```json
{
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

### Fields

`text`, `number`, `textarea`, `checkbox`, `select`. A `select` needs `options`,
either plain values or `{value, label}` objects. `number` takes `min`/`max`,
which Grimoire **clamps** to rather than rejecting — refusing to save a whole
character over one out-of-range score would lose the player's work.

### Computed values

A small expression language over the other fields: arithmetic, comparisons,
`and`/`or`/`not`, `a ? b : c`, and a closed function table — `floor`, `ceil`,
`round`, `abs`, `min`, `max`, `sum`, `len`, `if`, `clamp`, `signed` (which
formats `3` as `+3`, the way a sheet prints a modifier), and `concat` (which
joins values as text: `concat(level, 'd', 8)` is `5d8`; `+` stays arithmetic).
`ref(field, 'property')` reads a property of the entry picked into a field, and
reads as empty when nothing is picked.

The player can override any computed value - a Grimoire rule, not something a
sheet opts into - and whatever depends on it follows. So write the formula for
the ordinary case and let the table handle the exceptions.

Formulas are **parsed, never executed**. There is no `eval` anywhere in the
engine, so a formula cannot do anything but arithmetic.

A computed value may depend on another and they sort themselves out, so you can
declare them in whatever order reads best:

```json
"computed": {
  "attack": { "formula": "signed(str_mod + prof)" },
  "str_mod": { "formula": "floor((strength - 10) / 2)" },
  "prof":    { "formula": "2 + floor((level - 1) / 4)" }
}
```

A formula naming a field that does not exist is rejected when the sheet is
installed, not when it is drawn.

### The character's name

`"name_field": "hero_name"` names the text field that holds the character's
name. It starts as the name the player gave when creating the character, and
editing either updates the other, so the character list and the sheet agree.

### Lists of picked entries

A `content_list` draws each entry as a row the player can open to read the
whole entry - a feat's description, a spell's full text. `display_columns`
draws it as a table of the entries' own properties instead of a name and a
summary line:

```json
"spells": { "type": "content_list", "content_type": "spell",
            "display_columns": ["level", "casting_time", "range", "components"] }
```

### Values that start from a choice

`default_from` gives a field its value until the player sets one:

```json
"speed": { "type": "number", "default": 30, "default_from": "ref(species, 'speed')" }
```

The field stays an ordinary editable field. Picking a species fills it in; the
player can type over it, and reset it back. An empty result falls back to
`default`, so with no species picked - or no content installed at all - it is
30. It can read fields but not computed values, which are worked out after it.

Use this, not a computed value, for anything the player might reasonably set
themselves: it keeps the field on the sheet as something they can type in.

### What a pick does

A `content_ref` may carry `on_pick` rules, which run when the player picks an
entry:

```json
"background": {
  "type": "content_ref", "content_type": "background",
  "on_pick": [
    { "grant": "skill_profs", "from": "skill_proficiencies" },
    { "grant": "feats", "ref": "feat_id", "name": "feat" }
  ]
},
"klass": {
  "type": "content_ref", "content_type": "class",
  "on_pick": [
    { "choose": "skill_profs", "count": "skill_choices", "from": "skill_options",
      "label": "Choose class skill proficiencies" }
  ]
}
```

- **`grant`** adds values from the picked entry. Into a `multiselect`, `from`
  names a list property. Into a `content_list`, `ref` names an entry id; if the
  catalog has no such entry, `name` is added as a freeform entry instead.
- **`choose`** asks the player to pick `count` values (a number, or a property
  holding one) from the entry's `from` list. They can always put it off.

Everything a pick adds is remembered, so changing the pick takes it back off -
but only what it added, never something the player gave themselves. The rules
read properties of the picked entry, so **the content type must declare every
property a rule reads**; an undeclared one is dropped when the pack loads, and
the rule would quietly do nothing. Grimoire refuses to install a sheet whose
rule names a property its content type does not declare, so this is caught at
install rather than at the table.

### What belongs in a sheet

A sheet holds a character's **record** and its **arithmetic**. It does not run
the game's character creation procedure - careers, lifepaths, priority tables,
random rolls. Those stay at the table with the book, and the sheet holds what
they produced.

Everything a sheet works out is a suggestion the player can override, and every
sheet must work with no content installed: `ref()` reads as empty, a
`default_from` falls back to its `default`, and a pick with nothing behind it
does nothing. If a game needs something these cannot express, the answer is a
general capability in Grimoire that other games could use too - open an issue
rather than working around it.

### Layout

`layout` is a list of sections, each a title and the fields in it, drawn in a
responsive grid. Omit it and Grimoire lists every field in declaration order.
That is a perfectly good sheet for a rules-light game, and it needs no design
work.

For a sheet that should look like its published original, write a layout — in
its own `.html` file, as below.

## Custom HTML sheets

`layout_html` is an HTML **template**, with directives where the interactive
parts go:

```html
<div class="sheet">
  <g-section title="Abilities">
    <g-field name="strength" />
    <g-computed name="str_mod" />
  </g-section>
  <g-if test="level > 4">
    <g-field name="feat" />
  </g-if>
</div>
```

| Directive | What it draws |
| --- | --- |
| `<g-field name="x"/>` | The editable control for field `x` |
| `<g-computed name="x"/>` | A calculated value, which the player can click to override |
| `<g-label name="x"/>` | That field's label text alone |
| `<g-value name="x"/>` | That value alone, as plain text. A calculated value or a text or number field can still be clicked to set |
| `<g-section title="...">` | A titled group, and a styling hook |
| `<g-if test="...">` | Its contents, when the expression is true |
| `<g-repeat over="...">` | Its contents once per row of a list field |
| `<g-tabs>` + `<g-tab title="...">` | Pages - only the chosen one is drawn. A `<g-tab>` takes `visible_if` |
| `<g-option field="x" value="v"/>` | One checkbox for one option of multiselect `x`, so each can sit where the sheet wants it. Takes `class` for styling |

`<g-field variant="compact">` draws a number as a plain numeric box without the
browser's spinner, which otherwise takes most of a narrow box - a hit point,
coin or ability-bonus cell. Keep each cell of a repeated row in its own element
(`<span class="...">`), so a row keeps its columns even if one cell draws
nothing.

Put the CSS in `<id>.css` beside it. Inline `styles` still works for a rule or
two, but a real sheet's stylesheet belongs in a file:

```json
{ "layout_file": "my-sheet.html", "styles_file": "my-sheet.css" }
```

### What is and is not allowed

The template never becomes markup. Grimoire parses it into a tree and renders
that as components, so a sheet has no way to inject HTML into the app. What
follows is therefore about what will *load*, not about what you could sneak
past:

- **Structural tags only** — `div`, `section`, `table`, headings, lists, `img`,
  and so on. No `script`, `style`, `iframe`, `object`, or `form`.
- **No form controls.** You cannot write an `<input>`; `<g-field>` renders a
  real one for you. That is what stops a sheet forging a control that looks
  like part of the app.
- **No event handlers.** Every `on*` attribute is rejected.
- **URLs must be relative or `https:`**, which rules out `javascript:` and
  `data:`.
- **CSS is scoped to the sheet** and filtered to a property allowlist, so a
  sheet cannot restyle the app around it. `url()` is rejected wherever it
  appears — an image belongs in an `<img src>`.

Anything outside this fails when the sheet is installed, with a message naming
the problem. Test with `python3 scripts/build_index.py` before you commit.

## Licensing

Most TTRPG rules text is **not** freely redistributable. Before writing a sheet
that reproduces any, check what the game actually permits.

A sheet that carries licensed content must set `license`, `license_url`, and
`attribution`. Grimoire renders `attribution` **verbatim** wherever the sheet is
browsed or used, and the index build fails if you set a `license` without one.

Several licences mandate exact wording. Reproduce it character for character —
do not paraphrase, and record the source in the sheet's README so the next
person can check it:

```json
"license": "CC-BY-SA-4.0",
"license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
"attribution": "Cairn is © Yochai Gal, licensed under CC BY-SA 4.0. See cairnrpg.com."
```

**A sheet's structure is not its content.** Field names and layout are generally
fine; pages of rules text are generally not. When a game has no open licence,
ship the structure and leave the content to the player.

Do not include artwork, page scans, or logos from any published book.
