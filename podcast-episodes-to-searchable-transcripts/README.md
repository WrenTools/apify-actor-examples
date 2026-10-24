# Turn podcast episodes into searchable transcripts (Python and Node)

You remember a podcast saying something useful, but not which episode, or where in it. This example reads a
podcast's RSS feed, transcribes its newest episodes into one timestamped Markdown file each, and then searches them:
`--find salt` prints every episode and minute where "salt" was said.

It uses two Actors on Apify, both built by us:
[RSS Feed Reader](https://apify.com/wrentools/rss-feed-reader) reads the feed and returns each episode's audio link,
and [Audio & Video Transcription](https://apify.com/wrentools/audio-video-transcription) turns the audio into text
with times.

**Disclosure:** we built and sell both Actors (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actors before publishing.

## Try it on our test feed

`https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/podcast.xml` is "The Small Workshop", a podcast
we made up for this example: three short episodes, voiced by synthetic voices (Kokoro-82M). One tip, a few grains of
salt to stop glued boards sliding, is said in the middle of episode 2, and no title or summary mentions it.

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python podcast_transcripts.py https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/podcast.xml
python podcast_transcripts.py --find salt
```

```
3 episodes in the feed's newest 3; 0 already transcribed
Oil or varnish?: 00:33, 97 words, billed 1 min
Sharp chisels in ten minutes: 00:50, 142 words, billed 1 min
Your first hand saw: 00:43, 124 words, billed 1 min

Sharp chisels in ten minutes, 00:30: Sprinkle a few grains of salt on the glue before you put the boards together.
Oil or varnish?, 00:05: A lot of you tried last week's salt trick on a glue up, and it worked.
2 of 3 episodes mention 'salt'
```

In the audio, the salt line starts at 30.4 seconds into episode 2; the transcript gives the start of the phrase it is
in, rounded down to the second. `--latest 10` takes the newest 10 episodes instead of 3.

[`podcast_transcripts.py`](podcast_transcripts.py) makes two runs, and caps what each may spend:

```python
run = client.actor("wrentools/rss-feed-reader").call(
    run_input={"feedUrls": [feed_url], "maxItemsPerFeed": latest},
    max_total_charge_usd=Decimal("0.10"),
)
# ... each item's enclosures hold the episode's audio link
run = client.actor("wrentools/audio-video-transcription").call(
    run_input={"fileUrls": [e["audio"] for e in new], "language": "auto", "includeSegments": True,
               "subtitleFormats": []},
    max_total_charge_usd=Decimal("2.00"),
)
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node podcast_transcripts.mjs <feed url> [--latest N]
node podcast_transcripts.mjs --find salt
```

[`podcast_transcripts.mjs`](podcast_transcripts.mjs) starts each run and polls it until it finishes, because a long
episode takes longer than the 300 seconds a single synchronous call may wait. Both versions write the same files, so
either one can search or update what the other wrote.

## Output

One file per episode in `transcripts/`, named by its date and title, for example
`transcripts/2026-10-15-sharp-chisels-in-ten-minutes.md`:

```
# Sharp chisels in ten minutes

The Small Workshop, 2026-10-15
Audio: https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/workshop-ep2.mp3

[00:00] This is the small workshop. I'm Tom.
[00:03] I'm Anna. This week, chisels, and getting them sharp quickly.
...
[00:30] Sprinkle a few grains of salt on the glue before you put the boards together.
```

The `Audio:` line is how the script knows an episode is done: run it again next week and it transcribes only the new
episodes. Searching never starts a run.

## What it costs

- RSS Feed Reader: $0.001 per feed read and $0.0003 per episode returned.
- Audio & Video Transcription: $0.01 per started minute of audio, at least one minute per episode, nothing for files
  that fail. A one-hour episode costs $0.60, so the $2.00 cap covers about three. The Actor stops before a file it
  cannot pay for and transcribes only the minutes the rest of the cap covers; such an episode is marked `truncated`.

You also need an [Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings >
API & Integrations).

## Limits

- The transcript is Whisper's `base` model, so names and rare words come out wrong now and then. In our test it wrote
  the host Ana as "Anna" and "pare end grain" as "pair and grain". Search for a plain word you remember rather than a
  name.
- No speaker labels: the transcript does not say who spoke.
- The audio link must be a file, which is what podcast feeds carry. A video platform's page is not a file.
- A transcript time is where its phrase starts, not the exact word.
- Transcribe only episodes you have the right to process, and read a podcast's terms before you share a transcript
  of it.
