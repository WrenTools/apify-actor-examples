"""Merge CSV, JSON, JSON Lines or Excel files into one list without duplicates, with one Apify Actor run.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python dedup.py https://example.com/crm-export.csv https://example.com/signups.jsonl

Rows are duplicates when their email matches (ignoring case and surrounding spaces); of each group, the row with the
most non-empty fields is kept. Writes merged.csv in the current folder and prints the run's per-source counts.
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

ACTOR = "wrentools/dataset-merge-dedup"


def main(urls: list[str]) -> int:
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR).call(
        run_input={
            "fileUrls": urls,              # or "datasetIds": [...] to merge your own Apify datasets
            "dedupFields": ["email"],      # several fields together, dotted paths, or ["*"] for whole rows
            "keep": "mostComplete",        # or "first", "last"
            "addSourceField": "_source",   # which file each row came from
        },
        max_total_charge_usd=Decimal("1.00"),  # the run stops before spending more than this
    )
    if run is None or run.status != "SUCCEEDED":
        print(f"run did not succeed: {run.status if run else 'no run'}", file=sys.stderr)
        return 1

    csv = client.dataset(run.default_dataset_id).get_items_as_bytes(item_format="csv")
    (Path.cwd() / "merged.csv").write_bytes(csv)

    summary = client.key_value_store(run.default_key_value_store_id).get_record("SUMMARY")["value"]
    for source in summary["sources"]:
        print(f"{source['source']}: {source['status']}, read {source['rowsRead']}, "
              f"duplicates {source['duplicatesRemoved']}, written {source['rowsWritten']}")
    print(f"total: read {summary['rowsRead']}, removed {summary['duplicatesRemoved']} duplicates, "
          f"wrote {summary['rowsWritten']} rows to merged.csv")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
