# Add-on format reference

An add-on is a directory containing a YAML manifest named after its `id`:

```
scrapers/my-source/
├── my-source.yml     # required — the manifest
├── my-source.py      # optional — only for script-backed add-ons
└── README.md         # strongly encouraged
```

Everything here is validated by [`schema/addon.schema.json`](../schema/addon.schema.json).
Point your editor at it for completion and inline errors.

## Identity

```yaml
id: my-source            # lowercase, hyphenated; must match the directory name
name: My Source          # display name
version: 1.0.0           # semver — bump on every change
kind: scraper
target: game-system
description: One line, shown in the add-on browser.
homepage: https://example.com
attribution: Data from Example (example.com)
grimoire_min_version: 1.5.5
```

## `target` — what it populates

`game-system` (the default) or `book`. This decides which `map` fields are
valid and which editor the add-on shows up in. Grimoire rejects a manifest that
maps a field its target does not have.

## `source` — where the data comes from

Only `json` is supported. There are two shapes.

**Catalogue** — one URL serving every record:

```yaml
source:
  url: https://example.com/data.json
  format: json
  cache_ttl: 86400       # seconds Grimoire reuses a cached response
  user_agent: "Grimoire/{version} (+https://github.com/hunter-read/grimoire)"
```

Grimoire fetches it once and answers every search and fetch from the cache.
Prefer this when the source publishes a bulk file: it is a single request per
day rather than one per lookup.

**Search** — a URL containing `{query}`, answering per search:

```yaml
source:
  url: https://example.com/api/products?q={query}&limit=40
  format: json
  cache_ttl: 3600
```

`{query}` is replaced with the URL-encoded search term. Each distinct query is
cached separately, so keep `cache_ttl` shorter than a catalogue's.

Fetch a generous page (30–50) and let Grimoire re-rank locally — store relevance
usually favours popular items over exact title matches.

Grimoire enforces its own request timeout, response size cap, and redirect limit
regardless of what the manifest says.

## `detail` — a second request for the full record

Many search endpoints return trimmed summaries. When they do, name the per-item
endpoint and the field mapping runs against **that** response instead:

```yaml
detail:
  url: https://example.com/api/products/{identity}
  # root: data     # optional, if the item is nested
```

`{identity}` is the identity your `search` block produced. Use this whenever the
summary lacks fields you want to map — it is one extra request, made only when
the user actually picks a result.

## `records` — finding the list

```yaml
records:
  root: "$"                                  # bare top-level array
  # root: "data.systems"                     # or a dotted path
  skip_when: { field: hidden, equals: true } # drop records matching this
```

## `search` — matching a query to a record

```yaml
search:
  fields:
    - { field: name, weight: 1.0, strategy: fuzzy }
    - { field: edition, weight: 0.3, strategy: fuzzy }
  min_score: 0.55
  limit: 10
  label: { template: "{name} ({edition})" }
  identity: { template: "{name}", transform: slugify }
  url: { template: "https://example.com/s/{identity}" }
```

- `strategy` — `fuzzy` (similarity ratio), `exact`, or `contains`.
- `weight` — relative contribution; the best-scoring field dominates, others
  refine. Give secondary signals a low weight.
- `min_score` — 0–1 floor. Too low floods the user with junk; too high loses
  legitimate matches on differently-punctuated names. `0.5`–`0.6` is a good start.
- `identity` — must be **stable and unique**: it's how Grimoire re-finds the
  record when the user picks it. Use a real id field if the source has one.
- `label` — what the user sees in the candidate list. Include whatever
  distinguishes near-duplicates (edition, publisher, year).
- `url` — optional "view source" link. `{identity}` refers to the resolved
  identity value; any other `{field}` reads from the record.
- `identity_pattern` — optional regex enabling **"paste a link or ID"**. See below.

### Letting users paste a link

Search isn't always the fastest route: someone looking at the item's page in
another tab already knows exactly which one they want. Give a regex with
**exactly one capture group** that pulls the identity out of a source URL:

```yaml
search:
  identity: { from: productId }
  identity_pattern: "/product/(\\d+)"
```

Grimoire then shows a "paste a link or ID" box for your source. It accepts a
full URL, a partial one, or the bare identity typed by hand, and goes straight
to the review step. Sources without a pattern simply don't offer the box.

Whatever the pattern captures must be a valid `identity` — the same value your
`identity` spec produces — since it feeds the same lookup (and `detail`, if you
have one).

Keep the pattern simple. It is length-capped, must capture exactly one group,
and is rejected if it contains a nested quantifier such as `(a+)+`, which can
cause catastrophic backtracking. `([a-z0-9-]+)` and `(\\d+)` are fine.

