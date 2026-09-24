# Noble Knight Games scraper

Fills in **book** metadata from [Noble Knight Games](https://www.nobleknight.com),
a long-running store for new and out-of-print tabletop games. Its catalogue is
especially strong on older printed RPG books (TSR, early Paizo, Chaosium, and
other long out-of-print lines) that digital storefronts never carried, and it
lists each printing separately.

## What it fills in

| Grimoire field | Product Details row | Notes |
| --- | --- | --- |
| `title` | Title | A trailing article is moved back to the front: "Gaean Reach, The - Core Rules" becomes "The Gaean Reach - Core Rules" |
| `description` | Description | Store copy, reduced to plain text |
| `authors` | Author | Split into one entry per name |
| `artists` | Artist | Only when the listing has one, which is rare |
| `publisher` | Publisher | |
| `genres` | Genre | `RPG - ` entries only - see below |
| `year` | Publish Year | |
| `product_code` | MFG. Part # | The publisher's catalogue number, e.g. `HG235`, `PZO90140`. Needs Grimoire 1.7.2 |
| `isbn` | ISBN | Only when the listing has one, which is rare |
| `urls` | derived | A link back to the product page |

Not mapped: price, condition, stock, page count, dimensions, format (Type), and
the **NKG Part #**. Price, condition, and stock are volatile storefront data.
Page count is read from your actual file by the indexer. The NKG Part # is Noble
Knight's internal stock number, not the publisher's product code, so it is left
out.

## How it works

Noble Knight has no public API, so this is a script-backed add-on: it needs
**Allow add-on scripts** turned on and your approval at install. The script uses
only the Python standard library (`urllib.request`, `html.parser`) and is short
enough to read before you approve it.

Two requests per lookup:

1. **Search** - the store's search box is powered by
   [Zoovu](https://zoovu.com), a hosted search service. The script calls the
   same Zoovu JSON API the search box does
   (`api.search.zoovu.com/search?projectId=43167&query=…`), which returns names,
   publishers, years, and formats. Results are cached for an hour.
2. **Fetch** - `GET https://www.nobleknight.com/P/{id}/` for the result you
   pick. The page's **Product Details** block is a regular list of label/value
   rows, and the script reads those rows by their labels rather than by page
   position, so layout changes elsewhere on the page don't affect it. The parsed
   result is cached for a day.

An unknown ID redirects to the store's home page instead of returning a 404. The
script detects that and reports "no product with that ID".

## Matching

Noble Knight lists every printing, edition, and condition as its own product, so
searching "Tomb of Horrors" returns the 1978 pastel printing, the 1981 green
printings, the 2010 reprint, and more. Condition variants of one product are
merged into a single result. The label shows the publisher, year, and format
(`Tomb of Horrors (4th Printing, Green) — TSR (1981), Module`) so you can tell
the rest apart.

The store's own relevance order favours loose matches, so the script re-ranks
results locally by title similarity:

- Bracketed printing details are ignored when comparing, so every printing of
  "Tomb of Horrors" matches the query equally.
- A title that contains every word of your query ranks high even if it is much
  longer ("Wilderfeast Core Book" for "Wilderfeast").
- Non-book products (dice, card singles, boxed games, accessories) rank a little
  lower than an equally good book match, but still appear.

The catalogue covers board games, card games, and miniatures too, so a short
query can surface those. Check the format in the label before applying a result.

**Skip the search.** If you already have the product page open, paste its URL
into the "paste a link or ID" box instead. A bare ID (`2148278622`) works too.

## Genres

The Genre row mixes three kinds of entry: real genres (`RPG - Fantasy`,
`RPG - Horror`), game systems (`Pathfinder`, `Call of Cthulhu`), and formats
(`Magazine - Role-Playing`). Only the `RPG - ` entries are mapped, with the
prefix removed, so a book gets `Fantasy` and not `Pathfinder (1st Edition)`. A
book whose listing has only system or format entries gets no genres.

## Source terms

Noble Knight's `robots.txt` asks crawlers to stay out of its `/Search` pages.
This scraper is not a crawler: every request is one lookup that a person
started in Grimoire, the same thing their browser would do on the store's site.
It never walks the catalogue, follows links, or requests anything unprompted.
It also doesn't touch the `/Search` pages. Search goes to Zoovu's API host,
which has no `robots.txt`, and fetch reads product pages, which `robots.txt`
allows.

To keep the load light, each lookup is one search request and one page request,
both cached, sent with a User-Agent that identifies Grimoire. No analytics or
tracking calls are made.

Product data belongs to Noble Knight Games and the respective publishers. This
definition grants no rights to it.

## Known limitations

- The search project ID (`43167`) comes from the store's search plugin
  configuration. If Noble Knight changes search providers or projects, search
  breaks until this add-on is updated, but pasting a link keeps working.
- The year and product code are for the specific printing you pick.
- Magazine issues keep the store's title format (`#319 "Dark Sun Player's
  Handbook"`).
- Author credits are often missing on older or used listings.
- Fetch reads HTML, so a redesign of the product page can break it. Please open
  a PR if you spot breakage.
