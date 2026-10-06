#!/usr/bin/env python3
"""Generate the traveller-2e character sheet and its layout.

    python3 scripts/traveller/build_sheet.py

Writes character-sheets/traveller-2e/traveller-2e.json and traveller-2e.html.
The stylesheet beside them is written by hand.

The sheet follows J. Brannen's Mongoose Traveller 2e character spreadsheet: its
tabs, and the arithmetic in its formulas. Most of that arithmetic is one rule
applied to a hundred and thirty skills - a level, a misc bonus, an unskilled
penalty that Jack-of-All-Trades reduces, and a check DM against each of the six
characteristics - which is why this is a generator and not a hand-kept file.
Change the tables here and run it again, then `scripts/build_index.py`.
"""
from __future__ import annotations

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "character-sheets" / "traveller-2e"

ATTRIBUTION = (
    "The Traveller, 2300AD, Twilight: 2000 and Dark Conspiracy games in all forms are owned "
    "by Mongoose Publishing. Copyright 1977 - 2025 Mongoose Publishing. Traveller is a "
    "registered trademark of Mongoose Publishing. Mongoose Publishing permits web sites and "
    "fanzines for this game, provided it contains this notice, that Mongoose Publishing is "
    "notified, and subject to a withdrawal of permission on 90 days notice. The contents of "
    "this site are for personal, non-commercial use only. Any use of Mongoose Publishing’s "
    "copyrighted material or trademarks anywhere on this web site and its files should not be "
    "viewed as a challenge to those copyrights or trademarks. In addition, any "
    "program/articles/file on this site cannot be republished or distributed without the "
    "consent of the author who contributed it."
)

CHARACTERISTICS = [
    ("str", "strength", "STR", "Strength"),
    ("dex", "dexterity", "DEX", "Dexterity"),
    ("end", "endurance", "END", "Endurance"),
    ("int", "intellect", "INT", "Intellect"),
    ("edu", "education", "EDU", "Education"),
    ("soc", "social", "SOC", "Social Standing"),
]

#: The spreadsheet's four level lists. A skill with specialities is taken at 0
#: and its specialities at 1 or more; Jack-of-All-Trades runs 1 to 3.
LEVELS = ["--", "0", "1", "2", "3", "4", "5", "6", "7", "8"]
SPEC0 = ["--", "0"]
SPEC = ["--", "1", "2", "3", "4", "5", "6", "7", "8"]
JOAT = ["--", "1", "2", "3"]

# (name, specialities, whether a trained speciality makes the rest 0, open slots)
SKILLS_LEFT = [
    ("Admin", [], False, 0),
    ("Advocate", [], False, 0),
    ("Animals", ["Handling", "Training", "Veterinary"], True, 0),
    ("Art", ["Performer", "Holography", "Instrument", "Visual Media", "Write"], True, 0),
    ("Astrogation", [], False, 0),
    ("Athletics", ["Dexterity", "Endurance", "Strength"], True, 0),
    ("Broker", [], False, 0),
    ("Carouse", [], False, 0),
    ("Deception", [], False, 0),
    ("Diplomat", [], False, 0),
    ("Drive", ["Hovercraft", "Mole", "Track", "Walker", "Wheel"], True, 0),
    ("Electronics", ["Comms", "Computers", "Remote Ops", "Sensors"], True, 0),
    ("Engineer", ["J-Drive", "Life Support", "M-Drive", "Power"], True, 0),
    ("Explosives", [], False, 0),
    ("Flyer", ["Airship", "Grav", "Ornithopter", "Rotor", "Wing"], True, 0),
    ("Gambler", [], False, 0),
    ("Gunner", ["Capital", "Ortillery", "Screen", "Turret"], True, 0),
    ("Gun Combat", ["Archaic", "Energy", "Slug"], True, 0),
    ("Heavy Weapons", ["Artillery", "Man-Portable", "Vehicle"], True, 0),
    ("Investigate", [], False, 0),
]
SKILLS_RIGHT = [
    # Languages are named by the player; the first four start as the
    # spreadsheet's, the rest blank.
    ("Language", ["Anglic", "Vilani", "Zdetl", "Oynprith", "", "", "", "", "", ""], True, 10),
    ("Leadership", [], False, 0),
    ("Mechanic", [], False, 0),
    ("Medic", [], False, 0),
    ("Melee", ["Blade", "Bludgeon", "Natural", "Unarmed"], True, 0),
    ("Navigation", [], False, 0),
    ("Persuade", [], False, 0),
    ("Pilot", ["Capital Ships", "Small Craft", "Spacecraft"], True, 0),
    # The spreadsheet does not carry Profession 0 over to its specialities.
    ("Profession", ["Belter", "Biologicals", "Civil Engineering", "Construction",
                    "Hydroponics", "Polymers", "", ""], False, 8),
    ("Recon", [], False, 0),
    ("Science", ["Archaeology", "Astronomy", "Biology", "Chemistry", "Cosmology",
                 "Cybernetics", "Economics", "Genetics", "History", "Linguistics",
                 "Philosophy", "Physics", "Planetology", "Psionicology", "Psychology",
                 "Robotics", "Sophontology", "Xenology"], True, 0),
    ("Seafarer", ["Ocean Ship", "Personal", "Sail", "Submarine"], True, 0),
    ("Stealth", [], False, 0),
    ("Steward", [], False, 0),
    ("Streetwise", [], False, 0),
    ("Survival", [], False, 0),
    ("Tactics", ["Military", "Naval"], True, 0),
    ("Vacc Suit", [], False, 0),
]
CUSTOM_SKILLS = 4

PSIONIC_TALENTS = ["Awareness", "Clairvoyance", "Telekinesis", "Telepathy", "Teleportation"]
PSIONIC_CUSTOM = 2

# Attack skill -> (skill key, characteristic DM formula), the spreadsheet's
# T_AtkSk table: guns use DEX, melee the better of STR and DEX.
ATTACK_SKILLS = [
    ("Athletics (Dexterity)", "athletics_dexterity", "dex_dm"),
    ("Gun Combat (Archaic)", "gun_combat_archaic", "dex_dm"),
    ("Gun Combat (Energy)", "gun_combat_energy", "dex_dm"),
    ("Gun Combat (Slug)", "gun_combat_slug", "dex_dm"),
    ("Heavy Weapons (Man-Portable)", "heavy_weapons_man_portable", "dex_dm"),
    ("Melee (Blade)", "melee_blade", "max(str_dm, dex_dm)"),
    ("Melee (Bludgeon)", "melee_bludgeon", "max(str_dm, dex_dm)"),
    ("Melee (Natural)", "melee_natural", "max(str_dm, dex_dm)"),
    ("Melee (Unarmed)", "melee_unarmed", "max(str_dm, dex_dm)"),
]
WEAPON_SLOTS = 8

VEHICLE_SKILLS = [
    "Drive (Hovercraft)", "Drive (Mole)", "Drive (Track)", "Drive (Walker)", "Drive (Wheel)",
    "Flyer (Airship)", "Flyer (Grav)", "Flyer (Ornithopter)", "Flyer (Rotor)", "Flyer (Wing)",
    "Seafarer (Ocean Ship)", "Seafarer (Personal)", "Seafarer (Sail)", "Seafarer (Submarine)",
]
SPEED_BANDS = ["Stopped", "Idle", "Very Slow", "Slow", "Medium", "High", "Fast", "Very Fast",
               "Subsonic", "Supersonic", "Hypersonic"]
