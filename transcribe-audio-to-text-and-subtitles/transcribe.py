"""Transcribe audio or video files to text and subtitles with one Apify Actor run.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python transcribe.py https://example.com/interview.mp3 [more links...]

Writes <name>.txt and <name>.srt in the current folder for each file, and prints a one-line summary per file.
"""
import os
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

ACTOR = "canopy_ne3/audio-video-transcription"


def main(urls: list[str]) -> int:
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR).call(
        run_input={
            "fileUrls": urls,
            "language": "auto",          # or "en", "de", "es", ...
            "subtitleFormats": ["srt"],
        },
        max_total_charge_usd=Decimal("1.00"),  # the run stops before spending more than this
    )
    if run is None or run.status != "SUCCEEDED":
        print(f"run did not succeed: {run.status if run else 'no run'}", file=sys.stderr)
        return 1

    out = Path.cwd()
    for item in client.dataset(run.default_dataset_id).iterate_items():
        if item["status"] != "ok":
            print(f"FAILED {item['source']}: {item['error']['code']}")
            continue
        stem = Path(item["fileName"]).stem
        (out / f"{stem}.txt").write_text(item["text"], encoding="utf-8")
        srt_url = (item.get("subtitles") or {}).get("srt")
        if srt_url:
            with urllib.request.urlopen(srt_url) as response:
                (out / f"{stem}.srt").write_bytes(response.read())
        print(f"{item['fileName']}: {item['language']}, {item['durationSeconds']:.0f} s, "
              f"{item['wordCount']} words, billed {item['billedMinutes']} min")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
