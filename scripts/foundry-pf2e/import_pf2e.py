#!/usr/bin/env python3
"""Build the pf2e-player-core content pack from the Foundry VTT pf2e system.

    git clone --depth 1 --filter=blob:none --sparse https://github.com/foundryvtt/pf2e.git
    cd pf2e && git sparse-checkout set packs/pf2e/ancestries packs/pf2e/ancestry-features \\
        packs/pf2e/heritages packs/pf2e/backgrounds packs/pf2e/classes \\
        packs/pf2e/class-features packs/pf2e/feats packs/pf2e/spells
    python3 scripts/foundry-pf2e/import_pf2e.py /path/to/pf2e

Every Foundry item records the book it comes from and that book's licence. This
takes **Pathfinder Player Core only**, and only items Foundry marks as ORC - the
remastered core book, whose rules Paizo publishes under the ORC License. Other
books are left out even when they are ORC too, the way the Draw Steel pack
takes only its core book.

Foundry's descriptions are HTML with its own inline macros (`@UUID[...]`,
`@Damage[...]`, `@Check[...]`). They become plain paragraphs of text, which is
what a sheet's text fields hold - and **rules text only**. Paizo licenses its
rules under ORC but keeps its world as Reserved Material, so colour text goes:
an ancestry's or class's description becomes a summary of what it gives, a
background, heritage, feature or feat loses its lead-in, and any sentence,
section or entry naming a deity, place, plane or organisation is dropped. Ids are slugs of the names, unique across the
whole pack because a character stores a pick as the id alone.
"""
from __future__ import annotations

import glob
import html
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "content-packs" / "pf2e-player-core"
BOOK = "Pathfinder Player Core"

ATTRIBUTES = {"str": "Strength", "dex": "Dexterity", "con": "Constitution",
              "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"}
SKILLS = ["Acrobatics", "Arcana", "Athletics", "Crafting", "Deception", "Diplomacy",
          "Intimidation", "Medicine", "Nature", "Occultism", "Performance", "Religion",
          "Society", "Stealth", "Survival", "Thievery"]
SIZES = {"tiny": "Tiny", "sm": "Small", "med": "Medium", "lg": "Large", "huge": "Huge",
         "grg": "Gargantuan"}
RANKS = ["Untrained", "Trained", "Expert", "Master", "Legendary"]
ACTIONS = {"1": "[one action]", "2": "[two actions]", "3": "[three actions]",
           "A": "[one action]", "D": "[two actions]", "T": "[three actions]",
           "R": "[reaction]", "F": "[free action]"}
TRADITIONS = {"Bard": "Occult", "Cleric": "Divine", "Druid": "Primal", "Wizard": "Arcane",
              # A witch's tradition comes from their patron, so it is chosen.
              "Witch": ""}


