# Script-backed add-ons

Most sources are a URL and a field map, and the YAML format in
[`format.md`](format.md) covers them. Some are not: paginated catalogues,
multi-step lookups, HTML that needs real parsing. For those, an add-on can ship
a Python script.

**This is a genuine escape hatch, and it comes with genuine risk.** A script runs
real code on the user's server. Prefer YAML whenever YAML can do the job.

## Security model

Grimoire will not run a script unless **both** of these are true:

1. **Allow add-on scripts** is enabled globally (Settings → Metadata → Add-ons).
   Off by default.
2. That specific add-on was approved at install time, via a dialog that names the
   script and shows its SHA-256.

Changing the script changes its digest, which revokes approval — an update that
introduces a script, or alters an existing one, must be re-approved.

When it does run, the script is:

- executed in a **separate short-lived subprocess**, not in the Grimoire server
  process, so a crash, hang, or memory blow-up takes down only that subprocess;
- killed at its `timeout` (default 60s, hard cap 300s);
- given **no database handle, no session, and no Grimoire internals** — just the
  query and its own directory;
- limited to one request/response cycle over stdin/stdout.

What this does **not** do: it is process isolation, not a sandbox. A script can
still open sockets, read files the server user can read, and talk to the network.
Treat installing a script-backed add-on as running a program you were sent — the
subprocess boundary contains accidents, not malice. This is exactly why these
add-ons live in a public repo where the code can be read before it's installed.

## Contract

Declare the script in the manifest, in place of `source`:

```yaml
id: my-source
name: My Source
version: 1.0.0
kind: scraper
target: game-system

script:
  entry: my_source.py
  timeout: 60
```

Grimoire invokes the script with a single JSON object on **stdin** and expects a
single JSON object on **stdout**. Anything on stderr is logged for the user.

### Request

```json
{ "action": "search", "query": "Blades in the Dark", "addon_dir": "/data/add-ons/my-source" }
```

```json
{ "action": "fetch", "identity": "blades-in-the-dark", "addon_dir": "/data/add-ons/my-source" }
```

### Response

`search` returns ranked candidates:

```json
{
  "results": [
    { "identity": "blades-in-the-dark", "label": "Blades in the Dark", "score": 0.98,
      "url": "https://example.com/s/blades-in-the-dark" }
  ]
}
```

`fetch` returns mapped Grimoire fields — the same targets the `map` block writes:

```json
{
  "fields": {
    "description": "A game of daring scoundrels.",
    "year": 2017,
    "publishers": [{ "name": "Evil Hat", "url": "" }],
    "system_family": "Forged in the Dark",
    "genres": ["Fantasy"]
  },
  "url": "https://example.com/s/blades-in-the-dark"
}
```

Report failure with an `error` key; Grimoire surfaces it to the user rather than
treating it as a crash:

```json
{ "error": "Source returned HTTP 503" }
```

### Skeleton

```python
import json
import sys


def search(query, addon_dir):
    return {"results": []}


def fetch(identity, addon_dir):
    return {"fields": {}}


def main():
    req = json.load(sys.stdin)
    action = req.get("action")
    addon_dir = req.get("addon_dir", "")
    if action == "search":
        out = search(req.get("query", ""), addon_dir)
    elif action == "fetch":
        out = fetch(req.get("identity", ""), addon_dir)
    else:
        out = {"error": f"unknown action: {action}"}
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
```

## Rules for script authors

- **Standard library only.** Grimoire does not install dependencies for add-ons.
  `urllib.request` and `html.parser` are available; `httpx` may not be.
- **Be quick.** You share a timeout with the user's patience. Cache to
  `addon_dir` if you must fetch a lot.
- **Never write outside `addon_dir`**, and never touch Grimoire's database.
- **Fail loudly and cleanly.** Return `{"error": ...}` rather than raising —
  an uncaught exception looks identical to a crash.
- **Keep it readable.** People are going to audit this before they trust it.
  Obfuscated or minified scripts will not be merged.