## `map` — filling in Grimoire's fields

```yaml
map:
  description:    { from: tagline }
  year:           { from: year }
  license:        { from: license }
  system_family:  { from: family }
  parent_system:  { from: parent }
  edition:        { from: edition }
  genres:         { from: genre, transform: titlecase }
  dice_materials: { from: dice }
  tags:           { from: tags }
  publishers:     { from: publisher, as: link_list }
  urls:
    - { label: "Official site", from: officialUrl, when_present: true }
    - { label: "Store",         from: storeUrl,    when_present: true }
```

Mappable targets depend on `target`:

| `target: game-system` | `target: book` |
| --- | --- |
| `description`, `publishers`, `year`, `license`, `system_family`, `parent_system`, `edition`, `genres`, `dice_materials`, `tags`, `urls`, `character_builder_urls` | `title`, `description`, `authors`, `artists`, `publisher`, `publisher_url`, `urls`, `genres`, `isbn`, `version`, `language`, `license`, `year`, `month`, `day`, `tags` |

Note `publishers` (a system's list) versus `publisher` (a book's single name).

Grimoire coerces each mapped value to the shape its field expects — scalars for
text fields, lists for `genres`/`dice_materials`/`tags`, `{name, url}` objects
for `publishers`, `{label, url}` for the link lists. A single string mapped to a
list field becomes a one-element list.

### Mapping options

| Key | Effect |
| --- | --- |
| `from` | Source field name (dotted paths allowed) |
| `template` | Literal text with `{field}` placeholders |
| `split` | Split a scalar on this separator to make a list |
| `when_present` | Skip the entry entirely when the value is missing/empty |
| `as: link_list` | Wrap scalars as `[{name, url}]` (for `publishers`) |
| `label` | Entry label for `urls` / `character_builder_urls` |
| `transform` | A named transform, or a list applied in order |
| `select` | Narrow a list of objects before reading from it |
| `pluck` | Read one value out of each object `select` kept |
| `first` | Keep only the first value when the path yields several |

### Nested data

A dotted path descends through lists as well as objects, mapping over each
element and flattening once — so `filters.descriptions.name` collects the names
from every description of every filter.

That is often too broad. `select` narrows a list first, by `equals` or `in`:

```yaml
# One entry per language: keep the English one.
publisher_url:
  from: publisher.descriptions.url
  select: { field: languageCode, equals: en }
  first: true
```

When each surviving object holds its *own* repeated list, `pluck` reads one
value out of each:

```yaml
# `filters` mixes genre, format, and language branches in one flat list.
# Keep the genre branch, then take each entry's English name.
genres:
  from: filters
  select: { field: parentId, in: [10, 100] }
  pluck:
    from: descriptions.name
    select: { field: languageCode, equals: en }
    first: true
```

Repeated values are de-duplicated case-insensitively, since a flattened path can
reach the same value by several routes.

Transforms: `slugify`, `titlecase`, `upper`, `lower`, `trim`, `upper_dice`,
`strip_query`, `strip_html`.

`strip_html` reduces an HTML fragment to plain text, keeping paragraph breaks.
Store and catalogue descriptions are usually marketing HTML; Grimoire's
description fields are plain text, so map them through this.

`strip_query` drops a URL's query string and fragment. **Use it on any outbound
link whose source appends affiliate or tracking parameters** — importing those
into someone's library monetises their data on the source's behalf, and a PR
that maps affiliate links through unchanged will be asked to add it.

Use `split` only when the source really is a delimited list. Free-form prose
(`"d6 dice pool"`) should be mapped whole — splitting it produces fragments that
pollute the user's lookup values.

## Scripts

When a source can't be expressed declaratively, an add-on may ship a Python
script instead of `source`. Scripts run in an isolated subprocess and require
explicit user approval. See [`scripts.md`](scripts.md).

## Testing your add-on locally

You don't need to publish to test. Either:

- copy the directory into `DATA_PATH/add-ons/<id>/` and restart Grimoire; or
- serve this repo locally (`python3 -m http.server 8000`) and point
  **Settings → Metadata → Add-ons → Index URL** at
  `http://localhost:8000/index.json`.

Then open a game system, hit **Fetch metadata**, and check the diff.

## Conventions

- **Bump `version` on every change** — that's how installs detect updates.
- Prefer under-mapping to guessing.
- Keep `cache_ttl` generous. Every Grimoire install shares your request pattern.
- Document what you deliberately left unmapped, and why, in your README.
