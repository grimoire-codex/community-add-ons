#!/usr/bin/env python3
"""Bundle of Holding library add-on.

Implements the library add-on script contract for Bundle of Holding:
- sync: list owned bundles from the Bundle of Holding website (logged in)
- download: download a bundle or locate it locally
- scan: not applicable for Bundle of Holding (no local files)

Credentials are passed via the `config` object in the request JSON:
  config: { "username": "...", "password": "..." }

The parent process creates Book records for each owned resource and stores
them with virtual filepaths (owned://bundleofholding/<id>). The user can
then download individual files from each bundle. The sync only needs to
run when the user wants to refresh their owned resources (e.g., after a
new purchase) — Book records persist in the database.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from typing import Any


BASE_URL = "https://www.bundleofholding.com"
LOGIN_URL = f"{BASE_URL}/user/login"
MY_BUNDLES_URL = f"{BASE_URL}/my-account/bundles"


def _build_opener(username: str, password: str) -> urllib.request.OpenerDirector:
    """Build an opener that logs into Bundle of Holding."""
    cj = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(cj)
    login_page_req = urllib.request.Request(LOGIN_URL)
    with opener.open(login_page_req, timeout=30) as resp:
        login_html = resp.read().decode("utf-8")

    csrf_token_match = re.search(
        r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']',
        login_html,
    )
    csrf_token = csrf_token_match.group(1) if csrf_token_match else ""

    login_data = {
        "users_email": username,
        "password": password,
        "_token": csrf_token,
        "remember": "1",
    }
    data = urllib.parse.urlencode(login_data).encode("utf-8")
    req = urllib.request.Request(LOGIN_URL, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Referer", LOGIN_URL)
    req.add_header(
        "User-Agent",
        "Grimoire (+https://github.com/hunter-read/grimoire)",
    )
    try:
        with opener.open(req, timeout=30) as resp:
            pass
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError("Invalid credentials — check your Bundle of Holding email and password") from e
        raise RuntimeError(f"Login failed: {e.code} {e.reason}") from e

    return opener


def _list_bundles(opener: urllib.request.OpenerDirector) -> list[dict[str, Any]]:
    """Fetch the user's owned bundles from Bundle of Holding."""
    req = urllib.request.Request(MY_BUNDLES_URL)
    try:
        with opener.open(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("Session expired — please re-authenticate") from e
        raise RuntimeError(f"Bundle of Holding error: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Bundle of Holding: {e.reason}") from e

    # Parse bundle cards from the HTML page
    bundles = []
    for match in re.finditer(
        r'<a[^>]+href="(/product/[^"]+)"[^>]*>\s*<h4[^>]*>([^<]+)</h4>',
        html,
    ):
        href = match.group(1)
        title = match.group(2).strip()
        bundles.append({
            "id": href.split("/")[-1],
            "name": title,
            "url": f"{BASE_URL}{href}",
        })

    # Fallback: parse from a different page structure if no bundles found
    if not bundles:
        for match in re.finditer(
            r'<div[^>]+class="[^"]*bundle[^"]*"[^>]*>.*?<h4[^>]*>([^<]+)</h4>',
            html,
            re.DOTALL,
        ):
            title = match.group(1).strip()
            bundles.append({
                "id": title.lower().replace(" ", "-"),
                "name": title,
                "url": "",
            })

    return bundles


def _download_bundle(
    opener: urllib.request.OpenerDirector, bundle_id: str
) -> dict[str, Any]:
    """Download a bundle's contents."""
    url = f"{BASE_URL}/product/{bundle_id}/download"
    req = urllib.request.Request(url)
    try:
        with opener.open(req, timeout=30) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Bundle not found: {bundle_id}") from e
        raise RuntimeError(f"Bundle of Holding error: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Bundle of Holding: {e.reason}") from e

    return {
        "path": f"/tmp/grimoire-download/bundleofholding-{bundle_id}.zip",
        "mime_type": "application/zip",
        "file_size": len(data),
    }


def _scan_local(_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Bundle of Holding does not scan local directories."""
    return []


def main() -> None:
    """Entry point — reads the request from stdin, writes the response to stdout."""
    try:
        request_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError) as e:
        print(json.dumps({"error": f"Invalid request: {e}"}))
        sys.exit(1)

    action = request_data.get("action")
    config = request_data.get("config", {})
    username = config.get("username", "")
    password = config.get("password", "")

    if not username or not password:
        print(json.dumps({"error": "Missing username or password in config"}))
        sys.exit(1)

    try:
        opener = _build_opener(username, password)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    try:
        if action == "sync":
            bundles = _list_bundles(opener)
            resources = []
            for bundle in bundles:
                resources.append({
                    "id": bundle["id"],
                    "title": bundle["name"],
                    "authors": [],
                    "publisher": "Bundle of Holding",
                    "year": 0,
                    "genres": [],
                    "isbn": "",
                    "version": "1.0",
                    "license": "Commercial",
                    "urls": [bundle.get("url", "")] if bundle.get("url") else [],
                    "source_url": bundle.get("url", ""),
                    "download_url": "",
                    "local_path": None,
                    "metadata": {
                        "bundle_id": bundle["id"],
                        "bundle_name": bundle["name"],
                    },
                })
            print(json.dumps({"resources": resources}))

        elif action == "download":
            resource_id = request_data.get("resource_id", "")
            if not resource_id:
                print(json.dumps({"error": "Missing resource_id"}))
                sys.exit(1)
            result = _download_bundle(opener, resource_id)
            print(json.dumps(result))

        elif action == "scan":
            resources = _scan_local(config)
            print(json.dumps({"resources": resources}))

        else:
            print(json.dumps({"error": f"Unknown action: {action}"}))
            sys.exit(1)

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()