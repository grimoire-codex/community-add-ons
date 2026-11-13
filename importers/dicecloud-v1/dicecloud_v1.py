#!/usr/bin/env python3
"""DiceCloud v1 -> the dnd-5e-2024 sheet.

Ported from the converter Ian Hunter (@ianfhunter) wrote for Grimoire in
hunter-read/grimoire#552.

A DiceCloud character is not a list of values but a stack of effects -
"base 15", "add constitutionMod", "level * constitutionMod" - so every score,
hit point total and spell slot count has to be worked out, which YAML cannot
do. Effect calculations are read with a small arithmetic evaluator over a
parsed syntax tree; nothing in a character is ever executed.

Where the character comes from:

- a pasted link to a **public** sheet is read the way the DiceCloud website
  reads it, over SockJS's plain-HTTP polling transport (standard library only;
  no websocket package);
- a **private** sheet needs the player's DiceCloud API key, typed into the
  import dialog for that one import and sent only to DiceCloud;
- an uploaded file is a saved copy of DiceCloud's API JSON.

What the sheet works out for itself from the SRD content pack - maximum hit
points, speed, spell slots and spellcasting - is left to it, and imported only
when the sheet would get it wrong: a class the SRD lacks, several classes, or
a total that differs (rolled hit points, the Tough feat).
"""

import ast
import base64
import ipaddress
import json
import math
import random
import re
import socket
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

API_HOST = "v1.dicecloud.com"
API_BASE = f"https://{API_HOST}"
USER_AGENT = "grimoire-dicecloud-v1-import/1.0"
PUBLIC_TIMEOUT = 45
MAX_PORTRAIT_BYTES = 5 * 1024 * 1024

# Bound DiceCloud's ** so a hostile calculation cannot exhaust memory or CPU.
POW_MAX_BASE = 1_000_000
POW_MAX_EXP = 10

STAT_NAMES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")

SKILL_CANON = {
    "acrobatics": "Acrobatics",
    "animalhandling": "Animal Handling",
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
    "sleightofhand": "Sleight of Hand",
    "stealth": "Stealth",
    "survival": "Survival",
}

SAVE_FIELDS = {f"{name}save": f"{name}_save_prof" for name in STAT_NAMES}

# A class's hit die - DiceCloud only knows a class by name.
HIT_DIE = {
    "artificer": 8,
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
# The classes the SRD 5.2 pack has, which the sheet can work things out from.
SRD_CLASSES = set(HIT_DIE) - {"artificer"}
SRD_SPEED = {
    "dragonborn": 30,
    "dwarf": 30,
    "elf": 30,
    "gnome": 30,
    "goliath": 35,
    "halfling": 30,
    "human": 30,
    "orc": 30,
    "tiefling": 30,
}

ALIGNMENTS = {
    "lawful good": "Lawful Good",
    "neutral good": "Neutral Good",
    "chaotic good": "Chaotic Good",
    "lawful neutral": "Lawful Neutral",
    "neutral": "True Neutral",
    "true neutral": "True Neutral",
    "chaotic neutral": "Chaotic Neutral",
    "lawful evil": "Lawful Evil",
    "neutral evil": "Neutral Evil",
    "chaotic evil": "Chaotic Evil",
}

COIN = re.compile(
    r"^((plat(inum)?|gold|electrum|silver|copper)( coins?| pieces?)?|(pp|gp|ep|sp|cp))$", re.I
)
MAGIC_HINTS = (
    "potion of",
    "scroll of",
    "wand of",
    "ring of",
    "cloak of",
    "boots of",
    "amulet",
    "figurine",
    "bag of holding",
)

# What the website subscribes to for one character.
COLLECTIONS = (
    "characters",
    "classes",
    "effects",
    "attacks",
    "spells",
    "spellLists",
    "features",
    "items",
    "proficiencies",
    "notes",
    "containers",
    "conditions",
    "buffs",
)


class ImportFailed(Exception):
    def __init__(self, message, needs_input=None):
        super().__init__(message)
        self.needs_input = needs_input or []


# --- fetching -------------------------------------------------------------------


def fetch_with_key(char_id, api_key):
    """A private sheet, through DiceCloud's API. The key goes to DiceCloud and
    nowhere else, and is never repeated in an error."""
    query = urllib.parse.urlencode({"key": api_key})
    url = f"{API_BASE}/character/{urllib.parse.quote(char_id)}/json?{query}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ImportFailed(
                "DiceCloud did not accept that API key for this character.", ["api_key"]
            ) from None
        if exc.code == 404:
            raise ImportFailed("DiceCloud has no character at that link.") from None
        raise ImportFailed(f"DiceCloud answered {exc.code}.") from None
    except (urllib.error.URLError, OSError) as exc:
        raise ImportFailed(f"Could not reach DiceCloud: {getattr(exc, 'reason', exc)}") from None
    except ValueError:
        raise ImportFailed("DiceCloud's answer was not a character.") from None


