# RPGGeek (System) scraper

Fills in **game-system** metadata from [RPGGeek](https://rpggeek.com) - specifically
the `/rpg/` pages, which represent a game system as a whole rather than any
individual product. Think "Dragonbane" the system, not the Dragonbane core set box.

For individual books and supplements (`/rpgitem/` URLs), there's a companion
scraper: `rpggeek`.

> **Requires `rpggeek` to be installed.** This scraper shares its implementation
> with the `rpggeek` book scraper - `rpggeek_common.py` lives in the `rpggeek/`
> directory and is imported at runtime. Install `rpggeek` first, or this one
> won't work.

## What it fills in

| Grimoire field | Source | Notes |
| --- | --- | --- |
| `description` | Description field | HTML stripped to plain text |
| `publishers` | Publishers | All listed publishers |
| `year` | Year published | |
| `genres` | RPG genres | e.g. "Fantasy (High Fantasy)", "Science Fiction" |
| `dice_materials` | Mechanics | e.g. "D20", "D6", "Candles", "Playing Cards" |
| `system_family` | RPG family | e.g. "Dungeons & Dragons" |
| `edition` | Computed | Extracted from the difference between the item name and the family name |
| `urls` | Derived | Link back to the RPGGeek system page |

Not mapped: `license`. There's no licence field in the BGG API - it's
a catalogue, not a licence registry. Edition is computed since it is typically
baked into the system name on RPGGeek (e.g. "Dungeons & Dragons 5th Edition") rather
than a separate field.

## How it works

RPGGeek runs on the BGG XML API v2. That API is XML-only, which is why this
add-on ships a Python script rather than a plain YAML definition - Grimoire's
declarative format only speaks JSON.

Two requests per lookup:

1. **Search** - `GET /xmlapi2/search?query=…&type=rpg` returns matching system
   entries. Grimoire re-ranks them locally by title similarity.
2. **Detail** - `GET /xmlapi2/thing?id=…&type=rpg` for the system you pick.
   Detail responses are cached locally for 24 hours.

The actual implementation is shared with the `rpggeek` book scraper via
`rpggeek_common.py` in the sibling `rpggeek/` directory. Both add-ons need to be
installed for this one to work.

## Dice field

RPGGeek's mechanic tags are verbose - "Dice (Primarily d20)", "Skill Based
(buy or gain skills)", and so on. This scraper filters them down to dice-related
entries or specific physical supplies, and shortens the label to match Grimoire's convention:

| RPGGeek mechanic | `dice_materials` value |
| --- | --- |
| Dice (Primarily d20) | D20 |
| Dice (Primarily d6) | D6 |
| Dice (d6 Pool) | D6 |
| Dice (Primarily d100/percentile) | D100 |
| Dexterity-based (e.g. Jenga tower) | Tumbling Tower (Jenga Tower) |
| Matches for "candle" | Candles |
| Matches for "poker chip" | Poker Chips |
| Matches for "timer" | Timers |
| Matches for "phone" | Phone |
| Matches for "tarot" | Tarot Cards |
| Matches for "playing card", "standard deck", "french-suited" | Playing Cards |
| Matches for "card" or "deck" | Custom Deck |
| Class Based (...), Skill Based (...), etc. | *(not mapped)* |

## Authentication

The BGG API has required a Bearer Token since mid-2025. Register a free application
at https://boardgamegeek.com/account/api and set the token on your Grimoire server:

```
BGG_API_TOKEN=your_token_here
```

The same token works for both the `rpggeek` and `rpggeek-system` scrapers.

## Finding the right system

**Search works well.** Type the system name - "Dragonbane", "Blades in the Dark",
"Call of Cthulhu" - and pick from the list.

**Paste a URL if you know it.** Drop the RPGGeek system URL into the "paste a link
or ID" box:

```
https://rpggeek.com/rpg/79109/dragonbane
```

A bare numeric ID works too (`79109`).

## Source terms

This uses the BGG XML API v2 with authentication, at a modest request rate with
a 24-hour detail cache. It doesn't scrape pages or bypass anything.

Data from RPGGeek is community-contributed and belongs to its respective
contributors and publishers. This definition grants no rights to it.

## Known limitations

- **No licence field.** RPGGeek isn't a licence registry. Use `ttrpg-wiki` if
  licence data matters to you.
- **BGG token required.** It's free and one-time, but it is a setup step.
- **Both add-ons must be installed.** `rpggeek-system` imports its implementation
  from the sibling `rpggeek/` directory. Install `rpggeek` first.
