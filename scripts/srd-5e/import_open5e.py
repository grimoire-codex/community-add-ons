#!/usr/bin/env python3
"""Fill the dnd-5e-srd content pack from Open5e's SRD 5.2 fixtures.

    python3 scripts/srd-5e/import_open5e.py /path/to/open5e-api/data/v2/wizards-of-the-coast/srd-2024

Open5e (github.com/open5e/open5e-api) keeps the System Reference Document 5.2
as Django fixtures, one JSON file per model. This reads them and writes the
pack's spells, class and subclass features, subclasses, equipment and magic
items, and adds each class's level 1 features to class.json so picking a class
can grant them. A subclass feature keeps its class and names its subclass, and
each subclass lists the features it grants at the level it is chosen.

It also writes the reference material no character picks from - conditions,
rules (the Rules Glossary and the rules chapters) and monsters - which the
pack's _meta.json declares as content types of its own. Those are checked
against the SRD 5.2.1 PDF that the same Open5e clone keeps under
data/raw_sources/srd_5_2 (read by srd52.py, which needs pymupdf): a monster's
header comes from its stat block, and every condition, rule and stat block
entry takes the SRD's own words. The importer lists anything it could not match.

Everything written is SRD 5.2 text, under the CC BY 4.0 attribution the pack
already carries. Open5e expands a generic magic item into one row per weapon or
armour - a Holy Avenger for every weapon in the game - so those are folded back
into the single entry the SRD prints. Descriptions are reduced from markdown to
the plain text a pack holds.

The species, backgrounds, feats and their traits are hand-checked against the
SRD's lists (Grimoire's test suite holds the lists) and are left alone.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

from srd52 import Srd, Wording, glossary

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "content-packs" / "dnd-5e-srd"

#: The SRD 5.2.1, loaded in main() for the reference types.
SRD: Srd


def load(source: pathlib.Path, model: str) -> list[dict]:
    with open(source / f"{model}.json", encoding="utf-8") as handle:
        return json.load(handle)


def slug(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def short(pk: str) -> str:
    return pk.removeprefix("srd-2024_")


def title(text: str) -> str:
    return " ".join(word.capitalize() for word in re.split(r"[-\s]+", text or "") if word)


def plain(text: str | None, *, keep_marks: bool = False) -> str:
    """Markdown to the plain text a pack holds: paragraphs kept, markup gone.

    A table becomes one line per row, cells joined by " - ", which reads well
    enough in a sheet's entry view and keeps every value. `keep_marks` leaves
    each table row marked, for `prose`.
    """
    lines = []
    for line in (text or "").replace("\r", "").split("\n"):
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", cell) or not cell for cell in cells):
                continue
            line = (TABLE_ROW if keep_marks else "") + " - ".join(cell for cell in cells if cell)
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^\s*[-*]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", line)
        line = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", line)
        lines.append(line.rstrip())
    out = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", out)


#: Marks a line that was a table row, so `prose` leaves it as it is.
TABLE_ROW = "\x00"


def prose(name: str, markdown: str | None, against: Wording | None = None) -> str:
    """An entry's text as plain text in the SRD's own words.

    Open5e's paragraphs and table rows give the shape; `Wording.reword` puts
    the SRD's wording into each paragraph - matched against `against`, such as
    one monster's stat block, or the whole SRD. Text the SRD cannot be matched
    to is kept as Open5e has it, and listed when the importer finishes.
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
    reworded = (against or SRD).reword(name, bodies, keep)
    if reworded is None:
        return text.replace(TABLE_ROW, "")
    for n, i in enumerate(spots):
        lines[i] = bullets.get(n, "") + reworded[n]
    return "\n".join(lines)


def number(value) -> float | int:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0
    return int(result) if result.is_integer() else result


def cost(value) -> str:
    """Open5e stores cost in gold; the SRD prints it in the coin it is priced in."""
    gold = float(value or 0)
    if not gold:
        return ""
    for coin, rate in (("GP", 1), ("SP", 10), ("CP", 100)):
        amount = gold * rate
        if amount >= 1 and float(amount).is_integer():
            return f"{int(amount):,} {coin}"
    return f"{gold:g} GP"


