"""Read the text in every new scan in a folder, once each. Made to run on a schedule, every weekday morning.

    set APIFY_TOKEN=<your token>        (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python ocr_new_scans.py C:\\Scans

For each new scan it saves the text beside it (<name>.txt), adds any page read with low confidence to review.csv,
and only then records the scan's fingerprint in done.json. So a scan is read once, whatever it is called, and a scan
that failed is tried again the next morning.
"""
import base64
import csv
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ACTOR = "wrentools~scanned-pdf-image-ocr"
API = "https://api.apify.com/v2"


def send(method, path, body=None, **params):
    """One request to the Apify API. The token comes from the environment, never from this file."""
    request = urllib.request.Request(
        f"{API}{path}?{urllib.parse.urlencode(params)}", method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=330) as response:
        answer = json.load(response)
    return answer["data"] if isinstance(answer, dict) and "data" in answer else answer


def fingerprint(path):
    """The SHA-256 of the file's bytes: the same bytes always give the same fingerprint."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ocr(scans):
    """Start one run with every scan, wait until it ends, and return its results, one per scan."""
    files = [{"name": p.name, "data": base64.b64encode(p.read_bytes()).decode()} for p in scans]
    run = send("POST", f"/actors/{ACTOR}/runs", {"filesBase64": files, "includePages": True}, waitForFinish=300)
    while run["status"] in ("READY", "RUNNING"):
        run = send("GET", f"/actor-runs/{run['id']}", waitForFinish=60)
    if run["status"] != "SUCCEEDED":
        raise SystemExit(f"the run ended {run['status']}")
    return send("GET", f"/datasets/{run['defaultDatasetId']}/items", clean=1)


def save(path, data):
    """Write the whole file or nothing: a crash halfway leaves the old file as it was."""
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    temp.replace(path)


def main(folder):
    done_file = folder / "done.json"
    done = json.loads(done_file.read_text(encoding="utf-8")) if done_file.exists() else {}
    new = {}
    for scan in sorted(folder.glob("*.pdf")):
        mark = fingerprint(scan)
        if mark not in done and mark not in new.values():
            new[scan] = mark
    if not new:
        print("no new scans")
        return
    results = {r["source"]: r for r in ocr(list(new))}
    read = failed = to_check = 0
    review_file = folder / "review.csv"
    first = not review_file.exists()
    with open(review_file, "a", newline="", encoding="utf-8") as review:
        rows = csv.writer(review)
        if first:
            rows.writerow(["file", "page", "confidence"])
        for scan, mark in new.items():
            result = results[scan.name]
            if result["status"] != "ok":
                print(f"{scan.name}: failed ({result['error']['code']}), tried again next time")
                failed += 1
                continue
            scan.with_suffix(".txt").write_text(result["text"], encoding="utf-8")
            for page in result["pages"]:
                if page["page"] in result["lowConfidencePages"]:
                    rows.writerow([scan.name, page["page"], page["meanConfidence"]])
                    to_check += 1
            done[mark] = scan.name
            save(done_file, done)  # only after the text is saved
            read += 1
    print(f"{len(new)} new: {read} read, {failed} failed, {to_check} to check")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
