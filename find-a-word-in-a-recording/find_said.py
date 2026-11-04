"""Find each moment a word or phrase is said in a recording, with a link that plays from just before it.

    set APIFY_TOKEN=<your token>        (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python find_said.py bread-class.webm salt "ten minutes" Caitlin

The first search sends the recording to the transcription tool once, asking for a time for every word, and saves the
words beside it (bread-class.words.json). Every search after that reads that file, so nothing is sent again.
"""
import base64
import difflib
import json
import os
import string
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ACTOR = "wrentools~audio-video-transcription"
API = "https://api.apify.com/v2"
NUMBERS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
           "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "twenty": "20", "thirty": "30", "forty": "40",
           "fifty": "50", "sixty": "60"}
CLOSE = 0.8  # two spellings at least this alike (0 to 1) count as one word
LONG = 5  # but only for words this long or longer: short words are too alike ("the" and "they")
UNSURE = 0.7  # words the model was less sure of than this are listed, to listen to
LEAD = 1.0  # a link starts this many seconds before its word


def send(method, path, body=None, **params):
    """One request to the Apify API. The token comes from the environment, never from this file."""
    request = urllib.request.Request(
        f"{API}{path}?{urllib.parse.urlencode(params)}", method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=330) as response:
        answer = json.load(response)
    return answer["data"] if isinstance(answer, dict) and "data" in answer else answer


def transcribe(recording):
    """One run of the tool on the recording, asking for a time for every word; returns the words, in order."""
    file = {"name": recording.name, "data": base64.b64encode(recording.read_bytes()).decode()}
    run = send("POST", f"/actors/{ACTOR}/runs", {"filesBase64": [file], "wordTimestamps": True,
                                                 "subtitleFormats": []}, waitForFinish=300)
    while run["status"] in ("READY", "RUNNING"):
        run = send("GET", f"/actor-runs/{run['id']}", waitForFinish=60)
    if run["status"] != "SUCCEEDED":
        raise SystemExit(f"the run ended {run['status']}")
    item, = send("GET", f"/datasets/{run['defaultDatasetId']}/items", clean=1)
    if item["status"] != "ok":
        raise SystemExit(f"{recording.name}: {item['error']['code']}")
    return [word for segment in item["segments"] for word in segment["words"]]


def words_of(recording):
    """The recording's words with their times: transcribed the first time, then read from the saved file."""
    saved = recording.with_suffix(".words.json")
    if not saved.exists():
        saved.write_text(json.dumps(transcribe(recording), indent=1), encoding="utf-8")
    return json.loads(saved.read_text(encoding="utf-8"))


def plain(word):
    """A word as a search compares it: lower case, no punctuation round it, a number word as its digits."""
    word = word.lower().strip(string.punctuation)
    return NUMBERS.get(word, word)


def alike(heard, wanted):
    if heard == wanted:
        return True
    return len(wanted) >= LONG and difflib.SequenceMatcher(None, heard, wanted).ratio() >= CLOSE


def find(words, query):
    """Every place the query's words are said one after another; each hit is the first word, with its time."""
    wanted = [plain(w) for w in query.split()]
    heard = [plain(w["word"]) for w in words]
    return [words[i] for i in range(len(words) - len(wanted) + 1)
            if all(alike(heard[i + k], wanted[k]) for k in range(len(wanted)))]


def clock(seconds):
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def link(recording, word):
    """The recording at a time: a player that is given this address starts there."""
    return f"{recording.name}#t={max(0.0, word['start'] - LEAD):.1f}"


def main(recording, queries):
    words = words_of(recording)
    for query in queries:
        hits = find(words, query)
        print(f'"{query}": {len(hits)} found')
        for word in hits:
            print(f"  {clock(word['start'])}  {word['word']}  {link(recording, word)}")
    unsure = [w for w in words if w["probability"] < UNSURE]
    print(f"{len(unsure)} of {len(words)} words to listen to:")
    for word in unsure:
        print(f"  {clock(word['start'])}  {word['word']} ({word['probability']})  {link(recording, word)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), sys.argv[2:])