# --- spells ------------------------------------------------------------------

CASTING = {
    "action": "Action",
    "bonus-action": "Bonus Action",
    "reaction": "Reaction",
    "1minute": "1 minute",
    "10minutes": "10 minutes",
    "1hour": "1 hour",
    "8hours": "8 hours",
    "12hours": "12 hours",
    "24hours": "24 hours",
}


def spells(source: pathlib.Path, classes: dict[str, str]) -> list[dict]:
    out = []
    for row in load(source, "Spell"):
        f = row["fields"]
        components = [c for c, on in (("V", f["verbal"]), ("S", f["somatic"])) if on]
        if f["material"]:
            components.append(f"M ({f['material_specified']})" if f["material_specified"] else "M")
        casting = CASTING.get(f["casting_time"], f["casting_time"])
        duration = f["duration"][:1].upper() + f["duration"][1:]
        if f["concentration"]:
            duration = f"Concentration, up to {f['duration']}"
        description = plain(f["desc"])
        if f["casting_time"] == "reaction" and f.get("reaction_condition"):
            # The trigger is a sentence; it belongs with the text, not in the
            # casting-time column a sheet draws.
            description = f"Reaction, {f['reaction_condition']}.\n\n{description}"
        if f.get("higher_level"):
            heading = "Cantrip Upgrade." if f["level"] == 0 else "Using a Higher-Level Spell Slot."
            description += f"\n\n{heading} {plain(f['higher_level'])}"
        out.append(
            {
                "_id": short(row["pk"]),
                "name": f["name"],
                "level": f["level"],
                "school": title(f["school"]),
                "casting_time": casting,
                "range": f["range_text"],
                "components": ", ".join(components),
                "duration": duration,
                "concentration": bool(f["concentration"]),
                "ritual": bool(f["ritual"]),
                "classes": ", ".join(
                    sorted(classes[c] for c in f.get("classes") or [] if c in classes)
                ),
                "description": description,
            }
        )
    return sorted(out, key=lambda s: (s["level"], s["name"]))


# --- class features -----------------------------------------------------------

#: Open5e also stores each class table's columns as features. Those are the
#: table, not features a character has, so only plain features are taken.
SKIP_FEATURE = re.compile(r"(Subclass|Spell List)$")


def features(source: pathlib.Path) -> tuple[list[dict], dict[str, list[dict]]]:
    classes = {row["pk"]: row["fields"] for row in load(source, "CharacterClass")}
    levels: dict[str, list[int]] = collections.defaultdict(list)
    for item in load(source, "ClassFeatureItem"):
        levels[item["fields"]["parent"]].append(item["fields"]["level"])

    out, by_class = [], collections.defaultdict(list)
    for row in load(source, "ClassFeature"):
        f = row["fields"]
        if f.get("feature_type") or not levels.get(row["pk"]) or SKIP_FEATURE.search(f["name"]):
            continue
        owner = classes[f["parent"]]
        parent = classes.get(owner["subclass_of"]) if owner["subclass_of"] else None
        entry = {
            "_id": slug(f"{owner['name']} {f['name']}"),
            "name": f["name"],
            "class": parent["name"] if parent else owner["name"],
            "level": min(levels[row["pk"]]),
            "description": plain(f["desc"]),
        }
        if parent:
            entry["subclass"] = owner["name"]
        out.append(entry)
        by_class[short(f["parent"])].append(entry)
    out.sort(key=lambda e: (e["class"], e.get("subclass", ""), e["level"], e["name"]))
    ids = [e["_id"] for e in out]
    assert len(ids) == len(set(ids)), "duplicate feature id"
    return out, by_class


# --- equipment ----------------------------------------------------------------

