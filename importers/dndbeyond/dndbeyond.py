#!/usr/bin/env python3
"""D&D Beyond -> the dnd-5e-2024 sheet.

Ported from the converter Ian Hunter (@ianfhunter) wrote for Grimoire in
hunter-read/grimoire#552.

Grimoire fetches a shared character's JSON itself (the manifest's `url.fetch`)
or reads a saved copy, and hands it to this script as `document`. YAML cannot
do this one: an ability score is the sum of the base roll, bonuses and every
modifier that touches it, and proficiencies are spread across a list of
modifiers that need sorting into skills, saves, armour and tools.

What the sheet works out for itself - hit dice, spell slots, armour class -
is left to it, so those keep following the character as it levels. Maximum
hit points, speed and size are worked out from the class and species in the
SRD content pack, so they are imported only when the sheet would get them
wrong: a class or species the SRD lacks, rolled hit points, the Tough feat, a
monk's movement.

Standard library only. The one request it makes is for the portrait, and only
from D&D Beyond's own host.
"""

import base64
import html
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "grimoire-dndbeyond-import/1.0"
PORTRAIT_HOSTS = {"www.dndbeyond.com", "dndbeyond.com"}
MAX_PORTRAIT_BYTES = 5 * 1024 * 1024

STAT_BY_ID = {
    1: "strength",
    2: "dexterity",
    3: "constitution",
    4: "intelligence",
    5: "wisdom",
    6: "charisma",
}

STAT_SCORE_SUBTYPE = {f"{name}-score": name for name in STAT_BY_ID.values()}
SAVE_SUBTYPE = {f"{name}-saving-throws": f"{name}_save_prof" for name in STAT_BY_ID.values()}

SKILL_CANON = {
    "acrobatics": "Acrobatics",
    "animal-handling": "Animal Handling",
    "arcana": "Arcana",
    "athletics": "Athletics",
    "deception": "Deception",
    "history": "History",
    "insight": "Insight",
    "intimidation": "Intimidation",
    "investigation": "Investigation",
    "medicine": "Medicine",
    "nature": "Nature",
    "perception": "Perception",
    "performance": "Performance",
    "persuasion": "Persuasion",
    "religion": "Religion",
    "sleight-of-hand": "Sleight of Hand",
    "stealth": "Stealth",
    "survival": "Survival",
}

# The sheet's alignment options; D&D Beyond calls true neutral "Neutral".
ALIGNMENT_BY_ID = {
    1: "Lawful Good",
    2: "Neutral Good",
    3: "Chaotic Good",
    4: "Lawful Neutral",
    5: "True Neutral",
    6: "Chaotic Neutral",
    7: "Lawful Evil",
    8: "Neutral Evil",
    9: "Chaotic Evil",
}

ARMOR_TRAINING = {
    "light-armor": "armor_light",
    "medium-armor": "armor_medium",
    "heavy-armor": "armor_heavy",
    "shields": "armor_shields",
}

# Builder scaffolding rather than features a player reads.
SKIP_CLASS_FEATURES = {"hit points", "proficiencies", "equipment"}
SKIP_RACIAL_TRAITS = {"ability score increases", "languages", "size", "speed"}

# What the sheet can work out from the SRD 5.2 pack: a class's hit die, and a
# species' speed and size. Anything else has to come from D&D Beyond.
SRD_HIT_DIE = {
    "barbarian": 12,
    "bard": 8,
    "cleric": 8,
    "druid": 8,
    "fighter": 10,
    "monk": 8,
    "paladin": 10,
    "ranger": 10,
    "rogue": 8,
    "sorcerer": 6,
    "warlock": 8,
    "wizard": 6,
}
SRD_SPECIES = {
    "dragonborn": (30, "Medium"),
    "dwarf": (30, "Medium"),
    "elf": (30, "Medium"),
    "gnome": (30, "Small"),
    "goliath": (35, "Medium"),
    "halfling": (30, "Small"),
    "human": (30, "Medium or Small"),
    "orc": (30, "Medium"),
    "tiefling": (30, "Medium or Small"),
}