def fetch_public(char_id):
    """A public sheet, the way the website reads it: subscribe to the
    character over Meteor's DDP protocol, carried by SockJS's XHR polling
    transport - plain HTTPS POSTs, so the standard library is enough."""
    server = str(random.randint(100, 999))
    session = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    root = f"{API_BASE}/sockjs/{server}/{session}"
    headers = {"User-Agent": USER_AGENT, "Origin": API_BASE, "Content-Type": "text/plain"}

    def post(path, body=b""):
        request = urllib.request.Request(root + path, data=body, method="POST", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")

    def send(message):
        post("/xhr_send", json.dumps([json.dumps(message)]).encode())

    found = {name: {} for name in COLLECTIONS}
    deadline = time.monotonic() + PUBLIC_TIMEOUT
    try:
        if not post("/xhr").startswith("o"):
            raise ImportFailed("DiceCloud did not open a session.")
        send({"msg": "connect", "version": "1", "support": ["1", "pre2", "pre1"]})
        while time.monotonic() < deadline:
            for frame in post("/xhr").splitlines():
                if frame.startswith("c"):
                    raise ImportFailed("DiceCloud closed the connection.")
                if not frame.startswith("a"):
                    continue
                for item in json.loads(frame[1:]):
                    message = json.loads(item)
                    kind = message.get("msg")
                    if kind == "connected":
                        send({"msg": "sub", "id": "char", "name": "singleCharacter", "params": [char_id]})
                    elif kind == "ping":
                        send({"msg": "pong"})
                    elif kind == "nosub" and message.get("id") == "char":
                        raise ImportFailed(
                            "This DiceCloud character is private - paste your DiceCloud API key.",
                            ["api_key"],
                        )
                    elif kind == "added" and message.get("collection") in found:
                        found[message["collection"]][message["id"]] = {
                            "_id": message["id"],
                            **(message.get("fields") or {}),
                        }
                    elif kind == "changed" and message.get("collection") in found:
                        doc = found[message["collection"]].get(message.get("id"))
                        if doc is not None:
                            doc.update(message.get("fields") or {})
                    elif kind == "ready" and "char" in (message.get("subs") or []):
                        data = {name: list(docs.values()) for name, docs in found.items() if docs}
                        if not data.get("characters"):
                            raise ImportFailed(
                                "This DiceCloud character is private - paste your DiceCloud API key.",
                                ["api_key"],
                            )
                        return data
    except (urllib.error.URLError, OSError) as exc:
        raise ImportFailed(f"Could not reach DiceCloud: {getattr(exc, 'reason', exc)}") from None
    except ValueError:
        raise ImportFailed("DiceCloud sent something that was not a character.") from None
    raise ImportFailed("DiceCloud took too long to send the character.")


def fetch_portrait(url):
    """The picture as a data URL. It is an address the player typed, so only
    HTTPS, and only to a public address - never the server's own network."""
    parsed = urllib.parse.urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    try:
        for *_, address in socket.getaddrinfo(parsed.hostname, 443, proto=socket.IPPROTO_TCP):
            if not ipaddress.ip_address(address[0]).is_global:
                return None
        request = urllib.request.Request(parsed.geturl(), headers={"User-Agent": USER_AGENT})
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


# --- effect arithmetic ------------------------------------------------------------


class SafeEval(ast.NodeVisitor):
    """Arithmetic over named stats, for DiceCloud effect calculations. Only
    numbers, + - * / // % **, and a few functions; anything else is refused."""

    FUNCTIONS = {"floor": math.floor, "ceil": math.ceil, "round": round, "min": min, "max": max, "abs": abs}

    def __init__(self, names):
        self.names = {k.lower(): v for k, v in names.items()}

    def eval(self, expr):
        expr = expr.strip().replace("{", "").replace("}", "")
        if not expr:
            raise ValueError("empty expression")
        return self.visit(ast.parse(expr, mode="eval").body)

    def visit_BinOp(self, node):
        left, right = self.visit(node.left), self.visit(node.right)
        op = node.op
        try:
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.FloorDiv):
                return left // right
            if isinstance(op, ast.Mod):
                return left % right
            if isinstance(op, ast.Pow):
                if abs(left) > POW_MAX_BASE or abs(right) > POW_MAX_EXP:
                    raise ValueError("exponentiation out of range")
                result = left**right
                if isinstance(result, complex) or (isinstance(result, float) and not math.isfinite(result)):
                    raise ValueError("non-finite result")
                return result
        except ArithmeticError as exc:
            raise ValueError("arithmetic error") from exc
        raise ValueError(f"unsupported operator {type(op).__name__}")

    def visit_UnaryOp(self, node):
        value = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError("unsupported unary operator")

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError("only simple function calls")
        function = self.FUNCTIONS.get(node.func.id.lower())
        if not function:
            raise ValueError(f"unknown function {node.func.id}")
        return function(*[self.visit(arg) for arg in node.args])

    def visit_Name(self, node):
        key = node.id.lower()
        if key in self.names:
            return self.names[key]
        raise KeyError(node.id)

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("non-numeric constant")

    def generic_visit(self, node):
        raise ValueError(f"unsupported syntax {type(node).__name__}")


