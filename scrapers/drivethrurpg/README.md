# DriveThruRPG scraper

Fills in **book** metadata from [DriveThruRPG](https://www.drivethrurpg.com),
the largest storefront for tabletop RPG PDFs.

## What it fills in

| Grimoire field | Source field | Notes |
| --- | --- | --- |
| `title` | `description.name` | The store's product title |
| `description` | `description.description` | Store copy, HTML stripped to plain text |
| `authors` | `authors` | |
| `artists` | `artists` | |
| `publisher` | `publisher.name` | |
| `publisher_url` | `publisher.descriptions.url` | The publisher's own site, not the store page |
| `isbn` | `isbn` | Often empty for digital-only products |
| `genres` | `filters` | Genre branch only — see below |
| `year` | `dateAvailable` | Release year |
| `urls` | derived | A link back to the product page |

Not mapped: price, ratings, file size, page count, and format options. Price and
ratings are volatile storefront data with no Grimoire field; page count and file
size are read from your actual file by the indexer, which is more trustworthy
than the listing.

## How it works

DriveThruRPG's **website** sits behind a Cloudflare bot challenge — pages return
403 to anything that isn't a real browser, and scraping them would mean working
around that. This scraper doesn't touch the website at all.

Instead it uses the OneBookShelf **API** at `api.drivethrurpg.com`, which is a
documented, unauthenticated JSON API (it publishes an OpenAPI spec at
`/documentation`). That is both far more reliable than HTML scraping and
considerably lighter on their infrastructure.

Two requests per lookup:

1. **Search** — `GET /api/vBeta/products?keyword=…&order[matchWeight]=desc`
   returns relevance-ordered summaries. Grimoire re-ranks them locally by title
   similarity, because raw store relevance favours popular products over exact
   title matches.
2. **Detail** — `GET /api/vBeta/products/{productId}` for the result you pick.
   Search results are trimmed summaries with no authors, genres, or full
   description, and a placeholder release date, so the mapping runs against the
   detail response.

## Matching

DriveThruRPG's catalogue is enormous and includes a great deal of third-party
and community content, so searching a well-known title returns many near-misses
(supplements, character sheets, foreign-language editions, stock art). **Check
the publisher on the result before applying it** — the label shows it for
exactly this reason.

A book that isn't sold on DriveThruRPG simply won't be found. Several major
publishers (Free League, for instance) sell primarily through their own stores.

**Skip the search.** If you already have the product page open, paste its URL
into the "paste a link or ID" box instead — this scraper reads the product ID
straight out of it, so you land on the right item first time. A bare ID
(`170689`) works too, and any affiliate parameter on the end of a pasted link is
ignored.

## Genres

The API returns one flat `filters` list mixing several taxonomies: genre,
format ("PDF", "Physical Products"), language ("English"), and merchandising
("Staff Picks"). Only the genre branch is mapped — `parentId` 10 (top-level
genres) and 100 (sub-genres). Without that filter, a book's genre list would
fill up with "PDF" and "English".

## Source terms

This uses DriveThruRPG's own public API, unauthenticated and unmodified, at a
modest request rate with a one-hour response cache. It does not bypass the bot
protection on their web storefront, and it deliberately does not scrape pages.

The product links it writes contain **no affiliate code**. If you are a
DriveThruRPG affiliate and want your tag on links in your own library, add it
yourself after importing.

Product data belongs to DriveThruRPG and the respective publishers. This
definition grants no rights to it.

## Known limitations

- `isbn` is usually empty for digital products.
- The catalogue's breadth means search precision depends on a specific title.
  "Cairn" returns dozens of unrelated products; "Cairn Player's Guide" does not.
- `vBeta` is, as the name says, a beta API path. If it moves, this definition
  needs a version bump — please open a PR if you spot breakage.