_TAG = re.compile(r"<[^>]+>")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")


# --- helpers -----------------------------------------------------------------


def strip_html(value):
    if not value:
        return ""
    text = html.unescape(_TAG.sub("", value))
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_SPACE.sub("\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ability_mod(score):
    return math.floor((score - 10) / 2)


def modifiers(data):
    groups = data.get("modifiers") or {}
    if not isinstance(groups, dict):
        return
    for items in groups.values():
        for mod in items or []:
            if isinstance(mod, dict):
                yield mod


def kind(mod):
    return (mod.get("type") or "").lower(), (mod.get("subType") or "").lower()


def entry(name, description="", per=None):
    """A catalog value: matched by name against the installed content, kept
    with its text as a custom entry when nothing matches."""
    out = {"name": name}
    if description:
        out["description"] = description
    if per:
        out["per"] = per
    return out


def definition_text(defn):
    return strip_html(defn.get("description") or defn.get("snippet") or "")


# --- what the player has ------------------------------------------------------


def ability_scores(data):
    scores = {name: 10 for name in STAT_BY_ID.values()}
    for row in data.get("stats") or []:
        name = STAT_BY_ID.get(row.get("id"))
        if name and row.get("value") is not None:
            scores[name] = int(row["value"])
    for row in data.get("bonusStats") or []:
        name = STAT_BY_ID.get(row.get("id"))
        if name and row.get("value") is not None:
            scores[name] += int(row["value"])
    for mod in modifiers(data):
        mtype, subtype = kind(mod)
        stat = STAT_SCORE_SUBTYPE.get(subtype)
        if mtype == "bonus" and stat and mod.get("value") is not None:
            scores[stat] += int(mod["value"])
    for row in data.get("overrideStats") or []:
        name = STAT_BY_ID.get(row.get("id"))
        if name and row.get("value") is not None:
            scores[name] = int(row["value"])
    return scores


def class_levels(data):
    """(name, level, subclass) for each class, in D&D Beyond's order."""
    out = []
    for klass in data.get("classes") or []:
        name = ((klass.get("definition") or {}).get("name") or "").strip()
        if name:
            subclass = ((klass.get("subclassDefinition") or {}).get("name") or "").strip()
            out.append((name, int(klass.get("level") or 0), subclass))
    return out


def proficiencies(data):
    found = {
        "skill_profs": [],
        "skill_expertise": [],
        "skill_half_profs": [],
        "saves": [],
        "armor": set(),
        "weapons": [],
        "tools": [],
        "languages": ["Common"],
    }

    def add(key, value):
        if value and value not in found[key]:
            found[key].append(value)

    for mod in modifiers(data):
        mtype, subtype = kind(mod)
        label = (mod.get("friendlySubtypeName") or mod.get("friendlyTypeName") or "").strip()
        if mtype == "language":
            lang = label or subtype.replace("-", " ").title()
            if lang.lower() not in {x.lower() for x in found["languages"]}:
                found["languages"].append(lang)
            continue
        if subtype in SAVE_SUBTYPE and mtype in ("proficiency", "expertise"):
            add("saves", SAVE_SUBTYPE[subtype])
            continue
        skill = SKILL_CANON.get(subtype)
        if skill:
            if mtype == "expertise":
                add("skill_expertise", skill)
                add("skill_profs", skill)
            elif mtype == "half-proficiency":
                add("skill_half_profs", skill)
            elif mtype == "proficiency":
                add("skill_profs", skill)
            continue
        if mtype != "proficiency":
            continue
        if subtype in ARMOR_TRAINING:
            found["armor"].add(ARMOR_TRAINING[subtype])
            continue
        label = label or subtype.replace("-", " ").title()
        if "weapon" in subtype:
            add("weapons", label)
        elif "tool" in subtype or subtype.endswith("-kit") or "supplies" in subtype:
            add("tools", label)

    for custom in data.get("customProficiencies") or []:
        add("tools", (custom.get("name") or "").strip())
    return found


def hit_points(data, scores, level):
    """(maximum, current, temporary) as D&D Beyond works them out."""
    if data.get("overrideHitPoints") is not None:
        maximum = int(data["overrideHitPoints"])
    else:
        maximum = int(data.get("baseHitPoints") or 0) + int(data.get("bonusHitPoints") or 0)
        maximum += ability_mod(scores["constitution"]) * max(level, 0)
        for mod in modifiers(data):
            mtype, subtype = kind(mod)
            if mtype != "bonus":
                continue
            if subtype == "hit-points":
                maximum += int(mod.get("value") or 0)
            elif subtype == "hit-points-per-level":
                maximum += int(mod.get("value") or 0) * max(level, 0)
    maximum = max(maximum, 0)
    current = max(maximum - int(data.get("removedHitPoints") or 0), 0)
    return maximum, current, max(int(data.get("temporaryHitPoints") or 0), 0)


def sheet_hit_points(levels, scores):
    """The sheet's own maximum - the class's average per level - or None when
    it cannot work one out: no class, several, or one the SRD lacks."""
    if len(levels) != 1:
        return None
    die = SRD_HIT_DIE.get(levels[0][0].lower())
    if not die:
        return None
    con = ability_mod(scores["constitution"])
    return die + con + (levels[0][1] - 1) * (die // 2 + 1 + con)


def walk_speed(data):
    race = data.get("race") or {}
    speed = int(((race.get("weightSpeeds") or {}).get("normal") or {}).get("walk") or 30)
    for mod in modifiers(data):
        mtype, subtype = kind(mod)
        if mtype == "set" and subtype in ("innate-speed-walking", "unarmored-movement"):
            if mod.get("value") is not None:
                speed = int(mod["value"])
    return speed


def background_name(data):
    background = data.get("background") or {}
    custom = background.get("customBackground") or {}
    if isinstance(custom, dict) and (custom.get("name") or "").strip():
        return custom["name"].strip()
    return ((background.get("definition") or {}).get("name") or "").strip()


def features(data, levels):
    out = []
    seen = set()
    for klass in data.get("classes") or []:
        class_level = int(klass.get("level") or 0)
        for source in (klass.get("definition") or {}, klass.get("subclassDefinition") or {}):
            for feat in source.get("classFeatures") or []:
                name = (feat.get("name") or "").strip()
                if not name or name.lower() in SKIP_CLASS_FEATURES or feat.get("hideInSheet"):
                    continue
                if int(feat.get("requiredLevel") or 1) > class_level:
                    continue
                out.append(entry(name, definition_text(feat)))
                seen.add(name.lower())

    # Some features only show up as actions ("Lay on Hands Pool" is covered by
    # the class feature "Lay on Hands", so overlapping names are skipped).
    def covered(name):
        low = name.lower()
        return any(low.startswith(known) or known.startswith(low) for known in seen)

    actions = data.get("actions") if isinstance(data.get("actions"), dict) else {}
    for group in actions.values():
        for action in group or []:
            name = (action.get("name") or "").strip()
            if name and not covered(name):
                out.append(entry(name, definition_text(action)))
                seen.add(name.lower())
    return out


def species_traits(race):
    out = []
    for trait in race.get("racialTraits") or []:
        defn = trait.get("definition") or {}
        name = (defn.get("name") or "").strip()
        if name and name.lower() not in SKIP_RACIAL_TRAITS and not defn.get("hideInSheet"):
            out.append(entry(name, definition_text(defn)))
    return out


def gear(data):
    """(equipment, magic items, attacks, holding an equipped shield)."""
    equipment, magic_items, attacks = [], [], []
    shield = False
    for item in data.get("inventory") or []:
        defn = item.get("definition") or {}
        name = (defn.get("name") or "").strip()
        if not name:
            continue
        equipped = bool(item.get("equipped"))
        description = strip_html(defn.get("description") or "")
        armor_type = (defn.get("type") or "").lower()
        if equipped and ("shield" in armor_type or name.lower() == "shield"):
            shield = True

        if defn.get("filterType") == "Weapon":
            damage = defn.get("damage") or {}
            dealt = f"{(damage.get('diceString') or '').strip()} {(defn.get('damageType') or '').strip()}"
            notes = [", ".join(p["name"] for p in defn.get("properties") or [] if p.get("name"))]
            reach, long_reach = defn.get("range"), defn.get("longRange")
            if reach and long_reach and long_reach != reach:
                notes.append(f"range {reach}/{long_reach}")
            elif reach and int(reach) > 5:
                notes.append(f"range {reach}")
            attacks.append(
                {"name": name, "damage": dealt.strip(), "notes": "; ".join(n for n in notes if n)}
            )

        rarity = (defn.get("rarity") or "").strip().lower()
        if defn.get("magic") or rarity not in ("", "common", "none", "varies"):
            magic_items.append(entry(name, description, {"attuned": bool(item.get("isAttuned"))}))
        else:
            per = {"qty": max(int(item.get("quantity") or 1), 1), "equipped": equipped}
            equipment.append(entry(name, description, per))

    for custom in data.get("customItems") or []:
        name = (custom.get("name") or "").strip()
        if name:
            per = {"qty": max(int(custom.get("quantity") or 1), 1), "equipped": False}
            equipment.append(entry(name, strip_html(custom.get("description") or ""), per))
    return equipment, magic_items, attacks, shield


def spells(data):
    out, seen = [], set()

    def add(spell, prepared):
        name = ((spell.get("definition") or {}).get("name") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(entry(name, per={"prepared": prepared}))

    for group in data.get("classSpells") or []:
        for spell in group.get("spells") or []:
            add(spell, bool(spell.get("prepared") or spell.get("alwaysPrepared")))
    # Spells from a species, a feat or an item are always to hand.
    other = data.get("spells") if isinstance(data.get("spells"), dict) else {}
    for group in other.values():
        for spell in group or []:
            add(spell, True)
    return out


def portrait(data):
    """The avatar as a data URL, at full size rather than D&D Beyond's
    thumbnail. Only fetched from D&D Beyond itself."""
    url = (data.get("avatarUrl") or "").strip()
    if not url:
        return None
    url = re.sub(r"/avatars/thumbnails/(\d+)/(\d+)/\d+/\d+/", r"/avatars/\1/\2/", url)
    if urllib.parse.urlparse(url).hostname not in PORTRAIT_HOSTS:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            mime = (response.headers.get_content_type() or "").lower()
            body = response.read(MAX_PORTRAIT_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        return None
    if len(body) > MAX_PORTRAIT_BYTES:
        return None
    return f"data:{mime};base64,{base64.b64encode(body).decode()}"


# --- the answer ---------------------------------------------------------------


def convert(data, fetch_portrait=True):
    scores = ability_scores(data)
    levels = class_levels(data)
    level = sum(lv for _, lv, _ in levels)
    profs = proficiencies(data)
    maximum, current, temporary = hit_points(data, scores, level)
    equipment, magic_items, attacks, shield = gear(data)
    race = data.get("race") or {}

    fields = {
        "hero_name": (data.get("name") or "").strip(),
        "level": level or None,
        "xp": data.get("currentXp"),
        "alignment": ALIGNMENT_BY_ID.get(data.get("alignmentId") or 0),
        "hp_current": current,
        "hp_temp": temporary,
        "heroic_inspiration": bool(data.get("inspiration")),
        "skill_profs": profs["skill_profs"],
        "skill_expertise": profs["skill_expertise"],
        "skill_half_profs": profs["skill_half_profs"],
        "weapon_training": "; ".join(profs["weapons"]),
        "tool_training": "; ".join(profs["tools"]),
        "languages": ", ".join(profs["languages"]),
        "shield": shield,
        "attacks": attacks,
        "features": features(data, levels),
        "feats": [
            entry(name, definition_text(defn))
            for defn in ((f.get("definition") or {}) for f in data.get("feats") or [])
            for name in [(defn.get("name") or "").strip()]
            if name
        ],
        "species_traits": species_traits(race),
        "equipment": equipment,
        "magic_items": magic_items,
        "spells": spells(data),
    }
    fields.update(scores)
    for save in profs["saves"]:
        fields[save] = True
    for flag in profs["armor"]:
        fields[flag] = True

    # Left to the sheet's formulas when they give the same answer, so they
    # keep following the character; imported when they would not.
    if sheet_hit_points(levels, scores) != maximum:
        fields["hp_max"] = maximum
    race_name = (race.get("fullName") or race.get("baseName") or "").strip()
    speed = walk_speed(data)
    size = (race.get("size") or "").strip()
    srd_speed, srd_size = SRD_SPECIES.get(race_name.lower(), (None, None))
    if speed != srd_speed:
        fields["speed"] = speed
    if size and size != srd_size:
        fields["size"] = size

    death = data.get("deathSaves") or {}
    for n in range(1, 4):
        if int(death.get("successCount") or 0) >= n:
            fields[f"death_success_{n}"] = True
        if int(death.get("failCount") or 0) >= n:
            fields[f"death_failure_{n}"] = True

    # The sheet holds one class: the highest-levelled, with the first subclass
    # any class has. The full split goes in the notes.
    if levels:
        fields["klass"] = entry(max(levels, key=lambda row: row[1])[0])
        subclass = next((sub for _, _, sub in levels if sub), None)
        fields["subclass"] = entry(subclass) if subclass else None
    if race_name:
        fields["species"] = entry(race_name)
    background = background_name(data)
    if background:
        fields["background"] = entry(background)

    for key, currency in (("gp", "gp"), ("sp", "sp"), ("cp", "cp"), ("ep", "ep"), ("pp", "pp")):
        fields[key] = int((data.get("currencies") or {}).get(currency) or 0)

    look = [
        f"{label}: {str(data[key]).strip()}"
        for key, label in (
            ("gender", "Gender"),
            ("age", "Age"),
            ("height", "Height"),
            ("weight", "Weight"),
            ("eyes", "Eyes"),
            ("hair", "Hair"),
            ("skin", "Skin"),
        )
        if data.get(key) is not None and str(data[key]).strip()
    ]
    fields["appearance"] = "; ".join(look)

    notes = data.get("notes") if isinstance(data.get("notes"), dict) else {}
    traits = data.get("traits") if isinstance(data.get("traits"), dict) else {}
    story = [strip_html(notes.get("backstory") or "")]
    for key, label in (
        ("personalityTraits", "Personality"),
        ("ideals", "Ideals"),
        ("bonds", "Bonds"),
        ("flaws", "Flaws"),
    ):
        text = strip_html(traits.get(key) or "")
        if text:
            story.append(f"{label}:\n{text}")
    fields["backstory"] = "\n\n".join(p for p in story if p)

    extra = []
    if len(levels) > 1:
        extra.append("Class levels: " + ", ".join(f"{name} {lv}" for name, lv, _ in levels) + ".")
    for key, label in (
        ("organizations", "Organizations"),
        ("allies", "Allies"),
        ("enemies", "Enemies"),
        ("personalPossessions", "Personal possessions"),
        ("otherNotes", "Other notes"),
    ):
        text = strip_html(notes.get(key) or "")
        if text:
            extra.append(f"{label}:\n{text}")
    fields["notes"] = "\n\n".join(extra)

    answer = {
        "name": fields["hero_name"],
        "fields": {k: v for k, v in fields.items() if v not in (None, "", [])},
    }
    picture = portrait(data) if fetch_portrait else None
    if picture:
        answer["portrait"] = picture
    return answer


def main():
    request = json.load(sys.stdin)
    if request.get("action") != "import":
        answer = {"error": f"unknown action: {request.get('action')}"}
    else:
        document = request.get("document")
        if not isinstance(document, dict) or not document.get("id"):
            answer = {"error": "That is not a D&D Beyond character."}
        else:
            try:
                answer = convert(document)
            except (KeyError, TypeError, ValueError, AttributeError):
                # D&D Beyond changes its JSON without notice; say so rather
                # than crash.
                answer = {"error": "Couldn't read that D&D Beyond character - its format may have changed."}
    json.dump(answer, sys.stdout)


if __name__ == "__main__":
    main()