CATEGORY = {
    "weapon": "Weapon",
    "armor": "Armor",
    "adventuring-gear": "Adventuring Gear",
    "ammunition": "Ammunition",
    "tools": "Tool",
    "spellcasting-focus": "Spellcasting Focus",
    "equipment-pack": "Equipment Pack",
    "mount": "Mount",
    "land-vehicle": "Vehicle",
    "waterborne-vehicle": "Vehicle",
    "potion": "Adventuring Gear",
    "scroll": "Adventuring Gear",
}

#: The SRD's own magic items have no business in the mundane equipment list.
NOT_EQUIPMENT = {"airship", "ioun-stone", "potion-of-giant-strength", "potions-of-healing",
                 "spell-scroll"}


def weapons(source: pathlib.Path) -> dict[str, dict]:
    props = {row["pk"]: row["fields"] for row in load(source, "WeaponProperty")}
    assigned = collections.defaultdict(list)
    for row in load(source, "WeaponPropertyAssignment"):
        f = row["fields"]
        assigned[f["weapon"]].append((props[f["property"]], f.get("detail")))
    out = {}
    for row in load(source, "Weapon"):
        f = row["fields"]
        properties, mastery = [], ""
        for prop, detail in sorted(assigned[row["pk"]], key=lambda p: p[0]["name"]):
            if prop.get("type") == "Mastery":
                mastery = prop["name"]
                continue
            properties.append(f"{prop['name']} ({detail})" if detail else prop["name"])
        if f["range"] and not any("Range" in p for p in properties):
            # The SRD prints range inside the Ammunition or Thrown property.
            properties.append(f"Range {f['range']}/{f['long_range']}")
        damage = f["damage_dice"]
        if f["damage_type"]:
            damage = f"{damage} {f['damage_type'].capitalize()}"
        kind = "Simple" if f["is_simple"] else "Martial"
        kind += " Ranged" if f["range"] and not any(
            p.startswith("Thrown") for p in properties
        ) else " Melee"
        out[row["pk"]] = {
            "damage": damage,
            "properties": ", ".join(properties),
            "mastery": mastery,
            "weapon_type": f"{kind} Weapon",
        }
    return out


def armour(source: pathlib.Path) -> dict[str, dict]:
    out = {}
    for row in load(source, "Armor"):
        f = row["fields"]
        if f["name"] == "Shield":
            ac = "+2"
        elif f["ac_add_dexmod"] and f["ac_cap_dexmod"]:
            ac = f"{f['ac_base']} + Dex modifier (max {f['ac_cap_dexmod']})"
        elif f["ac_add_dexmod"]:
            ac = f"{f['ac_base']} + Dex modifier"
        else:
            ac = str(f["ac_base"])
        out[row["pk"]] = {
            "armor_class": ac,
            "strength": f["strength_score_required"] or 0,
            "stealth": "Disadvantage" if f["grants_stealth_disadvantage"] else "",
        }
    return out


def items(source: pathlib.Path, taken: set[str]) -> list[dict]:
    weapon_data, armour_data = weapons(source), armour(source)
    out = []
    for row in load(source, "Item"):
        f = row["fields"]
        item_id = short(row["pk"])
        if item_id in NOT_EQUIPMENT or f["category"] not in CATEGORY:
            continue
        # Ids are unique across the whole pack: the Shield spell has "shield".
        if item_id in taken:
            item_id += "-equipment"
        category = CATEGORY[f["category"]]
        entry = {
            "_id": item_id,
            "name": f["name"],
            "category": category,
            "cost": cost(f["cost"]),
            "weight": number(f["weight"]),
        }
        if f.get("weapon"):
            entry.update(weapon_data.get(f["weapon"], {}))
        elif f["category"] == "weapon":
            # Acid, Alchemist's Fire, Holy Water and the like: thrown gear the
            # SRD lists among adventuring gear, with the rules in their text.
            entry["category"] = "Adventuring Gear"
        if f.get("armor"):
            entry.update(armour_data.get(f["armor"], {}))
            if f["name"] == "Shield":
                entry["category"] = "Shield"
        description = plain(f["desc"])
        # "A battleaxe." says nothing the name does not.
        if description and not re.fullmatch(r"(An?|The) [^.]{0,40}\.", description):
            entry["description"] = description
        out.append(entry)
    return sorted(out, key=lambda e: (e["category"], e["name"]))


