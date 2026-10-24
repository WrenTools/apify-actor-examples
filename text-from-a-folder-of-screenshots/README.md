# Pull the text out of a folder of screenshots (Python and Node)

Screenshots pile up: order confirmations, error messages, tickets, chat messages. Their names say only when each was
taken, and the words in them are pixels, so you cannot search them. This example sends every image in a folder to the
[Image & Scanned PDF OCR](https://apify.com/wrentools/scanned-pdf-image-ocr) Actor on Apify and writes one
spreadsheet: a row per screenshot with its file name, confidence score, word count and text. Then `--find` searches
it.

**Disclosure:** we built and sell that Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## What the Actor does

- Reads each image with [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and its tessdata_fast models inside
  the run. Your files are not sent to any AI model or third-party API, and the same file always gives the same result.
- Takes PNG, JPEG, TIFF, GIF, BMP and WebP images (and PDFs), as links or sent inline as base64, in 27 languages, up to
  3 per run.
- Returns the text line by line and a `meanConfidence` (0 to 100) for each file.

It costs **$0.003 per page read** (a screenshot is one page), with no start fee and nothing for files that fail. A
folder of 100 screenshots costs $0.30. You also need an [Apify account](https://console.apify.com/sign-up) and its API
token (Console > Settings > API & Integrations).

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python ocr_folder.py screenshots                 # writes screenshots-text.csv
python ocr_folder.py screenshots --find order    # searches it
```

The screenshots are on your computer, not online, so [`ocr_folder.py`](ocr_folder.py) sends them inline in the
Actor's `filesBase64` input, about 4 MB of images per run, and caps what each run may spend:

```python
run = client.actor("wrentools/scanned-pdf-image-ocr").call(
    run_input={"filesBase64": [{"name": p.name, "data": base64.b64encode(p.read_bytes()).decode()} for p in batch],
               "languages": ["eng"]},
    max_total_charge_usd=Decimal("1.00"),
)
```

`--find` reads the CSV if it is already there, so searching again costs nothing. Delete the CSV to read the folder
again.

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node ocr_folder.mjs screenshots --find order
```

[`ocr_folder.mjs`](ocr_folder.mjs) does the same with Apify's `run-sync-get-dataset-items` endpoint, which starts the
run, waits for it and returns the results in one HTTP call. That endpoint answers HTTP 408 if a run takes more than
300 seconds; if it does, lower `BATCH_BYTES` so each run reads fewer images.

## Output

For a folder of six sample screenshots (made up for this example), the first command prints
`6 of 6 images read into screenshots-text.csv`, and `--find order` prints:

```text
Screenshot 2026-10-03 091522.png: Thanks, your order is confirmed
Screenshot 2026-10-03 091522.png: Order WT-48213
Screenshot 2026-10-14 081937.png: Your parcel for order WT-48213 arrives today between 10:00 and 14:00.
2 of 6 screenshots mention 'order'
```

Each row of `screenshots-text.csv` holds one screenshot (confidence 93.1 to 96.6 for these six):

| file | confidence | words | text |
|---|---|---|---|
| Screenshot 2026-10-03 091522.png | 93.1 | 20 | Thanks, your order is confirmed / Order WT-48213 / Walnut desk lamp 1 $38.40 / ... |
| Screenshot 2026-10-11 175301.png | 96.1 | 13 | Train ticket / Platform 4, coach C, seat 42 / Departs 07:14, Sunday 18 October |

(In the file, the text keeps its line breaks; `/` marks them here.) The CSV opens in Excel or Google Sheets, so you can
also filter it there.

## Limits

- OCR can misread a letter, and nothing in the text marks where. A low `confidence` is the sign to check a screenshot
  by eye.
- Small text reads worse. We took the same six screenshots at 100% and at 150% display scaling: at 150% every one of
  the 96 words came back exactly; at 100%, 92 did (`$38.40` came back as `$3840`). If words are missed, zoom in before
  taking the screenshots.
- The text keeps each screenshot's lines but not its layout: tables come out as lines of text.
- To copy the text from your screen as you go, without uploading anything, our Chrome extension
  [Offline OCR: Copy Text from Screen](../offline-ocr/) reads it on your own computer.
