# TTRPG Wiki scraper

Fills in game-system metadata from [ttrpgwiki.com](https://ttrpgwiki.com), a
community-maintained comparison site covering 227 tabletop RPG systems.

## What it fills in

| Grimoire field | Source field | Notes |
| --- | --- | --- |
| `description` | `tagline` | One-line summary |
| `publishers` | `publisher` | Single publisher, wrapped as a list |
| `year` | `year` | First-release year of that edition |
| `license` | `license` | e.g. `CC BY 4.0 (SRD); core books proprietary` |
| `system_family` | `family` | e.g. `Forged in the Dark`, `d20 System` |
| `edition` | `edition` | e.g. `5th Edition` |
| `genres` | `genre` | Title-cased from lowercase source tokens |
| `dice_materials` | `dice` | Free-form (`d20`, `d6 dice pool`, `Diceless`) |
| `tags` | `tags` | Descriptive play-style tags |
| `urls` | `officialUrl`, `dtrpgUrl` | Added only when present |

Not mapped: `complexity`, `accessibility`, `runnability`, `cost`,
`coreMechanic`, `bestFor`, `highlights`, `considerations`, `languages`. These
are either subjective ratings or long-form review copy with no Grimoire field to
land in.

## How it works

The site publishes its entire catalogue as a single static JSON document at
`/data/systems.json`, so this scraper makes **one** request per day (per the
`cache_ttl`) regardless of how many systems you look up. Individual
`/systems/<slug>` pages are client-rendered from that same file and contain no
additional data, so there is nothing to gain from fetching them.

## Matching

Candidates are ranked by fuzzy match on `name`, with `edition` as a light
tiebreaker. Because the source splits editions into separate records (`Pathfinder`
1st vs 2nd, three D&D editions), searching a bare system name usually returns
several candidates — pick the edition you own.

You can also paste a system's page URL (or its bare slug) into the "paste a link
or ID" box to go straight to that entry.

## Source terms

`robots.txt` permits general crawling (`Allow: /`). The site's Content-Signal
header is `search=yes, ai-train=no, use=reference`; this scraper consumes the
data as reference material for your own library, which is consistent with that.

The data belongs to TTRPG Wiki. This definition grants no rights to it — please
keep `cache_ttl` generous and don't remove the attribution.

## Known limitations

- The slug used for the "view source" link is derived from the system name. For
  a handful of titles that repeat the edition in the name, the derived slug can
  miss, giving a link that 404s. Metadata itself is unaffected.
- The upstream JSON is an undocumented static asset. If the site restructures it,
  this definition needs a version bump — please open a PR if you spot breakage.
