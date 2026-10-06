#!/usr/bin/env python3
"""Build the draw-steel-core content pack from a Forgesteel export.

    python3 scripts/forgesteel/import_forgesteel.py /tmp/core.json

Forgesteel (github.com/andyaiken/forgesteel, GPL-3.0) models Draw Steel as
code. `dump.ts` exports its core sourcebook to JSON; this reads that and writes
one file per content type into content-packs/draw-steel-core/, flattening each
rule structure into the text a player reads: a Stamina bonus becomes "+9
Stamina per level", a choice lists its options, an ability's power roll gets
its three tiers.

Nothing here is specific to Grimoire's engine beyond the pack format: every
property it writes is declared by the draw-steel sheet's content types.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACK = ROOT / "content-packs" / "draw-steel-core"
LISTS = ("Crafting", "Exploration", "Interpersonal", "Intrigue", "Lore")


def slug(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def clean(text: str | None) -> str:
    return re.sub(r"\n{3,}", "\n\n", (text or "").strip())


# --- abilities ---------------------------------------------------------------


def distance(parts: list[dict]) -> str:
    out = []
    for d in parts:
        kind, v, v2, within = d["type"], d.get("value"), d.get("value2"), d.get("within")
        if kind == "Self":
            text = "Self"
        elif kind in ("Melee", "Ranged"):
            text = f"{kind} {v}"
        elif kind in ("Burst", "Aura"):
            text = f"{v} {kind.lower()}"
        elif kind == "Cube":
            text = f"{v} cube within {within}"
        elif kind == "Line":
            text = f"{v} x {v2} line within {within}"
        elif kind == "Wall":
            text = f"{v} wall within {within}"
        else:
            text = d.get("special") or kind
        if d.get("qualifier"):
            text += f" ({d['qualifier']})"
        out.append(text)
    return " or ".join(out)


def ability_row(a: dict, origin: str, resource: str = "") -> dict:
    cost = a.get("cost")
    if cost == "signature":
        cost_text = "Signature"
    elif isinstance(cost, int) and cost > 0:
        cost_text = f"{cost} {resource}".strip()
    else:
        cost_text = ""
    roll = next((s["roll"] for s in a["sections"] if s["type"] == "roll"), None)
    effects = []
    for s in a["sections"]:
        if s["type"] == "text":
            effects.append(clean(s["text"]))
        elif s["type"] == "field":
            spend = f" {s['value']}" if s.get("value") else ""
            effects.append(f"**{s['name']}{spend}:** {clean(s['effect'])}")
    row = {
        "_id": slug(f"{origin}-{a['name']}"),
        "name": a["name"],
        "origin": origin,
        "level": a.get("minLevel") or 1,
        "cost": cost_text,
        "type": a["type"]["usage"] + (f" ({a['type']['trigger']})" if a["type"].get("trigger") else ""),
        "keywords": ", ".join(a.get("keywords") or []),
        "distance": distance(a.get("distance") or []),
        "target": a.get("target") or "",
        "power_roll": ("Power Roll + " + " or ".join(roll["characteristic"])) if roll and roll.get("characteristic") else "",
        "tier_1": roll["tier1"] if roll else "",
        "tier_2": roll["tier2"] if roll else "",
        "tier_3": roll["tier3"] if roll else "",
        "effect": "\n\n".join(e for e in effects if e),
        "description": clean(a.get("description")),
    }
    return row


# --- features -----------------------------------------------------------------


def describe(f: dict, resource: str = "") -> str:
    """The text a player reads for one feature, whatever its structure.

    Forgesteel's description usually says the rule in words already; the
    structure is added only when it carries something the words do not (a
    choice's options, a resource's gains) or when there are no words.
    """
    data = f.get("data") or {}
    kind = f["type"]
    text = clean(f.get("description"))
    extra = ""
    if kind == "Bonus":
        per = f" (+{data['valuePerLevel']} per level)" if data.get("valuePerLevel") else ""
        extra = f"+{data.get('value', 0)} {data.get('field')}{per}"
    elif kind == "Characteristic Bonus":
        extra = f"+{data.get('value')} {data.get('characteristic')}"
    elif kind == "Skill Choice":
        named = ", ".join(data.get("options") or [])
        lists = ", ".join(data.get("listOptions") or [])
        pool = " or ".join(x for x in (named, lists and f"the {lists} skill list") if x)
        extra = f"Choose {data.get('count', 1)} skill(s) from {pool}."
    elif kind == "Language Choice":
        extra = f"Choose {data.get('count', 1)} language(s)."
    elif kind == "Perk":
        lists = ", ".join(data.get("lists") or [])
        extra = f"Choose {data.get('count', 1)} perk(s)" + (f" from {lists}." if lists else ".")
    elif kind == "Choice":
        options = [o["feature"] for o in data.get("options") or []]
        extra = "\n".join(f"- **{o['name']}**: {describe(o, resource)}" for o in options)
        return "\n\n".join(x for x in (text, extra) if x)
    elif kind == "Multiple Features":
        extra = "\n\n".join(x for x in (describe(y, resource) for y in data.get("features") or []) if x)
        return "\n\n".join(x for x in (text, extra) if x)
    elif kind == "Ability":
        extra = f"You gain the {data['ability']['name']} ability."
        return "\n\n".join(x for x in (text, extra) if x)
    elif kind == "Class Ability":
        cost = data.get("cost")
        extra = "Choose a signature ability." if cost == "signature" else f"Choose a {cost}-{resource or 'resource'} ability."
    elif kind == "Heroic Resource":
        extra = "\n".join(f"- {g['trigger']}: gain {g['value']}" for g in data.get("gains") or [])
        return "\n\n".join(x for x in (text, extra) if x)
    elif kind == "Domain":
        extra = f"Choose {data.get('count', 1)} domain(s)."
    elif kind == "Kit":
        extra = f"Choose {data.get('count', 1)} kit."
    elif kind in ("Heroic Resource Gain", "Surge Gain"):
        noun = "surges" if kind == "Surge Gain" else (resource or "resource")
        extra = f"{data.get('trigger')}: gain {data.get('value')} {noun}."
        if data.get("condition"):
            extra += f" {data['condition']}"
    elif kind == "Heroic Resource Threshold":
        inner = data.get("feature") or {}
        extra = f"At {data.get('value')} {data.get('resource')}: {describe(inner, resource)}" if inner else ''
    elif kind == "Roll Modifier":
        on = ", ".join((data.get("skills") or []) + (data.get("skillLists") or []) + (data.get("characteristics") or []))
        extra = f"{data.get('modifier')} on {data.get('rollType', 'rolls').lower()}s" + (f" using {on}" if on else "")
        extra += f" ({data['condition'].lower()})." if data.get("condition") else "."
    elif kind in ("Ability Damage", "Ability Distance"):
        what = "damage" if kind == "Ability Damage" else "distance"
        extra = f"+{data.get('value')} {what} on {', '.join(data.get('keywords') or [])} abilities."
    elif kind == "Damage Modifier":
        mods = []
        for m in data.get("modifiers") or []:
            amount = " + ".join([str(m["value"])] * bool(m.get("value")) + list(m.get("valueCharacteristics") or []))
            mods.append(f"{m['damageType']} {m['type'].lower()} {amount}".strip())
        extra = "; ".join(mods) + "."
    elif kind == "Proficiency":
        extra = "Proficiency with " + ", ".join((data.get("weapons") or []) + (data.get("armor") or [])) + "."
    elif kind == "Potency Resistance":
        extra = f"+{data.get('value')} to resist potencies."
    elif kind == "Condition Immunity":
        extra = "Immune to: " + ", ".join(data.get("conditions") or [])
    elif kind == "Speed":
        extra = f"Your speed is {data.get('speed')}."
    elif kind == "Size":
        size = data.get("size") or {}
        extra = f"Your size is {size.get('value')}{size.get('mod', '')}."
    return text or extra


def abilities_in(f: dict) -> list[dict]:
    """Every ability a feature grants, however deeply it is nested."""
    data = f.get("data") or {}
    if f["type"] == "Ability":
        return [data["ability"]]
    if f["type"] == "Multiple Features":
        return [a for x in data.get("features") or [] for a in abilities_in(x)]
    if f["type"] == "Choice":
        return [a for o in data.get("options") or [] for a in abilities_in(o["feature"])]
    return []


def main(source: str) -> None:
    core = json.load(open(source, encoding="utf-8"))
    skills = {s["name"]: s["list"] for s in core["skills"]}
    by_list = {name: sorted(n for n, l in skills.items() if l == name) for name in LISTS}

    def skill_pool(data: dict) -> list[str]:
        pool = set(data.get("options") or [])
        for listed in data.get("listOptions") or []:
            pool.update(by_list.get(listed, []))
        return sorted(pool)

    out: dict[str, list[dict]] = {k: [] for k in (
        "class", "subclass", "ancestry", "trait", "kit", "career", "culture", "domain",
        "perk", "title", "complication", "ability", "feature")}
    abilities: dict[str, dict] = {}

    def add_abilities(f: dict, origin: str, resource: str = "") -> list[dict]:
        rows = []
        for a in abilities_in(f):
            row = ability_row(a, origin, resource)
            abilities.setdefault(row["_id"], row)
            rows.append(row)
        return rows

    def names(rows: list[dict]) -> str:
        # Comma-separated, so a comma inside a name would split it in two.
        return ", ".join(r["name"].replace(",", "") for r in rows)

    def feature_rows(levels: list[dict], origin: str, resource: str) -> list[dict]:
        rows = []
        for level in levels:
            for f in level["features"]:
                if f["type"] == "Bonus" and f["data"]["field"] in ("Stamina", "Recoveries"):
                    continue  # the class's own numbers, which the sheet derives
                add_abilities(f, origin, resource)
                rows.append({"_id": slug(f"{origin}-{level['level']}-{f['name']}"), "name": f["name"],
                             "origin": origin, "level": level["level"],
                             "description": describe(f, resource)})
        out["feature"].extend(rows)
        return rows

    for c in core["classes"]:
        level_one = c["featuresByLevel"][0]["features"]
        resource = next((f["name"] for f in level_one if f["type"] == "Heroic Resource"), "")
        stamina = next((f["data"] for f in level_one if f["type"] == "Bonus" and f["data"]["field"] == "Stamina"), {})
        recov = next((f["data"] for f in level_one if f["type"] == "Bonus" and f["data"]["field"] == "Recoveries"), {})
        skill_choice = next((f["data"] for f in level_one if f["type"] == "Skill Choice"), {})
        features = feature_rows(c["featuresByLevel"], c["name"], resource)
        first = [r for r in features if r["level"] == 1]
        for sc in c["subclasses"]:
            origin = f"{c['name']} ({sc['name']})"
            sub = [r for r in feature_rows(sc["featuresByLevel"], origin, resource) if r["level"] == 1]
            out["subclass"].append({
                "_id": slug(f"{c['name']}-{sc['name']}"), "name": sc["name"], "class": c["name"],
                "description": clean(sc["description"]),
                "feature_ids": ", ".join(r["_id"] for r in sub), "feature_names": names(sub)})
        for a in c["abilities"]:
            row = ability_row(a, c["name"], resource)
            abilities.setdefault(row["_id"], row)
        out["class"].append({
            "_id": slug(c["name"]), "name": c["name"], "description": clean(c["description"]),
            "heroic_resource": resource,
            "primary_characteristics": ", ".join(ch for g in c["primaryCharacteristicsOptions"] for ch in g),
            "stamina": stamina.get("value", 0), "stamina_per_level": stamina.get("valuePerLevel", 0),
            "recoveries": recov.get("value", 0), "subclass_name": c.get("subclassName") or "",
            "skill_choices": skill_choice.get("count", 0), "skill_options": skill_pool(skill_choice),
            # Level 1 only: a pick happens once, and later levels' features
            # are added as the hero reaches them.
            "feature_ids": ", ".join(r["_id"] for r in first), "feature_names": names(first),
        })

    for d in core["domains"]:
        rows = feature_rows(d["featuresByLevel"], f"{d['name']} Domain", "")
        out["domain"].append({"_id": slug(d["name"]), "name": d["name"], "description": "\n\n".join(
            [clean(d["description"])] + [f"**Level {r['level']} - {r['name']}**: {r['description']}" for r in rows])})

    for a in core["ancestries"]:
        signature, size, speed = [], "1M", 5
        for f in a["features"]:
            if f["type"] == "Choice" and f["name"] == "Purchased Traits":
                for o in f["data"]["options"]:
                    t = o["feature"]
                    granted = add_abilities(t, a["name"])
                    out["trait"].append({"_id": slug(f"{a['name']}-{t['name']}"), "name": t["name"],
                                         "ancestry": a["name"], "cost": o["value"], "signature": False,
                                         "description": describe(t),
                                         "ability_ids": ", ".join(r["_id"] for r in granted)})
                continue
            if f["type"] == "Size":
                s = (f["data"] or {}).get("size") or {}
                size = f"{s.get('value')}{s.get('mod', '')}"
            if f["type"] == "Speed":
                speed = (f["data"] or {}).get("speed", 5)
            granted = add_abilities(f, a["name"])
            row = {"_id": slug(f"{a['name']}-{f['name']}"), "name": f["name"], "ancestry": a["name"],
                   "cost": 0, "signature": True, "description": describe(f),
                   "ability_ids": ", ".join(r["_id"] for r in granted)}
            out["trait"].append(row)
            signature.append(row)
        out["ancestry"].append({
            "_id": slug(a["name"]), "name": a["name"], "description": clean(a["description"]),
            "ancestry_points": a.get("ancestryPoints", 3), "size": size, "speed": speed,
            "trait_ids": ", ".join(r["_id"] for r in signature), "trait_names": names(signature),
            # A granted trait's own grants do not fire, so the abilities its
            # signature traits give are listed on the ancestry itself.
            "ability_ids": ", ".join(i for r in signature for i in r["ability_ids"].split(", ") if i),
            "ability_names": ", ".join(abilities[i]["name"].replace(",", "") for r in signature
                                       for i in r["ability_ids"].split(", ") if i)})

    def tiers(d: dict | None) -> str:
        return f"+{d['tier1']}/+{d['tier2']}/+{d['tier3']}" if d else ""

    for k in core["kits"]:
        granted = [r for f in k.get("features") or [] for r in add_abilities(f, f"{k['name']} Kit")]
        out["kit"].append({
            "_id": slug(k["name"]), "name": k["name"], "description": clean(k["description"]),
            "armor": ", ".join(k.get("armor") or []), "weapon": ", ".join(k.get("weapon") or []),
            "stamina": k.get("stamina", 0), "speed": k.get("speed", 0), "stability": k.get("stability", 0),
            "melee_damage": tiers(k.get("meleeDamage")), "ranged_damage": tiers(k.get("rangedDamage")),
            "melee_distance": k.get("meleeDistance", 0), "ranged_distance": k.get("rangedDistance", 0),
            "disengage": k.get("disengage", 0),
            "ability_ids": ", ".join(r["_id"] for r in granted), "ability_names": names(granted)})

    def skill_groups(features: list[dict]) -> dict:
        groups = [f["data"] for f in features if f and f["type"] == "Skill Choice"][:3]
        row: dict = {}
        for i in range(3):
            g = groups[i] if i < len(groups) else {}
            row[f"skill_choices_{i + 1}"] = g.get("count", 0)
            row[f"skill_options_{i + 1}"] = skill_pool(g) if g else []
        return row

    for cr in core["careers"]:
        details = [f"**{f['name']}**: {describe(f)}" for f in cr["features"] if describe(f)]
        inciting = cr.get("incitingIncidents") or {}
        incidents = [f"- **{i['name']}**: {clean(i['description'])}" for i in inciting.get("options", [])]
        out["career"].append({"_id": slug(cr["name"]), "name": cr["name"],
                              "description": "\n\n".join([clean(cr["description"])] + details),
                              "inciting_incidents": "\n".join(incidents), **skill_groups(cr["features"])})

    for cu in core["cultures"]:
        parts = [cu.get(p) for p in ("environment", "organization", "upbringing")]
        out["culture"].append({"_id": slug(cu["name"]), "name": cu["name"],
                               "description": "\n\n".join([clean(cu.get("description"))] +
                                    [f"**{p['name']}**: {describe(p)}" for p in parts if p]),
                               **skill_groups(parts)})

    for p in core["perks"]:
        out["perk"].append({"_id": slug(p["name"]), "name": p["name"], "list": p.get("list", ""),
                            "description": describe(p)})
    for t in core["titles"]:
        for f in t.get("features") or []:
            add_abilities(f, f"{t['name']} (title)")
        benefits = "\n".join(f"- **{f['name']}**: {describe(f)}" for f in t.get("features") or [])
        out["title"].append({"_id": slug(t["name"]), "name": t["name"], "echelon": t.get("echelon", 1),
                             "prerequisites": clean(t.get("prerequisites")),
                             "description": "\n\n".join(x for x in (clean(t.get("description")), benefits) if x)})
    for c in core["complications"]:
        for f in c.get("features") or []:
            add_abilities(f, f"{c['name']} (complication)")
        out["complication"].append({"_id": slug(c["name"]), "name": c["name"],
                                    "description": "\n\n".join([clean(c["description"])] +
                                        [f"**{f['name']}**: {describe(f)}" for f in c.get("features") or []])})
    # A character stores a reference as the id alone, with no content type, so
    # ids must be unique across the whole pack - not just within one file. An
    # ancestry trait and the ability it grants often share a name; the ability
    # gives way.
    taken = {r["_id"] for kind, rows in out.items() for r in rows}
    renamed = {}
    for row in abilities.values():
        if row["_id"] in taken:
            renamed[row["_id"]] = row["_id"] + "-ability"
            row["_id"] = renamed[row["_id"]]
    for rows in out.values():
        for r in rows:
            if r.get("ability_ids"):
                r["ability_ids"] = ", ".join(renamed.get(i, i) for i in r["ability_ids"].split(", "))
    out["ability"] = sorted(abilities.values(), key=lambda r: (r["origin"], r["level"], r["name"]))

    PACK.mkdir(parents=True, exist_ok=True)
    for kind, rows in out.items():
        seen: set = set()
        unique = [r for r in rows if not (r["_id"] in seen or seen.add(r["_id"]))]
        # A sheet's text fields hold plain text, so markdown emphasis - ours
        # and Forge Steel's own - would show as literal asterisks.
        for r in unique:
            for key, value in r.items():
                if isinstance(value, str):
                    r[key] = value.replace("**", "")
        (PACK / f"{kind}.json").write_text(json.dumps(unique, indent=1, ensure_ascii=False) + "\n")
        print(f"{kind:13} {len(unique)}")
    # The sheet's skill options, by list, for pasting into its layout.
    print(json.dumps(by_list))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "core.json")
