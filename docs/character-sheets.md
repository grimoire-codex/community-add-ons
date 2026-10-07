# Character sheet reference

Everything a character sheet can use: every top-level key, field type, field
property, formula function, layout directive, HTML tag and CSS property Grimoire
accepts. For a walkthrough of adding a sheet to this repository, start with
[`character-sheets/README.md`](../character-sheets/README.md). For the content a
sheet draws from, see [`content-packs/README.md`](../content-packs/README.md).

Nothing in a sheet executes. Formulas are parsed by a small hand-written parser,
never `eval`ed; a custom layout is parsed into a tree and drawn as components,
never inserted as HTML; a stylesheet is filtered and scoped to the sheet. Each
of these is checked when the sheet is **installed**, so a sheet that would break
is refused with a message naming the problem rather than drawing wrong at the
table.

The machine-readable version of this page is
[`schema/character-sheet.schema.json`](../schema/character-sheet.schema.json).
Point your editor at it (`"$schema": "../../schema/character-sheet.schema.json"`)
for completion and inline errors.

## Contents

- [Top-level keys](#top-level-keys)
- [Fields](#fields)
- [Computed values](#computed-values)
- [Formulas](#formulas)
- [Function reference](#function-reference)
- [Defaults, conditions and validators](#defaults-conditions-and-validators)
- [Content types](#content-types)
- [What a pick does: `on_pick`](#what-a-pick-does-on_pick)
- [Simple layout](#simple-layout)
- [Custom HTML layout](#custom-html-layout)
- [Stylesheet](#stylesheet)
- [Limits](#limits)

## Top-level keys

| Key | Required | What it is |
| --- | --- | --- |
| `id` | yes | Lowercase letters, digits, and single `-` or `_` (`dnd-5e-2024`). Matches the directory name. A character stores this id, so **never change it** once published |
| `name` | yes | Shown in the sheet catalogue and on every character |
| `version` | | Semver (`1.2.0`), shown in the catalogue. Bump it on every change |
| `system` | | The game's name, for grouping |
| `description` | | One or two sentences for the catalogue |
| `author` | | Who wrote the sheet |
| `homepage` | | A link for the game or the sheet |
| `license`, `license_url`, `attribution` | | The game's licence. `attribution` is shown verbatim and is required once `license` is set - see [Licensing](../character-sheets/README.md#licensing) |
| `grimoire_min_version` | | The oldest Grimoire release the sheet works with |
| `fields` | | What a character stores. See [Fields](#fields) |
| `computed` | | What is worked out from them. See [Computed values](#computed-values) |
| `validators` | | Warnings the sheet raises. See [Validators](#validators) |
| `content_types` | | The shape of catalog content the sheet picks from. See [Content types](#content-types) |
| `name_field` | | A `text` field that holds the character's name. See [The character's name](#the-characters-name) |
| `layout` | | A simple layout of titled sections. See [Simple layout](#simple-layout) |
| `layout_file` / `layout_html` | | A custom HTML layout, as a sibling file (preferred) or an inline string |
| `styles_file` / `styles` | | Its stylesheet, as a sibling file (preferred) or an inline string |

With neither `layout` nor a custom layout, Grimoire lists every field in
declaration order under one heading - a perfectly good sheet for a rules-light
game.

## Fields

`fields` is an object keyed by field name. A name starts with a letter or `_`
and holds only letters, digits and underscores (`str_mod`, not `str-mod`),
because formulas refer to fields by name.

### Properties every field takes

| Property | What it does |
| --- | --- |
| `type` | One of the types below. Defaults to `text` |
| `label` | What the sheet shows. Defaults to the field name |
| `default` | The value a new character starts with |
| `default_from` | A formula giving the field its value until the player sets one. See [`default_from`](#default_from) |
| `visible_if` | A formula; the field is drawn only while it is true. See [`visible_if`](#visible_if) |
| `placeholder` | Hint text in an empty `text` or `textarea` |

### Field types

| Type | Stores | Extra properties |
| --- | --- | --- |
| `text` | A string | `placeholder` |
| `textarea` | A string, several lines | `rows` (height, default 4), `placeholder` |
| `number` | A number | `min`, `max` |
| `checkbox` | `true` / `false` | |
| `select` | One of its options | `options` (required) |
| `multiselect` | A list of its options | `options` (required) |
| `list` | Rows of typed columns - an inventory, a weapon table | `columns` (required), `add_label`, `empty_text` |
| `content_ref` | One picked catalog entry - a class, a species | `content_type` (required), `on_pick`, `allow_freeform`, `per_entry_fields` |
| `content_list` | Many picked catalog entries - spells, feats | `content_type` (required), `allow_freeform`, `per_entry_fields`, `display_columns`, `add_label`, `empty_text` |

**`min` and `max` clamp rather than reject.** A score of 25 on a sheet capped at
20 saves as 20; refusing to save a whole character over one box would lose the
player's work.

**`options`** is a list of plain values (`["Str", "Dex"]`) or objects
(`[{ "value": "str", "label": "Strength" }]`). A `select` or `multiselect`
without options is refused.

### `list` columns

```json
"equipment": {
  "type": "list", "label": "Equipment", "add_label": "Add item",
  "columns": [
    { "key": "item", "label": "Item", "flex": 3 },
    { "key": "qty", "label": "Qty", "type": "number", "min": 0, "default": 1 },
    { "key": "mass", "label": "Mass", "type": "number", "min": 0 },
    { "key": "equipped", "label": "Worn", "type": "checkbox" }
  ]
}
```

Each column takes `key` (required, an identifier), `label`, `type` (`text`,
`number`, `checkbox`, `select` or `textarea` - not another `list`), `options`
for a select, `min`/`max` for a number, `default` for new rows, and `flex` for
its relative width. Up to 20 columns, and 500 rows per character.

A list stores an array of row objects keyed by column:
`[{ "item": "Rope", "qty": 1, "mass": 1, "equipped": false }]`. The list
functions - [`count_where`](#function-reference), `sum_where`, `column`,
`sum_qty` - read it.

### Catalog fields: `content_ref` and `content_list`

A catalog field opens a searchable browser over the entries of one
[content type](#content-types). It stores a **reference**, never a copy:

```json
{ "_ref": "fireball", "_source": "srd", "_per": { "prepared": true } }
```

so an erratum to the entry reaches every character who picked it. A reference
to an entry that is not installed still saves and still opens; the sheet shows
it as missing.

| Property | What it does |
| --- | --- |
| `content_type` | Which of the sheet's `content_types` it picks from. Required |
| `allow_freeform` | Adds an **Add custom** button, so the player can add an entry the catalog lacks. It is stored inline as `{ "_inline": true, "name": "…", … }` with the content type's own properties |
| `per_entry_fields` | The character's own notes on each pick - prepared, equipped, uses left. An object of ordinary field definitions, stored under `_per` |
| `display_columns` | `content_list` only. Draws the list as a table of the entries' own properties: `["level", "range"]`, or `[{ "key": "level", "label": "Lvl" }]` |
| `add_label`, `empty_text` | The add button's text, and what an empty list says |
| `on_pick` | `content_ref` only. Rules that run when the player picks. See [`on_pick`](#what-a-pick-does-on_pick) |

The player's `_per` notes win over the entry's own values when a formula reads
the entry, so `count_refs(spells, 'prepared')` counts what the player ticked.

**Every sheet must work with no content installed.** A catalog field with
nothing installed is still a field: `allow_freeform` lets the player type
entries in, `ref()` reads as empty, and a `default_from` falls back to its
`default`.

### The character's name

`"name_field": "hero_name"` names a `text` field that holds the character's
name. It starts as the name the player gave when creating the character, and
renaming either one renames the other, so the character list and the sheet
agree.

## Computed values

`computed` is an object keyed by name, each a formula and a label:

```json
"computed": {
  "str_mod": { "formula": "floor((strength - 10) / 2)", "label": "STR Mod" },
  "attack": { "formula": "signed(str_mod + prof)", "label": "Attack" },
  "prof": { "formula": "2 + floor((level - 1) / 4)", "label": "Proficiency" }
}
```

- A computed name cannot also be a field name.
- A computed value may use others, declared in any order - they are worked out
  in as many passes as the chain needs (up to 12), so a cycle stops rather than
  spins.
- Computed values are **never stored**. They are worked out every time the
  sheet is read, so fixing a formula in a new version corrects every existing
  character.
- **The player can override any computed value**, and everything built on it
  follows. That is a Grimoire rule, not something a sheet opts into: write the
  formula for the ordinary case and let the table handle the exceptions.

A formula naming a field or computed value that does not exist is refused at
install.

## Formulas

Computed values, `default_from`, `visible_if`, validator rules, `<g-if test>`
and `visible_if` attributes all use the same small language.

| | |
| --- | --- |
| Arithmetic | `+ - * / %`, unary `-`, parentheses |
| Comparison | `== != < <= > >=` |
| Logic | `and`, `or`, `not` (or `&&`, `\|\|`) |
| Conditional | `cond ? a : b` |
| Literals | numbers (`3`, `1.5`), strings (`'elf'` or `"elf"`), `true`, `false`, `null` |
| Names | any field or computed value on the sheet |
| Calls | the [functions below](#function-reference) - nothing else |

How values behave, which is what keeps a half-filled sheet drawing:

- **An empty or unknown value reads as 0** in arithmetic. A level box mid-edit
  is `0`, not an error.
- **Dividing by zero gives 0.**
- `==` and `!=` compare values as written, so `ancestry == 'elf'` works; `<`,
  `>` and friends compare numerically.
- In a condition, `0`, `"0"`, `"false"`, an empty string and an empty list are
  false; everything else is true.
- `+` is always arithmetic. To build text, use [`concat`](#function-reference).
- A column name passed to a list function is a **string**: `count_where(gear,
  'equipped')`. A bare `equipped` would be read as a field of that name first.
- Inside a [`<g-repeat>`](#custom-html-layout), the current row's columns are
  names too, along with `_index` (the row's position, from 0).

## Function reference

The complete, closed set. A formula calling anything else is refused at
install.

### Numbers

| Function | Result |
| --- | --- |
| `floor(x)`, `ceil(x)` | Round down / up |
| `round(x)`, `round(x, digits)` | Round to the nearest whole number, or to `digits` places |
| `abs(x)` | Absolute value |
| `min(a, b, …)`, `max(a, b, …)` | Smallest / largest. Also takes a list: `max(column(gear, 'qty'))` |
| `sum(a, b, …)` | Total. Also takes a list |
| `clamp(x, low, high)` | `x` held between `low` and `high` |

### Text and logic

| Function | Result |
| --- | --- |
| `signed(x)` | A modifier as a sheet prints one: `+3`, `-1`, `+0` |
| `concat(a, b, …)` | Values joined as text: `concat(level, 'd', 8)` is `5d8`. Empty values print as nothing; capped at 1000 characters |
| `if(cond, a, b)` | `a` when `cond` is true, else `b` - the same as `cond ? a : b` |
| `len(x)` | Length of a list or a string |
| `contains(x, value)` | Whether a list (a `multiselect`) holds `value`, or text contains it (case-insensitive): `contains(skill_profs, 'Athletics')` |

### `list` fields

| Function | Result |
| --- | --- |
| `count_where(rows, 'col')` | How many rows have `col` true. `count_where(rows, 'col', value)` counts rows where `col` equals `value` |
| `sum_where(rows, 'col')` | Total of `col` across every row |
| `sum_where(rows, 'col', 'where')` | Total of `col` across rows where `where` is true; add a fourth argument to match a value instead: `sum_where(gear, 'mass', 'location', 'pack')` |
| `any_where(rows, 'col')` | Whether any row has `col` true (or equal to a third argument) |
| `column(rows, 'col')` | Every row's `col`, as a list - for `sum`, `min` and `max` |
| `sum_qty(rows, 'col')` | Total of `col` times each row's `qty` - carried weight, cargo. A blank quantity counts once; `0` counts as none. Name a different quantity column with a third argument: `sum_qty(cargo, 'tons', 'count')`. Works on a `content_list` too, reading each entry's property and the player's per-entry quantity |

### Catalog fields

| Function | Result |
| --- | --- |
| `ref(field, 'prop')` | One property of the entry picked into a `content_ref`: `ref(klass, 'hit_die')`. Reads as empty (`''`, which is `0` in arithmetic) when nothing is picked or the entry lacks the property |
| `sum_refs(field, 'prop')` | Total of one property across every entry in a `content_list` |
| `count_refs(field)` | How many entries a `content_list` holds |
| `count_refs(field, 'prop')` | How many have `prop` true; add a third argument to match a value: `count_refs(spells, 'level', 0)` counts cantrips |
| `has_ref(field, 'entry-id')` | Whether a list holds a reference to one entry id |

The catalog functions read the player's `_per` notes on top of the entry, and
an `allow_freeform` entry's own values, so a homebrew spell marked prepared is
counted like a catalog one.

## Defaults, conditions and validators

### `default_from`

Gives a field its value until the player sets one:

```json
"speed": { "type": "number", "default": 30, "default_from": "ref(species, 'speed')" }
```

The field stays an ordinary editable field. Picking a species fills it in and
marks it **auto**; the player can type over it, and the reset button hands it
back. An empty result falls back to `default`, so with no species picked - or
nothing installed at all - it is 30.

`default_from` reads **fields only, not computed values**: defaults are filled
in before anything is computed, so a computed name would silently read as
nothing, and is refused at install instead.

Use it rather than a computed value for anything a player might reasonably set
themselves.

### `visible_if`

A formula on a field, a simple-layout section, or a `<g-field>`,
`<g-computed>`, `<g-section>` or `<g-tab>` in a custom layout. The thing is
drawn only while it is true:

```json
"spell_dc": { "type": "number", "label": "Spell DC", "visible_if": "casts_spells" }
```

Hiding never deletes a value - the player can still reach every value from
**All values** in the sheet's header, whatever the layout shows.

### Validators

Warnings the sheet raises as the player fills it in:

```json
"validators": [
  {
    "rule": "len(prepared_spells) <= max_prepared",
    "message": "More spells prepared than your maximum allows",
    "field": "prepared_spells",
    "severity": "warning"
  }
]
```

The `rule` states what **should** hold; the message shows when it does not.
`field` attaches the message to one field (omit it for the whole sheet), and
`severity` is `warning` (the default) or `error`. **Neither blocks saving** - a
sheet mid-edit is routinely invalid, and a table's house rule is as good as the
book's. Up to 200 validators.

## Content types

`content_types` declares the shape of the catalog content the sheet picks from.
A [content pack](../content-packs/README.md) supplies the entries; the sheet
says what an entry looks like and how the browser presents it.

```json
"content_types": {
  "spell": {
    "label": "Spell",
    "label_plural": "Spells",
    "identity_field": "name",
    "fields": {
      "name": { "type": "text", "label": "Name" },
      "level": { "type": "number", "label": "Level" },
      "school": { "type": "select", "label": "School",
                  "options": ["Abjuration", "Evocation", "Illusion"] },
      "description": { "type": "textarea", "label": "Description" }
    },
    "sort_default": ["level", "name"],
    "search_fields": ["name", "description"],
    "filter_fields": ["level", "school"],
    "compact_display": "Level {level} {school}"
  }
}
```

| Key | What it does |
| --- | --- |
| `fields` | The entry's properties, as ordinary [field definitions](#fields). Required |
| `label`, `label_plural` | What the browser calls one entry, and several |
| `identity_field` | The property that names an entry - what a pick shows and what the catalog sorts by. Defaults to `name` |
| `sort_default` | Properties the browser sorts by, in order |
| `search_fields` | Properties full-text search indexes. Omit it and every text value is indexed |
| `filter_fields` | Properties the browser offers as filters, each with the values present |
| `compact_display` | A one-line summary under each entry's name, with `{property}` placeholders |

Every key that names a property is checked against `fields` at install. A pack
entry's properties are kept only if the content type declares them - so
**declare every property a formula or an `on_pick` rule reads**, or it is
dropped when the pack loads. Up to 50 content types per sheet.

## What a pick does: `on_pick`

A `content_ref` may carry rules that run when the player picks an entry:

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

Each rule has exactly one verb. The verb's value is the **target field** on the
character; every other key names a **property of the picked entry**.

| Rule | Target | What it does |
| --- | --- | --- |
| `{ "grant": "t", "from": "p" }` | `multiselect` | Adds the values in list property `p` |
| `{ "grant": "t", "ref": "p", "name": "q" }` | `content_list` | Adds the entry whose id is in `p`; if the catalog has no such entry, adds `q` as a freeform entry. Either key may be given alone |
| `{ "grant": "t", "from": "p", "names": "q", "carry": { … } }` | `content_list` | Adds several entries: `p` lists ids (a list, or comma-separated text), `q` the names to fall back to in the same order. `carry` copies properties of the pick onto the freeform entries it adds: `{ "species": "name" }` sets each trait's `species` to the picked species' `name` |
| `{ "choose": "t", "from": "p", "count": n, "label": "…" }` | `multiselect` | Asks the player to choose `count` values (1-20, or a property holding the number) from list property `p`. They can always put it off |

Everything a pick adds is remembered, so changing the pick takes it back off -
but only what it added, never something the player gave themselves. A rule may
not target its own field. Up to 20 rules per field.

Grimoire refuses to install a sheet whose rule reads a property its content type
does not declare, so a typo is caught at install rather than at the table.

## Simple layout

`layout` is a list of sections, drawn as titled cards in a responsive grid:

```json
"layout": [
  { "title": "Abilities", "fields": ["strength", "dexterity", "str_mod"] },
  { "title": "Spellcasting", "fields": ["spell_dc", "spells"], "visible_if": "casts_spells" }
]
```

A section takes `title`, `fields` (field and computed names, or
`{ "field": "name" }` objects) and `visible_if`. A computed value in a section
is drawn as a value the player can click to override. If no section names any
computed value, they are all drawn together in a **Derived** section at the end.

## Custom HTML layout

For a sheet that should follow its printed original, write an HTML template in
a sibling `<id>.html` file (or name it with `layout_file`). It is real HTML with
`g-` directives where the interactive parts go:

```html
<div class="sheet">
  <g-section title="Abilities" name="abilities">
    <div class="score">
      <g-label name="strength" />
      <g-field name="strength" label="" variant="compact" />
      <g-value name="str_mod" />
    </div>
  </g-section>
  <g-if test="level >= 4">
    <g-field name="feat" />
  </g-if>
</div>
```

### Directives

| Directive | Attributes | What it draws |
| --- | --- | --- |
| `<g-field>` | `name`, `label`, `placeholder`, `variant`, `readonly`, `visible_if` | The field's real control. `label=""` hides the label; `label="…"` replaces it. `variant="compact"` draws a number as a plain box without the browser's spinner - for a narrow cell. `readonly` shows it without editing |
| `<g-computed>` | `name`, `label`, `visible_if` | A calculated value with its label; the player can click it to override. `label=""` hides the label |
| `<g-value>` | `name` | A value alone, as plain text - any field or computed value. A computed value, or a `text` or `number` field, can still be clicked to set |
| `<g-label>` | `name`, `text` | A field's label alone, or `text` in its place |
| `<g-section>` | `title`, `name`, `visible_if` | A `<section class="gc-section">` with an optional `<h3>` title. `name` becomes `data-section="…"`, a styling hook |
| `<g-if>` | `test` | Its contents, while the formula is true |
| `<g-repeat>` | `over` | Its contents once per row of a `list` field. Inside, `<g-field name="qty">` is **that row's** `qty` cell, and formulas see the row's columns and `_index` |
| `<g-tabs>`, `<g-tab>` | `<g-tab title visible_if>` | Pages - the second page of a printed sheet. Only the chosen tab is drawn |
| `<g-option>` | `field`, `value`, `label` | One checkbox for one option of multiselect `field`, so each box can sit where the printed sheet puts it - a proficiency dot beside its skill |
| `<g-tier>` | `value`, `fields`, `labels`, `titles`, `label` | One dropdown for which rung of a ladder of multiselects holds `value`. `fields` lists the multiselects lowest rung first (`"skill_profs skill_expertise"`); `labels` is the short text shown closed and `titles` the full names in the list, both `\|`-separated, one more than the fields (the first is "none"). Choosing a rung adds `value` to every list up to it and removes it above |
| `<g-pips>` | `count`, `value`, `label` | `count` boxes - a number, or a field or computed name - with the first `value` ticked, `value` naming a `number` field. Ticking one uses everything up to it. Spell slots, stress, a feature's uses |

A layout naming a field or computed value the sheet does not declare is refused
at install. A field with its own `visible_if` honours it wherever it is drawn,
so the condition need not be repeated in the layout.

Keep each cell of a repeated row in its own element (`<span class="…">`), so a
row keeps its columns even if one cell draws nothing.

### Tags and attributes

**Allowed tags:** `div`, `span`, `section`, `article`, `header`, `footer`,
`aside`, `main`, `h1`-`h6`, `p`, `br`, `hr`, `small`, `strong`, `em`, `b`, `i`,
`u`, `s`, `ul`, `ol`, `li`, `dl`, `dt`, `dd`, `table`, `thead`, `tbody`,
`tfoot`, `tr`, `td`, `th`, `caption`, `figure`, `figcaption`, `img`, `fieldset`,
`legend`, `label`, `details`, `summary`, and the directives above.

**Allowed attributes:** `class`, `id`, `title`, `role` and `aria-label` on any
tag, plus:

| Tag | Also takes |
| --- | --- |
| `img` | `src`, `alt`, `width`, `height`, `loading` |
| `td` | `colspan`, `rowspan` |
| `th` | `colspan`, `rowspan`, `scope` |
| `label` | `for` |
| `details` | `open` |

**Refused:** `script`, `style`, `iframe`, `object`, `embed`, `svg`, `math`,
`template`, `form` and every form control (`input`, `select`, `textarea`,
`button`, `option`) - the directives draw real controls for you, which is what
stops a sheet forging one that looks like part of the app. Also refused: every
`on*` event attribute, the `style` attribute (use the stylesheet), and any
`src` or `href` that is not relative or `https:`.

## Stylesheet

Put the CSS in a sibling `<id>.css` file (or name it with `styles_file`).

**Every selector is scoped to the sheet.** `.score` becomes
`.<sheet-scope> .score`, so a sheet cannot restyle the app around it. `:root`,
`html` and `body` become the sheet's own root, so `:root { --ink: #222 }`
declares sheet-wide variables as you would expect, and a selector starting `&`
attaches to the root: `&.dark` matches the sheet's root element.

**At-rules:** `@media`, `@supports`, `@container` and `@layer` only.
`@import`, `@font-face` and `@keyframes` are refused - one loads a file, one a
font over the network, one animates.

**Values:** `url(…)` is refused wherever it appears - an image belongs in an
`<img src>`. So are `expression(…)`, `javascript:` and `-moz-binding`.

**Properties:** custom properties (`--anything`) are always allowed. Otherwise
only these:

| Group | Properties |
| --- | --- |
| Layout | `display`, `flex`, `flex-direction`, `flex-wrap`, `flex-grow`, `flex-shrink`, `flex-basis`, `gap`, `row-gap`, `column-gap`, `grid`, `grid-template`, `grid-template-columns`, `grid-template-rows`, `grid-template-areas`, `grid-area`, `grid-column`, `grid-row`, `grid-auto-flow`, `grid-auto-columns`, `grid-auto-rows`, `align-items`, `align-content`, `align-self`, `justify-items`, `justify-content`, `justify-self`, `place-items`, `place-content`, `place-self`, `order` |
| Box | `margin` and `margin-*`, `padding` and `padding-*`, `width`, `min-width`, `max-width`, `height`, `min-height`, `max-height`, `box-sizing`, `overflow`, `overflow-x`, `overflow-y`, `aspect-ratio` |
| Borders and surfaces | `border`, `border-top`, `border-right`, `border-bottom`, `border-left`, `border-width`, `border-style`, `border-color`, `border-radius` and its four corners, `border-collapse`, `border-spacing`, `background`, `background-color`, `box-shadow`, `outline`, `outline-offset`, `opacity` |
| Type | `color`, `font`, `font-family`, `font-size`, `font-weight`, `font-style`, `font-variant`, `font-stretch`, `line-height`, `letter-spacing`, `word-spacing`, `text-align`, `text-decoration`, `text-transform`, `text-indent`, `text-overflow`, `text-shadow`, `white-space`, `word-break`, `overflow-wrap`, `vertical-align`, `writing-mode`, `list-style`, `list-style-type`, `list-style-position` |
| Other | `visibility`, `cursor`, `table-layout`, `caption-side`, `object-fit`, `object-position` |

There is **no `position`** of any kind, no `transform`, no `z-index` and no
animation: those are how a stylesheet escapes its box or covers the page. Lay a
sheet out with grid and flex instead. Fonts are limited to what the reader's
device has, since a sheet cannot load one - name a fallback stack.

The app's theme tokens (`var(--gold)`, `var(--text)`, `var(--bg-card)`,
`var(--border)`) are in scope, and using them is what lets a sheet follow the
reader's light or dark theme.

## Limits

Far above any real sheet; they exist so a hostile document cannot exhaust the
server.

| | |
| --- | --- |
| Fields | 1000 |
| Computed values | 1500 |
| Validators | 200 |
| Content types | 50 |
| `list` columns / rows | 20 / 500 |
| `on_pick` rules per field | 20 |
| `choose` count | 1-20 |
| Layout HTML | 256 KiB, 8000 elements, 64 deep |
| Stylesheet | 128 KiB |
| Whole sheet document | 512 KiB |
