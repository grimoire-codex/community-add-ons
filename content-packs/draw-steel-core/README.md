# Draw Steel: Heroes

Content for the [`draw-steel`](../../character-sheets/draw-steel/) sheet - everything
a hero is built from in *Draw Steel: Heroes*:

| File | Entries | What it holds |
| --- | --- | --- |
| `class.json` | 9 | Stamina, recoveries, heroic resource, primary characteristics, skill choices, level 1 features |
| `subclass.json` | 25 | Each class's subclasses and their level 1 features |
| `ancestry.json` | 9 | Size, speed, ancestry points, signature traits |
| `trait.json` | 67 | Signature and purchased ancestry traits, with their point cost |
| `culture.json` | 16 | The three skill choices an environment, organisation and upbringing give |
| `career.json` | 18 | Skill choices, perks and languages, and inciting incidents |
| `kit.json` | 25 | Stamina, speed, stability, damage and distance bonuses, and kit abilities |
| `domain.json` | 12 | Domains for censors and conduits |
| `perk.json` | 47 | Perks, by type |
| `title.json` | 62 | Titles, by echelon |
| `complication.json` | 100 | Complications, benefit and drawback |
| `ability.json` | 553 | Every ability, with cost, keywords, distance, target and power-roll tiers |
| `feature.json` | 717 | Class, subclass and domain features, levels 1 to 10 |

## Where it comes from

[Forge Steel](https://forgesteel.net/) models Draw Steel as data. The pack is built
from its **core sourcebook only** - the one book covered by the Draw Steel Creator
License - by two scripts in [`scripts/forgesteel/`](../../scripts/forgesteel/):

```bash
# inside a Forge Steel checkout, after npm ci
npx tsx --tsconfig tsconfig.json /path/to/scripts/forgesteel/dump.ts /tmp/core.json
# then, from this repository
python3 scripts/forgesteel/import_forgesteel.py /tmp/core.json
python3 scripts/build_index.py
```

The importer turns each of Forge Steel's rule structures into the text a player
reads - a stamina bonus becomes "+9 Stamina per level", a choice lists its
options, an ability gets its three tiers - since the sheet records a hero rather
than building one.

## Licence

**Draw Steel Creator License.** The text is MCDM's published text for *Draw Steel:
Heroes*, and the credit the licence requires is reproduced verbatim wherever the
content appears.

- <https://www.mcdmproductions.com/draw-steel-creator-license>

Forge Steel is released under the GPL-3.0, but that covers its own code, not
MCDM's text. This pack is that text in Grimoire's own structure, written out by
our own scripts, so the Creator License is the licence that applies. Forge Steel
is credited as the source of the conversion.

**Text only.** The Creator License forbids artwork from MCDM books, screenshots of
pages or artwork, and the MCDM or *Draw Steel* logos, so none appear here.
