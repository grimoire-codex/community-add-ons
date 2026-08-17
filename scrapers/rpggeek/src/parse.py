import difflib
import html
import re
from html.parser import HTMLParser


# ── Text ─────────────────────────────────────────────────────────────────────

class _MessyHTMLScrubber(HTMLParser):
    """
    Minimal HTML-to-text converter using just the standard library.
    We don't want to drag in BeautifulSoup just for stripping BGG's messy description blocks.
    """

    def __init__(self):
        super().__init__()
        self._parts = []
        self._in_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._in_skip += 1
        # BGG's HTML can be a bit of a mess. Treat block-level tags as paragraph breaks 
        # so we don't end up with mashed together text when stripping tags.
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "hr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._in_skip = max(0, self._in_skip - 1)

    def handle_data(self, data):
        if not self._in_skip:
            self._parts.append(data)

    def get_text(self):
        text = "".join(self._parts)
        # Strip leading whitespace from each line (list indentation artefacts),
        # then collapse runs of blank lines.
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return html.unescape(text).strip()


def _scrub_html(text):
    """
    Feed messy BGG description HTML through our minimal parser to get 
    clean, readable plain text out the other side.
    """
    if not text:
        return ""
    parser = _MessyHTMLScrubber()
    parser.feed(text)
    return parser.get_text()


# ── Dice ─────────────────────────────────────────────────────────────────────

# Matches the dice notation inside "Dice (Primarily d20)" or "Dice (d6 Pool)".
_DICE_PAREN = re.compile(r"^Dice\s*\((.+?)\)", re.IGNORECASE)
# Matches a dice token like "d20", "2d6", "d100".
_DICE_TOKEN = re.compile(r"\d*d\d+", re.IGNORECASE)


def extract_dice(mechanic):
    """
    Sifts through BGG's noisy mechanic labels ("Dice (Primarily d20)", etc) 
    and distills them down to clean notations ("D20"). If it's a physical supply 
    we track (Jenga towers, cards), we map it. If it's something weird, we drop it.
    """
    stripped = mechanic.strip()

    m = _DICE_PAREN.match(stripped)
    if not m:
        # Check for other physical supplies supported by Grimoire
        lower = stripped.lower()
        if "jenga" in lower or "dexterity-based" in lower:
            return "Tumbling Tower (Jenga Tower)"
        if "candle" in lower:
            return "Candles"
        if "poker chip" in lower:
            return "Poker Chips"
        if "timer" in lower:
            return "Timers"
        if "phone" in lower:
            return "Phone"
            
        # Check for card types
        if "tarot" in lower:
            return "Tarot Cards"
        if "playing card" in lower or "standard deck" in lower or "french-suited" in lower:
            return "Playing Cards"
        if re.search(r"\b(card|cards|deck|decks)\b", lower):
            return "Custom Deck"
            
        # Not a dice or supported mechanic - discard it.
        return None

    inner = m.group(1)
    # BGG labels their dice mechanics with verbose, messy strings like "Dice (Primarily d20)".
    # We strip the common prefix here so we don't clutter the UI.
    inner = re.sub(r"^Primarily\s+", "", inner, flags=re.IGNORECASE)

    # Pull the first dice token out of whatever remains ("d20", "2d6", etc.).
    token = _DICE_TOKEN.search(inner)
    if token:
        return token.group(0).upper()

    # We just want the raw dice notation (e.g. "d20", "2d6"). If the parens didn't 
    # hold anything recognisable, we just throw it out.
    return None


def extract_edition(name, family):
    """
    BGG bakes editions directly into the system name (e.g. "Dungeons & Dragons 5th Edition").
    We try to smartly isolate the edition by subtracting the system family from the name.
    If that trick fails (because they don't share text), we fall back to sweeping for 
    common edition regex patterns.
    """
    if not name:
        return None
        
    if family and family.lower() in name.lower():
        pattern = re.compile(re.escape(family), re.IGNORECASE)
        diff = pattern.sub("", name).strip()
        
        # Clean up any wrapping parens
        if diff.startswith("(") and diff.endswith(")"):
            diff = diff[1:-1].strip()
            
        # Clean up leading dashes or colons
        diff = diff.lstrip(" :-").strip()
        
        # Clean up double spaces
        diff = " ".join(diff.split())
        
        if diff:
            return diff

    # Fallback: scan for common edition keywords
    patterns = [
        re.compile(r"\b(\d+(?:\.\d+)?e)\b", re.IGNORECASE),
        re.compile(r"\b(\d+(?:st|nd|rd|th)?(?:\s+\w+)?\s+(?:edition|ed\.?))\b", re.IGNORECASE),
        re.compile(r"\b((?:revised|anniversary|adventure|starter|core)\s+edition)\b", re.IGNORECASE)
    ]
    
    for p in patterns:
        m = p.search(name)
        if m:
            return m.group(1).strip()
            
    return None


# ── Fuzzy ranking ────────────────────────────────────────────────────────────

def _score_fuzzy_match(a, b):
    """
    Simple fuzzy ratio scoring so we don't need to import external libraries like thefuzz.
    Perfect for ranking API search results that might have slightly mangled titles.
    """
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ── BGG XML helpers ──────────────────────────────────────────────────────────

def _grab_attr(element, path, attrib="value", default=None):
    """
    BGG's XML is quirky - it stores almost everything in `value` attributes 
    rather than element text. This grabs a child node and pulls that value safely.
    """
    node = element.find(path)
    if node is None:
        return default
    return node.get(attrib, default)


def _grab_links(element, link_type):
    """
    Grabs all the values for a specific `<link type="...">` tag. 
    BGG uses these for everything from genres to mechanics.
    """
    return [
        link.get("value")
        for link in element.findall("link")
        if link.get("type") == link_type and link.get("value")
    ]


def _grab_links_with_id(element, link_type):
    """
    Same as _grab_links, but pulls the internal BGG ID as well.
    Useful when we actually need to make follow-up queries against specific entities.
    """
    return [
        (link.get("id"), link.get("value"))
        for link in element.findall("link")
        if link.get("type") == link_type and link.get("value")
    ]
