"""Read the text in scanned PDFs and images with one Apify Actor run (Tesseract OCR, inside the run).

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python ocr.py https://example.com/scan.pdf [more links...]

Writes <name>.txt for each file in the current folder and prints a one-line summary per file, naming any page read
with low confidence, so you know which pages to check by eye.
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

ACTOR = "wrentools/scanned-pdf-image-ocr"


def main(urls: list[str]) -> int:
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR).call(
        run_input={
            "fileUrls": urls,
            "languages": ["eng"],   # up to 3, e.g. ["eng", "deu"]; each one added slows every page
            "pdfDpi": 300,          # raise it for small print
        },
        max_total_charge_usd=Decimal("1.00"),  # the run stops before spending more than this
    )
    if run is None or run.status != "SUCCEEDED":
        print(f"run did not succeed: {run.status if run else 'no run'}", file=sys.stderr)
        return 1

    for item in client.dataset(run.default_dataset_id).iterate_items():
        if item["status"] != "ok":
            print(f"FAILED {item['source']}: {item['error']['code']}")
            continue
        Path(f"{Path(item['fileName']).stem}.txt").write_text(item["text"], encoding="utf-8")
        check = f", check pages {item['lowConfidencePages']}" if item["lowConfidencePages"] else ""
        print(f"{item['fileName']}: {item['pagesProcessed']} pages, {item['wordCount']} words, "
              f"confidence {item['meanConfidence']}{check}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
