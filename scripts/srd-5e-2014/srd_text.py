"""The SRD 5.1 itself, read from its PDF: the authority for the dnd-5e-srd-5-1 pack.

The SRD (https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf) decides
what the pack may hold and how it is worded. import_open5e.py takes its
structure from Open5e's fixtures and everything checkable from here:

- the class spell lists ("Spell Lists") - Open5e folds subclass bonus spells into
  them and leaves the Paladin off every spell;
- each spell's header - Open5e drops the area from a range of Self ("Self
  (15-foot cone)") and the trigger from a reaction's casting time;
- the equipment tables - Open5e prices single arrows and adds gear of its own;
- each monster's stat block header - size, type and tags, armor class, senses,
  challenge - which Open5e keeps without the tags ("humanoid (goblinoid)");
- the wording of every description, through `Srd.reword`: Open5e drops dashes,
  lower-cases ability names and adds sentences the SRD does not have. A
  monster's traits and actions are reworded against its own stat block, a
  `Wording` of its own.

`Wording` is shared with the SRD 5.2 importer (../srd-5e/srd52.py).

Needs PyMuPDF (pip install pymupdf).
"""
from __future__ import annotations

import collections
import difflib
import pathlib
import re
import sys

CLASSES = ["Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Warlock", "Wizard"]