# --- magic items -------------------------------------------------------------

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
        "description": plain(f["desc"]),
    }


#: Items Open5e expands into one copy per weapon or armour named "Vicious
#: Dagger", "Demon Plate Armor" - folded back into the SRD's own entry.
EXPANDED = {
    "Vicious": "Vicious Weapon",
    "Flame Tongue": "Flame Tongue",
    "Demon": "Demon Armor",
    "Dancing": "Dancing Sword",
    "Vorpal": "Vorpal Sword",
    "Berserker": "Berserker Axe",
    "Elven": "Elven Chain",
}


def magic_items(source: pathlib.Path) -> list[dict]:
    bases = [row["fields"]["name"] for row in load(source, "Weapon") + load(source, "Armor")]
    prefixes = "|".join(map(re.escape, EXPANDED))
    expanded = re.compile(rf"^({prefixes}) ({'|'.join(map(re.escape, bases))})$")
    groups: dict[tuple, list[dict]] = collections.OrderedDict()
    for row in load(source, "MagicItem"):
        f = row["fields"]
        spread = expanded.match(f["name"])
        if spread:
            f = {**f, "name": f"{EXPANDED[spread.group(1)]} ({spread.group(2)})"}
        match = re.match(r"^(.*?) \((.+)\)$", f["name"])
        if match and match.group(2).startswith("+"):
            # "Battleaxe (+1)" is the SRD's "Weapon, +1, +2, or +3".
            kind = "Ammunition" if "ammunition" in f["desc"] else title(f["category"])
            key = ("plus", kind)
        elif match:
            key = ("variant", match.group(1))
        else:
            # A base entry joins its own variants, when Open5e has both.
            key = ("variant", f["name"])
        groups.setdefault(key, []).append(f)

    out = []
    for key, rows in groups.items():
        first = rows[0]
        if key[0] == "plus":
            name = f"{key[1]}, +1, +2, or +3"
            by_bonus = {re.search(r"\(\+(\d)\)", r["name"]).group(1): r["rarity"] for r in rows}
            rarity_text = ", ".join(
                f"{title(by_bonus[b])} (+{b})" for b in sorted(by_bonus)
            )
            item_type = {"Weapon": "Weapon (any)", "Armor": "Armor (any)"}.get(key[1], key[1])
            if key[1] == "Armor" and any(r["name"].startswith("Shield") for r in rows):
                item_type = "Armor (any, including Shield)"
            description = plain(first["desc"])
        elif key[0] == "variant" and len(rows) > 1:
            name = key[1]
            variants = [
                m.group(1) for r in rows if (m := re.match(r"^.*? \((.+)\)$", r["name"]))
            ]
            item_type = title(first["category"])
            if len(variants) > 4 and first["category"] in ("weapon", "armor"):
                item_type += " (any)"
            else:
                item_type += f" ({', '.join(variants)})"
            rarity_text = rarity({r["rarity"] for r in rows})
            if len({r["desc"] for r in rows}) > 2:
                # Distinct items sharing a name - the Figurines of Wondrous
                # Power - stay separate, as the SRD prints them.
                out.extend(single(r) for r in rows)
                continue
            # The text the variants share; one variant's may carry an extra line.
            text = collections.Counter(r["desc"] for r in rows).most_common(1)[0][0]
            description = plain(text)
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
    ids = [e["_id"] for e in out]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    return sorted(out, key=lambda e: e["name"])


# --- classes -----------------------------------------------------------------


def add_class_features(by_class: dict[str, list[dict]]) -> list[dict]:
    """Give each class in class.json its level 1 features, as ids and names."""
    with open(PACK / "class.json", encoding="utf-8") as handle:
        classes = json.load(handle)
    for entry in classes:
        first = sorted(
            (f for f in by_class.get(entry["_id"], []) if f["level"] == 1),
            key=lambda f: f["name"],
        )
        entry["feature_ids"] = ", ".join(f["_id"] for f in first)
        entry["feature_names"] = ", ".join(f["name"] for f in first)
    return classes


