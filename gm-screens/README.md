# GM screen presets

Ready-made GM screens for Grimoire. A campaign's GM screen is a board of
Grimoire's built-in tools - a counter for Fear or Malice, countdowns and
clocks, token pools, an initiative tracker, the party at a glance, pinned notes
and a scratch note - placed on a twelve-column grid. A preset is one of those
boards set up for a game, so a GM starts from the trackers their system uses
instead of an empty page.

A GM applies one from **GM screen → Board → Community presets** in a campaign
they run. It changes that campaign's board and nothing else, so it needs no
admin approval.

Each preset is a directory named after its `id`, holding a single JSON file of
the same name:

```
gm-screens/
└── draw-steel/
    └── draw-steel.json   # required - the preset
```

Run `python3 scripts/build_index.py` after adding or editing one; CI checks
that `gm-screens/index.json` is current and validates every preset against
[`schema/gm-screen.schema.json`](../schema/gm-screen.schema.json).

## What a preset is

Data only. Every panel is one of Grimoire's built-in tools; a preset sets up
which ones, where they sit, and how each is configured. It carries no code and
no markup, and Grimoire checks and bounds every value again when it is applied.

```json
{
  "$schema": "../../schema/gm-screen.schema.json",
  "format": "grimoire://gm-screen/v1",
  "id": "my-game",
  "name": "My Game",
  "version": "1.0.0",
  "system": "My Game",
  "description": "Doom from 0 to 10 and a turn order where the sides alternate.",
  "author": "your-github-name",
  "grimoire_min_version": "1.11.0",
  "panels": [
    {
      "kind": "counter",
      "title": "Doom",
      "x": 0, "y": 0, "w": 3, "h": 3,
      "config": { "min": 0, "max": 10, "start": 0, "style": "pips", "resets": "session" }
    },
    {
      "kind": "initiative",
      "title": "Turns",
      "x": 3, "y": 0, "w": 4, "h": 8,
      "config": {
        "mode": "sides",
        "sides": [{ "key": "heroes", "label": "Heroes" }, { "key": "foes", "label": "Foes" }],
        "resets": "scene"
      }
    }
  ]
}
```

The easiest way to write one is to build the board in Grimoire, then
**Board → Export** it and add the catalogue fields (`id`, `version`, `system`,
`description`, `author`, and any licence) to the file it downloads.

## Panels

`x`, `y`, `w` and `h` place a panel in grid cells; the grid is twelve columns
wide, so `x + w` must be 12 or less, and panels may not overlap. `resets` is
when a tool clears - `"scene"`, `"session"`, `"rest"` or `""` for never - which
the GM triggers with **End scene**, **End session** and **Rest**.

| `kind` | `config` | `state` (optional starting contents) |
| --- | --- | --- |
| `counter` | `min`, `max` (`null` for no limit), `start`, `style` (`number` or `pips`), `resets` | `value` |
| `clocks` | `mode`: `countdown` (shows boxes left) or `clock` (boxes filled) | `items`: `{name, size, ticks, note, resets, loops}` |
| `pools` | `resets` - a pool's tokens go to 0, the pools stay | `items`: `{name, tokens, note}` |
| `initiative` | `mode`: `ordered` (by score) or `sides` (sides take turns, each combatant ticked once it has acted); `sides`: 2-4 `{key, label}`; `resets` | - |
| `party` | `stats`: `{label, value, max, style}` - `value` and `max` name fields or computed values of the system's character sheet; `include_inactive` | - |
| `note` | `page_slug` - the campaign note to pin, by its name | - |
| `scratch` | - | - |

A `party` panel reads the character sheet the table uses, so name fields from a
sheet in [`character-sheets/`](../character-sheets/) - the Draw Steel preset
reads `stamina_current` out of `stamina_max` from the Draw Steel sheet. Leave
`stats` empty when there is no sheet for the game yet; the GM picks them.

Credit the game the way its licence asks, in `license`, `license_url` and
`attribution`, as character sheets do.
