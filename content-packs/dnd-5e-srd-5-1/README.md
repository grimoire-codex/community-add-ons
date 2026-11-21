# D&D 5e SRD 5.1

Content for the [`dnd-5e-2014`](../../character-sheets/dnd-5e-2014/) sheet, from the
System Reference Document 5.1 - the open subset of the original 2014 rules:

| File | Entries | What it holds |
| --- | --- | --- |
| `class.json` | 12 | Hit die, saving throws, armor, weapon and tool proficiencies, skill choices, spellcasting, level 1 features |
| `subclass.json` | 12 | One per class, as the SRD has them, with the features they grant when chosen |
| `feature.json` | 216 | Every class and subclass feature by level, the 32 eldritch invocations, and the Acolyte's feature, filed under the class Background |
| `race.json` | 9 | Size, speed, ability score increases, languages, skill proficiencies |
| `subrace.json` | 4 | Hill Dwarf, High Elf, Lightfoot and Rock Gnome |
| `trait.json` | 34 | Racial and subracial traits |
| `background.json` | 1 | The Acolyte - the SRD's only background |
| `feat.json` | 1 | Grappler - the SRD's only feat |
| `spell.json` | 319 | Every spell, with the class lists the SRD prints |
| `item.json` | 232 | Weapons, armor, adventuring gear, tools, packs, mounts, vehicles and poisons |
| `magic_item.json` | 275 | Magic items |
| `condition.json` | 15 | The conditions of Appendix PH-A, exhaustion with its levels |
| `rule.json` | 282 | The SRD's rules a section each - abilities, combat, spellcasting, adventuring, equipment, traps, diseases, madness, the planes and pantheons, how to read a stat block - filed under the part they come from |
| `monster.json` | 317 | Every monster, miscellaneous creature and NPC stat block, header fields and all, with its traits, actions, reactions and legendary actions as text |

Conditions, rules and monsters are reference material: no character picks one,
so the sheet does not declare them. The pack declares the three types itself in
`_meta.json` (`content_types`), and Grimoire shows them in a system's Compendium
tab once the pack is linked to the system.

## Where it comes from

`scripts/srd-5e-2014/import_open5e.py` builds every file from two sources:

- [Open5e](https://github.com/open5e/open5e-api)'s SRD 5.1 fixtures give the pack its
  structure - which features a class has and at what level, which traits a race has,
  which items are magic.
- The SRD itself ([SRD_CC_v5.1.pdf](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf),
  read by `scripts/srd-5e-2014/srd_text.py`) has the last word on everything else.

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/open5e/open5e-api.git
cd open5e-api && git sparse-checkout set data/v2/wizards-of-the-coast
curl -LO https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf
# then, from this repository (needs pymupdf)
python3 scripts/srd-5e-2014/import_open5e.py \
    /path/to/open5e-api/data/v2/wizards-of-the-coast/srd-2014 /path/to/SRD_CC_v5.1.pdf
python3 scripts/build_index.py
```

Open5e's copy disagrees with the SRD in ways that matter, so the SRD wins:

- **Spell lists.** Open5e folds subclass bonus spells into the class lists and leaves
  the Paladin off every spell. The lists here are the SRD's "Spell Lists".
- **Spell headers.** Open5e drops the area from a range of Self ("Self (15-foot
  cone)") and the trigger from a reaction's casting time. Headers here are the SRD's.
- **Equipment.** Open5e prices single arrows, adds gear the SRD does not have and
  writes descriptions of its own ("For drinking."). Equipment here is the SRD's
  tables - names, prices and weights - with its own notes, container capacities and
  poisons.
- **Magic items.** Type, rarity and attunement come from each item's SRD heading
  (Open5e has the Staff of the Python as very rare; it is uncommon). The +1, +2 and
  +3 armor, shields and ammunition Open5e lacks are added from the SRD's text.
- **Wording.** Open5e drops dashes, lower-cases ability names and carries text from
  outside the SRD - its Bard College names the College of Valor, and its Metamagic
  cites *chromatic orb*. Every description is aligned word by word with the SRD and
  takes the SRD's words, keeping Open5e's paragraph breaks (the PDF has none). The
  importer lists anything it could not match; a regenerated pack should list nothing.
- **Grappler.** Open5e's second benefit is not the SRD's; the feat is written out
  from the SRD.
- **Monsters.** Each creature's header - size, type and tags ("humanoid
  (goblinoid)"), alignment, armor class, hit points, speed, ability scores,
  saves, skills, resistances, senses, languages, challenge and XP - is read from
  its stat block in the SRD. Its traits and actions are reworded against that
  stat block alone, so one creature's attack cannot take another's numbers, and
  each section is in the SRD's order, with the SRD's legendary action rules.
  Open5e adds stat blocks the SRD does not print (the Donkey, the diseased giant
  rat, each insect swarm variant as a creature of its own) and Monster Manual
  variants the SRD does not have (the erinyes' rope of entanglement, the
  ettercap's web garrote, the giant lizard's hold breath and spider climb, the
  satyr's panpipes); those are
  left out, as are its second copies of the Drow and the Deep Gnome.
- **Rules.** Open5e files a few sections under another section's name (the
  Standard Exchange Rates table as "Training"); they take the SRD's headings.
  Its "Sage Advice" quotes are not SRD text and are dropped; the SRD's own
  sidebars are kept as paragraphs.

Open5e splits a few items into one entry per variant - each Ioun Stone, Figurine of
Wondrous Power and Belt of Giant Strength. Those stay split, since a character owns
one figurine rather than the set, and each takes its type and attunement from the
SRD entry it belongs to.

Two things neither source holds as data are written into the importer: each class's
spellcasting ability, caster type and how it prepares spells, and the hit points a
level that Dwarven Toughness and Draconic Resilience add. The class summaries are
one-line descriptions written for this pack; the SRD has no class introductions.

## Licence

The SRD 5.1 is published under **CC BY 4.0**. Its required attribution, reproduced
character for character from the SRD's Legal Information page in `attribution`:

> This work includes material taken from the System Reference Document 5.1 ("SRD 5.1")
> by Wizards of the Coast LLC and available at
> https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is
> licensed under the Creative Commons Attribution 4.0 International License available
> at https://creativecommons.org/licenses/by/4.0/legalcode.

Nothing here comes from outside the SRD: the Player's Handbook's other races,
backgrounds, feats and subclasses are not open content, even where the SRD's own
text mentions them by name.
