# RPGGeek scraper

Fills in **book** metadata from [RPGGeek](https://rpggeek.com) - the RPG-focused
corner of the BoardGameGeek family. It covers rulebooks, supplements, adventures,
boxed sets, and anything else that ends up at a `/rpgitem/` URL.

For game systems themselves (the `/rpg/` pages, like "Dragonbane" the system rather
than the Dragonbane core set), there's a companion scraper: `rpggeek-system`.

## What it fills in

| Grimoire field | Source | Notes |
| --- | --- | --- |
| `title` | Primary name | |
| `description` | Description field | HTML stripped to plain text |
| `authors` | Designers | All credited designers |
| `artists` | Artists | All credited artists |
| `publisher` | Publishers | First listed publisher |
| `publisher_url` | Derived | Fetched from the publisher's detail page |
| `genres` | RPG genres | e.g. "Fantasy (High Fantasy)", "Science Fiction" |
| `year` | Year published | |
| `urls` | Derived | Link back to the RPGGeek item page |

Not mapped: `isbn`, `language`, `license`, `publisher_url`. RPGGeek doesn't carry
ISBN or language data in its API, and there's no licence field - it's a catalogue,
not a legal document store.

## How it works

RPGGeek runs on the BGG XML API v2. That API is XML-only, which is why this
add-on ships a Python script rather than a plain YAML definition - Grimoire's
declarative format only speaks JSON.

Two requests per lookup:

1. **Search** - `GET /xmlapi2/search?query=…&type=rpgitem` returns a short list
   of matching items with names and years. Grimoire re-ranks them locally by title
   similarity, because BGG's own ranking skews towards popularity.
2. **Detail** - `GET /xmlapi2/thing?id=…&type=rpgitem` for the item you pick.
   Detail responses are cached locally for 24 hours, so re-opening the same item
   doesn't hit the API again.

## Authentication

The BGG API has required a Bearer Token since mid-2025. You'll need to register a
free application at https://boardgamegeek.com/account/api and set the token as an
environment variable on your Grimoire server:

```
BGG_API_TOKEN=your_token_here
```

If the variable isn't set, the scraper will tell you clearly rather than returning
a confusing empty result. Not ideal that there's a setup step, but it's a one-time
thing.

## Finding the right item

**Search works well for most things.** Type the title, pick the edition you want
from the list - the label shows the year to help tell editions apart.

**Paste a URL if you're already on the page.** Drop a full RPGGeek URL into the
"paste a link or ID" box:

```
https://rpggeek.com/rpgitem/386173/dragonbane-mirth-and-mayhem-roleplaying
```

A bare numeric ID works too (`386173`). Either way you skip the search entirely
and land straight on the right item.

## Source terms

This uses the BGG XML API v2 with authentication, at a modest request rate with
a 24-hour detail cache. It doesn't scrape pages or bypass anything.

Data from RPGGeek is community-contributed and belongs to its respective
contributors and publishers. This definition grants no rights to it.

## Known limitations

- **No ISBN or language data.** The API doesn't carry them for RPG items.
- **No licence field.** RPGGeek isn't a licence registry.
- **First publisher only.** Items with multiple publishers (translated editions are
  common) list the primary one. The others are on the RPGGeek page itself.
- **Search breadth.** RPGGeek's catalogue is huge. A common name like "Player's
  Handbook" will return multiple editions - check the year in the label before
  applying.