def subclasses(source: pathlib.Path, by_class: dict[str, list[dict]]) -> list[dict]:
    """Each subclass, with the features it grants at the level it is chosen."""
    classes = {row["pk"]: row["fields"] for row in load(source, "CharacterClass")}
    out = []
    for pk, f in classes.items():
        if not f["subclass_of"]:
            continue
        granted = by_class.get(short(pk), [])
        level = min((g["level"] for g in granted), default=3)
        first = sorted((g for g in granted if g["level"] == level), key=lambda g: g["name"])
        out.append({
            "_id": short(pk),
            "name": f["name"],
            "class": classes[f["subclass_of"]]["name"],
            "level": level,
            "description": plain(f["desc"]),
            "feature_ids": ", ".join(g["_id"] for g in first),
            "feature_names": ", ".join(g["name"] for g in first),
        })
    out.sort(key=lambda e: (e["class"], e["name"]))
    return out


# --- conditions, rules and monsters ---------------------------------------------
# Reference material: no character picks a condition or a monster, so the sheet
# does not declare these types. The pack's _meta.json declares them itself.


def conditions(source: pathlib.Path) -> list[dict]:
    out = []
    for row in load(source, "ConditionDescription"):
        name = title(row["fields"]["describes"])
        out.append({"_id": slug(name), "name": name, "description": prose(name, row["fields"]["desc"])})
    return sorted(out, key=lambda e: e["name"])


def sidebars(markdown: str) -> str:
    """The SRD's sidebars - markdown block quotes in Open5e's copy - as plain
    paragraphs."""
    return "\n".join(re.sub(r"^\s*>\s?", "", line) for line in markdown.split("\n")).strip()


def unique_ids(entries: list[dict], taken: set[str]) -> None:
    """Give each entry an id from its name, qualified by its category when the
    name is used more than once or is already another entry's in the pack
    ("Cover" is a glossary entry and a section of Combat)."""
    counts = collections.Counter(e["name"] for e in entries)
    for entry in entries:
        entry_id = slug(entry["name"])
        if counts[entry["name"]] > 1 or entry_id in taken:
            entry_id = slug(f"{entry['category']} {entry['name']}")
        base, n = entry_id, 2
        while entry_id in taken:
            entry_id, n = f"{base}-{n}", n + 1
        taken.add(entry_id)
        entry["_id"] = entry_id


def rules(source: pathlib.Path, markdown: pathlib.Path, taken: set[str]) -> list[dict]:
    """The Rules Glossary, entry by entry, then the rules chapters a section
    each, filed under the part they come from; a part's own introduction is an
    entry named after it. The glossary's conditions are condition.json's."""
    out = []
    for heading, body in glossary(markdown):
        name, tag = re.fullmatch(r"(.+?)(?: \[(.+)\])?", heading).groups()
        if tag == "Condition":
            continue
        entry = {"name": name, "category": "Rules Glossary", "tag": tag or ""}
        entry["description"] = prose(f"Rules Glossary: {heading}", body)
        out.append({key: value for key, value in entry.items() if value != ""})
    for entry in out:
        # The Darkness spell has "darkness".
        entry["_id"] = slug(entry["name"]) + ("-rule" if slug(entry["name"]) in taken else "")
        assert entry["_id"] not in taken, entry["_id"]
        taken.add(entry["_id"])

    parts = {row["pk"]: row["fields"] for row in load(source, "RuleSet")}
    rows = [(f["name"], 0, f["name"], f["desc"]) for f in parts.values() if f["desc"]]
    for row in load(source, "Rule"):
        f = row["fields"]
        rows.append((parts[f["ruleset"]]["name"], f["index"], f["name"], f["desc"]))
    chapters = []
    for category, _, name, desc in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
        text = prose(f"{category}: {name}", sidebars(desc))
        chapters.append({"name": name, "category": category, "description": text})
    unique_ids(chapters, taken)
    return [{"_id": e.pop("_id"), **e} for e in out + chapters]