WEAPON_MOUNTS = ["Bay", "Fixed Mount", "Gun Port", "Hard Point", "Large Turret", "Modular Mount",
                 "Pintle Mount", "Pop-Up Mount", "Ring Mount", "Small Turret"]
VEHICLES = 2

# The spreadsheet's T_StdOfLiv: the lowest SOC each suits, and the monthly cost.
STANDARDS = [
    (2, "Very Poor", 400), (4, "Poor", 800), (5, "Low", 1000), (6, "Average", 1200),
    (7, "Good", 1500), (8, "High", 2000), (10, "Very High", 2500), (12, "Rich", 5000),
    (14, "Very Rich", 12000), (15, "Ludicrously Rich", 20000),
]

CREW = ["Captain", "Pilots", "Astrogators", "Engineers", "Maintenance", "Medics", "Gunners",
        "Stewards", "Administrators", "Officers"]

DESCRIPTORS = [
    ("Diplomatic", "Violent"), ("Passive", "Instigating"), ("Cautious", "Reckless"),
    ("Selfless", "Selfish"), ("Trusting", "Suspicious"), ("Logical", "Emotional"),
    ("Optimistic", "Pessimistic"), ("Extroverted", "Introverted"), ("Neat", "Messy"),
    ("Confident", "Shy"), ("Prefers Working", "Prefers Relaxing"),
]
RELATIONS = ["Mother", "Father", "Sibling", "Sibling", "Sibling", "Mentor", "Closest Friend",
             "Love Interest", "Most-Admired"]


def key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


fields: dict = {}
computed: dict = {}
validators: list = []


def field(name: str, **definition) -> str:
    assert name not in fields and name not in computed, name
    fields[name] = definition
    return name


def calc(name: str, formula: str, label: str) -> str:
    assert name not in fields and name not in computed, name
    computed[name] = {"formula": formula, "label": label}
    return name


def text(name: str, label: str, **extra) -> str:
    return field(name, type="text", label=label, **extra)


def number(name: str, label: str, **extra) -> str:
    return field(name, type="number", label=label, **extra)


def area(name: str, label: str, rows: int = 3) -> str:
    return field(name, type="textarea", label=label, rows=rows)


def check(name: str, label: str, **extra) -> str:
    return field(name, type="checkbox", label=label, **extra)


def select(name: str, label: str, options: list, default: str = "") -> str:
    definition = {"type": "select", "label": label, "options": options}
    if default:
        definition["default"] = default
    return field(name, **definition)


def table(name: str, label: str, columns: list[dict], add: str | None = None) -> str:
    definition = {"type": "list", "label": label, "columns": columns}
    if add:
        definition["add_label"] = add
    return field(name, **definition)


def col(key_: str, label: str, type_: str = "text", flex: int = 1, **extra) -> dict:
    return {"key": key_, "type": type_, "label": label, "flex": flex, **extra}


def choose(value: str, cases: list[tuple[str, str]], fallback: str) -> str:
    """A nested conditional: the spreadsheet's VLOOKUP into a small table."""
    formula = fallback
    for match, result in reversed(cases):
        formula = f"{value} == '{match}' ? {result} : ({formula})"
    return formula


# --- the HTML builder -------------------------------------------------------

def F(name: str, variant: str = "", cls: str = "") -> str:
    """An editable field with its label hidden - the layout labels it."""
    v = f' variant="{variant}"' if variant else ""
    tag = f'<g-field name="{name}" label=""{v} />'
    return f'<span class="{cls}">{tag}</span>' if cls else tag


def V(name: str) -> str:
    return f'<g-value name="{name}" />'


def cell(label: str, inner: str, cls: str = "cell") -> str:
    return f'<div class="{cls}"><span class="tiny">{esc(label)}</span>{inner}</div>'


def box(title: str, body: str, cls: str = "") -> str:
    extra = f" {cls}" if cls else ""
    return (f'<section class="box{extra}">\n  <h3 class="bar">{esc(title)}</h3>\n'
            f"{body}\n</section>")


def grid(cells: list[str], cls: str = "grid") -> str:
    return f'<div class="{cls}">' + "".join(cells) + "</div>"


# --- Profile ----------------------------------------------------------------

def profile() -> str:
    text("hero_name", "Name")
    text("species", "Race/Species")
    text("height", "Height")
    number("weight", "Weight (kg)", min=0)
    number("age", "Age", min=0)
    text("gender", "Gender")
    area("appearance", "Basic Appearance", 3)
    hw = [("hw_name", "Name"), ("hw_sector", "Sector"), ("hw_subsector", "Subsector"),
          ("hw_location", "Location"), ("hw_uwp", "UWP"), ("hw_bases", "Bases"),
          ("hw_trade_codes", "Trade Codes")]
    for name, label in hw:
        text(name, f"Homeworld {label}")
    select("hw_travel_zone", "Homeworld Travel Zone", ["Green", "Amber", "Red"])
    check("hw_gas_giant", "Homeworld Gas Giant")
    area("misc_notes", "Miscellaneous Notes", 4)
    table("lifepath", "Lifepath", [
        col("term", "Term", "number", 1, min=1),
        col("career", "Career", "text", 3),
        col("assignment", "Assignment", "text", 3),
        col("survived", "Surv.", "checkbox", 1),
        col("commissioned", "Com.", "checkbox", 1),
        col("advanced", "Adv.", "checkbox", 1),
        col("rank", "Rank", "text", 2),
        col("events", "Events, Connections & Notes", "text", 6),
    ], add="Add a term")
    calc("terms_served", "len(lifepath)", "Terms Served")

    basic = grid([
        cell("Name", F("hero_name"), "cell wide name"),
        cell("Race/Species", F("species")),
        cell("Height", F("height")),
        cell("Weight (kg)", F("weight", "compact")),
        cell("Age", F("age", "compact")),
        cell("Gender", F("gender")),
        cell("Basic Appearance", F("appearance"), "cell full"),
    ], "grid profile-grid")
    world = grid(
        [cell(label, F(name)) for name, label in hw]
        + [cell("Travel Zone", F("hw_travel_zone")),
           cell("Gas Giant", F("hw_gas_giant"), "cell tick")],
        "grid homeworld-grid",
    )
    return "\n".join([
        box("Basic Profile", basic),
        box("Homeworld", world),
        box("Miscellaneous Notes", F("misc_notes")),
        box("Lifepath", f'<p class="hint">Terms served: <b>{V("terms_served")}</b></p>'
            + F("lifepath")),
    ])


# --- Characteristics and skills ----------------------------------------------

DM = "{v} <= 0 ? -3 : clamp(floor({v} / 3) - 2, -3, 3)"


def hexdigit(v: str) -> str:
    """The UPP digit: 0-9, then A-F, capped at F as the spreadsheet does."""
    cases = [(str(n), f"'{c}'") for n, c in zip(range(10, 15), "ABCDE")]
    formula = "'F'"
    for match, result in reversed(cases):
        formula = f"{v} == {match} ? {result} : ({formula})"
    return f"{v} <= 0 ? 0 : ({v} <= 9 ? {v} : ({formula}))"


