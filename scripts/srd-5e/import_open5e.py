#!/usr/bin/env python3
"""Fill the dnd-5e-srd content pack from Open5e's SRD 5.2 fixtures.

    python3 scripts/srd-5e/import_open5e.py /path/to/open5e-api/data/v2/wizards-of-the-coast/srd-2024

Open5e (github.com/open5e/open5e-api) keeps the System Reference Document 5.2
as Django fixtures, one JSON file per model. This reads them and writes the
pack's spells, class features, equipment and magic items, and adds each class's
level 1 features to class.json so picking a class can grant them.

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

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "content-packs" / "dnd-5e-srd"


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


def plain(text: str | None) -> str:
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
            line = " - ".join(cell for cell in cells if cell)
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^\s*[-*]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", line)
        line = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", line)
        lines.append(line.rstrip())
    out = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", out)


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
        entry = {
            "_id": slug(f"{owner['name']} {f['name']}"),
            "name": f["name"],
            "class": owner["name"],
            "level": min(levels[row["pk"]]),
            "description": plain(f["desc"]),
        }
        out.append(entry)
        by_class[short(f["parent"])].append(entry)
    out.sort(key=lambda e: (e["class"], e["level"], e["name"]))
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


def write(name: str, rows: list[dict]) -> None:
    with open(PACK / f"{name}.json", "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"{name}.json: {len(rows)}")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    source = pathlib.Path(sys.argv[1])
    class_names = {
        row["pk"]: row["fields"]["name"]
        for row in load(source, "CharacterClass")
        if not row["fields"]["subclass_of"]
    }
    feature_rows, by_class = features(source)
    spell_rows = spells(source, class_names)
    write("spell", spell_rows)
    write("feature", feature_rows)
    write("item", items(source, {s["_id"] for s in spell_rows}))
    write("magic_item", magic_items(source))
    write("class", add_class_features(by_class))


if __name__ == "__main__":
    main()