SECTIONS = {
    "ACTION": "Actions",
    "BONUS_ACTION": "Bonus Actions",
    "REACTION": "Reactions",
    "LEGENDARY_ACTION": "Legendary Actions",
}

LEGENDARY = re.compile(
    r"Legendary Action Uses: .+?regains all expended uses at the start of each of its turns\."
)

CONDITIONS = {
    "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", "Grappled", "Incapacitated",
    "Invisible", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned",
    "Unconscious",
}

ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


def usage(f: dict) -> str:
    """What the SRD prints after an action's name: its form, recharge or uses."""
    if "(" in f["name"]:
        return ""
    parts = []
    if f.get("limited_to_form"):
        parts.append(f["limited_to_form"])
    if f.get("uses_type") in ("RECHARGE_ON_ROLL", "RECHARGE") and f.get("uses_param"):
        low = f["uses_param"]
        parts.append(f"Recharge {low}" if low == 6 else f"Recharge {low}–6")
    elif f.get("uses_type") == "PER_DAY" and f.get("uses_param"):
        parts.append(f"{f['uses_param']}/Day")
    return "".join(f" ({part})" for part in parts)


def locate(text: str, name: str, after: int) -> int:
    """Where a stat block entry starts: its name, starting a sentence unless it
    follows a spell list, which has no full stop. "Claw" finds "Claws"."""
    bare = re.escape(name.split(" (")[0])
    entry = rf"{bare}s?(?: \([^)]*\))?\. "
    # Not a choice in another entry's text: "uses (A) Fire Breath or (B) Weakening Breath."
    start = r"(?:(?<=[.):] )(?<!\([A-Z]\) )|(?<=ctions )|(?<=Traits ))"
    found = re.compile(start + entry).search(text, after)
    found = found or re.compile(r"(?<!\([A-Z]\) )" + entry).search(text, after)
    return found.start() if found else len(text)


def plainly(text: str) -> str:
    """Text without its layout, to compare two copies of an entry."""
    return re.sub(r"\s+", " ", text.replace("• ", " ")).strip()


def rating(challenge: str) -> float | int:
    top, _, bottom = challenge.partition("/")
    return int(top) / int(bottom) if bottom else int(top)


def immunities(printed: str) -> tuple[str, str]:
    """The SRD prints damage and condition immunities on one line, damage
    first: "Necrotic, Poison; Charmed, Exhaustion"."""
    damage, conditions_ = [], []
    for part in filter(None, printed.split("; ")):
        names = {word.strip() for word in part.split(",")}
        (conditions_ if names <= CONDITIONS else damage).append(part)
    return "; ".join(damage), "; ".join(conditions_)


