#!/usr/bin/env python3
"""Build the dnd-5e-srd-5-1 content pack from Open5e's SRD 5.1 fixtures.

    python3 scripts/srd-5e-2014/import_open5e.py \
        /path/to/open5e-api/data/v2/wizards-of-the-coast/srd-2014 /path/to/SRD_CC_v5.1.pdf

Open5e (github.com/open5e/open5e-api) keeps the System Reference Document 5.1
as Django fixtures, one JSON file per model, which give the pack its structure:
which features a class has and at what level, which traits a race has, which
items are magic. This reads them and writes every file in the pack - classes,
subclasses and their features, races, subraces and their traits, the
background, the feat, spells, equipment and magic items.

Everything written is SRD 5.1 text, under the CC BY 4.0 attribution the pack
carries, and the SRD itself (read by srd_text.py) has the last word: its class
spell lists, spell headers and equipment tables replace Open5e's, and every
description is reworded to the SRD's own text (see `Srd.reword`). Descriptions
the SRD cannot be matched to are kept as Open5e has them and listed at the end,
so a regenerated pack shows what it could not check. The Grappler feat is
written out here: Open5e's second benefit is not the SRD's.

The few things neither source states as data - each class's spellcasting, when
its subclass arrives, a one-line summary - are in CLASSES below.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

from srd_text import Srd

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACK = ROOT / "content-packs" / "dnd-5e-srd-5-1"

#: The SRD, loaded in main().
SRD: Srd

ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
SHORT_ABILITY = {a[:3]: a for a in ABILITIES}
SKILLS = [
    "Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception", "History", "Insight",
    "Intimidation", "Investigation", "Medicine", "Nature", "Perception", "Performance",
    "Persuasion", "Religion", "Sleight of Hand", "Stealth", "Survival",
]


def load(source: pathlib.Path, model: str) -> list[dict]:
    with open(source / f"{model}.json", encoding="utf-8") as handle:
        return json.load(handle)


def slug(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def short(pk: str) -> str:
    return pk.removeprefix("srd_")


def title(text: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[-\s]+", text or "") if word)


def plain(text: str | None, *, keep_marks: bool = False) -> str:
    """Markdown to the plain text a pack holds: paragraphs kept, markup gone.

    A table becomes one line per row, cells joined by " - ", which reads well
    enough in a sheet's entry view and keeps every value.
    """
    lines = []
    for line in (text or "").replace("\r", "").split("\n"):
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", cell) or not cell for cell in cells):
                continue
            line = TABLE_ROW + " - ".join(cell for cell in cells if cell)
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^\s*[-*]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", line)
        line = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", line)
        lines.append(line.rstrip())
    out = "\n".join(lines).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out if keep_marks else out.replace(TABLE_ROW, "")


#: Marks a line that was a table row, so `prose` leaves it as it is.
TABLE_ROW = "\x00"


def prose(name: str, markdown: str | None, *, required: bool = True) -> str:
    """An entry's text as plain text in the SRD's own words.

    Open5e's paragraphs and table rows give the shape; `Srd.reword` puts the
    SRD's wording into each paragraph. Text the SRD cannot be matched to is
    kept as Open5e has it, or with `required=False` dropped (for equipment,
    whose Open5e descriptions are partly its own).
    """
    text = plain(markdown, keep_marks=True)
    lines = text.split("\n")
    spots = [i for i, line in enumerate(lines) if line.strip()]
    bodies, keep, bullets = [], set(), {}
    for n, i in enumerate(spots):
        line = lines[i]
        if line.startswith(TABLE_ROW):
            keep.add(n)
            line = line[len(TABLE_ROW):]
        elif line.startswith("• "):
            bullets[n] = "• "
            line = line[2:]
        bodies.append(line)
    reworded = SRD.reword(name, bodies, keep, quiet=not required)
    if reworded is None:
        return text.replace(TABLE_ROW, "") if required else ""
    for n, i in enumerate(spots):
        lines[i] = bullets.get(n, "") + reworded[n]
    return "\n".join(lines)


def joined(names: list[str]) -> str:
    return ", ".join(names)


# --- classes -----------------------------------------------------------------

#: What the class tables say but Open5e does not hold as data. `subclass_level`
#: is when the class chooses its subclass; `prepares` is how many spells it
#: prepares - "full" for ability modifier + level, "half" for modifier + half
#: level, blank for a class that knows its spells instead.
CLASSES = {
    "barbarian": {
        "primary": "Strength", "subclass_level": 3,
        "blurb": "A primal warrior who channels fury into a battle rage.",
    },
    "bard": {
        "primary": "Charisma", "spellcasting": "charisma", "caster_type": "full", "subclass_level": 3,
        "blurb": "A performer whose words and music carry real magic.",
    },
    "cleric": {
        "primary": "Wisdom", "spellcasting": "wisdom", "caster_type": "full", "prepares": "full",
        "subclass_level": 1, "blurb": "A priest who wields divine magic on behalf of a god.",
    },
    "druid": {
        "primary": "Wisdom", "spellcasting": "wisdom", "caster_type": "full", "prepares": "full",
        "subclass_level": 2, "blurb": "A keeper of the old faith who draws on the power of nature.",
    },
    "fighter": {
        "primary": "Strength or Dexterity", "subclass_level": 3,
        "blurb": "A master of weapons and armour, trained in every form of combat.",
    },
    "monk": {
        "primary": "Dexterity and Wisdom", "subclass_level": 3,
        "blurb": "A martial artist who harnesses ki through discipline of body and mind.",
    },
    "paladin": {
        "primary": "Strength and Charisma", "spellcasting": "charisma", "caster_type": "half",
        "prepares": "half", "subclass_level": 3, "blurb": "A holy warrior bound by a sacred oath.",
    },
    "ranger": {
        "primary": "Dexterity and Wisdom", "spellcasting": "wisdom", "caster_type": "half",
        "subclass_level": 3, "blurb": "A hunter and tracker at home in the wilds.",
    },
    "rogue": {
        "primary": "Dexterity", "subclass_level": 3,
        "blurb": "A scoundrel who relies on stealth, skill and a well-placed strike.",
    },
    "sorcerer": {
        "primary": "Charisma", "spellcasting": "charisma", "caster_type": "full",
        "subclass_level": 1, "blurb": "A spellcaster whose magic is an inborn gift.",
    },
    "warlock": {
        "primary": "Charisma", "spellcasting": "charisma", "caster_type": "pact",
        "subclass_level": 1, "blurb": "A wielder of magic granted by a pact with an otherworldly patron.",
    },
    "wizard": {
        "primary": "Intelligence", "spellcasting": "intelligence", "caster_type": "full",
        "prepares": "full", "subclass_level": 2,
        "blurb": "A scholar of the arcane who learns spells from a spellbook.",
    },
}

#: Open5e also stores each class table's columns as features ("Rages", "Ki
#: Points") with "[Column data]" for text. Those are the table, not features a
#: character has, so they are skipped.
COLUMN = "[Column data]"


def proficiencies(desc: str) -> dict:
    """The class's "Proficiencies" block, as the properties a pick grants."""
    fields = dict(re.findall(r"\*\*(\w[\w ]*):\*\*\s*(.+)", desc))
    armour_text = fields.get("Armor", "None").lower()
    armour = []
    if "all armor" in armour_text:
        armour = ["Light", "Medium", "Heavy"]
    else:
        armour = [kind.capitalize() for kind in ("light", "medium", "heavy") if f"{kind} armor" in armour_text]
    if "shield" in armour_text:
        armour.append("Shields")
    skills_text = fields.get("Skills", "")
    count = re.search(r"[Cc]hoose (?:any )?(\w+)", skills_text)
    words = {"one": 1, "two": 2, "three": 3, "four": 4}
    options = [s for s in SKILLS if s in skills_text] if "from" in skills_text else list(SKILLS)
    return {
        "armor_text": fields.get("Armor", "None").strip(),
        "armor_training": armour,
        "weapon_proficiencies": "" if fields.get("Weapons", "None").strip() == "None" else fields["Weapons"].strip(),
        "tool_proficiencies": "" if fields.get("Tools", "None").strip() == "None" else fields["Tools"].strip(),
        "skills_text": skills_text.strip(),
        "skill_choices": words.get(count.group(1).lower(), 0) if count else 0,
        "skill_options": options,
    }