def active(doc):
    return bool(doc.get("enabled", True)) and not doc.get("removed", False)


def calculate(data, stat, names, base=0.0):
    """One stat, from its stack of effects."""
    add, mult, floor_at, cap_at = 0.0, 1.0, None, None
    evaluator = SafeEval(names)
    for effect in data.get("effects") or []:
        if not active(effect) or effect.get("stat") != stat:
            continue
        op = effect.get("operation") or "base"
        if op not in ("base", "add", "mul", "min", "max"):
            continue
        if effect.get("value") is not None:
            value = float(effect["value"])
        else:
            try:
                value = float(evaluator.eval(effect.get("calculation") or ""))
            except (ValueError, KeyError, SyntaxError, TypeError, ZeroDivisionError, OverflowError, RecursionError):
                continue
        if op == "base":
            base = max(base, value)
        elif op == "add":
            add += value
        elif op == "mul":
            mult *= value
        elif op == "min":
            floor_at = value if floor_at is None else min(floor_at, value)
        elif op == "max":
            cap_at = value if cap_at is None else max(cap_at, value)
    total = (base + add) * mult
    if floor_at is not None:
        total = max(total, floor_at)
    if cap_at is not None:
        total = min(total, cap_at)
    return total


def class_levels(data):
    levels = defaultdict(int)
    for klass in data.get("classes") or []:
        if not klass.get("removed"):
            levels[(klass.get("name") or "Class").strip()] += int(klass.get("level") or 0)
    return dict(levels)


