# Note template reference

A **note template** is a starting point for a campaign wiki page. Unlike a
scraper it fetches nothing and runs nothing — it is a markdown file Grimoire
copies into a campaign wiki as a new page.

```
templates/<system>/my-template/
├── my-template.yml   # required — the manifest
├── my-template.md    # required — the page body
└── README.md         # optional
```

Templates are filed under a folder per game system (`templates/dnd-5e/`,
`templates/draw-steel/`). Those folders are organisation for people reading the
repo — the index records the full path, and Grimoire groups the browser by the
manifest's `system` and `category`, never by directory. A template inside
`dnd-5e/` still has to declare `system: D&D 5e`. Use a new folder for a system
that doesn't have one yet.

Both files are validated by [`schema/addon.schema.json`](../schema/addon.schema.json)
and digested into `index.json` by CI.

## The manifest

```yaml
id: 5e-spell              # lowercase, hyphenated; must match the directory name
name: Spell               # display name in the template browser
version: 1.0.0            # semver — bump on every change
kind: note-template
system: D&D 5e            # omit for a system-agnostic template
category: Spells          # groups the template in the browser
description: One line, shown under the name.
grimoire_min_version: 1.5.6
```

`kind: note-template` is what distinguishes this from a scraper. The
scraper-only keys (`source`, `script`, `records`, `detail`, `search`, `map`,
`target`) are rejected on a template, and `system` / `category` / `body` are
rejected on a scraper.

| Key | Required | Notes |
| --- | --- | --- |
| `id` | yes | Must match the directory name |
| `name` | yes | Shown in the browser |
| `version` | yes | Semver; bump on every change so installs detect updates |
| `kind` | yes | Always `note-template` |
| `system` | no | Free text, e.g. `D&D 5e`. Omit for system-agnostic |
| `category` | no | Groups templates in the browser. Defaults to `General` |
| `description` | no | One line |
| `body` | no | Markdown filename. Defaults to `<id>.md` |
| `grimoire_min_version` | no | Minimum Grimoire version |

### Categories

Use an existing category where one fits, so the browser doesn't sprout a group
per template: **Characters**, **Items**, **Spells**, **Encounters**,
**Locations**, **Factions**, **Sessions**, **General**.

## The body

The markdown file is exactly what Grimoire's wiki import already understands:
optional YAML frontmatter, then the page body.

```markdown
---
title: Spell
icon: sparkles
visibility: group
---

*2nd-level transmutation*

**Casting Time:** 1 action
```

Recognised frontmatter keys are `title`, `icon`, `icon_color`, `visibility`,
and `page_type`. Everything else is ignored.

- **`title`** — the page's starting name. The GM renames it after importing, and
  Grimoire makes the slug unique, so a plain noun (`Spell`, `NPC`) beats a
  placeholder like `NPC — {{name}}`.
- **`icon`** — a Grimoire campaign icon name (`sparkles`, `user`, `gem`,
  `swords`, `scroll`, …). An unknown name falls back to the default page icon.
- **`visibility`** — `gm` (default), `group`, or `members`. Prefer `gm` for
  anything with secrets in it, `group` for player-facing reference.

### Writing a good body

- **Structure, not content.** The value is the headings and tables a GM fills
  in. One worked example (as in the 5e spell) shows the intended shape; a wall
  of prose does not.
- **Leave the blanks blank.** An empty table cell or a bare `- ` reads as
  "fill me in". Lorem ipsum reads as something to delete.
- **No copyrighted text.** Structure and field names are fine; do not paste
  rules text or statblocks out of a published book.
- **Link back with an embed placeholder.** End with
  `*Source: [[book:BOOK-ID:PAGE]]*` — the GM swaps in a real book id from their
  own library, and Grimoire renders it as a page-anchored book link.

## Contributing

1. Create `templates/<system>/<id>/` with the manifest and markdown file.
2. Add a row to [`templates/README.md`](../templates/README.md).
3. Open a PR. CI validates the manifest and regenerates `index.json` — don't
   hand-edit it.