def monsters(source: pathlib.Path, taken: set[str]) -> list[dict]:
    creatures = load(source, "Creature")
    parts: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
    for row in load(source, "CreatureTrait") + load(source, "CreatureAction"):
        f = row["fields"]
        # Open5e's "Bite " has a stray space.
        section = SECTIONS[f["action_type"]] if "action_type" in f else "Traits"
        parts[f["parent"]].append((section, {**f, "name": f["name"].strip()}))
    blocks = SRD.stat_blocks([row["fields"]["name"] for row in creatures])

    out, left_out, not_srd, from_srd = [], [], [], []
    for row in creatures:
        f = row["fields"]
        block = blocks.get(f["name"])
        if block is None:
            left_out.append(f["name"])
            continue
        text = block["text"]
        wording = Wording(text, SRD.unmatched, entries=True)

        # Where each section and entry starts in the stat block. A section is
        # searched from its heading, so an action and a legendary action of the
        # same name are each found in their own.
        spots, bounds = {}, {len(text)}
        for heading in ["Traits", *SECTIONS.values()]:
            # After a full stop, or after a spell list, which has none.
            begins = re.search(
                rf"(?<![\w(])(?<!Bonus )(?<!Legendary ){heading} (?=[A-Z][^.]{{0,60}}\. )", text
            )
            if begins:
                bounds.add(begins.start())
            for section, part in parts[row["pk"]]:
                if section == heading:
                    at = locate(text, part["name"], begins.end() if begins else 0)
                    spots[id(part)] = (at, part.get("order_in_statblock") or 0)
                    bounds.add(at)
        if intro := LEGENDARY.search(text):
            bounds.add(intro.start())

        def printed(part: dict) -> str | None:
            """The entry as the stat block prints it, for one Open5e has wrong
            or short, with a spell list laid out as Open5e lays it out."""
            begin = spots[id(part)][0]
            if begin == len(text):
                return None
            end = min(b for b in bounds if b > begin)
            entry = text[begin:end].strip()
            if end == len(text):
                # The last entry runs on to the next stat block's heading.
                entry = entry[: entry.rfind(".") + 1]
            head, *spells = re.split(r" (?=(?:At Will|\d+/Day(?: Each)?): )", entry)
            return head + ("\n\n" + "\n".join(f"• {line}" for line in spells) if spells else "")

        sections = []
        for heading in ["Traits", *SECTIONS.values()]:
            own = sorted((p for s, p in parts[row["pk"]] if s == heading), key=lambda p: spots[id(p)])
            paragraphs = []
            for part in own:
                label = part["name"] + usage(part)
                before = len(SRD.unmatched)
                reworded = prose(f"{f['name']}: {part['name']}", f"{label}. {part['desc']}", wording)
                srd = printed(part)
                ours = [line.removeprefix("• ") for line in reworded.split("\n") if line]
                if (
                    srd is not None
                    and plainly(srd) != plainly(reworded)
                    and all(p.startswith("• ") for p in reworded.split("\n\n")[1:])
                    and (
                        len(plainly(srd)) >= 0.9 * len(plainly(reworded))
                        or not all(line in srd for line in ours)
                    )
                ):
                    # The stat block's own text, where Open5e's is short of it
                    # ("Plane Shift (self only)") or has its own additions (an
                    # "At Will" list for Read Thoughts).
                    del SRD.unmatched[before:]
                    from_srd.append(f"{f['name']}: {part['name']}")
                    reworded = srd
                elif len(SRD.unmatched) > before and SRD.unmatched[-1].endswith(": not found in the SRD"):
                    # Nowhere in the stat block: Open5e's own.
                    SRD.unmatched.pop()
                    not_srd.append(f"{f['name']}: {part['name']}")
                    continue
                paragraphs.append(reworded)
            if not paragraphs:
                continue
            if heading == "Legendary Actions" and intro:
                paragraphs.insert(0, intro.group(0))
            sections.append("\n\n".join([heading, *paragraphs]))

        kind = re.fullmatch(r"(\w+)(?: \((.+)\))?", block["type"])
        if kind:
            kind, tags = kind.group(1), kind.group(2) or ""
        else:
            # "Swarm of Tiny Beasts": a Beast, and what it is a swarm of.
            kind, tags = title(f["type"]), block["type"]
        hit_points = re.fullmatch(r"(\d+) \((.+)\)", block["HP"])
        if block["scores"]:
            scores = dict(zip(ABILITIES, block["scores"]))
            saves = ", ".join(
                f"{a[:3].title()} {save}"
                for a, save, mod in zip(ABILITIES, block["saves"], block["mods"])
                if save != mod
            )
        else:
            # One stat block misprints a save; Open5e's row is the SRD's otherwise.
            print(f"  ! {f['name']}: ability scores and saves taken from Open5e")
            scores = {a: f[f"ability_score_{a}"] for a in ABILITIES}
            saves = ", ".join(
                f"{a[:3].title()} {f[f'saving_throw_{a}']:+d}"
                for a in ABILITIES
                if f[f"saving_throw_{a}"] is not None
                and f[f"saving_throw_{a}"] != (scores[a] - 10) // 2
            )
        if any(scores[a] != f[f"ability_score_{a}"] for a in ABILITIES):
            print(f"  ! {f['name']}: ability scores per the SRD are {list(scores.values())}")
        damage_immunities, condition_immunities = immunities(block["Immunities"])
        entry = {
            "name": f["name"],
            "size": block["size"],
            "type": kind,
            "subtype": tags,
            "alignment": block["alignment"],
            "armor_class": int(block["AC"]),
            "initiative": block["Initiative"],
            "hit_points": int(hit_points.group(1)),
            "hit_dice": hit_points.group(2),
            "speed": block["Speed"],
            **scores,
            "saving_throws": saves,
            "skills": block["Skills"],
            "damage_vulnerabilities": block["Vulnerabilities"],
            "damage_resistances": block["Resistances"],
            "damage_immunities": damage_immunities,
            "condition_immunities": condition_immunities,
            "gear": block["Gear"],
            "senses": block["Senses"],
            "languages": block["Languages"],
            "challenge": block["challenge"],
            "cr": rating(block["challenge"]),
            "xp": block["xp"],
            "xp_in_lair": block["xp_in_lair"] or "",
            "proficiency_bonus": block["proficiency_bonus"],
            "description": "\n\n".join(sections),
        }
        out.append({key: value for key, value in entry.items() if value != ""})
    if left_out:
        print(f"  No stat block in the SRD, left out: {', '.join(sorted(left_out))}")
    if not_srd:
        print(f"  Not in the SRD's stat blocks, left out: {'; '.join(not_srd)}")
    if from_srd:
        print(f"  Open5e's text differs, the stat block's taken: {'; '.join(from_srd)}")
    for entry in out:
        entry_id = slug(entry["name"])
        if entry_id in taken:
            entry_id += "-monster"
        assert entry_id not in taken, entry_id
        taken.add(entry_id)
        entry["_id"] = entry_id
    return sorted(({"_id": e.pop("_id"), **e} for e in out), key=lambda e: e["name"])