def stat_names(data, levels):
    """The names a calculation can use: level, each class's level, each score
    and its modifier - worked out in order, as later ones use earlier ones."""
    names = {"level": sum(levels.values()) or 1}
    for klass, level in levels.items():
        names[f"{re.sub(r'[^A-Za-z0-9]', '', klass)}Level"] = level
    for stat in STAT_NAMES:
        score = int(calculate(data, stat, names))
        names[stat] = score
        names[f"{stat}Mod"] = score // 2 - 5
    level = names["level"]
    names["proficiencyBonus"] = int(calculate(data, "proficiencyBonus", names) or (2 + (level - 1) // 4))
    names["dexterityArmor"] = int(calculate(data, "dexterityArmor", names, base=names["dexterityMod"]))
    return names


def adjustment(char, attribute):
    value = char.get(attribute)
    return int(value.get("adjustment") or 0) if isinstance(value, dict) else 0


# --- the answer -----------------------------------------------------------------


def entry(name, description="", per=None):
    out = {"name": name}
    if description:
        out["description"] = description
    if per:
        out["per"] = per
    return out


def proficiencies(data):
    found = {"skill_profs": [], "skill_expertise": [], "skill_half_profs": [], "saves": [],
             "armor": set(), "weapons": [], "tools": [], "languages": []}

    def add(key, value):
        if value not in found[key]:
            found[key].append(value)

    for prof in data.get("proficiencies") or []:
        if not active(prof):
            continue
        name = re.sub(r"\s+", " ", (prof.get("name") or "").strip())
        if not name:
            continue
        compact = name.lower().replace(" ", "")
        kind = (prof.get("type") or "").lower()
        # DiceCloud's proficiency value: 0.5 half, 1 proficient, 2 expertise.
        value = float(prof.get("value") or 1)
        if compact in SAVE_FIELDS:
            add("saves", SAVE_FIELDS[compact])
        elif compact in SKILL_CANON:
            skill = SKILL_CANON[compact]
            if value >= 2:
                add("skill_expertise", skill)
                add("skill_profs", skill)
            elif value < 1:
                add("skill_half_profs", skill)
            else:
                add("skill_profs", skill)
        elif kind == "armor" or "armor" in compact or "shield" in compact:
            for word, flag in (("light", "armor_light"), ("medium", "armor_medium"),
                               ("heavy", "armor_heavy"), ("shield", "armor_shields")):
                if word in compact:
                    found["armor"].add(flag)
        elif kind == "weapon" or "weapon" in compact:
            add("weapons", name)
        elif kind == "tool" or "tool" in compact:
            add("tools", name)
        elif kind == "language":
            add("languages", name)
    return found


def subclass_of(data):
    for feature in data.get("features") or []:
        if not active(feature):
            continue
        name = (feature.get("name") or "").strip()
        oath = re.match(r"\(Oath of ([^)]+)\)\s*$", name)
        if oath:
            return f"Oath of {oath.group(1).strip()}"
        named = re.search(r"subclass[:\s]+(.+)", name, re.I)
        if named:
            return named.group(1).strip()
    return ""


def background_of(char):
    """DiceCloud has no background field; players tend to put its name on the
    first line of the backstory. Returns (background, the rest)."""
    story = (char.get("backstory") or "").strip()
    first, _, rest = story.partition("\n")
    first = first.strip()
    if first and len(first) <= 40 and not first.startswith("#") and "**" not in first:
        return first, rest.lstrip("\n")
    return "", story


def features_and_feats(data):
    features, feats, traits, seen = [], [], [], set()
    for feature in data.get("features") or []:
        if not active(feature):
            continue
        name = (feature.get("name") or "").strip()
        if not name or name == "Base Ability Scores":
            continue
        text = (feature.get("description") or "").strip()
        if feature.get("uses"):
            text = f"{text}\n\nUses: {feature['uses']}".strip()
        low = name.lower()
        if re.match(r"^(?:free\s+)?feat:", low) or "free feat" in low:
            clean = re.sub(r"^(?:Free\s+)?Feat:\s*", "", name, flags=re.I).strip()
            feats.append(entry(clean, text))
            seen.add(clean.lower())
        elif "species" in low or "lineage" in low:
            traits.append(entry(name, text))
        else:
            features.append(entry(name, text))
    # A feat that only exists as an effect's label ("Feat: Telepathic").
    for effect in data.get("effects") or []:
        if not active(effect):
            continue
        match = re.match(r"^(?:Free\s+)?Feat:\s*(.+)$", (effect.get("name") or "").strip(), re.I)
        if match and match.group(1).strip().lower() not in seen:
            seen.add(match.group(1).strip().lower())
            feats.append(entry(match.group(1).strip()))
    return features, feats, traits


def attacks(data, names):
    evaluator = SafeEval(names)

    def resolve(text):
        def one(match):
            try:
                return str(int(evaluator.eval(match.group(1))))
            except Exception:
                return match.group(0)

        return re.sub(r"\{([^{}]+)\}", one, text or "")

    rows = []
    for attack in data.get("attacks") or []:
        if not active(attack):
            continue
        bonus = (attack.get("attackBonus") or "").strip()
        if bonus:
            try:
                value = int(evaluator.eval(bonus))
                bonus = f"+{value}" if value >= 0 else str(value)
            except Exception:
                bonus = bonus.replace("{", "").replace("}", "")
        damage = re.sub(r"\+\s*-", "- ", resolve(attack.get("damage")).replace("{", "").replace("}", ""))
        damage = " ".join(damage.split())
        damage = f"{damage} {(attack.get('damageType') or '').strip()}".strip()
        rows.append({
            "name": (attack.get("name") or "Attack").strip(),
            "bonus": bonus,
            "damage": damage,
            "notes": resolve(attack.get("details")).strip(),
        })
    return rows


def items(data):
    equipment, magic_items, coins = [], [], {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0}
    shield = False
    for item in data.get("items") or []:
        if item.get("removed"):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        quantity = int(item.get("quantity") or 0)
        if COIN.fullmatch(name):
            low = name.lower()
            for prefix, key in (("p", "pp"), ("g", "gp"), ("e", "ep"), ("s", "sp"), ("c", "cp")):
                if low.startswith(prefix):
                    coins[key] += quantity
                    break
            continue
        # DiceCloud's `enabled` on an item is "equipped".
        equipped = bool(item.get("enabled"))
        if name.lower() == "shield" and equipped:
            shield = True
        description = (item.get("description") or "").strip()
        low = name.lower()
        if re.search(r"\+\s*\d", low) or any(hint in low for hint in MAGIC_HINTS):
            magic_items.append(entry(name, description, {"attuned": bool(item.get("attuned"))}))
        else:
            equipment.append(entry(name, description, {"qty": max(quantity, 1), "equipped": equipped}))
    return equipment, magic_items, coins, shield


def convert(data, fetch_picture=True):
    chars = data.get("characters") or []
    if not chars:
        raise ImportFailed("That DiceCloud data has no character in it.")
    char = chars[0]
    levels = class_levels(data)
    names = stat_names(data, levels)
    level = names["level"]
    primary = max(levels.items(), key=lambda kv: kv[1])[0] if levels else ""
    srd_class = len(levels) == 1 and primary.lower() in SRD_CLASSES
    profs = proficiencies(data)
    features, feats, traits = features_and_feats(data)
    equipment, magic_items, coins, shield = items(data)
    background, story = background_of(char)

    fields = {name: names[name] for name in STAT_NAMES}
    fields.update({
        "hero_name": (char.get("name") or "").strip(),
        "level": level,
        "subclass": entry(subclass) if (subclass := subclass_of(data)) else None,
        "alignment": ALIGNMENTS.get((char.get("alignment") or "").strip().lower()),
        "skill_profs": profs["skill_profs"],
        "skill_expertise": profs["skill_expertise"],
        "skill_half_profs": profs["skill_half_profs"],
        "weapon_training": "; ".join(profs["weapons"]),
        "tool_training": "; ".join(profs["tools"]),
        "languages": ", ".join(profs["languages"]),
        "shield": shield,
        "attacks": attacks(data, names),
        "features": features,
        "feats": feats,
        "species_traits": traits,
        "equipment": equipment,
        "magic_items": magic_items,
        "spells": [
            entry(spell["name"].strip(), per={"prepared": spell.get("prepared") in ("prepared", "always")})
            for spell in data.get("spells") or []
            if not spell.get("removed") and (spell.get("name") or "").strip()
        ],
        "appearance": (char.get("description") or "").strip(),
        **coins,
    })
    for save in profs["saves"]:
        fields[save] = True
    for flag in profs["armor"]:
        fields[flag] = True

    maximum = int(calculate(data, "hitPoints", names))
    fields["hp_current"] = max(maximum + adjustment(char, "hitPoints"), 0)
    fields["hp_temp"] = max(int(calculate(data, "tempHP", names)) + adjustment(char, "tempHP"), 0)
    die = HIT_DIE.get(primary.lower(), 8)
    con = names["constitutionMod"]
    average = die + con + (level - 1) * (die // 2 + 1 + con)
    if not srd_class or maximum != average:
        fields["hp_max"] = maximum

    speed = int(calculate(data, "speed", names, base=30))
    race = (char.get("race") or "").strip()
    if speed != SRD_SPEED.get(race.lower()):
        fields["speed"] = speed

    # The sheet's armour class is 10 + Dex + this bonus + 2 for a shield;
    # DiceCloud's resolved total sets the bonus that makes them agree.
    armor = int(calculate(data, "armor", names))
    if armor:
        fields["armor_bonus"] = armor - 10 - names["dexterityMod"] - (2 if shield else 0)

    death = char.get("deathSave") if isinstance(char.get("deathSave"), dict) else {}
    for n in range(1, 4):
        if int(death.get("pass") or 0) >= n:
            fields[f"death_success_{n}"] = True
        if int(death.get("fail") or 0) >= n:
            fields[f"death_failure_{n}"] = True

    # The sheet works out spellcasting from an SRD class; for anything else,
    # DiceCloud's slots and casting ability are all there is.
    slots = {n: int(calculate(data, f"level{n}SpellSlots", names)) for n in range(1, 10)}
    if not srd_class and (any(slots.values()) or fields["spells"]):
        fields["is_caster"] = True
        fields["caster_level"] = level
        ability = None
        for spell_list in data.get("spellLists") or []:
            bonus = (spell_list.get("attackBonus") or "").lower()
            ability = next((a for a in ("charisma", "wisdom", "intelligence") if a in bonus), ability)
        if ability:
            fields["spell_ability"] = ability
        for n, count in slots.items():
            if count:
                fields[f"slots_{n}_total"] = count

    if primary:
        fields["klass"] = entry(primary)
    if race:
        fields["species"] = entry(race)
    if background:
        fields["background"] = entry(background)

    story_parts = [story.strip()]
    for key, label in (("personality", "Personality"), ("ideals", "Ideals"), ("bonds", "Bonds"), ("flaws", "Flaws")):
        text = (char.get(key) or "").strip()
        if text:
            story_parts.append(f"{label}:\n{text}")
    if (char.get("gender") or "").strip():
        story_parts.insert(0, f"Gender: {char['gender'].strip()}")
    fields["backstory"] = "\n\n".join(p for p in story_parts if p)

    notes = []
    if len(levels) > 1:
        notes.append("Class levels: " + ", ".join(f"{n} {lv}" for n, lv in levels.items()) + ".")
    for note in data.get("notes") or []:
        if not note.get("removed") and (note.get("description") or "").strip():
            notes.append(f"{(note.get('name') or 'Note').strip()}:\n{note['description'].strip()}")
    fields["notes"] = "\n\n".join(notes)

    answer = {
        "name": fields["hero_name"],
        "fields": {k: v for k, v in fields.items() if v not in (None, "", [])},
    }
    picture = fetch_portrait(char.get("picture")) if fetch_picture else None
    if picture:
        answer["portrait"] = picture
    return answer


def run(request):
    document = request.get("document")
    if isinstance(document, dict) and document.get("characters"):
        return convert(document)
    char_id = (request.get("identity") or "").strip()
    if not char_id:
        raise ImportFailed("That is not a DiceCloud character.")
    api_key = ((request.get("inputs") or {}).get("api_key") or "").strip()
    data = fetch_with_key(char_id, api_key) if api_key else fetch_public(char_id)
    return convert(data)


def main():
    request = json.load(sys.stdin)
    if request.get("action") != "import":
        answer = {"error": f"unknown action: {request.get('action')}"}
    else:
        try:
            answer = run(request)
        except ImportFailed as exc:
            answer = {"error": str(exc)}
            if exc.needs_input:
                answer["needs_input"] = exc.needs_input
        except (KeyError, TypeError, ValueError, AttributeError):
            answer = {"error": "Couldn't read that DiceCloud character - its format may have changed."}
    json.dump(answer, sys.stdout)


if __name__ == "__main__":
    main()
