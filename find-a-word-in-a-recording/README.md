# Find every moment a word is said in a recording (Python)

This example finds each place a word or phrase is said in an audio or video file, and prints its time with a link that
plays from just before it. It sends the recording to the
[Audio & Video Transcription](https://apify.com/wrentools/audio-video-transcription) Actor on Apify once, asking for a
time for every word, saves those words beside the recording, and searches the saved words from then on. It is about
110 lines of Python, with no packages to install.

**Disclosure:** we built and sell that Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

For a transcript and subtitle files rather than a search, the shorter
[transcription example](../transcribe-audio-to-text-and-subtitles/) is simpler.

## Run it

You need Python 3 (we ran it with Python 3.14 on Windows 11), an
[Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings > API & Integrations). The
token goes in an environment variable, `APIFY_TOKEN`, never in the script.

```bash
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python find_said.py bread-class.webm salt
```

`bread-class.webm` is in this folder: a made-up 77-second bread class, spoken by a synthetic voice, so you can try the
script before using your own recording. Give it any number of words or phrases after the file:

```bash
python find_said.py bread-class.webm rest "ten minutes" Caitlin knead Siobhan tin
```

## Saved words: transcribe once, search often

The first search sends the recording to the Actor in one run, with `wordTimestamps` on, and writes every word it gets
back, with its start, end and the model's confidence, to `bread-class.words.json` beside the recording:

```json
{"start": 0.3, "end": 0.9, "word": "Hello,", "probability": 0.578}
```

Every search after that reads that file and sends nothing, so it costs nothing and answers at once. On the bread
class the first search took about 14 seconds on our computer, 12.5 seconds of it the Actor's run. To transcribe a
recording again, delete its `.words.json`.

## What it printed

This is the second search above, on our run of the Actor (build 0.1.11):

```text
"rest": 3 found
  0:37.7  rest.  bread-class.webm#t=36.7
  0:38.6  Rest  bread-class.webm#t=37.6
  1:00.1  rest  bread-class.webm#t=59.1
"ten minutes": 2 found
  0:39.4  10  bread-class.webm#t=38.4
  0:44.4  10  bread-class.webm#t=43.4
"Caitlin": 1 found
  1:13.2  Caitlyn  bread-class.webm#t=72.2
"knead": 1 found
  0:42.9  Knead  bread-class.webm#t=41.9
"Siobhan": 0 found
"tin": 1 found
  0:59.0  tin,  bread-class.webm#t=58.0
9 of 233 words to listen to:
  0:00.3  Hello, (0.578)  bread-class.webm#t=0.0
  0:04.3  Chavorn, (0.345)  bread-class.webm#t=3.3
  0:09.4  Oldwick (0.635)  bread-class.webm#t=8.4
  0:15.4  grams (0.569)  bread-class.webm#t=14.4
  0:28.7  it (0.491)  bread-class.webm#t=27.7
  0:31.2  milliliters (0.666)  bread-class.webm#t=30.2
  0:41.6  need (0.645)  bread-class.webm#t=40.6
  0:42.9  Knead (0.653)  bread-class.webm#t=41.9
  1:13.2  Caitlyn (0.578)  bread-class.webm#t=72.2
```

Each hit is the time of its first word, the word as the model wrote it, and a link.

## How it matches

**Plain words.** The model writes words as they would be printed: with capitals, with the punctuation beside them, and
with numbers as digits. So before comparing, the script makes each side plain: lower case, punctuation stripped from
the ends, and a number word (`one` to `twelve`, and `twenty` to `sixty` in tens) turned into its digits. Compared as
typed, `rest` matches once in the bread class; made plain, it matches all three (`rest.`, `Rest`, `rest`), and
`ten minutes` finds the two places the model wrote `10 minutes`.

**Close spellings.** A name can come back spelled another way. Two words count as one when Python's `difflib` rates
them at least 0.8 alike (`CLOSE`): `caitlyn` and `caitlin` are 0.857 alike, so a search for `Caitlin` finds `Caitlyn`.
That rule applies only to words of five letters or more (`LONG`), because short words are too alike: without the
length rule, a search for `tin` also finds `in` (0.8 alike), eight times.

**A phrase** is found where its words are said one after another, each matched by the same two rules.

## Words to listen to

After the results, the script lists every word the model was less than 0.7 sure of (`UNSURE`), with its link. That is
where a mistake is most likely. A search can't find a word the model wrote as something else: in our run the teacher's
name, Siobhan, came back as `Chavorn,` (0 found), and one of the two times she says "knead" came back as `need`. Both
are on the list. Not every misheard word is: "the middle" came back as `middles.`, at 0.797, so it is not listed.

## The link, and its second of lead

`bread-class.webm#t=19.2` is the recording's address with a media fragment, `#t=` and a time in seconds
([W3C Media Fragments](https://www.w3.org/TR/media-frags/)). A browser's own player that is given that address starts
there: we checked it in Chromium, which started the bread class at 19.2 seconds. The link is relative, so use it beside
the recording (a page in the same folder) or add it to the address where the recording is published.

Each link starts one second (`LEAD`) before its word, and never before 0. Word times are a little off: on the bread
class, whose phrases' starts we know because we made it, each phrase's first word was timed between 0.31 seconds early
and 0.05 seconds late, most of them early (32 of 37; median 0.09 seconds early). A second's lead covers that, with
room to spare.

## What it costs

The Actor charges **$0.01 per started minute of audio**, at least one minute per file, with no start fee and nothing
for a file that fails. The bread class is 77 seconds, so it is billed 2 minutes: $0.02, once. Every search after the
first reads the saved words and costs nothing.

## Limits

- The recording goes inside the run's input, as base64 (about a third larger than the file). We ran it on the bread
  class, 0.5 MB. Apify limits the size of a run's whole input, so the Actor's own input notes say to send larger files
  as links: put a longer recording online and change `transcribe` to send `fileUrls` instead (the
  [transcription example](../transcribe-audio-to-text-and-subtitles/) does that).
- The run uses the Actor's default timeout, 300 seconds. If the run ends any way but `SUCCEEDED`, the script stops
  and prints the run's status.
- Matching is by spelling, not by sound. A word heard as a different word (`need` for "knead") is not found by
  searching for the word that was said; listen to the unsure list, or search for what the model wrote.
- Only the number words listed above become digits; `hundred`, `thousand` and compounds such as `twenty-five` do not.
- The Actor uses Whisper's `base` model. Our run misheard two made-up names (Siobhan, Aldwyck); real names you know are
  in a recording are worth searching for in more than one spelling.
- Process only recordings you have the right to use.