def characteristics() -> str:
    rows = []
    for short, total, abbr, label in CHARACTERISTICS:
        number(f"{short}_base", f"{label} (base)", min=0, default=7)
        number(f"{short}_misc", f"{label} misc", default=0)
        number(f"{short}_injury", f"{label} injury", min=0, default=0)
        calc(total, f"{short}_base + {short}_misc - {short}_injury", label)
        calc(f"{short}_dm", DM.format(v=total), f"{abbr} Dice Mod")
        rows.append(
            f'<div class="char"><span class="char-abbr">{abbr}</span>'
            f'<span class="char-label">{esc(label)}</span>'
            f'<span class="char-total">{V(total)}</span>'
            f'{F(f"{short}_base", "compact")}{F(f"{short}_misc", "compact")}'
            f'{F(f"{short}_injury", "compact")}'
            f'<span class="char-dm">{V(f"{short}_dm")}</span></div>'
        )
    upp = "".join(f"{hexdigit(total)}, " for _, total, _, _ in CHARACTERISTICS)
    calc("upp", f"concat({upp}psi_base + psi_misc > 0 ? ({hexdigit('psi')}) : '')",
         "Universal Personality Profile")
    head = ('<div class="char head"><span></span><span></span><span class="tiny">Total</span>'
            '<span class="tiny">Base</span><span class="tiny">Misc</span>'
            '<span class="tiny">Injury</span><span class="tiny">Dice Mod</span></div>')
    body = (f'<div class="chars">{head}{"".join(rows)}</div>'
            f'<p class="upp"><span class="tiny">UPP</span><b>{V("upp")}</b></p>')
    return box("Characteristics", body, "characteristics")


def psionics() -> str:
    number("psi_base", "Psionic Strength (base)", min=0, default=0)
    number("psi_misc", "Psionic Strength misc", default=0)
    number("psi_spent", "Psionic Strength spent", min=0, default=0)
    calc("psi", "psi_base + psi_misc - psi_spent", "Psionic Strength")
    calc("psi_dm", DM.format(v="psi"), "PSI DM")
    rows = []
    talents = [(t, key(t)) for t in PSIONIC_TALENTS]
    talents += [("", f"custom_{n}") for n in range(1, PSIONIC_CUSTOM + 1)]
    for label, k in talents:
        name = f"psi_{k}"
        title = label or f"Psionic talent {k[-1]}"
        select(name, title, LEVELS, "--")
        number(f"{name}_misc", f"{title} misc", default=0)
        calc(f"{name}_check", f"{name} == '--' ? '--' : signed({name} + {name}_misc + psi_dm)",
             f"{title} check")
        if label:
            name_cell = f'<span class="sk-name">{esc(label)}</span>'
        else:
            text(f"{name}_name", f"Psionic talent {k[-1]} name")
            name_cell = F(f"{name}_name", cls="sk-name")
        rows.append(name_cell + F(name) + F(f"{name}_misc", "compact")
                    + f'<span class="sk-dm">{V(f"{name}_check")}</span>')
    top = grid([
        cell("Total", f'<span class="big">{V("psi")}</span>'),
        cell("Base", F("psi_base", "compact")),
        cell("Misc", F("psi_misc", "compact")),
        cell("Spent", F("psi_spent", "compact")),
        cell("DM", f'<span class="big">{V("psi_dm")}</span>'),
    ], "grid five")
    head = ('<span class="tiny">Talent</span><span class="tiny">Level</span>'
            '<span class="tiny">Misc</span><span class="tiny">Check</span>')
    return box("Psionics", top + f'<div class="psi-talents">{head}{"".join(rows)}</div>')


def conditions() -> str:
    number("radiation", "Radiation (cumulative rads)", min=0, default=0)
    calc("radiation_effect",
         "radiation <= 150 ? 'None' : concat(radiation <= 300 ? -1 : (radiation <= 500 ? -2 : "
         "(radiation <= 800 ? -3 : -4)), ' END permanently')", "Radiation Effect")
    area("diseases", "Disease(s)", 2)
    check("fatigued", "Fatigued")
    body = grid([
        cell("Radiation", F("radiation", "compact")),
        cell("Effect", V("radiation_effect"), "cell wide"),
        cell("Fatigued", F("fatigued"), "cell tick"),
        cell("Disease(s)", F("diseases"), "cell full"),
    ])
    return box("Conditions", body)


def study() -> str:
    number("study_weeks", "Study weeks complete", min=0, default=0)
    number("study_periods", "Study periods complete", min=0, default=0)
    text("study_skill", "Study skill")
    area("study_notes", "Study notes", 2)
    body = grid([
        cell("Weeks Complete", F("study_weeks", "compact")),
        cell("Periods Complete", F("study_periods", "compact")),
        cell("Skill", F("study_skill"), "cell wide"),
        cell("Notes", F("study_notes"), "cell full"),
    ])
    return box("Study Period", body)


level_names: list[str] = []


def skill_row(name: str, label: str, options: list[str], unskilled: str,
              name_cell: str, cls: str) -> str:
    select(name, label, options, "--")
    level_names.append(name)
    number(f"{name}_misc", f"{label} misc", default=0)
    calc(f"{name}_total", f"{name}_misc + ({name} == '--' ? {unskilled} : {name})",
         f"{label} total")
    dms = []
    for short, _, abbr, _ in CHARACTERISTICS:
        calc(f"{name}_{short}", f"signed({name}_total + {short}_dm)", f"{label} + {abbr}")
        dms.append(f'<span class="sk-dm">{V(f"{name}_{short}")}</span>')
    return (f'<div class="sk-row {cls}">{name_cell}{F(name)}{F(f"{name}_misc", "compact")}'
            f'<span class="sk-total">{V(f"{name}_total")}</span>{"".join(dms)}</div>')


def skill_group(title: str, specs: list[str], grouped: bool, open_slots: int) -> list[str]:
    base = f"sk_{key(title)}"
    has_specs = bool(specs)
    group_names = [base]
    spec_names = []
    for index, spec in enumerate(specs, 1):
        spec_key = f"{base}_{index}" if open_slots else f"{base}_{key(spec)}"
        spec_names.append((spec_key, spec))
        group_names.append(spec_key)
    unskilled = "unskilled"
    if grouped:
        trained = " or ".join(f"{n} != '--'" for n in group_names)
        unskilled = f"(({trained}) ? 0 : unskilled)"
    rows = [skill_row(base, title, SPEC0 if has_specs else LEVELS, unskilled,
                      f'<span class="sk-name">{esc(title)}</span>', "parent")]
    for spec_key, spec in spec_names:
        label = f"{title} ({spec})" if spec else f"{title} {spec_key.rsplit('_', 1)[1]}"
        if open_slots:
            text(f"{spec_key}_name", f"{label} name", **({"default": spec} if spec else {}))
            name_cell = F(f"{spec_key}_name", cls="sk-name spec")
        else:
            name_cell = f'<span class="sk-name spec">{esc(spec)}</span>'
        rows.append(skill_row(spec_key, label, SPEC, unskilled, name_cell, "spec"))
    return rows


