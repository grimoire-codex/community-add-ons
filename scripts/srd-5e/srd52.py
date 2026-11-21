"""The SRD 5.2.1 itself, read from its PDF: the authority for the dnd-5e-srd pack's
conditions, rules and monsters.

Open5e keeps the SRD (SRD_CC_v5.2.1.pdf, under raw_sources/srd_5_2 in its
repository) beside its fixtures, and says to check the fixtures against it.
import_open5e.py takes each entry's structure from the fixtures and, for the
reference types, its words from here:

- each monster's header - size, type, armor class, initiative, hit points,
  senses, challenge - from its stat block, which Open5e has wrong in places (it
  files every Tiny creature as Small, and leaves out the dragons' "(Chromatic)");
- the wording of every condition, rule and stat block entry, through
  `Wording.reword` (shared with the SRD 5.1 importer, in
  ../srd-5e-2014/srd_text.py): Open5e drops each attack's "Hit:" and leaves
  markup in its text ("Sphere [Area of Effect]").

The Rules Glossary is not among Open5e's fixtures. Its entries come from the
markdown the fixtures were first imported from (raw_sources/srd_5_2/sections),
which gives each entry's paragraphs and tables, and are reworded against the
PDF like everything else - Open5e notes the markdown no longer matches it.

Needs PyMuPDF (pip install pymupdf).
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "srd-5e-2014"))

from srd_text import SIZES, Wording  # noqa: E402


def text_of(pdf: pathlib.Path) -> str:
    """The PDF's text as one line, page furniture gone and words rejoined.

    The PDF breaks words over lines with a plain hyphen ("suc-\\nceed"), so a
    hyphen at a line end is dropped when the word it leaves is one the SRD uses
    elsewhere, and kept when the hyphenated word is ("shape-shifts").
    """
    import pymupdf

    pages = []
    for page in pymupdf.open(pdf):
        text = page.get_text("text")
        text = re.sub(r"^\s*(?:\d+\s*\n\s*System Reference Document 5\.2\.1|"
                      r"System Reference Document 5\.2\.1\s*\n\s*\d+)\s*\n", "", text)
        pages.append(text)
    raw = "\n".join(pages)
    raw = raw.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')

    whole = re.sub(r"(\w)-\n(\w)", r"\1 \2", raw).lower()
    words = collections.Counter(re.findall(r"[a-z]+", whole))
    hyphenated = set(re.findall(r"[a-z]+-[a-z]+", whole))

    def rejoin(match: re.Match) -> str:
        left, right = match.group(1), match.group(2)
        if words[(left + right).lower()]:
            return left + right
        if f"{left}-{right}".lower() in hyphenated or left[-1].isdigit() or right[0].isupper():
            return f"{left}-{right}"
        return left + right

    raw = re.sub(r"(\w+)-\n(\w+)", rejoin, raw)
    return re.sub(r"\s+", " ", raw).strip()


# --- monsters ------------------------------------------------------------------

#: A stat block's labelled header lines, in the order the SRD prints them.
STAT_LINES = [
    "AC", "Initiative", "HP", "Speed", "Skills", "Vulnerabilities", "Resistances",
    "Immunities", "Gear", "Senses", "Languages",
]

ABILITY_ROW = re.compile(
    r"MOD SAVE MOD SAVE MOD SAVE "
    + " ".join(rf"{a} (\d+) ([+−-]\d+) ([+−-]\d+)" for a in ("Str", "Dex", "Con", "Int", "Wis", "Cha"))
)

#: "CR 17 (XP 18,000, or 20,000 in lair; PB +6)"; a few blocks print "700 XP".
CHALLENGE = re.compile(
    r"CR (?P<cr>[\d/]+) \((?:XP (?P<xp>[\d,]+)|(?P<xp_after>[\d,]+) XP)"
    r"(?:,? or (?P<lair>[\d,]+) in lair)?; PB \+(?P<pb>\d+)\)"
)


def stat_blocks(text: str, names: list[str]) -> dict[str, dict]:
    """Each named creature's stat block: its header lines, and its text.

    A block runs from its name to the next block's, so `text` holds its traits
    and actions for rewording against. A name with no stat block is left out.
    """
    sizes = rf"(?:{SIZES})(?: or (?:{SIZES}))?"
    starts: dict[str, re.Match] = {}
    # Longest first, so the Hawk is not found inside the Blood Hawk's block.
    for name in sorted(names, key=len, reverse=True):
        pattern = rf"(?<![\w']){re.escape(name)} ({sizes}) ((?:[^,(]|\([^)]*\))+?), (.+?) AC (?=\d)"
        for found in re.finditer(pattern, text):
            if all(not other.start() <= found.start() < other.end() for other in starts.values()):
                starts[name] = found
                break
    order = sorted(starts.values(), key=lambda m: m.start())
    ends = {m.start(): n.start() for m, n in zip(order, order[1:])}
    blocks = {}
    for name, found in starts.items():
        segment = text[found.start() : ends.get(found.start(), len(text))]
        challenge = CHALLENGE.search(segment)
        header = segment[found.end() - found.start() - len("AC ") : challenge.start()]
        scores = ABILITY_ROW.search(header)
        if scores:
            header = header[: scores.start()] + header[scores.end() :]
        labels = "|".join(STAT_LINES)
        lines = dict(re.findall(rf"(?:^| )({labels}) (.+?)(?= (?:{labels}) |$)", header.strip()))
        blocks[name] = {
            "size": found.group(1),
            "type": found.group(2),
            "alignment": found.group(3),
            "scores": [int(scores.group(1 + 3 * i)) for i in range(6)] if scores else None,
            "saves": [scores.group(3 + 3 * i).replace("−", "-") for i in range(6)] if scores else None,
            "mods": [scores.group(2 + 3 * i).replace("−", "-") for i in range(6)] if scores else None,
            **{label: lines.get(label, "").strip() for label in STAT_LINES},
            "challenge": challenge["cr"],
            "xp": int((challenge["xp"] or challenge["xp_after"]).replace(",", "")),
            "xp_in_lair": int(challenge["lair"].replace(",", "")) if challenge["lair"] else None,
            "proficiency_bonus": int(challenge["pb"]),
            "text": segment,
        }
    return blocks


# --- rules glossary --------------------------------------------------------------


def glossary(markdown: pathlib.Path) -> list[tuple[str, str]]:
    """The Rules Glossary's entries as (heading, markdown) pairs, in order."""
    text = markdown.read_text(encoding="utf-8")
    text = text[text.index("## Rules Definitions") :]
    entries: list[tuple[str, list[str]]] = []
    for line in text.split("\n"):
        heading = re.match(r"#{3,4} (?!\*\*)(.+)", line)
        if heading:
            entries.append((heading.group(1).strip(), []))
        elif entries and not line.startswith("## "):
            entries[-1][1].append(re.sub(r"^#{3,} \*\*(.+)\*\*$", r"\1", line))
    return [(heading, "\n".join(body).strip()) for heading, body in entries]


class Srd(Wording):
    """The SRD 5.2.1's text, and the stat blocks read from it."""

    def __init__(self, pdf: pathlib.Path):
        super().__init__(text_of(pdf))
        self.stat_blocks = lambda names: stat_blocks(self.text, names)