def write(name: str, rows: list[dict]) -> None:
    with open(PACK / f"{name}.json", "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"{name}.json: {len(rows)}")


def main() -> None:
    global SRD
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    source = pathlib.Path(sys.argv[1])
    # The SRD itself and the Rules Glossary's markdown, from the same clone.
    raw = source.resolve().parents[2] / "raw_sources" / "srd_5_2"
    SRD = Srd(raw / "SRD_CC_v5.2.1.pdf")
    class_names = {
        row["pk"]: row["fields"]["name"]
        for row in load(source, "CharacterClass")
        if not row["fields"]["subclass_of"]
    }
    feature_rows, by_class = features(source)
    spell_rows = spells(source, class_names)
    item_rows = items(source, {s["_id"] for s in spell_rows})
    magic_rows = magic_items(source)
    subclass_rows = subclasses(source, by_class)
    class_rows = add_class_features(by_class)
    write("spell", spell_rows)
    write("feature", feature_rows)
    write("item", item_rows)
    write("magic_item", magic_rows)
    write("subclass", subclass_rows)
    write("class", class_rows)

    # Ids are unique across the whole pack, the reference types included. The
    # species, backgrounds, feats and traits are hand-kept, so read from disk.
    taken = {
        e["_id"]
        for rows in (spell_rows, feature_rows, item_rows, magic_rows, subclass_rows, class_rows)
        for e in rows
    }
    for name in ("species", "background", "feat", "trait"):
        with open(PACK / f"{name}.json", encoding="utf-8") as handle:
            taken |= {e["_id"] for e in json.load(handle)}
    condition_rows = conditions(source)
    assert not taken & {e["_id"] for e in condition_rows}
    taken |= {e["_id"] for e in condition_rows}
    write("condition", condition_rows)
    write("rule", rules(source, raw / "sections" / "09_rules_glossary.md", taken))
    write("monster", monsters(source, taken))
    if SRD.unmatched:
        print(f"\nKept as Open5e has them - check against the SRD ({len(SRD.unmatched)}):")
        for line in SRD.unmatched:
            print(f"  {line}")


if __name__ == "__main__":
    main()
