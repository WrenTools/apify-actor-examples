"""Audit your own website's on-page SEO in one run: every page's score and problems, printed and written to a CSV.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python seo_check.py <your home page> [--max-pages 50] [--csv seo-report.csv]

One run of Own-Site SEO Audit starts at your home page, follows the links on the same site (obeying your robots.txt)
and checks every page it reaches the way a search engine reads it: the title, the meta description, the headings,
images without alt text, structured data that does not parse, links to pages that are broken, and titles or
descriptions that two pages share. Each page gets a score out of 100. The problems are printed under each page and
written to the CSV, one row per problem. The exit code is 1 when any problem is rated high, so a scheduled job can
tell you.
"""
import argparse
import csv
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

AUDIT = "wrentools/own-site-seo-audit"
FIELDS = ["page", "score", "severity", "problem", "what is wrong"]
# A cell starting with one of these could be run as a formula by a spreadsheet; a leading ' keeps it text (OWASP,
# "CSV Injection"). Titles and links are whatever the site wrote, so every cell is treated this way.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


WORDS = {  # the Actor's issue codes, in words; d is the issue's detail, p the page
    "missing-title": lambda d, p: "no <title>",
    "title-too-long": lambda d, p: f"the title is {d} characters; search results cut it after about 60",
    "title-too-short": lambda d, p: f"the title is only {d} characters",
    "multiple-title-tags": lambda d, p: f"{d} <title> tags",
    "missing-meta-description": lambda d, p: "no meta description",
    "meta-description-length": lambda d, p: f"the meta description is {d} characters; aim for 50 to 160",
    "missing-h1": lambda d, p: "no <h1> heading",
    "multiple-h1": lambda d, p: f"{d} <h1> headings",
    "images-missing-alt": lambda d, p: plural(d, "image", "images") + " without alt text",
    "noindex": lambda d, p: "marked noindex, so search engines are asked not to list it",
    "canonical-points-elsewhere": lambda d, p: f"its canonical address is another page: {d}",
    "missing-html-lang": lambda d, p: "no lang on <html>",
    "missing-viewport": lambda d, p: "no mobile viewport tag",
    "invalid-json-ld": lambda d, p: plural(d, "structured data (JSON-LD) block does", "structured data (JSON-LD) "
                                           "blocks do") + " not parse",
    "redirected": lambda d, p: f"redirects to {d}",
    "http-error": lambda d, p: f"HTTP {d}" if isinstance(d, int) else f"no answer ({d})",
    "broken-internal-links": lambda d, p: "links to " + plural(d, "broken page", "broken pages") + " on your site: "
                                          + ", ".join(p["brokenInternalLinks"]),
    "broken-external-links": lambda d, p: "links to " + plural(d, "broken page", "broken pages") + " on other "
                                          "sites: " + ", ".join(p["brokenExternalLinks"]),
    "duplicate-title": lambda d, p: "the same title as " + ", ".join(d),
    "duplicate-meta-description": lambda d, p: "the same meta description as " + ", ".join(d),
}


def as_text(value) -> str:
    value = " ".join(str(value if value is not None else "").split())
    return "'" + value if value.startswith(FORMULA_START) else value


def words(issue: dict, page: dict) -> str:
    code = issue["code"]
    return WORDS[code](issue.get("detail"), page) if code in WORDS else code


def audit(start: str, max_pages: int, sheet: Path) -> int:
    print(f"auditing {start} and the pages it links to on the same site, in one run...")
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(AUDIT).call(
        run_input={"startUrl": start, "maxPages": max_pages},
        max_total_charge_usd=Decimal("0.50"),  # $0.005 a page audited: at most 100 pages
    )
    rows, counts = [], {"high": 0, "medium": 0, "low": 0, "info": 0}
    for page in client.dataset(run.default_dataset_id).iterate_items():  # in the order the pages were reached
        print(f"{page['score']:>3}  {page['url']}")
        for issue in page["issues"]:
            what = words(issue, page)
            counts[issue["severity"]] += 1
            print(f"     {issue['severity'].upper():<7} {what}")
            rows.append({"page": page["url"], "score": page["score"], "severity": issue["severity"],
                         "problem": issue["code"], "what is wrong": what})
    summary = client.key_value_store(run.default_key_value_store_id).get_record("SUMMARY")["value"]
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:  # the BOM tells Excel the file is UTF-8
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")  # the same file on every system
        writer.writeheader()
        writer.writerows({k: as_text(v) for k, v in row.items()} for row in rows)
    average = summary["averageScore"]
    print(f"{plural(summary['pagesAudited'], 'page', 'pages')}, average score "
          + (f"{average:.1f}" if average is not None else "none") + f": {counts['high']} high, {counts['medium']} "
          f"medium, {counts['low']} low" + (f", {counts['info']} info" if counts["info"] else "")
          + f"; {plural(len(rows), 'problem', 'problems')} in {sheet}")
    if summary["urlsBlockedByRobotsTxt"]:
        print(f"{summary['urlsBlockedByRobotsTxt']} linked pages were not audited, because your robots.txt blocks them")
    if summary["stoppedReason"]:  # max pages, the charge cap or the time limit; pages after it were not audited
        print(f"the run stopped early ({summary['stoppedReason']})")
    return 1 if counts["high"] else 0


def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("start")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--csv", type=Path, default=Path("seo-report.csv"))
    opts = parser.parse_args(args)
    return audit(opts.start, opts.max_pages, opts.csv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
