# Pathfinder Player Core

Content for the [`pathfinder-2e`](../../character-sheets/pathfinder-2e/) sheet, from
*Pathfinder Player Core* - the remastered core rulebook:

| File | Entries | What it holds |
| --- | --- | --- |
| `ancestry.json` | 8 | Hit points, size, speed, boosts and flaw, languages, senses |
| `heritage.json` | 49 | Heritages, with the ancestry each belongs to ("Versatile" for those that belong to none) |
| `background.json` | 40 | Boosts, trained skills, lore and skill feat |
| `class.json` | 8 | HP a level, key attribute, starting proficiencies, trained and additional skills, spell tradition, level 1 features |
| `feature.json` | 166 | Class features by level, and ancestry features |
| `feat.json` | 846 | Ancestry, class, general and skill feats, with actions, traits and prerequisites |
| `spell.json` | 489 | Spells and cantrips (rank 0), with traditions, casting, range, area, defense and heightening |

## Where it comes from

The [Pathfinder Second Edition system for Foundry VTT](https://github.com/foundryvtt/pf2e)
keeps Paizo's rules content as JSON, and records each item's book and licence. The
pack takes **Pathfinder Player Core only**, and only items marked ORC. Other books
are left out even when they are ORC too. So is anything Player Core refers to from
another book: the dwarf's Clan Dagger is from the OGL Core Rulebook, so it is not
here.

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/foundryvtt/pf2e.git
cd pf2e && git sparse-checkout set packs/pf2e/ancestries packs/pf2e/ancestry-features \
    packs/pf2e/heritages packs/pf2e/backgrounds packs/pf2e/classes \
    packs/pf2e/class-features packs/pf2e/feats packs/pf2e/spells
# then, from this repository
python3 scripts/foundry-pf2e/import_pf2e.py /path/to/pf2e
python3 scripts/build_index.py
```

Foundry's descriptions are HTML with its own inline macros. The importer turns
them into plain paragraphs: `@Damage[6d6[fire]]` becomes "6d6 fire",
`@Check[reflex|dc:20|basic]` becomes "DC 20 basic Reflex", and links to Foundry's
own rules pages are dropped.

## Rules text only

Paizo licenses Pathfinder's rules under ORC but keeps its world - deities, places,
planes, organisations - as Reserved Material. So the pack carries rules text only:

- An ancestry's or class's description is a summary of what it gives (hit points,
  boosts, languages, starting proficiencies), not the book's colour text.
- A background, heritage, feature or feat loses the colour sentences it opens with.
  The trim stops at the first sentence that states a rule, so a rule is never cut;
  some colour sharing a sentence with a rule survives.
- Any sentence, list item, table row or section naming the setting is dropped -
  Avatar keeps its battle form but not its per-deity forms - and the two feats
  named after it (First World Adept, First World Magic) are left out.

## Licence

**ORC License.** The pack's `attribution` carries the ORC notice and Paizo's
attribution for Player Core verbatim, and Grimoire shows it wherever the content
appears.

- <https://paizo.com/orclicense>

Pathfinder is a trademark of Paizo Inc., which is Reserved Material under the ORC
License; this pack is not published, endorsed, or specifically approved by Paizo.
Foundry's code is Apache-2.0; its artwork is not used. **Text only** - no art,
logos or page images.
