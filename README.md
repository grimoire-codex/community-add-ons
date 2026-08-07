# Grimoire Community Add-ons

Community-maintained add-ons for [Grimoire](https://github.com/hunter-read/grimoire),
the self-hosted TTRPG library manager.

This is the single home for everything the community contributes to Grimoire.
Today that means **scrapers** and **note templates**; the layout leaves room for
plugins and character-sheet modules as those land.

| Directory | What lives there |
| --- | --- |
| [`scrapers/`](scrapers/) | Metadata scrapers — look a game system up on an external source and pre-fill its fields |
| [`templates/`](templates/) | Note templates — ready-made starting points for campaign wiki pages |
| [`plugins/`](plugins/) | Reserved for future add-on kinds |
| [`schema/`](schema/) | JSON Schemas that every add-on and the index are validated against |
| [`docs/`](docs/) | Authoring reference |

## Installing an add-on

In Grimoire, go to **Settings → Metadata → Add-ons**. Grimoire reads
[`index.json`](index.json) from this repo, lists what's available, and installs
the ones you pick. Use **Refresh** to pull the latest index.

To install by hand — or to run a private add-on you don't want to publish —
drop its directory into `DATA_PATH/add-ons/<id>/` and restart Grimoire.

### A note on add-ons that run scripts

Most add-ons are plain YAML: they describe *where* the data is and *how* to map
it onto Grimoire's fields. Grimoire interprets that itself, and no third-party
code ever executes.

Some sources need more than YAML can express, so an add-on may ship a Python
script. **Those run code on your server.** Grimoire will not run one unless you
both enable *Allow add-on scripts* globally and approve that specific add-on when
you install it. Install script-backed add-ons only from sources you trust, and
read the script first — that's why they live here in the open.

See [`docs/scripts.md`](docs/scripts.md) for the security model.

## Available add-ons

### Scrapers

| Add-on | Target | Scripts? | Description |
| --- | --- | --- | --- |
| [TTRPG Wiki](scrapers/ttrpg-wiki/) | game system | No | System metadata from [ttrpgwiki.com](https://ttrpgwiki.com) |
| [DriveThruRPG](scrapers/drivethrurpg/) | book | No | Book metadata from [drivethrurpg.com](https://www.drivethrurpg.com) |

### Note templates

Starting points for campaign wiki pages — see [`templates/`](templates/) for the
full list.

| Add-on | System | Category |
| --- | --- | --- |
| [NPC](templates/dnd-5e/5e-npc/) | D&D 5e | Characters |
| [Magic Item](templates/dnd-5e/5e-magic-item/) | D&D 5e | Items |
| [Spell](templates/dnd-5e/5e-spell/) | D&D 5e | Spells |
| [Encounter](templates/draw-steel/ds-encounter/) | Draw Steel | Encounters |
| [Montage Test](templates/draw-steel/ds-montage-test/) | Draw Steel | Encounters |
| [Negotiation](templates/draw-steel/ds-negotiation/) | Draw Steel | Encounters |

Note templates fetch nothing and run nothing — they are markdown files Grimoire
copies into a campaign wiki, so they carry none of the trust considerations a
scraper does.

## Contributing

1. Read the authoring reference for what you're adding —
   [`docs/format.md`](docs/format.md) for scrapers,
   [`docs/note-templates.md`](docs/note-templates.md) for note templates.
2. Add your add-on under the right directory, in its own folder named after its
   `id` (e.g. `scrapers/my-source/my-source.yml`,
   `templates/<system>/my-template/my-template.yml`).
3. Open a PR. CI validates every add-on against
   [`schema/addon.schema.json`](schema/addon.schema.json) and regenerates
   `index.json`, so **don't hand-edit `index.json`** — it's a build artifact.

### What makes a good scraper

- **Respect the source.** Check its `robots.txt` and terms. Set a realistic
  `cache_ttl` so Grimoire installs aren't hammering someone's server, and
  prefer a bulk/structured endpoint over scraping rendered pages when one exists.
- **Attribute it.** Fill in `attribution` and `homepage`.
- **Map conservatively.** Only map fields you're confident about. Grimoire shows
  the user a diff before anything is written, but a wrong mapping is still noise.
- **Don't map what you can't source.** Leaving a field unmapped is better than
  guessing at it.

## Licence

Add-ons in this repo are MIT-licensed unless their own directory says otherwise.
The *data* each scraper fetches belongs to its respective source and is subject
to that source's terms — a scraper definition grants you no rights to it.