def skills() -> str:
    select("sk_jack_of_all_trades", "Jack-of-All-Trades", JOAT, "--")
    level_names.append("sk_jack_of_all_trades")
    calc("unskilled", "-3 + sk_jack_of_all_trades", "Unskilled Penalty")

    head = ('<div class="sk-row head"><span class="tiny">Skill</span>'
            '<span class="tiny">Level</span><span class="tiny">Misc</span>'
            '<span class="tiny">Total</span>'
            + "".join(f'<span class="tiny">{abbr}</span>' for _, _, abbr, _ in CHARACTERISTICS)
            + "</div>")
    left = [r for group in SKILLS_LEFT for r in skill_group(*group)]
    left.append(
        '<div class="sk-row joat"><span class="sk-name">Jack-of-All-Trades</span>'
        f'{F("sk_jack_of_all_trades")}<span class="tiny">Unskilled</span>'
        f'<span class="sk-total">{V("unskilled")}</span></div>'
    )
    right = [r for group in SKILLS_RIGHT for r in skill_group(*group)]

    custom = []
    for n in range(1, CUSTOM_SKILLS + 1):
        name = f"sk_custom_{n}"
        text(f"{name}_name", f"Custom skill {n}")
        text(f"{name}_specialty", f"Custom skill {n} speciality")
        cells = (f'<span class="sk-name custom">{F(f"{name}_name")}'
                 f'{F(f"{name}_specialty")}</span>')
        custom.append(skill_row(name, f"Custom skill {n}", LEVELS, "unskilled", cells, "custom"))

    calc("skill_levels", "sum(" + ", ".join(level_names) + ")", "Total Skill Levels")
    calc("skill_levels_max", "3 * (education + intellect)", "Maximum Skill Levels")
    validators.append({
        "rule": "skill_levels <= skill_levels_max",
        "message": "More skill levels than 3 x (EDU + INT) allows.",
    })

    total = (f'<p class="hint">Total skill levels <b>{V("skill_levels")}</b> of '
             f'<b>{V("skill_levels_max")}</b> - a trained speciality makes the rest of its '
             "skill 0; anything else untrained takes the unskilled penalty.</p>")
    return "\n".join([
        box("Skills", total + '<div class="skill-columns">'
            f'<div class="skills">{head}{"".join(left)}</div>'
            f'<div class="skills">{head}{"".join(right)}</div></div>', "skills-box"),
        box("Custom Skills", f'<div class="skills">{head}{"".join(custom)}</div>'),
    ])


def characteristics_page() -> str:
    # Built in order: the skills read the characteristic DMs and psionics read
    # nothing they define, but every name must exist before the sheet is written.
    top = [characteristics(), psionics(), conditions(), study()]
    return (
        f'<div class="char-top">{top[0]}<div class="stack">{top[1]}</div>'
        f'<div class="stack">{top[2]}{top[3]}</div></div>\n{skills()}'
    )


# --- Combat and equipment ---------------------------------------------------

def combat() -> str:
    for _, k, dm in ATTACK_SKILLS:
        calc(f"atk_{k}", f"sk_{k}_total + {dm}", f"Attack DM ({k.replace('_', ' ')})")
    rows = []
    for n in range(1, WEAPON_SLOTS + 1):
        w = f"wpn_{n}"
        text(f"{w}_name", f"Weapon {n}")
        text(f"{w}_range", f"Weapon {n} range")
        select(f"{w}_skill", f"Weapon {n} skill", [a for a, _, _ in ATTACK_SKILLS])
        text(f"{w}_damage", f"Weapon {n} damage")
        text(f"{w}_magazine", f"Weapon {n} magazine")
        text(f"{w}_traits", f"Weapon {n} traits")
        cases = [(label, f"signed(atk_{k})") for label, k, _ in ATTACK_SKILLS]
        calc(f"{w}_attack", choose(f"{w}_skill", cases, "'--'"), f"Weapon {n} attack")
        rows.append(
            '<div class="wpn-row">' + F(f"{w}_name") + F(f"{w}_range") + F(f"{w}_skill")
            + f'<span class="sk-total">{V(f"{w}_attack")}</span>' + F(f"{w}_damage")
            + F(f"{w}_magazine") + F(f"{w}_traits") + "</div>"
        )
    head = ('<div class="wpn-row head">' + "".join(
        f'<span class="tiny">{h}</span>' for h in
        ("Weapon", "Range", "Skill Used", "Attack", "Damage", "Magazine", "Traits")) + "</div>")
    attack_dms = grid([cell(label, f'<span class="sk-total">{V(f"atk_{k}")}</span>')
                       for label, k, _ in ATTACK_SKILLS], "grid attack-dms")
    weapons = box("Weapons", f'<div class="weapons">{head}{"".join(rows)}</div>'
                  '<h4 class="sub">Attack DM by skill</h4>' + attack_dms, "wide")

    table("armour", "Armour", [
        col("worn", "Worn", "checkbox", 1, default=True),
        col("type", "Armour Type", "text", 4),
        col("protection", "Protection", "number", 2, min=0),
        col("rad", "Rad", "number", 1, min=0),
        col("skill", "Required Skill", "text", 3),
    ], add="Add armour")
    number("subdermal", "Subdermal Armour Protection", min=0, default=0)
    calc("armour_total", "sum_where(armour, 'protection', 'worn', true) + subdermal",
         "Total Armour Value")
    armour = box("Armour", F("armour") + grid([
        cell("Subdermal Protection", F("subdermal", "compact")),
        cell("Total Armour", f'<span class="big">{V("armour_total")}</span>'),
    ]))

    table("augments", "Augments", [
        col("augment", "Augment", "text", 3),
        col("notes", "Improvement/Notes", "text", 5),
        col("tl", "TL", "number", 1, min=0),
        col("cost", "Cost", "number", 2, min=0),
    ], add="Add an augment")

    calc("initiative_dm", "signed(max(dex_dm, int_dm))", "Initiative DM")
    calc("tactics_dm", "signed(sk_tactics_total)", "Tactics DM")
    calc("leadership_dm", "signed(sk_leadership_total)", "Leadership DM")
    calc("dodge_penalty", "max(0, dex_dm, sk_athletics_dexterity_total)",
         "Opponent Dodge Penalty")
    misc = box("Misc Info", grid([
        cell("UPP", f'<b class="upp-inline">{V("upp")}</b>', "cell wide"),
        cell("Initiative DM", f'<span class="big">{V("initiative_dm")}</span>'),
        cell("Tactics DM", f'<span class="big">{V("tactics_dm")}</span>'),
        cell("Leadership DM", f'<span class="big">{V("leadership_dm")}</span>'),
        cell("Opponent Dodge Penalty", f'<span class="big">{V("dodge_penalty")}</span>'),
    ]))

    table("gear", "Equipment on Person", [
        col("qty", "#", "number", 1, min=0, default=1),
        col("item", "Item", "text", 4),
        col("notes", "Notes", "text", 4),
        col("tl", "TL", "number", 1, min=0),
        col("mass", "Mass (kg)", "number", 1, min=0),
        col("cost", "Cost", "number", 2, min=0),
    ], add="Add an item")
    calc("gear_count", "sum_where(gear, 'qty')", "Items Carried")
    calc("carried", "sum_qty(gear, 'mass')", "Carried (kg)")
    calc("gear_cost", "sum_qty(gear, 'cost')", "Equipment Cost")
    calc("encumbrance_threshold",
         "strength + endurance + sk_athletics_endurance + sk_athletics_strength",
         "Encumbrance Threshold")
    calc("encumbrance",
         "carried <= encumbrance_threshold ? 'Okay' : (carried <= 2 * encumbrance_threshold ? "
         "'Encumbered' : 'Carrying Too Much')", "Encumbrance")
    calc("total_weight", "weight + carried", "Total Character Weight")
    validators.append({"rule": "carried <= 2 * encumbrance_threshold",
                       "message": "Carrying more than twice the encumbrance threshold."})
    gear = box("Equipment on Person", F("gear") + (
        f'<p class="hint">{V("gear_count")} items, {V("carried")} kg, Cr{V("gear_cost")}</p>'),
        "wide")
    encumbrance = box("Encumbrance", grid([
        cell("Carried (kg)", f'<span class="big">{V("carried")}</span>'),
        cell("Threshold", f'<span class="big">{V("encumbrance_threshold")}</span>'),
        cell("Status", f'<b class="state">{V("encumbrance")}</b>', "cell wide"),
        cell("Total Character Weight (kg)", V("total_weight"), "cell full"),
    ]))

    # Finances
    number("cash", "Cash on Hand", default=0)
    number("pension", "Yearly Pension", min=0, default=0)
    number("salary", "Monthly Salary", min=0, default=0)
    number("ship_costs", "Ship Operating Costs", min=0, default=0)
    table("mortgages", "Mortgages", [
        col("name", "Mortgage", "text", 3),
        col("owed", "Remaining Owed", "number", 2, min=0),
        col("payment", "Monthly Payment", "number", 2, min=0),
    ], add="Add a mortgage")
    calc("debt_payments", "sum_where(mortgages, 'payment')", "Monthly Debt Payments")
    table("debts", "Other Debts", [
        col("who", "Person/Bank/Location", "text", 4),
        col("value", "Value", "number", 2),
    ], add="Add a debt")
    calc("debts_total", "sum_where(debts, 'value') + sum_where(mortgages, 'owed')", "Total Debts")
    table("savings", "Savings & Assets", [
        col("what", "Thing/Person/Bank/Location", "text", 4),
        col("value", "Value", "number", 2),
    ], add="Add an asset")
    calc("savings_total", "sum_where(savings, 'value')", "Total Savings & Assets")

    soc_cases = [(f"social >= {soc}", f"'{name}'") for soc, name, _ in reversed(STANDARDS)]
    formula = "'Very Poor'"
    for test, result in reversed(soc_cases):
        formula = f"{test} ? {result} : ({formula})"
    calc("standard_for_soc", formula, "Standard of Living for SOC")
    select("standard_chosen", "Chosen Standard of Living",
           [name for _, name, _ in STANDARDS], "Good")
    calc("living_cost", choose("standard_chosen", [(n, str(c)) for _, n, c in STANDARDS], "0"),
         "Monthly Living Cost")
    calc("monthly_outgoings", "living_cost + debt_payments + ship_costs", "Monthly Outgoings")

    finances = box("Finances", grid([
        cell("Cash on Hand (Cr)", F("cash", "compact")),
        cell("Yearly Pension", F("pension", "compact")),
        cell("Monthly Salary", F("salary", "compact")),
        cell("Ship Operating Costs", F("ship_costs", "compact")),
        cell("Monthly Debt Payments", V("debt_payments")),
        cell("Monthly Outgoings", f'<b>{V("monthly_outgoings")}</b>'),
    ]))
    living = box("Standard of Living", grid([
        cell("SOC", f'<span class="big">{V("social")}</span>'),
        cell("Standard for SOC", V("standard_for_soc"), "cell wide"),
        cell("Chosen", F("standard_chosen"), "cell wide"),
        cell("Monthly Living Cost", V("living_cost"), "cell wide"),
    ]))
    savings = box("Savings & Debts",
                  '<h4 class="sub">Mortgages</h4>' + F("mortgages")
                  + '<h4 class="sub">Other Debts</h4>' + F("debts")
                  + f'<p class="hint">Total debts <b>{V("debts_total")}</b></p>'
                  + '<h4 class="sub">Savings &amp; Assets</h4>' + F("savings")
                  + f'<p class="hint">Total savings &amp; assets <b>{V("savings_total")}</b></p>')

    return "\n".join([
        weapons,
        '<div class="two-col"><div class="stack">', armour, misc,
        box("Augments", F("augments")), encumbrance,
        '</div><div class="stack">', finances, living, savings, "</div></div>",
        gear,
    ])


