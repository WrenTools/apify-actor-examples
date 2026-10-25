"""Check every page your sitemap lists, and the sitemap itself, in one run; write the problems to a CSV.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python check_sitemap.py <sitemap URL, or your site's address> [--csv sitemap-report.csv]

Give it a sitemap or a sitemap index, or just your site's address: the Actor then reads the Sitemap: lines in your
robots.txt, or tries /sitemap.xml. One run of Sitemap Validator checks each sitemap file against the sitemaps.org
rules and requests every page it lists once. Pages that are broken or redirect, and entries that break a rule, are
printed and written to the CSV, one row per problem. The exit code is 1 when there is any problem, so a scheduled job
can tell you.
"""
import argparse
import csv
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

VALIDATOR = "wrentools/sitemap-validator"
FIELDS = ["page", "problem", "what is wrong", "HTTP status", "redirects to", "sitemap"]
# A cell starting with one of these could be run as a formula by a spreadsheet; a leading ' keeps it text (OWASP,
# "CSV Injection"). A sitemap is whatever its site wrote, so every cell is treated this way.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")
FREQS = "always, hourly, daily, weekly, monthly, yearly or never"
RULES = {  # the Actor's issue codes for the sitemaps.org rules, in words
    "invalid-lastmod": lambda e: f'lastmod "{e["lastmod"]}" is not a W3C date; write it YYYY-MM-DD',
    "lastmod-in-future": lambda e: f"lastmod {e['lastmod']} is in the future",
    "invalid-changefreq": lambda e: f'changefreq "{e["changefreq"]}" is not {FREQS}',
    "invalid-priority": lambda e: f'priority "{e["priority"]}" is not a number',
    "priority-out-of-range": lambda e: f"priority {e['priority']} is not between 0.0 and 1.0",
    "duplicate-loc": lambda e: "listed more than once",
    "loc-on-other-host": lambda e: "on another host than the sitemap, which the protocol does not allow",
    "loc-not-absolute-http-url": lambda e: "not a full http:// or https:// address",
    "loc-not-escaped": lambda e: "has characters that must be escaped (& as &amp;)",
    "missing-loc": lambda e: "an entry with no <loc>",
}


def as_text(value) -> str:
    value = " ".join(str(value if value is not None else "").split())
    return "'" + value if value.startswith(FORMULA_START) else value


def problems_of(entry: dict) -> list[tuple[str, str, str]]:
    """(label, issue code, what is wrong) for each issue the Actor reported on one entry."""
    out = []
    for code in entry["issues"]:
        if code == "url-not-ok":
            status = entry.get("httpStatus")
            out.append(("BROKEN", code, f"HTTP {status}" if status else f"no answer ({entry.get('statusError')})"))
        elif code == "url-redirects":
            out.append(("REDIRECT", code, f"redirects to {entry.get('redirectedTo')}; list that address instead"))
        elif code == "url-blocked-by-robots-txt":
            out.append(("BLOCKED", code, "your robots.txt blocks it, so it was not requested"))
        else:
            out.append(("RULE", code, RULES[code](entry) if code in RULES else code))
    return out


def check(target: str, sheet: Path) -> int:
    if target.lower().split("?")[0].endswith((".xml", ".xml.gz", ".gz")):
        run_input = {"sitemapUrls": [target]}
    else:
        run_input = {"siteUrl": target}  # robots.txt Sitemap: lines, else /sitemap.xml
    run_input.update({"checkUrlStatus": True, "maxUrls": 5000, "maxSitemapFiles": 50})
    print(f"checking {target} and every page it lists, in one run...")
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(VALIDATOR).call(
        run_input=run_input,
        max_total_charge_usd=Decimal("0.50"),  # $0.002 a sitemap file + $0.0006 a page checked: about 830 pages
    )
    rows, pages, works, broken, redirects, unchecked, rule_breaking = [], 0, 0, 0, 0, 0, 0
    for item in client.dataset(run.default_dataset_id).iterate_items():
        if item["type"] == "sitemap-file":
            if item["errors"] or item["httpStatus"] != 200:
                what = ", ".join(item["errors"]) or f"HTTP {item['httpStatus']}"
                print(f"SITEMAP   {item['url']}  ({what})")
                rows.append({"page": item["url"], "problem": "sitemap-file", "what is wrong": what,
                             "HTTP status": item["httpStatus"], "redirects to": "", "sitemap": item["url"]})
            elif item["kind"] == "sitemapindex":
                print(f"{item['url']}: an index of {item['entryCount']} sitemaps")
            else:
                print(f"{item['url']}: {item['entryCount']} pages listed")
            continue
        pages += 1
        found = problems_of(item)
        labels = {label for label, _, _ in found}
        broken += "BROKEN" in labels
        redirects += "REDIRECT" in labels
        if not labels & {"BROKEN", "REDIRECT"}:  # requested and answered, or not requested (robots.txt, a bad <loc>)
            works += bool(item.get("statusChecked"))
            unchecked += not item.get("statusChecked")
        rule_breaking += "RULE" in labels
        for label, code, what in found:
            print(f"{label:<9} {item['loc']}  ({what})")
            rows.append({"page": item["loc"], "problem": code, "what is wrong": what,
                         "HTTP status": item.get("httpStatus"), "redirects to": item.get("redirectedTo"),
                         "sitemap": item["sitemap"]})
    summary = client.key_value_store(run.default_key_value_store_id).get_record("SUMMARY")["value"]
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:  # the BOM tells Excel the file is UTF-8
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")  # the same file on every system
        writer.writeheader()
        writer.writerows({k: as_text(v) for k, v in row.items()} for row in rows)
    print(f"{pages} pages: {works} work, {broken} broken, {redirects} redirect"
          + (f", {unchecked} not requested" if unchecked else "") + f"; {rule_breaking} "
          f"{'breaks' if rule_breaking == 1 else 'break'} a sitemap rule; "
          f"{len(rows)} {'problem' if len(rows) == 1 else 'problems'} in {sheet}")
    if summary["stoppedReason"]:  # the charge cap, maxUrls or the time limit; the pages after it were not checked
        print(f"the run stopped early ({summary['stoppedReason']}); pages after that point were not checked")
    return 1 if rows or summary["stoppedReason"] else 0


def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("target")
    parser.add_argument("--csv", type=Path, default=Path("sitemap-report.csv"))
    opts = parser.parse_args(args)
    return check(opts.target, opts.csv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
