# D&D 5e SRD 5.2

Content for the [`dnd-5e-2024`](../../character-sheets/dnd-5e-2024/) sheet, from the
System Reference Document 5.2 - the open subset of the 2024 rules:

| File | Entries | What it holds |
| --- | --- | --- |
| `class.json` | 12 | The twelve classes, with their level 1 features |
| `subclass.json` | 12 | One per class, as the SRD has them, with the features they grant when chosen |
| `feature.json` | 221 | Every class and subclass feature by level |
| `species.json` | 9 | The SRD's species |
| `trait.json` | 33 | Their traits |
| `background.json` | 4 | Acolyte, Criminal, Sage and Soldier |
| `feat.json` | 17 | The SRD's feats |
| `spell.json` | 339 | Every spell |
| `item.json` | 198 | Weapons, armor, adventuring gear, tools, mounts and vehicles |
| `magic_item.json` | 276 | Magic items |
| `condition.json` | 15 | The conditions |
| `rule.json` | 207 | The Rules Glossary (140 entries; its conditions are in `condition.json`), and the Playing the Game and Character Creation chapters a section each |
| `monster.json` | 331 | Every stat block in Monsters A-Z and Animals, and the Giant Fly the Figurine of Wondrous Power becomes: header fields and all, with traits, actions, bonus actions, reactions and legendary actions as text |

Conditions, rules and monsters are reference material: no character picks one,
so the sheet does not declare them. The pack declares the three types itself in
`_meta.json` (`content_types`), and Grimoire shows them in a system's Compendium
tab once the pack is linked to the system. A glossary entry keeps its tag
(Action, Area of Effect, Attitude, Hazard) in `tag`.

## Where it comes from

`scripts/srd-5e/import_open5e.py` converts
[Open5e](https://github.com/open5e/open5e-api)'s SRD 5.2 fixtures: spells, class
and subclass features, subclasses, equipment and magic items, and the
conditions, rules and monsters. The species, backgrounds, feats and their traits
are hand-checked against the SRD's lists and left alone.

```bash
git clone --depth 1 https://github.com/open5e/open5e-api.git
# then, from this repository (needs pymupdf)
python3 scripts/srd-5e/import_open5e.py \
    /path/to/open5e-api/data/v2/wizards-of-the-coast/srd-2024
python3 scripts/build_index.py
```

The conditions, rules and monsters are checked against the SRD 5.2.1 itself,
which Open5e keeps beside its fixtures (`data/raw_sources/srd_5_2/SRD_CC_v5.2.1.pdf`,
read by `scripts/srd-5e/srd52.py`):

- **Monster headers** - size, type and tags, alignment, armor class, initiative,
  hit points, speed, ability scores and saves, skills, resistances, immunities,
  gear, senses, languages, challenge, XP and proficiency bonus - come from each
  stat block. Open5e files every Tiny creature as Small and drops the tags
  ("Dragon (Chromatic)").
- **Wording.** Every condition, rule and stat block entry is aligned word by word
  with the SRD and takes its words: Open5e drops each attack's "Hit:", leaves
  markup in the text ("Sphere [Area of Effect]") and shortens spell lists
  ("Plane Shift" for "Plane Shift (self only)"). An entry Open5e has wrong is
  taken from the stat block whole (the bandit captain's Parry is the 2014
  wording in Open5e). The importer lists anything it could not match.
- **Rules Glossary.** Open5e has no glossary among its fixtures. Its entries
  come from the markdown the fixtures were first imported from
  (`data/raw_sources/srd_5_2/sections/09_rules_glossary.md`), which gives each
  entry's paragraphs and tables, reworded against the SRD like everything else.

A few rules paragraphs that the PDF prints around a page break or a sidebar
cannot be matched, and keep Open5e's wording; the importer lists them.

## Licence

The SRD 5.2 is published under **CC BY 4.0**. Its required attribution is in
`_meta.json`'s `attribution`, reproduced from the SRD's Legal Information page.

Nothing here comes from outside the SRD: the Player's Handbook's other species,
backgrounds, feats and subclasses, and the Monster Manual's other creatures, are
not open content. Grimoire's test suite checks the species, backgrounds and
feats against the SRD's lists.