# --- Vehicles ---------------------------------------------------------------

def vehicle(n: int) -> str:
    v = f"v{n}"
    text(f"{v}_type", f"Vehicle {n} type")
    text(f"{v}_cost", f"Vehicle {n} cost")
    number(f"{v}_tl", f"Vehicle {n} TL", min=0)
    select(f"{v}_skill", f"Vehicle {n} skill", VEHICLE_SKILLS)
    number(f"{v}_agility", f"Vehicle {n} agility", default=0)
    cases = [(s, f"sk_{key(s.replace('(', '').replace(')', ''))}_total")
             for s in VEHICLE_SKILLS]
    calc(f"{v}_check", f"{v}_skill == '' ? '--' : signed(("
         + choose(f"{v}_skill", cases, "0") + f") + dex_dm + {v}_agility)",
         f"Vehicle {n} skill check DM")
    select(f"{v}_max_speed", f"Vehicle {n} max speed", SPEED_BANDS)
    slower = [(band, f"'{SPEED_BANDS[max(0, i - 1)]}'") for i, band in enumerate(SPEED_BANDS)]
    calc(f"{v}_cruise_speed", choose(f"{v}_max_speed", slower, "'--'"),
         f"Vehicle {n} cruise speed")
    number(f"{v}_max_range", f"Vehicle {n} max range (km)", min=0)
    calc(f"{v}_cruise_range", f"{v}_max_range ? {v}_max_range * 1.5 : '--'",
         f"Vehicle {n} cruise range")
    for side in ("front", "rear", "sides"):
        number(f"{v}_armour_{side}", f"Vehicle {n} armour ({side}) current", min=0)
        number(f"{v}_armour_{side}_max", f"Vehicle {n} armour ({side}) total", min=0)
    number(f"{v}_hull", f"Vehicle {n} hull current", min=0)
    number(f"{v}_hull_max", f"Vehicle {n} hull total", min=0)
    number(f"{v}_cargo", f"Vehicle {n} cargo capacity (tons)", min=0)
    text(f"{v}_crew", f"Vehicle {n} crew")
    text(f"{v}_passengers", f"Vehicle {n} passengers")
    text(f"{v}_shipping", f"Vehicle {n} shipping size")
    area(f"{v}_damage", f"Vehicle {n} misc damage", 2)
    area(f"{v}_equipment", f"Vehicle {n} equipment", 3)
    systems = [("autopilot", "Autopilot (skill level)"), ("comms", "Communications (range)"),
               ("navigation", "Navigation (Navigation DM)"),
               ("sensors", "Sensors (Electronics (Sensors) DM)"),
               ("camouflage", "Camouflage (Recon DM)"),
               ("stealth", "Stealth (Electronics (Sensors) DM)")]
    for s, label in systems:
        text(f"{v}_{s}", f"Vehicle {n} {label}")
    table(f"{v}_traits", f"Vehicle {n} traits", [
        col("trait", "Trait", "text", 2), col("description", "Description", "text", 5),
    ], add="Add a trait")
    table(f"{v}_weapons", f"Vehicle {n} weapons", [
        col("weapon", "Weapon", "text", 3),
        {"key": "mount", "type": "select", "label": "Mount", "flex": 2, "options": WEAPON_MOUNTS},
        col("location", "Location", "text", 2),
        col("range", "Range", "text", 1),
        col("damage", "Damage", "text", 1),
        col("magazine", "Magazine", "text", 1),
        col("magazine_cost", "Mag. Cost", "text", 1),
        col("traits", "Traits", "text", 2),
        col("fire_control", "Fire Control", "text", 1),
    ], add="Add a weapon")
    table(f"{v}_stored", f"Vehicle {n} stored cargo", [
        col("qty", "#", "number", 1, min=0, default=1),
        col("item", "Item", "text", 4),
        col("notes", "Notes", "text", 3),
        col("tl", "TL", "number", 1, min=0),
        col("mass", "Mass (tons)", "number", 1, min=0),
        col("cost", "Cost", "number", 2, min=0),
    ], add="Add cargo")
    calc(f"{v}_stored_mass", f"sum_qty({v}_stored, 'mass')", f"Vehicle {n} stored cargo (tons)")
    calc(f"{v}_stored_cost", f"sum_qty({v}_stored, 'cost')", f"Vehicle {n} stored cargo cost")
    validators.append({"rule": f"{v}_cargo == 0 or {v}_stored_mass <= {v}_cargo",
                       "message": f"Vehicle {n} carries more cargo than its capacity."})

    armour_rows = "".join(
        f'<span class="tiny">{side.title()}</span>{F(f"{v}_armour_{side}", "compact")}'
        f'{F(f"{v}_armour_{side}_max", "compact")}' for side in ("front", "rear", "sides"))
    body = "".join([
        f'<div class="vehicle-title">{F(f"{v}_type", cls="vname")}</div>',
        '<div class="vehicle-top">',
        grid([
            cell("Cost", F(f"{v}_cost")), cell("TL", F(f"{v}_tl", "compact")),
            cell("Skill", F(f"{v}_skill"), "cell wide"),
            cell("Agility", F(f"{v}_agility", "compact")),
            cell("Skill Check DM", f'<span class="big">{V(f"{v}_check")}</span>'),
            cell("Max Speed", F(f"{v}_max_speed")),
            cell("Cruise Speed", V(f"{v}_cruise_speed")),
            cell("Max Range (km)", F(f"{v}_max_range", "compact")),
            cell("Cruise Range (km)", V(f"{v}_cruise_range")),
            cell("Cargo (tons)", F(f"{v}_cargo", "compact")),
            cell("Crew", F(f"{v}_crew")),
            cell("Passengers", F(f"{v}_passengers")),
            cell("Shipping Size", F(f"{v}_shipping")),
        ], "grid vehicle-stats"),
        (
            '<div class="vehicle-armour"><h4 class="sub">Armour</h4>'
            '<div class="armour-grid"><span></span><span class="tiny">Current</span>'
            f'<span class="tiny">Total</span>{armour_rows}'
            f'<span class="tiny">Hull</span>{F(f"{v}_hull", "compact")}'
            f'{F(f"{v}_hull_max", "compact")}</div>'
            f'<span class="tiny">Misc Damage</span>{F(f"{v}_damage")}</div>'
        ),
        "</div>",
        '<div class="two-col"><div class="stack">',
        f'<h4 class="sub">Equipment</h4>{F(f"{v}_equipment")}',
        '<h4 class="sub">Traits</h4>' + F(f"{v}_traits"),
        '</div><div class="stack"><h4 class="sub">Systems</h4>',
        grid([cell(label, F(f"{v}_{s}")) for s, label in systems], "grid systems"),
        "</div></div>",
        '<h4 class="sub">Weapons</h4>' + F(f"{v}_weapons"),
        f'<h4 class="sub">Stored Cargo - {V(f"{v}_stored_mass")} of {V(f"{v}_cargo")} tons, '
        f'Cr{V(f"{v}_stored_cost")}</h4>' + F(f"{v}_stored"),
    ])
    return box(f"Vehicle {n}", body, "vehicle")


