"""Turn PDFs into Markdown and RAG-ready chunks with one Apify Actor run.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python extract.py https://example.com/report.pdf [more links...]

Writes <name>.md for each PDF and one chunks.jsonl (a chunk per line, with its source and page range) in the current
folder, and prints a one-line summary per PDF.
"""
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

ACTOR = "wrentools/pdf-text-markdown-extractor"


def main(urls: list[str]) -> int:
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR).call(
        run_input={
            "pdfUrls": urls,
            "outputFormat": "markdown",
            "chunkSize": 1500,      # characters per chunk, split at paragraph boundaries; 0 turns chunking off
            "chunkOverlap": 200,
        },
        max_total_charge_usd=Decimal("1.00"),  # the run stops before spending more than this
    )
    if run is None or run.status != "SUCCEEDED":
        print(f"run did not succeed: {run.status if run else 'no run'}", file=sys.stderr)
        return 1

    out = Path.cwd()
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as chunks:
        for item in client.dataset(run.default_dataset_id).iterate_items():
            if item["status"] != "ok":
                print(f"FAILED {item['source']}: {item['error']['code']}")
                continue
            (out / f"{Path(item['fileName']).stem}.md").write_text(item["markdown"], encoding="utf-8")
            for chunk in item.get("chunks", []):
                chunks.write(json.dumps({"source": item["source"], **chunk}, ensure_ascii=False) + "\n")
            scanned = f", no text on pages {item['pagesWithoutText']}" if item["pagesWithoutText"] else ""
            print(f"{item['fileName']}: {item['pagesExtracted']} pages, {item['wordCount']} words, "
                  f"{len(item.get('chunks', []))} chunks{scanned}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
