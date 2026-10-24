"""Turn the RSS, Atom and JSON feeds you follow into one spreadsheet of posts, newest first.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python feeds_to_csv.py <feeds file> [--csv posts.csv] [--since "7 days"]

The feeds file has one feed URL per line, or a blog's home page, whose feed is then found (blank lines and lines
starting with # are skipped). One run of RSS, Atom & JSON Feed Reader reads them all. Posts not yet in the CSV are
added to it, and the CSV is written newest first, so running the same command again adds only what is new. --since
reads only posts published after a date or a period back from now ("2026-10-01", "7 days").
"""
import argparse
import csv
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

READER = "wrentools/rss-feed-reader"
FIELDS = ["published (UTC)", "blog", "title", "link", "author", "summary", "id"]
FORMATS = {"rss20": "RSS 2.0", "rss10": "RSS 1.0", "atom10": "Atom", "jsonfeed": "JSON Feed"}
# A cell starting with one of these could be run as a formula by a spreadsheet; a leading ' keeps it text (OWASP,
# "CSV Injection"). Feeds are other people's text, so the text columns are treated this way.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")


def posts(n: int) -> str:
    return f"{n} post" if n == 1 else f"{n} posts"


def read_feeds(path: Path) -> list[str]:
    feeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line not in feeds:
            feeds.append(line)
    return feeds


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_text(value) -> str:
    value = " ".join(str(value or "").split())
    return "'" + value if value.startswith(FORMULA_START) else value


def row_of(item: dict) -> dict:
    published = item.get("published") or item.get("updated") or ""
    return {"published (UTC)": published.replace("T", " ")[:16], "blog": as_text(item.get("feedTitle")),
            "title": as_text(item.get("title")), "link": item.get("link") or "",
            "author": as_text(item.get("author")), "summary": as_text(item.get("summary")),
            "id": item.get("id") or item.get("link") or ""}


def update(feeds_file: Path, sheet: Path, since: str | None) -> int:
    feeds = read_feeds(feeds_file)
    rows = read_csv(sheet)
    seen = {r["id"] for r in rows}
    print(f"{len(feeds)} feeds; {sheet} has {posts(len(rows))}")
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    print(f"reading {len(feeds)} feeds in one run...")
    run_input = {"feedUrls": feeds, "maxItemsPerFeed": 100}
    if since:
        run_input["publishedAfter"] = since
    run = client.actor(READER).call(
        run_input=run_input,
        max_total_charge_usd=Decimal("0.50"),  # $0.001 a feed + $0.0003 a post: about 1,600 posts
    )
    found: dict[str, dict] = {url: {"feeds": {}, "failed": None} for url in feeds}
    added = 0
    for item in client.dataset(run.default_dataset_id).iterate_items():
        got = found.setdefault(item["requestedUrl"], {"feeds": {}, "failed": None})
        if item["type"] == "error":
            got["failed"] = item["error"]
            continue
        feed = got["feeds"].setdefault(item["feedUrl"], {"title": item.get("feedTitle") or item["feedUrl"],
                                                         "format": item.get("feedFormat"), "posts": 0, "new": 0})
        feed["posts"] += 1
        row = row_of(item)
        if row["id"] and row["id"] not in seen:
            seen.add(row["id"])
            rows.append(row)
            feed["new"] += 1
            added += 1
    summary = client.key_value_store(run.default_key_value_store_id).get_record("SUMMARY")["value"]
    failed = 0
    for url, got in found.items():
        if got["failed"]:
            failed += 1
            print(f"FAILED {url}: {got['failed']['code']} ({got['failed']['message']}), not charged")
        for feed_url, feed in got["feeds"].items():
            kind = FORMATS.get(feed["format"], feed["format"] or "feed")
            if feed_url != url:
                kind += ", found on the page you listed"
            print(f"{feed['title']} ({kind}): {posts(feed['posts'])}, {feed['new']} new")
        if not got["failed"] and not got["feeds"]:
            print(f"{url}: no posts returned before the run stopped" if summary["stoppedReason"]
                  else f"{url}: no posts" + (f" since {since}" if since else ""))
    rows.sort(key=lambda r: (r["blog"], r["title"]))
    rows.sort(key=lambda r: r["published (UTC)"], reverse=True)  # newest first; undated posts last
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:  # the BOM tells Excel the file is UTF-8
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")  # the same file on every system
        writer.writeheader()
        writer.writerows(rows)
    print(f"{added} new; {sheet} has {posts(len(rows))}, newest first")
    if summary["stoppedReason"]:  # at its charge cap or time limit; a re-run reads every feed again from the start
        print(f"the run stopped early ({summary['stoppedReason']}); raise max_total_charge_usd in this script, "
              "or read fewer posts with --since")
    return 1 if failed or summary["stoppedReason"] else 0


def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("feeds_file", type=Path)
    parser.add_argument("--csv", type=Path, default=Path("posts.csv"))
    parser.add_argument("--since")
    opts = parser.parse_args(args)
    return update(opts.feeds_file, opts.csv, opts.since)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
