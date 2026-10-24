"""Pull the text out of a folder of screenshots or photos with Apify Actor runs (Tesseract OCR, inside the run).

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python ocr_folder.py <folder>                    reads every image in the folder into <folder>-text.csv
    python ocr_folder.py <folder> --find <words>     prints each screenshot whose text holds <words>, and the line

The files are on your computer, not online, so they are sent inline as base64, a few megabytes per run. --find reads
the CSV if it is already there, so searching again costs nothing; delete the CSV to read the folder again.
"""
import base64
import csv
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

ACTOR = "wrentools/scanned-pdf-image-ocr"
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
BATCH_BYTES = 4_000_000  # image bytes per run; base64 makes the input a third larger


def batches(files: list[Path]):
    batch, size = [], 0
    for path in files:
        if batch and size + path.stat().st_size > BATCH_BYTES:
            yield batch
            batch, size = [], 0
        batch.append(path)
        size += path.stat().st_size
    if batch:
        yield batch


def read_folder(folder: Path, out: Path) -> int:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGES)
    if not files:
        print(f"no images in {folder}", file=sys.stderr)
        return 1
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    rows = []
    for batch in batches(files):
        run = client.actor(ACTOR).call(
            run_input={
                "filesBase64": [{"name": p.name, "data": base64.b64encode(p.read_bytes()).decode()} for p in batch],
                "languages": ["eng"],   # up to 3, e.g. ["eng", "deu"]; each one added slows every page
            },
            max_total_charge_usd=Decimal("1.00"),  # the run stops before spending more than this
        )
        if run is None or run.status != "SUCCEEDED":
            print(f"run did not succeed: {run.status if run else 'no run'}", file=sys.stderr)
            return 1
        for item in client.dataset(run.default_dataset_id).iterate_items():
            if item["status"] != "ok":
                print(f"FAILED {item['fileName']}: {item['error']['code']}")
                continue
            rows.append({"file": item["fileName"], "confidence": item["meanConfidence"],
                         "words": item["wordCount"], "text": item["text"]})
    with out.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig, so Excel reads it as UTF-8
        writer = csv.DictWriter(f, fieldnames=["file", "confidence", "words", "text"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} of {len(files)} images read into {out}")
    return 0


def find(out: Path, words: str) -> int:
    with out.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    hits = 0
    for row in rows:
        lines = [line.strip() for line in row["text"].splitlines() if words.lower() in line.lower()]
        for line in lines:
            print(f"{row['file']}: {line}")
        hits += bool(lines)
    print(f"{hits} of {len(rows)} screenshots mention {words!r}")
    return 0


def main(args: list[str]) -> int:
    folder = Path(args[0])
    out = Path(f"{folder.resolve().name}-text.csv")
    words = args[2] if len(args) == 3 and args[1] == "--find" else None
    if len(args) not in (1, 3) or (len(args) == 3 and words is None):
        sys.exit(__doc__)
    if words is None or not out.exists():
        status = read_folder(folder, out)
        if status or words is None:
            return status
    return find(out, words)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