# --- Spacecraft -------------------------------------------------------------

def spacecraft() -> str:
    text("ship_type", "Ship type")
    text("ship_class", "Ship class")
    text("ship_cost", "Ship cost")
    number("ship_tl", "Ship TL", min=0)
    number("ship_hull_tons", "Hull (tons)", min=0, default=0)
    components = [("armour", "Armour"), ("m_drive", "M-Drive"), ("j_drive", "J-Drive"),
                  ("power_plant", "Power Plant"), ("fuel", "Fuel Tanks"), ("bridge", "Bridge"),
                  ("computer", "Computer"), ("sensors", "Sensors"), ("weapons", "Weapons"),
                  ("systems", "Systems"), ("staterooms", "Staterooms"),
                  ("software", "Software"), ("common", "Common Areas"), ("cargo", "Cargo")]
    for k, label in components:
        if k in ("weapons", "systems", "software"):
            area(f"ship_{k}", label, 2)
        else:
            text(f"ship_{k}", label)
    number("ship_armour_protection", "Armour protection", min=0, default=0)
    select("ship_thrust", "Thrust", ["--"] + [str(n) for n in range(17)], "1")
    select("ship_jump", "Jump", ["--"] + [str(n) for n in range(1, 10)], "1")
    number("ship_cargo_tons", "Cargo (tons)", min=0, default=0)
    number("ship_hull", "Hull points current", min=0)
    number("ship_hull_max", "Hull points total", min=0)
    area("ship_damage", "Misc damage", 3)
    for role in CREW:
        number(f"ship_crew_{key(role)}", f"Crew: {role}", min=0)
    number("ship_power_available", "Power points available", min=0, default=0)
    number("ship_battery", "Battery capacity", min=0, default=0)
    power = [("basic", "Basic Ship Systems", "ship_hull_tons * 0.2"),
             ("m_drive", "M-Drive",
              ("ship_thrust == '--' ? '--' : ship_hull_tons * 0.1 * "
               "(ship_thrust > 0 ? ship_thrust : 0.25)")),
             ("j_drive", "J-Drive",
              "ship_jump == '--' ? '--' : ship_hull_tons * 0.1 * ship_jump"),
             ("sensors", "Sensors", None), ("weapons", "Weapons", None)]
    power_rows = []
    for k, label, formula in power:
        number(f"ship_power_{k}", f"Power allocated: {label}", min=0)
        if formula:
            calc(f"ship_power_{k}_required", formula, f"Power required: {label}")
            required = V(f"ship_power_{k}_required")
        else:
            number(f"ship_power_{k}_required", f"Power required: {label}", min=0)
            required = F(f"ship_power_{k}_required", "compact")
        power_rows.append(f'<span>{esc(label)}</span>{F(f"ship_power_{k}", "compact")}'
                          f'<span class="num">{required}</span>')
    calc("ship_power_allocated",
         "sum(" + ", ".join(f"ship_power_{k}" for k, _, _ in power) + ")",
         "Power allocated")
    validators.append({"rule": "ship_power_allocated <= ship_power_available + ship_battery",
                       "message": "More power is allocated than the ship has available."})
    text("ship_maintenance", "Maintenance cost")
    text("ship_purchase", "Purchase cost")
    table("ship_weapons_list", "Ship weapons", [
        col("weapon", "Weapon", "text", 3), col("mount", "Mount", "text", 2),
        col("location", "Location", "text", 2), col("range", "Range", "text", 1),
        col("damage", "Damage", "text", 1), col("ammo", "Ammo", "text", 1),
        col("ammo_cost", "Ammo Cost", "text", 1), col("traits", "Traits", "text", 2),
    ], add="Add a weapon")
    table("ship_stored", "Ship stored cargo", [
        col("qty", "#", "number", 1, min=0, default=1),
        col("item", "Item", "text", 4), col("notes", "Notes", "text", 3),
        col("tl", "TL", "number", 1, min=0), col("mass", "Mass (tons)", "number", 1, min=0),
        col("cost", "Cost", "number", 2, min=0),
    ], add="Add cargo")
    calc("ship_stored_mass", "sum_qty(ship_stored, 'mass')", "Stored cargo (tons)")
    calc("ship_stored_cost", "sum_qty(ship_stored, 'cost')", "Stored cargo cost")
    validators.append({"rule": "ship_cargo_tons == 0 or ship_stored_mass <= ship_cargo_tons",
                       "message": "The ship carries more cargo than its hold."})

    comp_cells = []
    for k, label in components:
        extra = ""
        if k == "armour":
            extra = f'<span class="tiny">Protection</span>{F("ship_armour_protection", "compact")}'
        elif k == "m_drive":
            extra = f'<span class="tiny">Thrust</span>{F("ship_thrust")}'
        elif k == "j_drive":
            extra = f'<span class="tiny">Jump-</span>{F("ship_jump")}'
        elif k == "cargo":
            extra = f'<span class="tiny">Tons</span>{F("ship_cargo_tons", "compact")}'
        comp_cells.append(f'<div class="comp"><span class="comp-label">{esc(label)}</span>'
                          f'{F(f"ship_{k}")}{extra}</div>')
    left = box("Spacecraft", "".join([
        grid([cell("Ship Type", F("ship_type"), "cell wide"),
              cell("Ship Class", F("ship_class"), "cell wide"),
              cell("Cost", F("ship_cost")), cell("TL", F("ship_tl", "compact")),
              cell("Hull (tons)", F("ship_hull_tons", "compact"))], "grid ship-head"),
        f'<div class="components">{"".join(comp_cells)}</div>',
    ]))
    crew = "".join(f'<span>{role}</span>{F(f"ship_crew_{key(role)}", "compact")}'
                   for role in CREW)
    right = "\n".join([
        box("Hull Points", grid([
            cell("Current", F("ship_hull", "compact")),
            cell("Total", F("ship_hull_max", "compact")),
            cell("Misc Damage", F("ship_damage"), "cell full"),
        ])),
        box("Crew", f'<div class="pairs">{crew}</div>'),
        box("Power Allocation", grid([
            cell("Allocated", f'<span class="big">{V("ship_power_allocated")}</span>'),
            cell("Available", F("ship_power_available", "compact")),
            cell("Battery", F("ship_battery", "compact")),
        ]) + '<div class="power"><span class="tiny"></span><span class="tiny">Allocated</span>'
            f'<span class="tiny">Required</span>{"".join(power_rows)}</div>'),
        box("Finances", grid([
            cell("Maintenance Cost", F("ship_maintenance"), "cell wide"),
            cell("Purchase Cost", F("ship_purchase"), "cell wide"),
        ])),
    ])
    return "\n".join([
        '<div class="two-col ship"><div class="stack">', left,
        '</div><div class="stack">', right, "</div></div>",
        box("Weapons", F("ship_weapons_list")),
        box("Stored Cargo",
            f'<p class="hint">{V("ship_stored_mass")} of {V("ship_cargo_tons")} tons, '
            f'Cr{V("ship_stored_cost")}</p>' + F("ship_stored")),
    ])


