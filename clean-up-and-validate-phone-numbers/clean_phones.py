"""Clean up the phone numbers in a CSV file: each valid number in one standard form (E.164), the repeats marked, and
the numbers that can't be right listed with the reason.

    set APIFY_TOKEN=<your token>        (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python clean_phones.py signups.csv GB

The second argument is the default country, the two-letter code (GB, US, DE ...) used for a number written without a
plus. The script sends the file's Phone column to the Phone Number Validator on Apify in one run, then writes
<name>-clean.csv beside the file: every row as it was, with the result beside it.
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ACTOR = "wrentools~phone-number-validator-offline"
API = "https://api.apify.com/v2"
MAX_CHARGE_USD = "1.00"  # 2,500 numbers at $0.0004 each: the run stops before it spends more


def send(method, path, body=None, **params):
    """One request to the Apify API. The token comes from the environment, never from this file."""
    request = urllib.request.Request(
        f"{API}{path}?{urllib.parse.urlencode(params)}", method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=330) as response:
        answer = json.load(response)
    return answer["data"] if isinstance(answer, dict) and "data" in answer else answer


def validate(numbers, region):
    """Start one run with every number, wait until it ends, and return its results, one per number, in order."""
    run = send("POST", f"/actors/{ACTOR}/runs", {"phoneNumbers": numbers, "defaultRegion": region},
               waitForFinish=300, maxTotalChargeUsd=MAX_CHARGE_USD)
    while run["status"] in ("READY", "RUNNING"):
        run = send("GET", f"/actor-runs/{run['id']}", waitForFinish=60)
    if run["status"] != "SUCCEEDED":
        raise SystemExit(f"the run ended {run['status']}")
    return send("GET", f"/datasets/{run['defaultDatasetId']}/items", clean=1)


def main(sheet, region):
    with sheet.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    phone = next((c for c in (rows[0] if rows else {}) if c.strip().lower() == "phone"), None)
    if phone is None:
        raise SystemExit(f"{sheet.name} has no rows with a Phone column")

    results = validate([row[phone] for row in rows], region)
    # One result per row, in the sheet's order. If the run stopped early (its charge limit), write nothing.
    if [r["input"] for r in results] != [row[phone] for row in rows]:
        raise SystemExit(f"the run checked {len(results)} of {len(rows)} numbers; nothing was written")

    first_row = {}  # E.164 number -> the first row that has it
    problems = 0
    for n, (row, got) in enumerate(zip(rows, results), start=1):
        e164 = got["e164"]
        same = first_row.setdefault(e164, n) if e164 else n
        row.update(e164=e164 or "", country=got["regionCode"] or "", line_type=got["numberType"] or "",
                   problem=got["error"] or "", same_as_row=same if same != n else "")
        if not e164:
            problems += 1
            print(f"row {n}: {row[phone]!r} {got['error']}")
        elif same != n:
            print(f"row {n}: {row[phone]!r} is the same number as row {same}")

    out = sheet.with_name(f"{sheet.stem}-clean.csv")
    with out.open("w", newline="", encoding="utf-8-sig") as f:  # the byte order mark lets Excel read accents
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows: {len(rows) - problems} valid ({len(first_row)} different numbers), "
          f"{problems} to check. Wrote {out.name}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), sys.argv[2].upper())
