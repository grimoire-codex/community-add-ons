# D&D 5th Edition (2014)

A character sheet for the original 2014 rules of D&D 5th Edition, with a custom
HTML layout that follows the three pages of the printed sheet: the character,
their details, and their spellcasting.

On a phone the sheet has its own layout, `dnd-5e-2014.mobile.html` and
`.mobile.css`, with the same content in one column across seven tabs:
**Main** (hit points, hit dice, death saves, armor class, initiative, speed and
the six abilities with their saving throws - what play reaches for),
**Skills** (every skill with its proficiency dropdown, then proficiencies and
languages, then each ability's base, racial and improvement parts),
**Combat** (attacks, features and traits), **Spells** (casting stats, slots to
tick off and the spell list), **Gear**, **Story** (identity, portrait,
appearance, personality, backstory and allies) and **Notes**.

## What it covers

- **Abilities** built from a base score, the racial increase and later
  improvements - the racial increase fills in from your race and subrace (a
  half-elf's two free +1s are yours to place)
- **Saving throws** that add proficiency where your class gives it
- **Armor class, initiative, passive Perception and proficiency bonus**, all
  derived - proficiency scales `2 + floor((level - 1) / 4)`
- **Skill proficiency tiers** - none, half (Jack of All Trades), proficient, or
  expertise
- **Hit points** from your class's hit die and Constitution, with Dwarven
  Toughness and Draconic Resilience counted when you pick them
- **Spellcasting** that only appears for casters: the class (or a subclass, for a
  third caster) sets the ability, save DC, attack bonus and slots, and a
  prepared caster sees how many spells it can prepare. Warlocks get pact slots
- **Picking a race or subrace** adds its traits and skill proficiencies, and asks
  a half-elf for their two skills; **picking a class** asks for its skills and
  adds its level 1 features and armor proficiencies; **picking a subclass** adds
  the features it grants when chosen; **picking a background** adds its skills
  and feature. Weapons, tools and languages fill in from the same picks
- **The feature browser filters by class, then by where it came from** - pick a
  class (or Background) and the From filter lists its subclasses and the
  class itself
- **Equipment** picked from the catalogue or typed in, with a quantity, and
  carried weight against a `Strength × 15` capacity
- **Magic items**, with a quantity for a stack of potions or scrolls and a
  warning if more than three are attuned
- **Personality traits, ideals, bonds and flaws**, appearance and backstory
- **Your character's art, large** in the Character Appearance box - framed the
  way you chose (click it to choose)
- **Your organization's symbol** - a picture you add beside your allies and
  organizations, as on the printed sheet
- **Custom anything** - type a homebrew race, class, background or spell when
  the catalogue lacks it

## With the SRD 5.1 pack

The [`dnd-5e-srd-5-1`](../../content-packs/dnd-5e-srd-5-1/) pack carries the
SRD's classes, subclasses and every feature, its races, subraces and traits, the
Acolyte, the Grappler feat, all 319 spells, its equipment and its magic items.

## Licence

The SRD 5.1 is published under **CC BY 4.0**, which permits redistribution and
adaptation with attribution.

The credit Grimoire displays, reproduced in `attribution`:

> This work includes material taken from the System Reference Document 5.1 ("SRD 5.1")
> by Wizards of the Coast LLC and available at
> https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is
> licensed under the Creative Commons Attribution 4.0 International License available
> at https://creativecommons.org/licenses/by/4.0/legalcode.

- Licence: <https://creativecommons.org/licenses/by/4.0/>
- SRD: <https://dnd.wizards.com/resources/systems-reference-document>

This sheet reproduces the *structure* of a character, not the text of the rules.
No artwork or page scans are included; the layout follows the printed sheet's
arrangement but none of its art. A content pack carrying SRD entries themselves
is a separate download and carries the same notice.