# --- Background and personality ---------------------------------------------

def background() -> str:
    pairs = []
    for left, right in DESCRIPTORS:
        name = f"trait_{key(left)}"
        select(name, f"{left} - {right}", ["1", "2", "3", "4", "5"])
        pairs.append(f'<span class="d-left">{left}</span>{F(name)}'
                     f'<span class="d-right">{right}</span>')
    personality_fields = [
        ("goals_short", "Short-Term Goals & Ambitions"),
        ("goals_long", "Long-Term Goals & Ambitions"),
        ("traits_good", "Good Personality Traits"), ("traits_bad", "Bad Personality Traits"),
        ("strength_greatest", "Greatest Strength"), ("weakness_greatest", "Greatest Weakness"),
        ("mannerisms", "Mannerisms & Peculiarities"), ("speech", "Conversation & Speech Quirks"),
    ]
    emotions = [
        ("mood", "Typical Mood"), ("humour", "Sense of Humour"), ("joys", "Greatest Joys"),
        ("fears", "Greatest Fears"), ("most_at_ease", "Most at Ease"),
        ("least_at_ease", "Least at Ease"), ("soft_spots", "Soft Spots"),
        ("enraged", "Enraged When"), ("depressed", "Depressed When"),
        ("accomplishment", "Biggest Accomplishment"), ("regret", "Biggest Regret"),
        ("secrets", "Darkest Secrets"), ("lie", "The Lie You Believe"),
    ]
    favourites = [
        ("fav_colours", "Favourite Colours"), ("fav_foods", "Favourite Foods"),
        ("fav_music", "Favourite Music"), ("fav_joke", "Favourite Joke"),
        ("spending", "Spending Habits"), ("possessions", "Most Prized Possessions"),
        ("hobbies", "Hobbies"),
    ]
    appearance = [
        ("visual_age", "Visual Age"), ("body_build", "Body Build"),
        ("attractiveness", "Attractiveness"), ("posture", "Posture"),
        ("marks", "Prominent & Distinguishing Marks/Features"),
    ]
    face = [("eye_colour", "Eye Colour"), ("hair_colour", "Hair Colour"),
            ("face_shape", "Shape of Face"), ("hair_style", "Hair Style"),
            ("skin_tone", "Skin Tone"), ("facial_hair", "Facial Hair")]
    clothing = [("clothes_everyday", "Everyday Clothes"), ("clothes_combat", "Combat-Ready Gear"),
                ("jewelry", "Jewelry & Accessories")]
    history = [
        ("birthday", "Birthday"), ("childhood_memory", "Most Important Childhood Memory"),
        ("childhood_hero", "Childhood Hero"), ("childhood_enemies", "Childhood Enemies"),
        ("shaping_events", "Personality-Shaping Events"), ("arrested", "Ever Arrested?"),
        ("military", "Served in the Military?"), ("education_notes", "Prominent Education?"),
    ]
    training = [("teachers", "Teacher(s)"), ("training_skills", "Which Skills"),
                ("training_where", "Where"), ("training_when", "When"),
                ("training_why", "Why"), ("training_how", "How")]
    society = [("upbringing_effect", "Upbringing's Effect on World View"),
               ("class_growing_up", "Social Class Growing Up"),
               ("class_current", "Current Social Class")]

    def lines(items: list[tuple[str, str]], multiline: bool = True) -> str:
        out = []
        for k, label in items:
            if multiline:
                area(k, label, 2)
            else:
                text(k, label)
            out.append(cell(label, F(k), "cell line"))
        return "".join(out)

    relations = []
    seen: dict[str, int] = {}
    for role in RELATIONS:
        seen[role] = seen.get(role, 0) + 1
        k = key(role) + (f"_{seen[role]}" if RELATIONS.count(role) > 1 else "")
        text(f"rel_{k}_name", f"{role} name")
        check(f"rel_{k}_alive", f"{role} alive", default=True)
        text(f"rel_{k}", f"{role} relationship")
        relations.append(
            f'<div class="relation"><span class="tiny">{role}</span>{F(f"rel_{k}_name")}'
            f'<label class="alive">{F(f"rel_{k}_alive")}Alive</label>'
            f'{F(f"rel_{k}", cls="rel-text")}</div>')
    area("background_story", "Background Notes/Story", 8)
    area("general_description", "General Description", 4)

    col1 = "\n".join([
        box("Personality", '<h4 class="sub">Descriptor Opposites</h4>'
            f'<div class="descriptors">{"".join(pairs)}</div>'),
        box("Goals, Traits & Habits", lines(personality_fields)),
        box("Emotions & Experiences", lines(emotions)),
        box("Favourites & Hobbies", lines(favourites, multiline=False)),
    ])
    col2 = "\n".join([
        box("Appearance", '<p class="hint">Species, gender, age and height are on the '
            "Profile page.</p>" + lines(appearance, multiline=False)
            + '<h4 class="sub">Facial Features</h4>'
            + grid([cell(label, F(text(k, label))) for k, label in face], "grid two")
            + '<h4 class="sub">Clothing</h4>' + lines(clothing)
            + '<h4 class="sub">General Description</h4>' + F("general_description")),
        box("Relationships", '<p class="hint">Allies, contacts, rivals and enemies are on the '
            "Campaign Notes page.</p>" + "".join(relations)),
    ])
    col3 = "\n".join([
        box("Background", '<h4 class="sub">Childhood &amp; Adolescence</h4>' + lines(history)
            + '<h4 class="sub">Training &amp; Learning Skills</h4>' + lines(training, False)
            + '<h4 class="sub">Role in Society</h4>' + lines(society)),
        box("Background Notes/Story", F("background_story")),
    ])
    return (f'<div class="three-col"><div class="stack">{col1}</div>'
            f'<div class="stack">{col2}</div><div class="stack">{col3}</div></div>')


