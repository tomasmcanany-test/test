#!/usr/bin/env python3
"""
Reusable tool to add papers to a Zotero collection via the Zotero Web API.

Use this to flag papers for you to save/download. It reads the paper list from
a JSON file, creates (or finds) a collection, and adds each paper as a journal
article tagged with your chosen tags.

Security:
  - The API key is read from the ZOTERO_KEY environment variable (never
    hardcoded). Create a scoped, revocable key at
    https://www.zotero.org/settings/keys and revoke it when done.

Usage:
  set ZOTERO_KEY=your_key
  python zotero_add.py --papers papers.json --collection "Drosophila Terminalia"
  python zotero_add.py --papers papers.json --tag "to-download" --tag "terminalia"

Dependencies:
  requests  (pip install -r requirements.txt)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

BASE = "https://api.zotero.org"


def get_user_id(api_key: str) -> int:
    """Resolve the user ID from the API key itself."""
    r = requests.get(f"{BASE}/keys/current", headers={"Zotero-API-Key": api_key})
    r.raise_for_status()
    return r.json()["userID"]


def find_collection(user: int, api_key: str, name: str) -> str | None:
    r = requests.get(f"{BASE}/users/{user}/collections",
                     headers={"Zotero-API-Key": api_key})
    r.raise_for_status()
    for c in r.json():
        if c["data"]["name"] == name:
            return c["key"]
    return None


def create_collection(user: int, api_key: str, name: str) -> str:
    r = requests.post(
        f"{BASE}/users/{user}/collections",
        headers={"Zotero-API-Key": api_key, "Content-Type": "application/json"},
        data=json.dumps([{"name": name, "parentCollection": False}]),
    )
    r.raise_for_status()
    body = r.json()
    if isinstance(body, list) and "successful" in body[0]:
        return body[0]["successful"]["key"]
    return body[0]["data"]["key"]


def load_papers(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("papers", [])
    return data


def add_items(user: int, api_key: str, papers: list[dict],
              collection: str, tags: list[str]) -> int:
    headers = {"Zotero-API-Key": api_key, "Content-Type": "application/json"}
    items = []
    for p in papers:
        items.append({
            "itemType": p.get("itemType", "journalArticle"),
            "title": p["title"],
            "creators": p.get("creators", []),
            "date": p.get("date", ""),
            "publicationTitle": p.get("journal", ""),
            "DOI": p.get("doi", ""),
            "abstractNote": p.get("abstract", ""),
            "tags": [{"tag": t} for t in tags],
            "collections": [collection],
        })

    ok = 0
    for i in range(0, len(items), 50):
        batch = items[i:i + 50]
        r = requests.post(f"{BASE}/users/{user}/items", headers=headers,
                          data=json.dumps(batch))
        if r.status_code in (200, 201):
            res = r.json()
            ok += len(res.get("successful", {}))
        else:
            print(f"[!] Batch {i} failed: {r.status_code} {r.text[:300]}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add papers to a Zotero collection")
    parser.add_argument("--papers", required=True, help="Path to JSON file of papers")
    parser.add_argument("--collection", default="Drosophila Terminalia",
                        help="Collection name to create/use")
    parser.add_argument("--tag", action="append", default=["terminalia", "to-download"],
                        help="Tag to apply (repeatable)")
    args = parser.parse_args(argv)

    api_key = os.environ.get("ZOTERO_KEY")
    if not api_key:
        print("Error: set the ZOTERO_KEY environment variable first.")
        return 1

    user = get_user_id(api_key)
    print(f"[*] Zotero user ID: {user}")

    col = find_collection(user, api_key, args.collection)
    if col:
        print(f"[=] Using existing collection '{args.collection}' ({col})")
    else:
        col = create_collection(user, api_key, args.collection)
        print(f"[+] Created collection '{args.collection}' ({col})")

    papers = load_papers(Path(args.papers))
    print(f"[*] Adding {len(papers)} papers with tags {args.tag}")
    ok = add_items(user, api_key, papers, col, args.tag)
    print(f"[=] Added {ok} items.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