def class_entries(source: pathlib.Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Classes, subclasses, and every class and subclass feature."""
    rows = load(source, "CharacterClass")
    by_pk = {row["pk"]: row["fields"] for row in rows}
    levels: dict[str, list[int]] = collections.defaultdict(list)
    for item in load(source, "ClassFeatureItem"):
        levels[item["fields"]["parent"]].append(item["fields"]["level"])

    features, by_owner, special = [], collections.defaultdict(list), collections.defaultdict(dict)
    for row in load(source, "ClassFeature"):
        f = row["fields"]
        kind = f.get("feature_type")
        owner_pk = f["parent"]
        if kind in ("PROFICIENCIES", "STARTING_EQUIPMENT"):
            special[owner_pk][kind] = f["desc"]
            continue
        if kind == "CLASS_FEATURE_OPTION_LIST":
            special[owner_pk]["options"] = (f["name"], f["desc"])
            continue
        if kind or f["desc"].strip() == COLUMN:
            continue
        # Open5e gives the Druid's Timeless Body no level; its text has one.
        stated = re.search(r"(?:At|Starting at|Beginning at|When you reach) (\d+)\w\w level", f["desc"])
        level = min(levels[row["pk"]]) if levels.get(row["pk"]) else int(stated.group(1)) if stated else None
        if level is None:
            continue
        owner = by_pk[owner_pk]
        parent = by_pk[owner["subclass_of"]] if owner["subclass_of"] else owner
        name = f["name"].removesuffix(" (table)")
        entry = {
            "_id": slug(f"{owner['name']} {name}"),
            "name": name,
            "origin": owner["name"],
            "class": parent["name"],
            "level": level,
            "description": prose(f"{owner['name']}: {name}", f["desc"]),
        }
        features.append(entry)
        by_owner[owner_pk].append(entry)

    # The Warlock's eldritch invocations are one long feature in Open5e; each is
    # its own pick on a sheet, so each becomes an entry.
    for owner_pk, data in special.items():
        if "options" not in data:
            continue
        owner = by_pk[owner_pk]
        for name, body in re.findall(r"### (.+?)\r?\n(.*?)(?=\r?\n### |\Z)", data["options"][1], re.DOTALL):
            # Open5e lost the heading of one invocation into the text before it.
            stray = re.search(r"\r?\n([A-Z][\w' ]+)\r?\n\r?\n", body)
            pieces = [(name.strip(), body)]
            if stray and not stray.group(1).startswith("Prerequisite"):
                pieces = [
                    (name.strip(), body[: stray.start()]),
                    (stray.group(1).strip(), body[stray.end() :]),
                ]
            for piece_name, piece_body in pieces:
                level = re.search(r"Prerequisite: (\d+)\w\w level", piece_body)
                features.append(
                    {
                        "_id": slug(f"eldritch invocation {piece_name}"),
                        "name": piece_name,
                        "origin": "Eldritch Invocation",
                        "class": owner["name"],
                        "level": int(level.group(1)) if level else 2,
                        "description": prose(f"Invocation: {piece_name}", piece_body),
                    }
                )

    classes, subclasses = [], []
    for pk, f in by_pk.items():
        first = sorted(by_owner[pk], key=lambda e: (e["level"], e["name"]))
        if f["subclass_of"]:
            parent_id = short(f["subclass_of"])
            parent = by_pk[f["subclass_of"]]
            level = min((e["level"] for e in first), default=CLASSES[parent_id]["subclass_level"])
            granted = [e for e in first if e["level"] == level]
            subclasses.append(
                {
                    "_id": short(pk),
                    "name": f["name"],
                    "class": parent["name"],
                    "level": level,
                    "description": subclass_description(f["name"], parent["name"], first),
                    "hp_per_level": HP_PER_LEVEL.get(short(pk), 0),
                    "feature_ids": joined([e["_id"] for e in granted]),
                    "feature_names": joined([e["name"] for e in granted]),
                }
            )
            continue
        data = CLASSES[short(pk)]
        profs = proficiencies(special[pk].get("PROFICIENCIES", ""))
        granted = [e for e in first if e["level"] == 1]
        saves = [SHORT_ABILITY[s] for s in sorted(f["saving_throws"], key=lambda s: list(SHORT_ABILITY).index(s))]
        description = "\n".join(
            [
                data["blurb"],
                "",
                f"Hit Dice: 1d{f['hit_dice'][1:]} per level",
                f"Armor: {profs['armor_text']}",
                f"Weapons: {profs['weapon_proficiencies'] or 'None'}",
                f"Tools: {profs['tool_proficiencies'] or 'None'}",
                f"Saving Throws: {joined([s.capitalize() for s in saves])}",
                f"Skills: {profs['skills_text']}",
            ]
        )
        equipment = special[pk].get("STARTING_EQUIPMENT")
        if equipment:
            description += "\n\nEquipment. " + prose(f"{f['name']} equipment", equipment)
        classes.append(
            {
                "_id": short(pk),
                "name": f["name"],
                "hit_die": int(f["hit_dice"][1:]),
                "primary_ability": data["primary"],
                "saving_throws": joined([s.capitalize() for s in saves]),
                "description": description,
                "spellcasting": data.get("spellcasting", ""),
                "caster_type": data.get("caster_type", ""),
                "prepares": data.get("prepares", ""),
                "subclass_level": data["subclass_level"],
                "skill_choices": profs["skill_choices"],
                "skill_options": profs["skill_options"],
                "armor_training": profs["armor_training"],
                "weapon_proficiencies": profs["weapon_proficiencies"],
                "tool_proficiencies": profs["tool_proficiencies"],
                "feature_ids": joined([e["_id"] for e in granted]),
                "feature_names": joined([e["name"] for e in granted]),
            }
        )

    features.sort(key=lambda e: (e["class"], e["origin"] != e["class"], e["origin"], e["level"], e["name"]))
    ids = [e["_id"] for e in features]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    return (
        sorted(classes, key=lambda e: e["name"]),
        sorted(subclasses, key=lambda e: (e["class"], e["name"])),
        features,
    )


def subclass_description(name: str, klass: str, features: list[dict]) -> str:
    listing = ", ".join(f"{e['name']} ({ordinal(e['level'])})" for e in features)
    return f"A {klass} subclass. Features: {listing}."


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# --- races ---------------------------------------------------------------------

#: Traits that describe the race rather than give the character something to
#: use. Their facts become the race's own properties (speed, size, ability
#: increases, languages) and its description, not entries a pick grants.
DESCRIPTIVE = {"Ability Score Increase", "Age", "Alignment", "Size", "Speed", "Languages"}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3}

#: Hit points a subrace or subclass adds at every level - Dwarven Toughness,
#: Draconic Resilience - so the sheet's hit point maximum can count them.
HP_PER_LEVEL = {"hill-dwarf": 1, "draconic-bloodline": 1}


def increases(text: str) -> dict[str, int]:
    found = {a: 0 for a in ABILITIES}
    if re.search(r"ability scores each increase by 1", text):
        return {a: 1 for a in ABILITIES}
    for ability, amount in re.findall(r"(\w+) score increases by (\d)", text):
        if ability.lower() in found:
            found[ability.lower()] = int(amount)
    return found


def race_entries(source: pathlib.Path) -> tuple[list[dict], list[dict], list[dict]]:
    species = {row["pk"]: row["fields"] for row in load(source, "Species")}
    traits_by: dict[str, list[dict]] = collections.defaultdict(list)
    for row in load(source, "SpeciesTrait"):
        traits_by[row["fields"]["parent"]].append({"pk": row["pk"], **row["fields"]})

    races, subraces, traits = [], [], []
    for pk, f in species.items():
        own = traits_by[pk]
        facts = {t["name"]: prose(f"{f['name']}: {t['name']}", t["desc"]) for t in own}
        table = facts.pop("Draconic Ancestry table", None)
        granted = []
        for trait in own:
            if trait["name"] in DESCRIPTIVE or trait["name"] == "Draconic Ancestry table":
                continue
            description = facts[trait["name"]]
            if trait["name"] == "Draconic Ancestry" and table:
                description += "\n\n" + table
            entry = {
                "_id": slug(f"{f['name']} {trait['name']}"),
                "name": trait["name"],
                "race": f["name"],
                "description": description,
            }
            traits.append(entry)
            granted.append(entry)

        skills = sorted({s for t in granted for s in SKILLS if re.search(rf"proficiency in the {s} skill", t["description"])})
        versatile = next((t for t in granted if re.search(r"proficiency in (\w+) skills of your choice", t["description"])), None)
        bonus = increases(facts.get("Ability Score Increase", ""))
        description_parts = [prose(f["name"], f["desc"])]
        for fact in ("Ability Score Increase", "Age", "Alignment", "Size", "Speed", "Languages"):
            if fact in facts:
                description_parts.append(f"{fact}. {facts[fact]}")
        entry = {
            "_id": short(pk),
            "name": f["name"],
            **{f"{a}_increase": bonus[a] for a in ABILITIES},
            "description": "\n\n".join(description_parts),
            "traits": joined([t["name"] for t in granted]),
            "trait_ids": joined([t["_id"] for t in granted]),
            "skill_proficiencies": skills,
        }
        if f["subspecies_of"]:
            entry["hp_per_level"] = HP_PER_LEVEL.get(short(pk), 0)
            entry["race"] = species[f["subspecies_of"]]["name"]
            subraces.append(entry)
            continue
        size = re.search(r"Your size is (\w+)", facts.get("Size", ""))
        speed = re.search(r"walking speed is (\d+) feet", facts.get("Speed", ""))
        languages = re.search(r"(?:speak, read, and write|write) (.+?)\.", facts.get("Languages", ""))
        entry.update(
            {
                "size": size.group(1) if size else "Medium",
                "speed": int(speed.group(1)) if speed else 30,
                "languages": languages.group(1) if languages else "",
                "subraces": "",
            }
        )
        if versatile:
            entry["skill_choices"] = NUMBER_WORDS[re.search(r"proficiency in (\w+) skills", versatile["description"]).group(1)]
            entry["skill_options"] = list(SKILLS)
        races.append(entry)

    for race in races:
        race["subraces"] = joined(sorted(s["name"] for s in subraces if s["race"] == race["name"]))
    ids = [t["_id"] for t in traits]
    assert len(ids) == len(set(ids)), "duplicate trait id"
    return sorted(races, key=lambda e: e["name"]), sorted(subraces, key=lambda e: e["name"]), traits


# --- background and feat --------------------------------------------------------


def background_entries(source: pathlib.Path) -> tuple[list[dict], list[dict]]:
    benefits = collections.defaultdict(list)
    for row in load(source, "BackgroundBenefit"):
        benefits[row["fields"]["parent"]].append(row["fields"])
    backgrounds, features = [], []
    for row in load(source, "Background"):
        f = row["fields"]
        own = {b["type"]: b for b in benefits[row["pk"]]}
        feature = own.get("feature")
        skills = [s for s in SKILLS if s in own.get("skill_proficiency", {}).get("desc", "")]
        feature_entry = {
            "_id": slug(f"{f['name']} {feature['name']}"),
            "name": feature["name"],
            # Filed under "Background" so the class filter reaches it: origin is
            # filtered within a class, and the browser waits for one.
            "origin": f["name"],
            "class": "Background",
            "description": prose(feature["name"], feature["desc"]),
        }
        features.append(feature_entry)
        description = prose(f["name"], f["desc"])
        for benefit in benefits[row["pk"]]:
            if benefit["type"] in ("skill_proficiency", "language", "equipment", "feature", "tool_proficiency"):
                continue
            description += f"\n\n{benefit['name']}. {prose(benefit['name'], benefit['desc'])}"
        backgrounds.append(
            {
                "_id": short(row["pk"]),
                "name": f["name"],
                "skill_proficiencies": skills,
                "tool_proficiencies": own.get("tool_proficiency", {}).get("desc", ""),
                "languages": own.get("language", {}).get("desc", ""),
                "equipment": plain(own.get("equipment", {}).get("desc", "")),
                "feature": feature["name"],
                "feature_id": feature_entry["_id"],
                "description": description,
            }
        )
    return backgrounds, features


def feat_entries() -> list[dict]:
    """The SRD's one feat, in its own words."""
    return [
        {
            "_id": "grappler",
            "name": "Grappler",
            "category": "General",
            "prerequisite": "Strength 13 or higher",
            "description": (
                "You've developed the skills necessary to hold your own in close-quarters "
                "grappling. You gain the following benefits:\n\n"
                "• You have advantage on attack rolls against a creature you are grappling.\n"
                "• You can use your action to try to pin a creature grappled by you. To do so, "
                "make another grapple check. If you succeed, you and the creature are both "
                "restrained until the grapple ends."
            ),
        }
    ]


# --- spells --------------------------------------------------------------------


def spells(source: pathlib.Path) -> list[dict]:
    lists = SRD.spell_lists
    headers = SRD.spell_headers
    out = []
    for row in load(source, "Spell"):
        f = row["fields"]
        header = headers[f["name"]]
        if header["ritual"] != bool(f["ritual"]):
            print(f"  ! {f['name']}: ritual per the SRD is {header['ritual']}")
        text = f["desc"]
        if f.get("higher_level"):
            heading = "" if f["level"] == 0 else "At Higher Levels. "
            text += f"\n\n{heading}{f['higher_level']}"
        description = prose(f["name"], text)
        duration = header["duration"]
        out.append(
            {
                "_id": short(row["pk"]),
                "name": f["name"],
                "level": f["level"],
                "school": title(f["school"]),
                "casting_time": header["casting_time"],
                "range": header["range"],
                "components": header["components"],
                "duration": duration,
                "concentration": duration.startswith("Concentration"),
                "ritual": header["ritual"],
                "classes": joined(sorted(c for c, names in lists.items() if f["name"] in names)),
                "description": description,
            }
        )
    assert len(out) == len(headers), "Open5e and the SRD disagree on the spells"
    return sorted(out, key=lambda s: (s["level"], s["name"]))


# --- equipment -----------------------------------------------------------------


def items(taken: set[str]) -> list[dict]:
    """The SRD's equipment tables and notes - Open5e's items are not used."""
    out = []
    for row in SRD.equipment:
        entry = {"_id": slug(row["name"]), **row}
        # Ids are unique across the whole pack: the Shield spell has "shield".
        if entry["_id"] in taken:
            entry["_id"] += "-equipment"
        out.append(entry)
    ids = [e["_id"] for e in out]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    return sorted(out, key=lambda e: (e["category"], e["name"]))


# --- magic items ---------------------------------------------------------------

RARITY_ORDER = ["common", "uncommon", "rare", "very-rare", "legendary", "artifact"]


def rarity(values: set[str]) -> str:
    ordered = sorted(values, key=RARITY_ORDER.index)
    if len(ordered) == 1:
        return title(ordered[0])
    return "Varies"


def single(f: dict) -> dict:
    return {
        "_id": "magic-" + slug(f["name"]),
        "name": f["name"],
        "item_type": title(f["category"]),
        "rarity": rarity({f["rarity"]}),
        "attunement": bool(f["requires_attunement"]),
        "description": prose(f["name"], f["desc"]),
    }


def magic_items(source: pathlib.Path) -> list[dict]:
    """The SRD's magic items, with Open5e's per-weapon and per-armour copies folded
    back into the one entry the SRD prints: "Adamantine Armor (Breastplate)",
    "Battleaxe (+1)" and the rest."""
    groups: dict[tuple, list[dict]] = collections.OrderedDict()
    for row in load(source, "MagicItem"):
        f = row["fields"]
        match = re.match(r"^(.*?) \((.+)\)$", f["name"])
        if match and match.group(2).startswith("+") and f["category"] == "wand":
            key = ("plus", "Wand of the War Mage")
        elif match and match.group(2).startswith("+"):
            kind = "Ammunition" if f["category"] == "ammunition" or "ammunition" in f["desc"].lower()[:80] else title(f["category"])
            key = ("plus", kind)
        elif match:
            key = ("variant", match.group(1))
        else:
            key = ("variant", f["name"])
        groups.setdefault(key, []).append(f)

    out = []
    for key, rows in groups.items():
        first = rows[0]
        if key[0] == "plus":
            name = f"{key[1]}, +1, +2, or +3"
            key = ("plus", "Wand") if key[1] == "Wand of the War Mage" else key
            by_bonus = {re.search(r"\(\+(\d)\)", r["name"]).group(1): r["rarity"] for r in rows}
            rarity_text = ", ".join(f"{title(by_bonus[b])} (+{b})" for b in sorted(by_bonus))
            item_type = {"Weapon": "Weapon (any)", "Armor": "Armor (any)"}.get(key[1], key[1])
            description = prose(name, first["desc"])
        elif key[0] == "variant" and len(rows) > 1:
            name = key[1]
            variants = [m.group(1) for r in rows if (m := re.match(r"^.*? \((.+)\)$", r["name"]))]
            item_type = title(first["category"])
            if len(variants) > 4 and first["category"] in ("weapon", "armor"):
                item_type += " (any)"
            elif variants:
                item_type += f" ({', '.join(variants)})"
            rarity_text = rarity({r["rarity"] for r in rows})
            if len({r["desc"] for r in rows}) > 2:
                # Distinct items sharing a name - the Figurines of Wondrous
                # Power - stay separate, as the SRD prints them.
                out.extend(single(r) for r in rows)
                continue
            text = collections.Counter(r["desc"] for r in rows).most_common(1)[0][0]
            description = prose(name, text)
        else:
            out.append(single(first))
            continue
        out.append(
            {
                "_id": "magic-" + slug(name),
                "name": name,
                "item_type": item_type,
                "rarity": rarity_text,
                "attunement": bool(first["requires_attunement"]),
                "description": description,
            }
        )
    parents = {
        e["name"]: next((p for pattern, p in VARIANT_OF if re.fullmatch(pattern, e["name"])), e["name"])
        for e in out
    }
    # Every heading at once, so each one's text stops at the next.
    headings = SRD.magic_headings(sorted(set(parents.values()) | set(MISSING_MAGIC)))
    out.extend(missing_magic_items({e["name"] for e in out}, headings))
    parents.update({name: name for name in MISSING_MAGIC})
    apply_magic_headings(out, parents, headings)
    ids = [e["_id"] for e in out]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    return sorted(out, key=lambda e: e["name"])


#: SRD items Open5e has no rows for, written from the SRD's own text.
MISSING_MAGIC = ["Ammunition, +1, +2, or +3", "Armor, +1, +2, or +3", "Shield, +1, +2, or +3"]

#: Items Open5e splits into one row per variant, and the SRD entry each is part of.
VARIANT_OF = [
    (r"Belt of \w+ Giant Strength", "Belt of Giant Strength"),
    (r"Potion of \w+ Giant Strength", "Potion of Giant Strength"),
    (r"Potion of (?:Greater |Superior |Supreme )?Healing", "Potion of Healing"),
    (r"Crystal Ball of .+", "Crystal Ball"),
    (r"Ioun Stone \(.+\)", "Ioun Stone"),
    (r"Figurine of Wondrous Power \(.+\)", "Figurine of Wondrous Power"),
]


def missing_magic_items(have: set[str], headings: dict[str, dict]) -> list[dict]:
    out = []
    for name in MISSING_MAGIC:
        if name in have:
            continue
        heading = headings[name]
        out.append(
            {
                "_id": "magic-" + slug(name),
                "name": name,
                "item_type": "",
                "rarity": "",
                "attunement": False,
                "description": heading["text"],
            }
        )
    return out


def apply_magic_headings(entries: list[dict], parents: dict[str, str], headings: dict[str, dict]) -> None:
    """Type, rarity and attunement as the SRD's heading line gives them.

    A variant Open5e split out (one Ioun Stone) takes its type and attunement
    from the SRD entry it belongs to, and keeps its own rarity. An attunement
    restricted to a class goes at the head of the description."""
    for entry in entries:
        heading = headings.get(parents[entry["name"]])
        if heading is None:
            print(f"  ! {entry['name']}: no SRD heading")
            continue
        kind = heading["kind"]
        entry["item_type"] = (kind[:1].upper() + kind[1:]).replace("Wondrous item", "Wondrous Item")
        if parents[entry["name"]] == entry["name"]:
            rarity_text = re.sub(r"^rarity (varies|by figurine)$", "varies", heading["rarity"])
            entry["rarity"] = re.sub(
                r"\b(common|uncommon|rare|very|legendary|artifact|varies)\b",
                lambda m: m.group(1).capitalize(),
                rarity_text,
            )
        entry["attunement"] = bool(heading["attunement"])
        by = (heading["by"] or "").strip()
        if by and not entry["description"].startswith("Requires attunement"):
            entry["description"] = f"Requires attunement {by}.\n\n{entry['description']}"


# --- output --------------------------------------------------------------------


def write(name: str, rows: list[dict]) -> None:
    with open(PACK / f"{name}.json", "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"{name}.json: {len(rows)}")


def main() -> None:
    global SRD
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    source = pathlib.Path(sys.argv[1])
    SRD = Srd(pathlib.Path(sys.argv[2]))
    PACK.mkdir(parents=True, exist_ok=True)
    classes, subclasses, features = class_entries(source)
    races, subraces, traits = race_entries(source)
    backgrounds, background_features = background_entries(source)
    spell_rows = spells(source)
    write("class", classes)
    write("subclass", subclasses)
    write("feature", features + background_features)
    write("race", races)
    write("subrace", subraces)
    write("trait", traits)
    write("background", backgrounds)
    write("feat", feat_entries())
    write("spell", spell_rows)
    write("item", items({s["_id"] for s in spell_rows}))
    write("magic_item", magic_items(source))
    if SRD.unmatched:
        print(f"\nKept as Open5e has them - check against the SRD ({len(SRD.unmatched)}):")
        for line in SRD.unmatched:
            print(f"  {line}")


if __name__ == "__main__":
    main()