# --- Campaign notes ---------------------------------------------------------

def campaign() -> str:
    table("party", "Party", [
        col("member", "Member", "text", 3), col("player", "Player", "text", 2),
        col("species", "Gender & Species", "text", 2), col("notes", "Description/Notes", "text", 5),
        col("alive", "Alive", "checkbox", 1, default=True),
    ], add="Add a party member")
    text("party_name", "Party name")
    text("party_date", "Current date")
    text("party_location", "Current location")
    area("party_jobs", "Job(s)", 3)
    text("party_patron", "Patron")
    text("party_reward", "Reward")
    table("contacts", "Allies, Contacts, Rivals & Enemies", [
        col("name", "Name", "text", 3), col("species", "Gender & Species", "text", 2),
        {"key": "type", "type": "select", "label": "Type", "flex": 2,
         "options": ["Ally", "Contact", "Rival", "Enemy"]},
        col("notes", "Description/Notes", "text", 5),
        col("alive", "Alive", "checkbox", 1, default=True),
    ], add="Add a connection")
    for kind in ("Ally", "Contact", "Rival", "Enemy"):
        calc(f"count_{kind.lower()}", f"count_where(contacts, 'type', '{kind}')",
             f"{kind} count")
    table("organisations", "Organisations", [
        col("name", "Name", "text", 3), col("location", "Location", "text", 2),
        col("notes", "Description/Notes", "text", 5),
    ], add="Add an organisation")
    table("npcs", "Other NPCs", [
        col("name", "Name", "text", 3), col("species", "Gender & Species", "text", 2),
        col("location", "Location", "text", 2), col("notes", "Description/Notes", "text", 5),
        col("alive", "Alive", "checkbox", 1, default=True),
    ], add="Add an NPC")
    table("locations", "Locations", [
        col("name", "Name", "text", 3), col("uwp", "UPP/UWP", "text", 2),
        col("notes", "Description/Notes", "text", 5),
    ], add="Add a location")
    area("campaign_notes", "Various Notes", 10)

    plurals = {"Ally": "Allies", "Contact": "Contacts", "Rival": "Rivals", "Enemy": "Enemies"}
    counts = " · ".join(f'{plural} <b>{V(f"count_{kind.lower()}")}</b>'
                        for kind, plural in plurals.items())
    return "\n".join([
        '<div class="two-col wide-left"><div class="stack">',
        box("Party", cell("Party Name", F("party_name"), "cell line") + F("party")),
        box("Allies, Contacts, Rivals & Enemies", f'<p class="hint">{counts}</p>'
            + F("contacts")),
        box("Other NPCs", F("npcs")),
        '</div><div class="stack">',
        box("Party Current Info", grid([
            cell("Date", F("party_date")), cell("Location", F("party_location")),
            cell("Job(s)", F("party_jobs"), "cell full"),
            cell("Patron", F("party_patron")), cell("Reward", F("party_reward")),
        ], "grid two")),
        box("Organisations", F("organisations")),
        box("Locations", F("locations")),
        box("Various Notes", F("campaign_notes")),
        "</div></div>",
    ])


# --- assemble ---------------------------------------------------------------

def main() -> None:
    tabs = [
        ("Profile", profile()),
        ("Characteristics &amp; Skills", characteristics_page()),
        ("Combat &amp; Equipment", combat()),
        ("Vehicles", "\n".join(vehicle(n) for n in range(1, VEHICLES + 1))),
        ("Spacecraft", spacecraft()),
        ("Background &amp; Personality", background()),
        ("Campaign Notes", campaign()),
    ]
    layout = [
        "<!-- Traveller (Mongoose 2nd Edition) traveller sheet - generated by",
        "     scripts/traveller/build_sheet.py; edit that, not this file.",
        "     The tabs follow J. Brannen's character spreadsheet. -->",
        '<div class="sheet-trav">',
        (
            f'<header class="masthead"><span class="mast-name">{V("hero_name")}</span>'
            f'<span class="mast-upp">{V("upp")}</span>'
            f'<span class="mast-meta">{V("species")}</span></header>'
        ),
        "<g-tabs>",
    ]
    for title, body in tabs:
        layout += [f'<g-tab title="{title}">', body, "</g-tab>"]
    layout += ["</g-tabs>", "</div>", ""]

    document = {
        "$schema": "../../schema/character-sheet.schema.json",
        "id": "traveller-2e",
        "name": "Traveller (Mongoose 2nd Edition)",
        "version": "1.0.0",
        "system": "Traveller (Mongoose 2nd Edition)",
        "description": (
            "A traveller sheet for Mongoose Traveller 2nd Edition, after J. Brannen's character "
            "spreadsheet: characteristics with their dice modifiers and UPP, every skill and "
            "speciality with its check DM against each characteristic, psionics, weapons with "
            "their attack DM, armour, encumbrance, finances and standard of living, vehicles, "
            "a spacecraft, background and campaign notes."
        ),
        "author": "hunter-read",
        "homepage": "https://www.mongoosepublishing.com/pages/traveller-licensing",
        "license": "Traveller Fair Use Policy",
        "license_url": "https://www.mongoosepublishing.com/pages/traveller-licensing",
        "attribution": ATTRIBUTION,
        "name_field": "hero_name",
        "layout_file": "traveller-2e.html",
        "styles_file": "traveller-2e.css",
        "fields": fields,
        "computed": computed,
        "validators": validators,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "traveller-2e.html").write_text("\n".join(layout), encoding="utf-8")
    (OUT / "traveller-2e.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(fields)} fields, {len(computed)} computed, {len(validators)} validators")


if __name__ == "__main__":
    main()
