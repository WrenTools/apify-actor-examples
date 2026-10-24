"""Turn a podcast's episodes into timestamped transcripts, then search them for the moment something was said.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python podcast_transcripts.py <feed url> [--latest N]    transcribes the newest N episodes (default 3) into
                                                              transcripts/, one Markdown file each
    python podcast_transcripts.py --find <words>              prints each episode and time where <words> were said

Two Actor runs: RSS Feed Reader reads the feed and returns each episode's audio link, and Audio & Video Transcription
transcribes the episodes that are not in transcripts/ yet. Episodes already there are skipped, so running it again
next week transcribes only the new ones, and --find reads the saved files, so searching costs nothing.
"""
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

FEED_READER = "wrentools/rss-feed-reader"
TRANSCRIBER = "wrentools/audio-video-transcription"
OUT = Path("transcripts")


def stamp(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}" if seconds >= 3600 \
        else f"{seconds // 60:02d}:{seconds % 60:02d}"


def file_name(episode: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (episode["title"] or "episode").lower()).strip("-")[:60]
    return f"{(episode['published'] or 'undated')[:10]}-{slug}.md"


def saved_audio() -> set[str]:
    """The audio links of the transcripts already in transcripts/."""
    links = set()
    for path in OUT.glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines()[:5]:
            if line.startswith("Audio: "):
                links.add(line[len("Audio: "):])
    return links


def transcribe(feed_url: str, latest: int) -> int:
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(FEED_READER).call(
        run_input={"feedUrls": [feed_url], "maxItemsPerFeed": latest},  # the feed's own order: newest first
        max_total_charge_usd=Decimal("0.10"),
    )
    episodes = []
    for item in client.dataset(run.default_dataset_id).iterate_items():
        if item["type"] == "error":
            print(f"feed failed: {item['error']['code']}: {item['error']['message']}", file=sys.stderr)
            return 1
        audio = next((e["url"] for e in item["enclosures"] if (e["type"] or "").startswith(("audio/", "video/"))),
                     None)
        if audio is None:
            print(f"no audio: {item['title']}")
            continue
        episodes.append({**item, "audio": audio})
    done = saved_audio()
    new = [e for e in episodes if e["audio"] not in done]
    print(f"{len(episodes)} episodes in the feed's newest {latest}; {len(episodes) - len(new)} already transcribed")
    if not new:
        return 0
    run = client.actor(TRANSCRIBER).call(
        run_input={"fileUrls": [e["audio"] for e in new], "language": "auto", "includeSegments": True,
                   "subtitleFormats": []},
        max_total_charge_usd=Decimal("2.00"),  # $0.01 per started minute: about three one-hour episodes
    )
    results = {item["url"]: item for item in client.dataset(run.default_dataset_id).iterate_items()}
    OUT.mkdir(exist_ok=True)
    for episode in new:
        item = results.get(episode["audio"])
        if item is None or item["status"] != "ok":
            print(f"FAILED {episode['title']}: {item['error']['code'] if item else 'not transcribed'}")
            continue
        lines = [f"# {episode['title']}", "", f"{episode['feedTitle']}, {(episode['published'] or '')[:10]}",
                 f"Audio: {episode['audio']}", ""]
        lines += [f"[{stamp(s['start'])}] {s['text'].strip()}" for s in item["segments"]]
        (OUT / file_name(episode)).write_text("\n".join(lines) + "\n", encoding="utf-8",
                                                    newline="\n")  # the same file on every system
        print(f"{episode['title']}: {stamp(item['durationSeconds'])}, {item['wordCount']} words, "
              f"billed {item['billedMinutes']} min{', truncated' if item.get('truncated') else ''}")
    return 0


def find(words: str) -> int:
    hits = 0
    for path in sorted(OUT.glob("*.md")):
        text = path.read_text(encoding="utf-8").splitlines()
        found = [line for line in text if line.startswith("[") and words.lower() in line.lower()]
        for line in found:
            time, said = line[1:].split("] ", 1)
            print(f"{text[0][2:]}, {time}: {said}")
        hits += bool(found)
    print(f"{hits} of {len(list(OUT.glob('*.md')))} episodes mention {words!r}")
    return 0


def main(args: list[str]) -> int:
    if len(args) == 2 and args[0] == "--find":
        return find(args[1])
    if len(args) == 1:
        return transcribe(args[0], 3)
    if len(args) == 3 and args[1] == "--latest" and args[2].isdigit():
        return transcribe(args[0], int(args[2]))
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
