# Transcribe audio and video files to text and subtitles (Python and Node)

This example sends links to audio or video files to the
[Audio & Video Transcription](https://apify.com/canopy_ne3/audio-video-transcription) Actor on Apify and saves, for
each file, the transcript as `.txt` and subtitles as `.srt`. It is about 50 lines in either language.

**Disclosure:** we built and sell that Actor (Apify account `canopy_ne3`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## What the Actor does

- Runs OpenAI's Whisper speech model (`base`, through faster-whisper) inside the run, so your files are not sent to a
  third-party speech API.
- Accepts most audio and video formats (MP3, M4A, WAV, FLAC, OGG, Opus, MP4, MOV, WebM, MKV and more); only the
  first audio track is used.
- Detects the language (100 languages), or translates speech to English text with `"task": "translate"`.
- Returns the text, timed segments, optional word timestamps, and `.srt`/`.vtt` subtitle files.
- Skips silence and music before transcribing, which reduces made-up text in long pauses.

It costs **$0.01 per started minute of audio**, at least one minute per file, with no start fee and nothing for files
that fail. A 30-second voice note costs $0.01 and a one-hour meeting $0.60. You also need an
[Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings > API & Integrations).

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python transcribe.py https://example.com/interview.mp3 https://example.com/lecture.mp4
```

[`transcribe.py`](transcribe.py) starts the run with `ApifyClient.actor(...).call()`, waits for it, then reads the
run's dataset: one item per file, in the order you gave them.

```python
run = client.actor("canopy_ne3/audio-video-transcription").call(
    run_input={"fileUrls": urls, "language": "auto", "subtitleFormats": ["srt"]},
    max_total_charge_usd=Decimal("1.00"),
)
for item in client.dataset(run.default_dataset_id).iterate_items():
    print(item["fileName"], item["language"], item["text"][:80])
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node transcribe.mjs https://example.com/interview.mp3
```

[`transcribe.mjs`](transcribe.mjs) uses Apify's `run-sync-get-dataset-items` endpoint, which starts the run, waits
for it and returns the results in one HTTP call. That endpoint answers HTTP 408 if the run takes more than 300 seconds, so keep it
to files up to about 8 minutes in total (the Actor transcribes about 2 minutes of audio per minute of run time). For longer files, start the run with `POST /v2/acts/canopy_ne3~audio-video-transcription/runs`
and poll it, or use the Python client, which waits for you.

## Output

Each file gives one item like this (shortened; the sample is a 24-second recording):

```json
{
  "fileName": "speech-sample.mp3",
  "status": "ok",
  "language": "en",
  "durationSeconds": 24.005,
  "billedMinutes": 1,
  "wordCount": 59,
  "text": "This is a short sample recording for the transcription actor. The Riverside Community Garden will hold ...",
  "segments": [
    {"id": 0, "start": 0, "end": 4, "text": "This is a short sample recording for the transcription actor."}
  ],
  "subtitles": {"srt": "https://api.apify.com/v2/key-value-stores/<store>/records/file-1.srt?signature=..."}
}
```

The `.srt` written by the example starts:

```
1
00:00:00,000 --> 00:00:04,000
This is a short sample recording for the transcription actor.
```

A file that fails has `"status": "error"` and an `error.code` such as `fetch-failed`, `no-audio-track` or
`unsupported-codec`, and is not charged.

## Options worth knowing

| Input | What it does |
|---|---|
| `language` | `auto`, or a code such as `en`, `de`, `es`, `ja`. Setting it skips detection. |
| `task` | `translate` writes English text from speech in any language (rougher than transcription). |
| `wordTimestamps` | Each word's start, end and probability, for karaoke-style captions or search. |
| `subtitleFormats` | `["srt", "vtt"]` by default; `[]` for none. |
| `filesBase64` | Send small files inline instead of as links (Apify limits the whole input to a few MB). |
| `maxMinutesPerFile` | Stops long files early (they are marked `truncated`). |

`max_total_charge_usd` (Python) and `maxTotalChargeUsd` (Node) cap what one run can cost you: the Actor stops before
a file it cannot pay for and transcribes only the minutes the remainder covers.

## Limits

- Links must point to the media file itself. Pages on video platforms (YouTube, TikTok, Instagram) are not files,
  and the Actor does not extract media from them.
- No speaker labels: the text does not say who spoke.
- `base` is a small, fast model. It does well on clear speech in widely spoken languages; names, rare words and noisy
  audio are weaker. Check transcripts that matter against the audio.
- Transcribe only recordings you have the right to process, and do not use the output alone for decisions about
  people. Both cautions come from the [Whisper model card](https://github.com/openai/whisper/blob/main/model-card.md).