def text_of(pdf: pathlib.Path) -> str:
    import pymupdf

    doc = pymupdf.open(pdf)
    raw = "\n".join(page.get_text("text") for page in doc)
    # The PDF draws hyphens as runs of soft and non-breaking hyphens, and
    # spaces as tabs; page furniture interrupts text that crosses a page.
    raw = re.sub(r"[\u00ad\u2010\u2011\u2012]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw)
    raw = re.sub(r"\s+", " ", raw)
    raw = re.sub(r" ?System Reference Document 5\.1 \d+ ", " ", raw)
    # A hyphenated word broken over a line keeps a stray space: "mud- filled".
    raw = re.sub(r"(\w)- (\w)", r"\1-\2", raw)
    raw = re.sub(r"(\w)— (\w)", r"\1—\2", raw)
    return raw.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')


def between(text: str, start: str, end: str) -> str:
    begin = text.index(start) + len(start)
    return text[begin : text.index(end, begin)]


# --- spell lists ---------------------------------------------------------------


def spell_lists(text: str, spell_names: list[str]) -> dict[str, list[str]]:
    """Each class's spells, matched against the spell names the SRD describes.

    The list prints names run together ("Cure Wounds Detect Magic"), so names
    are matched longest first and removed as they are found.
    """
    section = between(text, "Spell Lists ", "Spell Descriptions")
    parts = re.split(r"\b(" + "|".join(CLASSES) + r") Spells ", section)
    names = sorted(spell_names, key=len, reverse=True)
    lists = {}
    for index in range(1, len(parts), 2):
        body = re.sub(r"Cantrips \(0 Level\)|\d(?:st|nd|rd|th) Level", " | ", parts[index + 1])
        rest, found = body.lower(), []
        for name in names:
            if name.lower() in rest:
                found.append(name)
                rest = rest.replace(name.lower(), " | ")
        leftover = re.sub(r"[|\s]+", " ", rest).strip()
        if leftover:
            sys.exit(f"{parts[index]} spell list: no spell matches {leftover!r}")
        lists[parts[index]] = sorted(found)
    return lists


def spell_names_described(text: str) -> list[str]:
    """Every spell the SRD describes: a name followed by its level and school line."""
    section = text[text.index("Spell Descriptions") :]
    schools = ["Abjuration", "Conjuration", "Divination", "Enchantment", "Evocation",
               "Illusion", "Necromancy", "Transmutation"]
    # "Acid Arrow 2nd-level evocation", but "Acid Splash Conjuration cantrip".
    levelled = "|".join(s.lower() for s in schools)
    cantrip = "|".join(schools + [s.lower() for s in schools])
    pattern = (
        r"((?:[A-Z][\w'/-]*)(?: (?:[A-Z][\w'/-]*|of|and|or|the|from|with|without|into|on|to|in|via|for|a))*)"
        rf" (?:\d(?:st|nd|rd|th)-level (?:{levelled})|(?:{cantrip}) cantrip)"
    )
    # A heading can run on from the text before it ("Storm Counterspell 3rd-level"
    # after a weather table), so the name is the longest run of its last words
    # that the spell lists also print - every SRD spell is on at least one.
    listed = between(text, "Spell Lists ", "Spell Descriptions").lower()
    names = []
    for match in re.finditer(pattern, section):
        words = match.group(1).split(" ")
        name = next(
            (" ".join(words[i:]) for i in range(len(words)) if " ".join(words[i:]).lower() in listed),
            None,
        )
        if name is None:
            sys.exit(f"spell heading {match.group(1)!r} is on no spell list")
        names.append(name)
    if len(names) != len(set(names)):
        sys.exit("a spell is described twice")
    return names


DURATION = (
    r"(?:Concentration, up to )?(?:Instantaneous|Until dispelled(?: or triggered)?|Special|"
    r"Up to \d+ (?:round|minute|hour|day)s?|\d+ (?:round|minute|hour|day)s?)"
)


def spell_headers(text: str, names: list[str]) -> dict[str, dict]:
    """Each spell's header as the SRD prints it: casting time, range, components,
    duration, and whether it is a ritual. Open5e drops the area from a range of
    Self ("Self (15-foot cone)") and the trigger from a reaction's casting time."""
    section = text[text.index("Spell Descriptions") :]
    headers = {}
    for name in names:
        # "Fire Shield 4th-level evocation" also reads as Shield's heading, so a
        # match that is the tail of a longer spell's name is passed over.
        longer = [n for n in names if n != name and n.endswith(" " + name)]
        pattern = re.compile(
            re.escape(name)
            + r" (?:\d(?:st|nd|rd|th)-level \w+|\w+ cantrip)(?P<ritual> \(ritual\))? "
            # The SRD misprints Contagion's "Components:" as "Component:".
            r"Casting Time: (?P<casting>.+?) Range: (?P<range>.+?) Components?: (?P<components>.+?) "
            rf"Duration: (?P<duration>{DURATION}) "
        )
        match = next(
            (
                m for m in pattern.finditer(section)
                if not any(section[m.start() - len(n) + len(name) : m.start() + len(name)] == n for n in longer)
            ),
            None,
        )
        if not match:
            sys.exit(f"no header found for {name}")
        headers[name] = {
            "casting_time": match.group("casting"),
            "range": match.group("range"),
            "components": match.group("components"),
            "duration": match.group("duration"),
            "ritual": bool(match.group("ritual")),
        }
    return headers


# --- equipment tables ------------------------------------------------------------

COST = r"\d[\d,]* (?:cp|sp|gp)"
WEIGHT = r"(?:\d+ ?½|\d+/\d+|\d+) lb\.(?: \(full\))?|—"

#: Headings printed with no price of their own, above the rows they group:
#: "Arcane focus" then "Crystal 10 gp".
GROUPS = ["Ammunition", "Arcane focus", "Druidic focus", "Holy symbol", "Artisan's tools",
          "Gaming set", "Musical instrument", "Saddle"]


def pounds(weight: str) -> float | int:
    if weight == "—":
        return 0
    value = weight.split(" lb.")[0].replace(" ", "")
    if "/" in value:
        top, bottom = value.split("/")
        return int(top) / int(bottom)
    if value.endswith("½"):
        return int(value[:-1]) + 0.5
    return int(value)


def priced_rows(segment: str, category: str) -> list[dict]:
    """Name / cost / weight rows. A group heading printed before its first row
    ("Arcane focus Crystal 10 gp") is dropped; membership sets the category."""
    rows = []
    pattern = re.compile(
        rf"(?P<name>[A-Z][A-Za-z',\- ]*?(?: \([^)]*\))?) (?P<cost>{COST}) (?P<weight>{WEIGHT})"
    )
    for match in pattern.finditer(segment):
        name = match.group("name").strip()
        for heading in GROUPS:
            if name.startswith(heading + " "):
                name = name[len(heading) + 1 :]
        rows.append(
            {
                "name": name,
                "category": category,
                "cost": coins(match.group("cost")),
                "weight": pounds(match.group("weight")),
            }
        )
    return rows


def coins(cost: str) -> str:
    return re.sub(r" (cp|sp|gp)$", lambda m: " " + m.group(1).upper(), cost)


#: Rows that belong to the heading above them. Everything else ends a group.
GROUP_MEMBERS = {
    "Ammunition": {"Arrows (20)", "Blowgun needles (50)", "Crossbow bolts (20)", "Sling bullets (20)"},
    "Arcane Focus": {"Crystal", "Orb", "Rod", "Staff", "Wand"},
    "Druidic Focus": {"Sprig of mistletoe", "Totem", "Wooden staff", "Yew wand"},
    "Holy Symbol": {"Amulet", "Emblem", "Reliquary"},
    "Artisan's Tools": {
        "Alchemist's supplies", "Brewer's supplies", "Calligrapher's supplies",
        "Carpenter's tools", "Cartographer's tools", "Cobbler's tools", "Cook's utensils",
        "Glassblower's tools", "Jeweler's tools", "Leatherworker's tools", "Mason's tools",
        "Painter's supplies", "Potter's tools", "Smith's tools", "Tinker's tools",
        "Weaver's tools", "Woodcarver's tools",
    },
    "Gaming Set": {"Dice set", "Playing card set"},
    "Musical Instrument": {
        "Bagpipes", "Drum", "Dulcimer", "Flute", "Lute", "Lyre", "Horn", "Pan flute", "Shawm", "Viol",
    },
    "Saddle": {"Exotic", "Military", "Pack", "Riding"},
}


def gear(text: str) -> list[dict]:
    segment = between(text, "Adventuring Gear Item Cost Weight ", "Container Capacity")
    rows = priced_rows(segment, "Adventuring Gear")
    for row in rows:
        for label, members in GROUP_MEMBERS.items():
            if row["name"] in members and label in ("Ammunition", "Arcane Focus", "Druidic Focus", "Holy Symbol"):
                row["category"] = label
    return rows


def tools(text: str) -> list[dict]:
    segment = between(text, "Tools Item Cost Weight ", "Vehicles (land or water)")
    rows = priced_rows(segment, "Tool")
    for row in rows:
        row["category"] = next(
            (label for label, members in GROUP_MEMBERS.items() if row["name"] in members), "Tool"
        )
    return rows


def packs(text: str) -> list[dict]:
    segment = between(text, "might be cheaper than buying the items individually. ", " Tools A tool helps")
    rows = []
    for match in re.finditer(r"([A-Z][a-z]+'s Pack) \((\d+) gp\)\. (.*?)(?= [A-Z][a-z]+'s Pack \(|$)", segment):
        rows.append(
            {
                "name": match.group(1),
                "category": "Equipment Pack",
                "cost": f"{match.group(2)} GP",
                "description": match.group(3).strip(),
            }
        )
    return rows


def mounts(text: str) -> list[dict]:
    segment = between(text, "Mounts and Other Animals Item Cost Speed Carrying Capacity ", " Tack, Harness")
    rows = []
    for match in re.finditer(rf"([A-Z][a-z]+(?:,? [a-z]+)*?) ({COST}) (\d+ ft\.) ([\d,]+ lb\.)", segment):
        rows.append(
            {
                "name": match.group(1),
                "category": "Mount",
                "cost": coins(match.group(2)),
                "description": f"Speed {match.group(3)}, carrying capacity {match.group(4)}",
            }
        )
    return rows


def tack(text: str) -> list[dict]:
    segment = between(text, "Tack, Harness, and Drawn Vehicles Item Cost Weight ", " Waterborne Vehicles")
    rows = priced_rows(segment, "Tack and Harness")
    for row in rows:
        if row["name"] in GROUP_MEMBERS["Saddle"]:
            row["name"] = f"Saddle, {row['name'].lower()}"
        if row["name"] in ("Carriage", "Cart", "Chariot", "Sled", "Wagon"):
            row["category"] = "Vehicle"
        else:
            row["category"] = "Tack and Harness"
    return rows


def waterborne(text: str) -> list[dict]:
    segment = between(text, "Waterborne Vehicles Item Cost Speed ", " Trade Goods")
    rows = []
    for match in re.finditer(rf"([A-Z][a-z]+(?: [a-z]+)?) ({COST}) ([\d½]+ mph)", segment):
        rows.append(
            {
                "name": match.group(1),
                "category": "Vehicle",
                "cost": coins(match.group(2)),
                "description": f"Speed {match.group(3)}",
            }
        )
    return rows


WEAPON_NAMES = [
    "Club", "Dagger", "Greatclub", "Handaxe", "Javelin", "Light hammer", "Mace", "Quarterstaff",
    "Sickle", "Spear", "Crossbow, light", "Dart", "Shortbow", "Sling", "Battleaxe", "Flail",
    "Glaive", "Greataxe", "Greatsword", "Halberd", "Lance", "Longsword", "Maul", "Morningstar",
    "Pike", "Rapier", "Scimitar", "Shortsword", "Trident", "War pick", "Warhammer", "Whip",
    "Blowgun", "Crossbow, hand", "Crossbow, heavy", "Longbow", "Net",
]
WEAPON_KINDS = ["Simple Melee", "Simple Ranged", "Martial Melee", "Martial Ranged"]


def weapons(text: str) -> list[dict]:
    segment = between(text, "Weapons Name Cost Damage Weight Properties ", " Adventuring Gear This section")
    rows, kind = [], None
    names = "|".join(re.escape(n) for n in WEAPON_NAMES)
    kinds = "|".join(WEAPON_KINDS)
    for match in re.finditer(
        rf"(?:(?P<kind>{kinds}) Weapons )?(?P<name>{names}) (?P<cost>{COST}) (?P<damage>\d+d?\d* \w+|—) "
        rf"(?P<weight>{WEIGHT}) ?(?P<props>.*?)(?= (?:{kinds}) Weapons | (?:{names}) {COST} |$)",
        segment,
    ):
        kind = match.group("kind") or kind
        props = match.group("props").strip()
        rows.append(
            {
                "name": match.group("name"),
                "category": "Weapon",
                "weapon_type": f"{kind} Weapon",
                "cost": coins(match.group("cost")),
                "damage": "" if match.group("damage") == "—" else match.group("damage"),
                "weight": pounds(match.group("weight")),
                "properties": "" if props == "—" else props[:1].upper() + props[1:],
            }
        )
    found = [r["name"] for r in rows]
    if found != WEAPON_NAMES:
        sys.exit(f"weapons table: read {found}")
    return rows


ARMOR_NAMES = [
    "Padded", "Leather", "Studded leather", "Hide", "Chain shirt", "Scale mail", "Breastplate",
    "Half plate", "Ring mail", "Chain mail", "Splint", "Plate", "Shield",
]


def armor(text: str) -> list[dict]:
    segment = between(text, "Armor Armor Cost Armor Class (AC) Strength Stealth Weight ", " Getting Into")
    rows, kind = [], None
    names = "|".join(re.escape(n) for n in ARMOR_NAMES)
    for match in re.finditer(
        rf"(?:(?P<kind>Light Armor|Medium Armor|Heavy Armor|Shield) )?(?P<name>{names}) (?P<cost>{COST}) "
        rf"(?P<ac>\+2|\d+(?: \+ Dex modifier(?: \(max 2\))?)?) (?P<str>Str \d+|—) "
        rf"(?P<stealth>Disadvantage|—) (?P<weight>{WEIGHT})",
        segment,
    ):
        kind = match.group("kind") or kind
        rows.append(
            {
                "name": match.group("name"),
                "category": "Shield" if kind == "Shield" else kind,
                "cost": coins(match.group("cost")),
                "armor_class": match.group("ac"),
                "strength": int(match.group("str")[4:]) if match.group("str") != "—" else 0,
                "stealth": "Disadvantage" if match.group("stealth") == "Disadvantage" else "",
                "weight": pounds(match.group("weight")),
            }
        )
    found = [r["name"] for r in rows]
    if found != ARMOR_NAMES:
        sys.exit(f"armor table: read {found}")
    return rows


# --- equipment notes -------------------------------------------------------------

GEAR_NOTES = [
    "Acid", "Alchemist's Fire", "Antitoxin", "Arcane Focus", "Ball Bearings", "Block and Tackle",
    "Book", "Caltrops", "Candle", "Case, Crossbow Bolt", "Case, Map or Scroll", "Chain",
    "Climber's Kit", "Component Pouch", "Crowbar", "Druidic Focus", "Fishing Tackle", "Healer's Kit",
    "Holy Symbol", "Holy Water", "Hunting Trap", "Lamp", "Lantern, Bullseye", "Lantern, Hooded",
    "Lock", "Magnifying Glass", "Manacles", "Mess Kit", "Oil", "Poison, Basic", "Potion of Healing",
    "Pouch", "Quiver", "Ram, Portable", "Rations", "Rope", "Scale, Merchant's", "Spellbook",
    "Spyglass", "Tent", "Tinderbox", "Torch",
]
TOOL_NOTES = [
    "Artisan's Tools", "Disguise Kit", "Forgery Kit", "Gaming Set", "Herbalism Kit",
    "Musical Instrument", "Navigator's Tools", "Poisoner's Kit", "Thieves' Tools",
]
CONTAINERS = [
    "Backpack", "Barrel", "Basket", "Bottle", "Bucket", "Chest", "Flask or tankard",
    "Jug or pitcher", "Pot, iron", "Pouch", "Sack", "Vial", "Waterskin",
]
POISON_TYPES = ["Contact", "Ingested", "Inhaled", "Injury"]


def headed(segment: str, headings: list[str]) -> dict[str, str]:
    """"Acid. As an action..." paragraphs, split at headings the SRD prints in order."""
    pattern = "|".join(re.escape(h) for h in headings)
    parts = re.split(rf"(?:^| )({pattern})\. ", segment)
    notes = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    missing = [h for h in headings if h not in notes]
    if missing:
        sys.exit(f"no SRD note for {missing}")
    return notes


def equipment_notes(text: str) -> dict[str, str]:
    """Every description the SRD gives mundane equipment, keyed by its heading."""
    notes = headed(between(text, "require further explanation. ", " Adventuring Gear Item Cost Weight"), GEAR_NOTES)
    notes.update(headed(between(text, 'See the "Mounts and Vehicles" section. ', " Mounts and Vehicles A good mount"), TOOL_NOTES))
    notes.update(headed(between(text, "Weapons with special rules are described here. ", " Weapons Name Cost"), ["Lance", "Net"]))
    return notes


def capacities(text: str) -> dict[str, str]:
    segment = between(text, "Container Capacity Container Capacity ", " * You can also strap")
    pattern = "|".join(re.escape(c) for c in CONTAINERS)
    parts = re.split(rf"(?:^| )({pattern})\*? ", segment)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def poisons(text: str) -> list[dict]:
    """The SRD's sample poisons: price and type from its table, effect from its text,
    and the rule for how that type of poison is delivered."""
    rules = headed(between(text, "Poisons come in the following four types. ", " Poisons Item Type"), POISON_TYPES)
    table = between(text, "Poisons Item Type Price per Dose ", " Sample Poisons")
    prices = {
        m.group(1).lower(): (m.group(2), coins(m.group(3)))
        for m in re.finditer(rf"([A-Z][a-z' ]+?) ({'|'.join(POISON_TYPES)}) ({COST})", table)
    }
    effects = between(text, "Each type of poison has its own debilitating effects. ", " Magic Items Magic items")
    rows = []
    for m in re.finditer(rf"([A-Z][\w' ]+?) \(({'|'.join(POISON_TYPES)})\)\. (.+?)(?= [A-Z][\w' ]+? \((?:{'|'.join(POISON_TYPES)})\)\. |$)", effects):
        name, kind, effect = m.groups()
        listed_kind, price = prices[name.lower()]
        assert listed_kind == kind, name
        rows.append(
            {
                "name": name,
                "category": "Poison",
                "cost": price,
                "weight": 0,
                "description": f"{kind} poison. {effect}\n\n{kind}. {rules[kind]}",
            }
        )
    if len(rows) != len(prices):
        sys.exit(f"poisons: read {len(rows)} of {len(prices)}")
    return rows


def describe_equipment(text: str, rows: list[dict]) -> None:
    """Give each row the SRD's note for it, and a container its capacity."""
    notes, capacity = equipment_notes(text), capacities(text)
    by_category = {
        "Arcane Focus": "Arcane Focus", "Druidic Focus": "Druidic Focus", "Holy Symbol": "Holy Symbol",
        "Artisan's Tools": "Artisan's Tools", "Gaming Set": "Gaming Set",
        "Musical Instrument": "Musical Instrument",
    }
    lowered = {h.lower(): h for h in notes}
    for row in rows:
        if row.get("description"):
            continue
        name = re.sub(r" \(.*?\)$", "", row["name"]).lower()
        heading = by_category.get(row["category"]) or lowered.get(name) or lowered.get(name.split(",")[0])
        parts = [notes[heading]] if heading else []
        held = capacity.get(row["name"]) or capacity.get(row["name"].split(",")[0])
        if held:
            parts.append(f"Capacity: {held}.")
        if parts:
            row["description"] = "\n\n".join(parts)


# --- magic items -------------------------------------------------------------------

MAGIC_KINDS = r"(?:Armor|Weapon|Wondrous item|Potion|Ring|Rod|Scroll|Staff|Wand)"
RARITY = r"(?:common|uncommon|rare|very rare|legendary|artifact|rarity varies|rarity by figurine|varies)"


def magic_headings(text: str, names: list[str]) -> dict[str, dict]:
    """Each named magic item's heading line as the SRD prints it - "Staff of the
    Python Staff, uncommon (requires attunement by a cleric, druid, or warlock)" -
    and the text under it, up to the next heading."""
    # Through to the end: the artifacts follow the sentient items.
    section = text[text.index("Magic Items A-Z") :]
    found = {}
    for name in names:
        match = re.search(
            rf"(?<![\w,]){re.escape(name)} (?P<kind>{MAGIC_KINDS}(?: \([^)]*\))?), "
            rf"(?P<rarity>{RARITY}(?: \((?!requires)[^)]*\))?(?:(?:,| or|, or) {RARITY}(?: \((?!requires)[^)]*\))?)*)"
            r"(?P<attunement> \(requires attunement(?P<by>[^)]*)\))? ",
            section,
        )
        if match:
            found[name] = {"start": match.start(), "end": match.end(), **match.groupdict()}
    starts = sorted(h["start"] for h in found.values())
    for heading in found.values():
        later = [s for s in starts if s > heading["start"]]
        heading["text"] = section[heading["end"] : later[0] if later else len(section)].strip()
    return found


# --- the whole document ---------------------------------------------------------


def equipment(text: str) -> list[dict]:
    rows = (
        weapons(text) + armor(text) + gear(text) + tools(text) + packs(text)
        + mounts(text) + tack(text) + waterborne(text)
    )
    describe_equipment(text, rows)
    return rows + poisons(text)


# --- monsters ------------------------------------------------------------------

SIZES = "Tiny|Small|Medium|Large|Huge|Gargantuan"

#: Where the SRD files a creature under another name than Open5e's.
SRD_NAMES = {"Deep Gnome (Svirfneblin)": "Gnome, Deep (Svirfneblin)", "Drow": "Elf, Drow"}

#: A stat block's labelled header lines, in the order the SRD prints them.
STAT_LINES = [
    "Armor Class", "Hit Points", "Speed", "Saving Throws", "Skills", "Damage Vulnerabilities",
    "Damage Resistances", "Damage Immunities", "Condition Immunities", "Senses", "Languages",
    "Challenge",
]

SCORES = re.compile(r" ?STR DEX CON INT WIS CHA ((?:\d+ \([+−-]\d+\) ?){6})")


def stat_blocks(text: str, names: list[str]) -> dict[str, dict]:
    """Each named creature's stat block: its header lines, and its text.

    A block runs from its name to the next block's, so `text` holds its traits
    and actions - and any variant the SRD prints after them - for rewording
    against. A name the SRD has no stat block for is left out: Open5e adds a
    few of its own (the Donkey, and each insect swarm variant as a creature).
    """
    starts: dict[str, re.Match] = {}
    # Longest first, so the Hawk is not found inside the Blood Hawk's block.
    for name in sorted(names, key=len, reverse=True):
        printed = re.escape(SRD_NAMES.get(name, name))
        pattern = rf"(?<![\w']){printed} ({SIZES}) ((?:[^,(]|\([^)]*\))+?), (.+?) Armor Class "
        for found in re.finditer(pattern, text):
            if all(not other.start() <= found.start() < other.end() for other in starts.values()):
                starts[name] = found
                break
    order = sorted(starts.values(), key=lambda m: m.start())
    ends = {m.start(): n.start() for m, n in zip(order, order[1:])}
    blocks = {}
    for name, found in starts.items():
        segment = text[found.start() : ends.get(found.start(), len(text))]
        challenge = re.search(r"Challenge ([\d/]+) \(([\d,]+) XP\)", segment)
        header = segment[found.end() - found.start() - len("Armor Class ") : challenge.end()]
        scores = SCORES.search(header)
        header = header[: scores.start()] + header[scores.end() - 1 :]
        labels = "|".join(STAT_LINES)
        lines = dict(re.findall(rf"({labels}) (.+?)(?= (?:{labels}) |$)", header))
        blocks[name] = {
            "size": found.group(1),
            "type": found.group(2),
            "alignment": found.group(3),
            "scores": [int(score) for score in re.findall(r"(\d+) \(", scores.group(1))],
            **{label: lines.get(label, "") for label in STAT_LINES},
            "challenge": challenge.group(1),
            "xp": int(challenge.group(2).replace(",", "")),
            "text": segment,
        }
    return blocks


def _key(token: str) -> str:
    """What two tokens must share to be the same word: letters and digits, any case."""
    return re.sub(r"[^a-z0-9]", "", token.lower()) or token


def _tokens(text: str) -> list[tuple[str, str]]:
    """Words with what follows each, splitting at an em dash so "cleric—performing"
    still lines up with a copy that dropped the dash."""
    return [(m.group(1), " " if m.group(2) else "") for m in re.finditer(r"([^\s—]+|—)(\s*)", text)]


class Wording:
    """A stretch of the SRD's text - the whole document, or one stat block of it -
    that copies of its text are reworded against (see `reword`).

    Matching a copy against one stat block rather than the whole SRD keeps a
    goblin's attack from taking a hobgoblin's numbers. Pass the whole SRD's
    `unmatched` list to have a block report into it, and `entries` for text
    that is a run of named entries, as a stat block is.
    """

    def __init__(self, text: str, unmatched: list[str] | None = None, *, entries: bool = False):
        self.text = text
        self.entries = entries
        # Bullets are layout; the copies being reworded carry their own.
        self._tokens = [t for t in _tokens(self.text) if t[0] != "•"]
        self._keys = [_key(t) for t, _ in self._tokens]
        self._grams: dict[tuple, list[int]] = collections.defaultdict(list)
        for i in range(len(self._keys) - 3):
            self._grams[tuple(self._keys[i : i + 4])].append(i)
        self.unmatched: list[str] = [] if unmatched is None else unmatched

    def reword(
        self, name: str, paragraphs: list[str], keep: set[int] = frozenset(), *, quiet: bool = False
    ) -> list[str] | None:
        """`paragraphs` (one entry's text, from another copy of the SRD) in the
        SRD's own words.

        The paragraphs are aligned word by word against the passage of the SRD
        they come from; each keeps its place but takes the SRD's words, so
        dropped dashes and words come back, case follows the SRD and sentences
        the SRD lacks fall away. The PDF keeps no paragraph breaks, which is
        what the other copy supplies. Paragraphs in `keep` (table rows, which
        the PDF scrambles) take part in the alignment but are returned as given.

        When the entry as a whole will not align - its paragraphs come from
        different places in the SRD - each paragraph is tried on its own.
        Returns None when nothing can be matched; the name is recorded in
        `unmatched`, as is every paragraph left unmatched.
        """
        whole = self._match(paragraphs, keep)
        if whole is not None:
            return whole
        out, missed = [], 0
        for index, paragraph in enumerate(paragraphs):
            if index in keep:
                out.append(paragraph)
                continue
            alone = self._match([paragraph], set())
            if alone is None:
                missed += 1
                out.append(paragraph)
            else:
                out.extend(alone)
        prose = len(paragraphs) - len(keep)
        if missed == prose:
            if not quiet:
                self.unmatched.append(f"{name}: not found in the SRD")
            return None
        if missed:
            self.unmatched.append(f"{name}: {missed} of {prose} paragraphs not found in the SRD")
        return out

    def _match(self, paragraphs: list[str], keep: set[int]) -> list[str] | None:
        """In a stat block the copy's first words are the entry's name, which
        the SRD may follow differently ("Sneak Attack. Once per turn, the"), so
        they are first held to; failing that, matched like any other text."""
        if self.entries:
            named = self._align(paragraphs, keep, named=True)
            if named is not None:
                return named
        return self._align(paragraphs, keep)

    def _align(self, paragraphs: list[str], keep: set[int], *, named: bool = False) -> list[str] | None:
        words: list[str] = []
        owner: list[int] = []
        for index, paragraph in enumerate(paragraphs):
            for token, _ in _tokens(paragraph):
                words.append(_key(token))
                owner.append(index)
        if len(words) < 4:
            return list(paragraphs)
        best = None
        # The likeliest places, best alignment wins: a copy can share a stock
        # sentence with another class's text more closely than with its own.
        for start in self._locate(words):
            window = slice(max(0, start - 20), start + int(len(words) * 1.4) + 40)
            matcher = difflib.SequenceMatcher(None, words, self._keys[window], autojunk=False)
            opcodes = matcher.get_opcodes()
            equal = [op for op in opcodes if op[0] == "equal"]
            if not equal:
                continue
            # Words matched, less the SRD words the match skips over: a passage
            # that shares one stock sentence scores below the passage itself.
            matched = sum(i2 - i1 for _, i1, i2, _, _ in equal)
            score = 2 * matched - (equal[-1][4] - equal[0][3])
            if best is None or score > best[0]:
                best = (score, window, opcodes)
        if best is None:
            return None
        _, window, opcodes = best
        equal = [op for op in opcodes if op[0] == "equal"]
        # A word or two matched in the text either side ("and" in the next
        # entry) is chance, not the passage: the passage is where runs agree.
        while len(equal) > 1 and equal[-1][2] - equal[-1][1] <= 2 and equal[-1][3] - equal[-2][4] >= 3:
            equal.pop()
        while (
            not named and len(equal) > 1 and equal[0][2] - equal[0][1] <= 2
            and equal[1][3] - equal[0][4] >= 3
        ):
            equal.pop(0)
        if not equal:
            return None
        matched = sum(i2 - i1 for _, i1, i2, _, _ in equal)
        first, last = equal[0][3], equal[-1][4]
        # Trust the alignment when most of the copy's words are the SRD's, or
        # when the SRD passage it spans is mostly matched - a copy that adds a
        # sentence of its own ("such as the College of Valor") still lines up.
        if matched < 0.8 * len(words) and matched < 0.8 * (last - first):
            return None
        if matched < 0.5 * len(words):
            return None
        sizes = collections.Counter(owner)
        taken: list[list[int]] = [[] for _ in paragraphs]
        ran_on = False
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "replace" and i1 == 0 and j2 == first and i2 - i1 <= 2:
                # The copy's first word or two, where the SRD has a form of the
                # same word ("Claw" for "Claws"), take the SRD's.
                for k in range(i2 - i1):
                    j = j2 - (i2 - i1) + k
                    if words[k][:3] == self._keys[window.start + j][:3]:
                        taken[owner[k]].append(j)
                continue
            if j2 <= first or tag == "delete":
                continue
            if j1 >= last:
                # Past the last agreed word the SRD runs on into the next entry:
                # take only the rest of the sentence ("ray of frost is."). In a
                # stat block, a copy whose last word agrees has ended where the
                # SRD does - a spell list has no full stop - and what follows is
                # the next entry's name.
                if ran_on or self._tokens[window.start + last - 1][0].endswith((".", "!", "?", ":")):
                    continue
                if self.entries and equal[-1][2] == len(words):
                    continue
                ran_on = True
                for j in range(j1, min(j2, j1 + (i2 - i1) + 3)):
                    taken[owner[max(i1 - 1, 0) if i1 == i2 else i1]].append(j)
                    if self._tokens[window.start + j][0].endswith((".", "!", "?")):
                        break
                else:
                    taken[owner[max(i1 - 1, 0) if i1 == i2 else i1]][:] = [
                        j for j in taken[owner[max(i1 - 1, 0) if i1 == i2 else i1]] if j < last
                    ]
                continue
            if tag == "equal":
                for k in range(i2 - i1):
                    taken[owner[i1 + k]].append(j1 + k)
            elif tag == "replace":
                for j in range(j1, j2):
                    taken[owner[i1 + (j - j1) * (i2 - i1) // (j2 - j1)]].append(j)
            elif tag == "insert":
                # A word or clause the copy dropped comes back; a passage it
                # left out (another variant's paragraph) does not.
                home = owner[max(i1 - 1, 0)]
                if j2 - j1 <= max(8, sizes[home] // 4):
                    for j in range(j1, j2):
                        taken[home].append(j)
        # Every paragraph must be mostly its own words, or the copy is in a
        # different order from the SRD and each paragraph is matched alone.
        agreed = collections.Counter()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal" and first <= j1 and j2 <= last:
                for i in range(i1, i2):
                    agreed[owner[i]] += 1
        for index in range(len(paragraphs)):
            if index in keep or sizes[index] < 6:
                continue
            if agreed[index] < 0.5 * sizes[index]:
                return None
            # Matching stock phrases across several of the SRD's paragraphs - one
            # figurine's text against every figurine - spans far more than it holds.
            if taken[index] and max(taken[index]) - min(taken[index]) > 1.3 * sizes[index] + 8:
                return None
        offset = window.start
        out = []
        for index, paragraph in enumerate(paragraphs):
            if index in keep or not taken[index]:
                out.append(paragraph)
                continue
            js = sorted(taken[index])
            pieces = [self._tokens[offset + j] for j in range(js[0], js[-1] + 1)]
            out.append("".join(token + gap for token, gap in pieces).strip())
        return out

    def _locate(self, words: list[str]) -> list[int]:
        """Where the passage may start: the places most of its word-runs point
        to, likeliest first.

        Votes within a few words of each other count together, since one copy's
        extra or missing word shifts every run after it."""
        votes: collections.Counter = collections.Counter()
        for i in range(max(1, len(words) - 3)):
            for position in self._grams.get(tuple(words[i : i + 4]), ())[:50]:
                votes[position - i] += 1
        if not votes:
            return []

        def near(offset: int) -> int:
            return sum(votes.get(offset + d, 0) for d in range(-6, 7))

        ranked, places = sorted(votes, key=lambda o: (-near(o), -votes[o])), []
        for offset in ranked:
            if all(abs(offset - p) > 30 for p in places):
                places.append(offset)
            if len(places) == 8:
                break
        minimum = 2 if len(words) >= 12 else 1
        return [p for p in places if near(p) >= minimum]


class Srd(Wording):
    """The SRD's text, and the lists, headers, tables and stat blocks read from it."""

    def __init__(self, pdf: pathlib.Path):
        super().__init__(text_of(pdf))
        self.spell_names = spell_names_described(self.text)
        self.spell_lists = spell_lists(self.text, self.spell_names)
        self.spell_headers = spell_headers(self.text, self.spell_names)
        self.equipment = equipment(self.text)
        self.magic_headings = lambda names: magic_headings(self.text, names)
        self.stat_blocks = lambda names: stat_blocks(self.text, names)