def slug(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def title(text: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in str(text).replace("-", " ").split())


# --- text ------------------------------------------------------------------------


def _uuid(match: re.Match) -> str:
    target, label = match.group(1), match.group(2)
    if "JournalEntry" in target:
        return ""  # a link to Foundry's own rules pages, not part of the text
    if label:
        return label
    return target.rsplit(".", 1)[-1] if "Item." in target else ""


def _damage(match: re.Match) -> str:
    if match.group(2):
        return match.group(2)
    body = match.group(1).split("|")[0]
    # `(2d6+4)[fire]`, or several joined with commas.
    parts = re.findall(r"\(?([^\[\],]+?)\)?\[([^\]]+)\]", body)
    return " plus ".join(f"{amount} {kinds.replace(',', ' ')}" for amount, kinds in parts) or body


def _check(match: re.Match) -> str:
    if match.group(2):
        return match.group(2)
    params = dict(p.split(":", 1) if ":" in p else ("type", p) for p in match.group(1).split("|"))
    kind = title(params.get("type", ""))
    dc = f"DC {params['dc']} " if params.get("dc", "").isdigit() else ""
    basic = "basic " if "basic" in match.group(1).split("|") or params.get("basic") == "true" else ""
    return f"{dc}{basic}{kind}".strip()


def _template(match: re.Match) -> str:
    if match.group(2):
        return match.group(2)
    params = dict(p.split(":", 1) if ":" in p else ("type", p) for p in match.group(1).split("|"))
    return f"{params.get('distance', '')}-foot {params.get('type', '')}".strip("- ")


def text(markup: str | None) -> str:
    """Foundry description HTML as plain paragraphs."""
    s = markup or ""
    s = re.sub(r"@UUID\[([^\]]+)\](?:\{([^}]*)\})?", _uuid, s)
    s = re.sub(r"@Damage\[((?:[^\[\]]|\[[^\]]*\])*)\](?:\{([^}]*)\})?", _damage, s)
    s = re.sub(r"@Check\[([^\]]+)\](?:\{([^}]*)\})?", _check, s)
    s = re.sub(r"@Template\[([^\]]+)\](?:\{([^}]*)\})?", _template, s)
    s = re.sub(r"@\w+\[[^\]]*\](?:\{([^}]*)\})?", lambda m: m.group(1) or "", s)
    s = re.sub(r"\[\[/\w+ ([^\]]*?)(?: #[^\]]*)?\]\](?:\{([^}]*)\})?",
               lambda m: m.group(2) or m.group(1).split("[")[0].strip(), s)
    s = re.sub(r'<span class="action-glyph">([^<]*)</span>',
               lambda m: ACTIONS.get(m.group(1).strip().upper(), m.group(1)), s)
    s = re.sub(r"<hr\s*/?>", "\n\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<li[^>]*>", "\n- ", s)
    s = re.sub(r"</(td|th)>", " | ", s)
    s = re.sub(r"</(p|h\d|ul|ol|tr|table|div|section)>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# --- rules text only ------------------------------------------------------------

#: Paizo's setting: deities, places, planes and organisations. Under the ORC
#: License these are Reserved Material - Paizo licenses the rules, not the world
#: - so no sentence naming one is carried, and no entry named after one.
RESERVED = re.compile(r"\b(" + "|".join([
    # the world and its regions
    "Golarion", "Inner Sea", "Absalom", "Varisia", "Tian Xia", "Avistan", "Garund", "Casmaron",
    "Arcadia", "Cheliax", "Andoran", "Taldor", "Qadira", "Osirion", "Katapesh", "Numeria",
    "Ustalav", "Geb", "Nex", "Mwangi", "Galt", "Isger", "Kyonin", "Highhelm", "Sarkoris",
    "Worldwound", "Lastwall", "Belkzen", "Irrisen", "Mendev", "Brevoy", "Rahadoum", "Thuvia",
    "Jalmer\\w*", "Vudra", "Alkenstar", "Nidal", "Razmir", "Druma", "Starstone",
    # the planes
    "First World", "Netherworld", "Boneyard", "Maelstrom", "Abaddon", "Nirvana", "Elysium",
    "Axis", "Heaven", "Hell", "Abyss", "Shadow Plane", "Plane of \\w+", "Great Beyond",
    # organisations and villains
    "Pathfinder Society", "Magaambya", "Arclords", "Tar-Baphon", "Whispering Tyrant",
    # deities
    "Nethys", "Sarenrae", "Iomedae", "Pharasma", "Desna", "Gozreh", "Abadar", "Cayden Cailean",
    "Erastil", "Gorum", "Irori", "Lamashtu", "Norgorber", "Rovagug", "Torag", "Urgathoa",
    "Zon-Kuthon", "Asmodeus", "Calistria", "Shelyn", "Aroden", "Arazni", "Achaekek", "Alseta",
    "Grandmother Spider", "Besmara", "Groetus", "Milani", "Brigh", "Kurgess", "Ketephys",
    "Dahak", "Apsu", "Zura", "Nocticula", "Ragathiel", "Kazutal", "Tsukiyo", "Hei Feng",
]) + r")\b")

RESERVED_CLAUSE = re.compile(r"\s*,?\s*(?:or|and)\s+(?:the\s+)?" + RESERVED.pattern)

#: Words that mark a sentence as a rule rather than colour. Deliberately broad:
#: a lead-in is trimmed only while none of these appear, so a rule is never cut
#: for want of a keyword - some colour survives instead.
_RULE_WORDS = re.compile(
    r"\b(gain\w*|increas\w*|proficien\w*|bonus\w*|penalt\w*|resist\w*|trait\w*|feats?|"
    r"reactions?|actions?|activit\w*|DC|sav\w+ throws?|saves?|damage|Hit Points|Speed|vision|"
    r"critical\w*|skills?|checks?|spells?|cantrips?|level|ignor\w*|reduc\w*|treat\w*|immun\w*|"
    r"frequency|trigger\w*|requirement\w*|conditions?|can|can't|cannot|must|choose|instead|"
    r"once|per|rounds?|minutes?|hours?|feet|Strike\w*|attack\w*|rolls?|trained|expert|master|"
    r"legendary|familiar|focus|lesson|curriculum|patron skill|spell list|muse|off-guard|target\w*)\b",
    re.IGNORECASE)

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(])")


def _heading(paragraph: str) -> bool:
    return len(paragraph.split()) <= 6 and not paragraph.rstrip().endswith((".", ":", ";", ","))


def scrub(body: str) -> str:
    """Drop every sentence, list item, table row or section that names the setting.

    A section under a heading that names it - Avatar's forms, one per deity -
    goes with its heading, up to the next heading, and an introduction left
    pointing at nothing ("...listed for your deity below:") goes too.
    """
    kept_paragraphs: list[str] = []
    skipping = False
    for paragraph in body.split("\n\n"):
        if _heading(paragraph):
            skipping = bool(RESERVED.search(paragraph))
            if skipping:
                continue
        elif skipping:
            continue
        lines = []
        for line in paragraph.split("\n"):
            if line.startswith("- ") or " | " in line:
                if not RESERVED.search(line):
                    lines.append(line)
                continue
            sentences = [s for s in _SENTENCE.split(line) if not RESERVED.search(s)]
            if sentences:
                lines.append(" ".join(sentences))
        if any(l.strip() for l in lines):
            kept_paragraphs.append("\n".join(lines))
    while kept_paragraphs and kept_paragraphs[-1].rstrip().endswith(":"):
        kept_paragraphs.pop()
    return "\n\n".join(kept_paragraphs)


def scrub_clause(value: str) -> str:
    """A short field loses only the clause naming the setting, not all of it."""
    return RESERVED_CLAUSE.sub("", value).strip()


def without_flavour(markup: str) -> str:
    """Foundry marks an ancestry's or class's colour text as italic paragraphs."""
    return re.sub(r"<p>\s*<em>.*?</em>\s*</p>", "", markup or "", flags=re.S)


def from_first_rule(body: str, marker: str) -> str:
    """A background opens with a paragraph of colour; the rules start at `marker`."""
    paragraphs = body.split("\n\n")
    for index, paragraph in enumerate(paragraphs):
        if marker in paragraph.lower():
            return "\n\n".join(paragraphs[index:])
    return body


def lead_trimmed(body: str, whole_paragraphs: bool = False) -> str:
    """Drop colour from the start, up to the first sentence that states a rule.

    A feat opens with a sentence of colour before its rule; a subclass option
    or heritage may open with a whole paragraph of it.
    """
    paragraphs = body.split("\n\n")
    while whole_paragraphs and len(paragraphs) > 1 and not _RULE_WORDS.search(paragraphs[0]):
        paragraphs.pop(0)
    sentences = _SENTENCE.split(paragraphs[0])
    while len(sentences) > 1 and not _RULE_WORDS.search(sentences[0]):
        sentences.pop(0)
    return "\n\n".join([" ".join(sentences)] + paragraphs[1:])


# --- sources ---------------------------------------------------------------------


def load(source: str, directory: str) -> list[dict]:
    """The Player Core, ORC-licensed items of one Foundry pack directory."""
    items = []
    for path in sorted(glob.glob(os.path.join(source, "packs", "pf2e", directory, "**", "*.json"),
                                 recursive=True)):
        with open(path, encoding="utf-8") as handle:
            item = json.load(handle)
        if not isinstance(item, dict) or "system" not in item:
            continue
        publication = item["system"].get("publication") or {}
        # An entry named after the setting (First World Magic) is Reserved
        # Material in its name, so it is left out whole.
        if RESERVED.search(item["name"]):
            continue
        if publication.get("title") == BOOK and publication.get("license") == "ORC":
            items.append(item)
    return sorted(items, key=lambda i: i["name"])


def item_name(uuid: str) -> str:
    return uuid.rsplit("Item.", 1)[-1]


def boosts(system: dict) -> str:
    parts = []
    for slot in (system.get("boosts") or {}).values():
        values = slot.get("value") or []
        if len(values) >= 6:
            parts.append("Free")
        elif values:
            parts.append(" or ".join(ATTRIBUTES[v] for v in values))
    return ", ".join(parts)


def actions(system: dict) -> str:
    kind = (system.get("actionType") or {}).get("value")
    count = (system.get("actions") or {}).get("value")
    if kind == "action" and count:
        return ACTIONS.get(str(count), "")
    return ACTIONS.get({"reaction": "R", "free": "F"}.get(kind, ""), "")


def traits(system: dict) -> str:
    return ", ".join(title(t) for t in (system.get("traits") or {}).get("value") or [])


def ancestry_rules(system: dict) -> str:
    """What an ancestry gives, in words - its own text is colour only."""
    extra = system.get("additionalLanguages") or {}
    parts = [
        f"Hit Points: {system.get('hp', 0)}. Size: {SIZES.get(system.get('size'), 'Medium')}. "
        f"Speed: {system.get('speed', 25)} feet.",
        f"Attribute boosts: {boosts(system)}."
        + (f" Attribute flaw: {', '.join(ATTRIBUTES[v] for slot in (system.get('flaws') or {}).values() for v in slot.get('value') or [])}."
           if system.get("flaws") else ""),
        "Languages: " + ", ".join(title(l) for l in (system.get("languages") or {}).get("value") or []) + ".",
    ]
    if extra.get("value"):
        parts.append("Additional languages equal to your Intelligence modifier (if it's positive), "
                     "chosen from " + ", ".join(title(l) for l in extra["value"]) + ".")
    if (system.get("vision") or "normal") != "normal":
        parts.append(f"{title(system['vision'])}.")
    parts.append(f"Traits: {traits(system)}.")
    body = rules(without_flavour((system.get("description") or {}).get("value")))
    return "\n\n".join(parts + ([body] if body else []))


def class_rules(name: str, system: dict) -> str:
    """A class's starting numbers and proficiencies, in words."""
    saves = system.get("savingThrows") or {}
    trained = system.get("trainedSkills") or {}
    skills = [title(v) for v in trained.get("value") or []]
    parts = [
        "Key attribute: " + " or ".join(ATTRIBUTES[k] for k in (system.get("keyAbility") or {}).get("value") or []) + ".",
        f"Hit Points: {system.get('hp', 8)} plus your Constitution modifier at each level.",
        f"Perception: {RANKS[system.get('perception', 0)]}. Saving throws: Fortitude "
        f"{RANKS[saves.get('fortitude', 0)]}, Reflex {RANKS[saves.get('reflex', 0)]}, "
        f"Will {RANKS[saves.get('will', 0)]}.",
        "Skills: " + (f"trained in {', '.join(skills)}, and " if skills else "trained in ")
        + f"{trained.get('additional', 0)} more skills plus your Intelligence modifier.",
        "Class DC: Trained.",
    ]
    if system.get("spellcasting"):
        tradition = TRADITIONS.get(name) or "your patron's"
        parts.append(f"Spellcasting: Trained in {tradition.lower()} spell attack modifier and spell DC.")
    body = rules(without_flavour((system.get("description") or {}).get("value")))
    return "\n\n".join(parts + ([body] if body else []))


def rules(markup: str) -> str:
    return scrub(text(markup))


def rarity(system: dict) -> str:
    return title((system.get("traits") or {}).get("rarity") or "common")


def main(source: str) -> None:
    out: dict[str, list[dict]] = {k: [] for k in (
        "ancestry", "heritage", "background", "class", "feature", "feat", "spell")}
    ids: dict[str, str] = {}

    def claim(name: str, kind: str) -> str:
        # First come keeps the plain slug; a later type with the same name -
        # the Shield Block class feature after the Shield Block feat - is
        # suffixed with its type.
        wanted = slug(name)
        entry_id = wanted if wanted not in ids else f"{wanted}-{kind}"
        ids[entry_id] = kind
        return entry_id

    by_name: dict[tuple[str, str], str] = {}

    # Feats first, so a feat keeps the plain id that backgrounds point at.
    for f in load(source, "feats"):
        s = f["system"]
        entry_id = claim(f["name"], "feat")
        by_name[("feat", f["name"])] = entry_id
        out["feat"].append({
            "_id": entry_id, "name": f["name"], "level": (s.get("level") or {}).get("value", 1),
            "category": title(s.get("category", "")), "actions": actions(s), "traits": traits(s),
            "rarity": rarity(s),
            "prerequisites": scrub_clause("; ".join(p.get("value", "") for p in (s.get("prerequisites") or {}).get("value") or [])),
            "description": lead_trimmed(rules(s["description"]["value"]))})

    classes = load(source, "classes")
    class_names = {c["name"].lower(): c["name"] for c in classes}
    for f in load(source, "class-features"):
        s = f["system"]
        entry_id = claim(f["name"], "feature")
        by_name[("feature", f["name"])] = entry_id
        owners = [class_names[t] for t in (s.get("traits") or {}).get("value") or [] if t in class_names]
        out["feature"].append({
            "_id": entry_id, "name": f["name"], "origin": ", ".join(owners),
            "level": (s.get("level") or {}).get("value", 1), "actions": actions(s),
            "traits": traits(s),
            "description": lead_trimmed(rules(s["description"]["value"]), whole_paragraphs=True)})
    for f in load(source, "ancestry-features"):
        s = f["system"]
        entry_id = claim(f["name"], "feature")
        by_name[("feature", f["name"])] = entry_id
        out["feature"].append({
            "_id": entry_id, "name": f["name"], "origin": "Ancestry", "level": 0,
            "actions": actions(s), "traits": traits(s), "description": rules(s["description"]["value"])})

    for sp in load(source, "spells"):
        s = sp["system"]
        kinds = (s.get("traits") or {}).get("value") or []
        area = s.get("area") or {}
        defense = (s.get("defense") or {})
        save = (defense.get("save") or {}) if defense else {}
        duration = s.get("duration") or {}
        out["spell"].append({
            "_id": claim(sp["name"], "spell"), "name": sp["name"],
            # Foundry gives a cantrip level 1 and the cantrip trait; the book
            # lists cantrips apart, so they are rank 0 here.
            "rank": 0 if "cantrip" in kinds else (s.get("level") or {}).get("value", 1),
            "traditions": ", ".join(title(t) for t in (s.get("traits") or {}).get("traditions") or []),
            "traits": traits(s), "rarity": rarity(s),
            "cast": ACTIONS.get(str((s.get("time") or {}).get("value", "")),
                                str((s.get("time") or {}).get("value", ""))),
            "range": (s.get("range") or {}).get("value", "") or "",
            "area": f"{area['value']}-foot {area['type']}" if area and area.get("value") else "",
            "targets": (s.get("target") or {}).get("value", "") or "",
            "defense": (("basic " if save.get("basic") else "") + title(save.get("statistic", ""))).strip()
            if save else ("AC" if defense and defense.get("passive") else ""),
            "duration": ("sustained up to " if duration.get("sustained") else "") + (duration.get("value") or ""),
            "description": rules(s["description"]["value"])})

    for a in load(source, "ancestries"):
        s = a["system"]
        features = [i["name"] for i in (s.get("items") or {}).values()
                    if ("feature", i["name"]) in by_name]
        flaws = [ATTRIBUTES[v] for slot in (s.get("flaws") or {}).values() for v in slot.get("value") or []]
        out["ancestry"].append({
            "_id": claim(a["name"], "ancestry"), "name": a["name"], "hp": s.get("hp", 0),
            "size": SIZES.get(s.get("size"), "Medium"), "speed": s.get("speed", 25),
            "boosts": boosts(s), "flaws": ", ".join(flaws), "rarity": rarity(s),
            "languages": ", ".join(title(l) for l in (s.get("languages") or {}).get("value") or []),
            "vision": title(s.get("vision") or "normal"),
            "feature_ids": ", ".join(by_name[("feature", n)] for n in features),
            "feature_names": ", ".join(n.replace(",", "") for n in features),
            "description": ancestry_rules(s)})

    for h in load(source, "heritages"):
        s = h["system"]
        out["heritage"].append({
            "_id": claim(h["name"], "heritage"), "name": h["name"],
            # A versatile heritage (Changeling, Nephilim) belongs to no one ancestry.
            "ancestry": ((s.get("ancestry") or {}).get("name") or "Versatile"),
            "rarity": rarity(s), "traits": traits(s),
            "description": lead_trimmed(rules(s["description"]["value"]), whole_paragraphs=True)})

    for b in load(source, "backgrounds"):
        s = b["system"]
        automation = s.get("rules") or []
        feats = [item_name(i["uuid"]) for i in (s.get("items") or {}).values()]
        # Some grant their feat by rule instead; one that depends on a choice
        # (Cat Fall or Quick Jump) is named both ways and left for the player.
        granted = [item_name(r["uuid"]) for r in automation if r.get("key") == "GrantItem"]
        conditional = [item_name(r["uuid"]) for r in automation
                       if r.get("key") == "GrantItem" and r.get("predicate")]
        feats += [f for f in granted if f not in conditional]
        feat = next((f for f in feats if ("feat", f) in by_name), feats[0] if feats else "")
        if not feat and conditional:
            feat = " or ".join(conditional)
        either = [title(ch["value"]) for r in automation if r.get("key") == "ChoiceSet"
                  and isinstance(r.get("choices"), list)
                  for ch in r["choices"] if title(ch.get("value", "")) in SKILLS]
        trained = s.get("trainedSkills") or {}
        out["background"].append({
            "_id": claim(b["name"], "background"), "name": b["name"], "boosts": boosts(s),
            "skills": [title(v) for v in trained.get("value") or [] if title(v) in SKILLS],
            "either_skills": either,
            "lore": ", ".join(trained.get("lore") or []), "feat": feat,
            "feat_id": by_name.get(("feat", feat), ""), "rarity": rarity(s),
            "description": from_first_rule(rules(s["description"]["value"]), "attribute boost")})

    for c in classes:
        s = c["system"]
        first = [i["name"] for i in sorted((s.get("items") or {}).values(), key=lambda i: i["name"])
                 if i["level"] == 1 and ("feature", i["name"]) in by_name]
        either = [title(ch["value"]) for r in s.get("rules") or [] if r.get("key") == "ChoiceSet"
                  and isinstance(r.get("choices"), list)
                  for ch in r["choices"] if title(ch.get("value", "")) in SKILLS]
        saves = s.get("savingThrows") or {}
        defenses = s.get("defenses") or {}
        trained = s.get("trainedSkills") or {}
        out["class"].append({
            "_id": claim(c["name"], "class"), "name": c["name"], "hp_per_level": s.get("hp", 8),
            "key_ability": ", ".join(ATTRIBUTES[k] for k in (s.get("keyAbility") or {}).get("value") or []),
            # Ranks as the sheet's proficiency values: trained is 2, legendary 8.
            "perception": 2 * s.get("perception", 0), "fortitude": 2 * saves.get("fortitude", 0),
            "reflex": 2 * saves.get("reflex", 0), "will": 2 * saves.get("will", 0),
            "unarmored": 2 * defenses.get("unarmored", 0), "light_armor": 2 * defenses.get("light", 0),
            "medium_armor": 2 * defenses.get("medium", 0), "heavy_armor": 2 * defenses.get("heavy", 0),
            "armor": ", ".join(f"{RANKS[defenses[k]]} in {k} armor" if k != "unarmored" else
                               f"{RANKS[defenses[k]]} in unarmored defense"
                               for k in ("unarmored", "light", "medium", "heavy") if defenses.get(k)),
            "weapons": ", ".join(f"{RANKS[r]} in {k} " + ("attacks" if k == "unarmed" else "weapons")
                                 for k, r in (s.get("attacks") or {}).items() if isinstance(r, int) and r),
            "trained_skills": [title(v) for v in trained.get("value") or [] if title(v) in SKILLS],
            "either_skills": either,
            "additional_skills": trained.get("additional", 0),
            "skill_options": SKILLS,
            "tradition": TRADITIONS.get(c["name"], "") if s.get("spellcasting") else "",
            "spellcaster": bool(s.get("spellcasting")),
            "feature_ids": ", ".join(by_name[("feature", n)] for n in first),
            "feature_names": ", ".join(n.replace(",", "") for n in first),
            "description": class_rules(c["name"], s)})

    PACK.mkdir(parents=True, exist_ok=True)
    for kind, rows in out.items():
        (PACK / f"{kind}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
        print(f"{kind:11} {len(rows)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
