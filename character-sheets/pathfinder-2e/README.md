# Pathfinder 2e

A character sheet for **Pathfinder Second Edition**, with a custom HTML layout.

Version 2 changes fields a version 1 character may have filled in: **heritage** and
**background** were free text and are now picks from the pack, and **skills** moved
from a table you filled in to the sixteen skills with a rank each. Re-enter them
after updating.

## What it covers

Four pages: **Character**, **Feats & Features**, **Spells** and **Gear & Notes**.

- **Proficiency ranks** that add your level only once you are trained - which
  is the thing most sheets get wrong. An untrained check stays flat as you
  level; a trained one scales.
- **Six attribute modifiers** (not scores), **Perception**, the **three saves**,
  **class DC** and **armor class**, each with its rank
- **The sixteen skills**, each with an untrained / trained / expert / master /
  legendary dropdown and its modifier worked out, plus two Lore skills
- **Hit points**, dying as boxes, wounded, doomed and hero points
- **Spellcasting**: spell DC and attack, spell slots by rank as boxes to tick,
  cantrips and focus points
- **Feats**, **class and ancestry features** and **spells** as lists whose rows
  open to their full text
- Strikes, conditions, equipment with **bulk** against a `5 + Strength` limit and
  a count of invested items, coins and notes

## With the Pathfinder Player Core pack

Install the [`pf2e-player-core`](../../content-packs/pf2e-player-core/) pack and
picks fill the sheet in:

| Pick | What it does |
| --- | --- |
| Ancestry | Adds its ancestry features; sets size, speed, senses and languages, and its hit points |
| Heritage | Warns if it belongs to a different ancestry |
| Background | Trains its skill (or asks which, where there is a choice); adds its skill feat; fills in its Lore |
| Class | Trains its skills and asks for the rest; adds its level 1 features; sets Perception, saves, armor proficiency, key attribute, hit points a level and spellcasting |

Maximum hit points are the ancestry's hit points plus, for every level, the
class's hit points plus your Constitution modifier. A caster's spell slots follow
the full-caster table: two of a new rank when you first reach it, three from the
next level, and one 10th-rank slot at 19th.

**Every value can be set by hand.** A value filled in from a pick shows a link
marker; type over it and it is yours, and the marker resets it. Nothing needs the
pack - with no content installed, every field is a plain field and every list
takes custom entries. Attribute boosts are yours to apply: the sheet records the
resulting modifiers, and warns if one is above +4 at 1st level.

inst a `5 + Strength` limit, and a count of
  invested items
- Catalogues of classes, ancestries, feats and spells, with spell **ranks**
  rather than levels

Ability fields hold **modifiers**, not scores, which is how PF2e character
sheets are normally filled in.

## Licence

Pathfinder Second Edition's rules are available under the **ORC License**.

The credit Grimoire displays, reproduced in `attribution`:

> This product is based on the Pathfinder Second Edition rules, published by
> Paizo Inc. under the ORC License. Pathfinder is a trademark of Paizo Inc.
> See https://paizo.com/orclicense.

- Licence: <https://paizo.com/orclicense>

This sheet reproduces the structure of a character, not the text of the rules,
and includes no artwork. The rules text is in the pack, which carries Paizo's full
ORC attribution for Player Core.
