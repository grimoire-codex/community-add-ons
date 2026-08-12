# Themes

Colour schemes for Grimoire. A user installs the ones they want from
**Settings → Appearance** and picks one for their own account — a theme never
changes what anyone else sees, so it needs no admin approval.

Each theme is a directory named after its `id`, holding a single JSON file of
the same name:

```
themes/
└── high-contrast/
    ├── high-contrast.json   # required — the theme
    └── README.md            # optional
```

Run `python3 scripts/build_index.py` after adding or editing one; CI checks that
`themes/index.json` is current.

## What a theme is

A map of colour tokens overriding Grimoire's palette:

```json
{
  "id": "midnight",
  "name": "Midnight",
  "version": "1.0.0",
  "mode": "dark",
  "author": "you",
  "description": "One sentence about the look.",
  "tokens": {
    "bg-deep": "#000000",
    "text": "#ffffff",
    "accent": "#ffd54a"
  }
}
```

`mode` is the built-in palette yours is a variation of — `light` or `dark`.
Every token is optional and anything you leave out falls back to that palette,
so a theme can be three colours or all of them.

## Pairing light and dark

A theme can ship both palettes in one file, so it appears once in the picker and
**System** mode works with it:

```json
{
  "id": "midnight",
  "name": "Midnight",
  "version": "1.0.0",
  "mode": "dark",
  "variants": {
    "dark":  { "bg-deep": "#000000", "text": "#ffffff" },
    "light": { "bg-deep": "#ffffff", "text": "#000000" }
  }
}
```

`variants` replaces `tokens` when present; `mode` then names the primary one,
used when the app cannot tell which to prefer. Shipping only one mode is still
fine — it just applies in both, rather than switching itself off.

`app_mode` is optional and says which side of the product the theme was made
for — `grimoire` (TTRPG, the default) or `codex` (wargaming). It is a preference
the picker sorts by, not a restriction: a theme that reads well is usable in
either, so set it only if your palette is genuinely tuned to one.

## Tokens

Surfaces, in back-to-front order: `bg-deep` (the page), `bg-panel`, `bg-card`,
`bg-card-hover`, `bg-input`.

Lines: `border`, `border-light`.

Accent (Grimoire's gold): `accent`, `accent-dim`, `accent-bright`, `accent-alt`,
plus `on-accent` for text drawn *on* an accent fill. `on-accent` is dark in both
built-in palettes, because the accent is light in both.

Text: `text`, `text-dim`, `text-muted`.

Status: `danger`, `warning`, `success`, and the older `red` / `green` / `blue`.
`danger-fill` and `on-danger` are the plate and label of a destructive button.

Content types, which must stay distinguishable from each other: `type-book`,
`type-map`, `type-token`, `type-audio`, `type-file`.

Over artwork: `on-media` and `on-media-border` sit on `scrim` / `scrim-strong`.
These stay light-on-dark in both modes, because the page theme says nothing
about what a user's cover image looks like underneath.

Everything else: `tag-bg`, `tag-border`, `mark-bg` (search highlight),
`invite-bg`, `overlay`, `shadow`.

## Rules

Values must be a plain colour — hex, `rgb()`/`rgba()`, `hsl()`/`hsla()`, or
`transparent`/`currentcolor`/`inherit`. Grimoire drops anything else, and drops
token names it does not recognise, because these values go straight into a
stylesheet. A theme that sets nothing recognisable is refused rather than
installed as a silent no-op.

Check your contrast. Body text should clear 4.5:1 against every surface it can
land on, and `on-accent` against `accent`. `high-contrast` targets 7:1 (AAA)
throughout and is the worked example.

Note that a theme changes colour only. Conveying meaning without hue — for
colourblind users — needs icons and labels in the app itself, which a theme
cannot add.

## Available themes

| Theme | Mode | Description |
| --- | --- | --- |
| [High Contrast](high-contrast/) | light & dark | Pure black or pure white surfaces at full-strength contrast; every pairing clears WCAG AAA, and it follows System. |
