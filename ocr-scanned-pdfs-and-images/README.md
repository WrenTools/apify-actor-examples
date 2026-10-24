# Read the text in scanned PDFs and images with OCR (Python and Node)

This example sends links to scanned PDFs or images to the
[Image & Scanned PDF OCR](https://apify.com/wrentools/scanned-pdf-image-ocr) Actor on Apify and saves the text of
each file as `.txt`. It prints one line per file with its confidence score, and names any page read with low
confidence so you know which pages to check by eye. It is about 45 lines in either language.

**Disclosure:** we built and sell that Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## What the Actor does

- Reads each page with [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and its tessdata_fast models inside
  the run. Your files are not sent to any AI model or third-party API, and the same file always gives the same result.
- Takes PDFs (every page drawn at `pdfDpi`) and PNG, JPEG, TIFF, GIF, BMP and WebP images, in 27 languages, up to 3
  per run.
- Returns the text line by line, a `meanConfidence` (0 to 100) for each file and page, and `lowConfidencePages`: the
  pages under 60.
- With `includeWords`, returns every word with its confidence and its box on the page, in pixels, for reading forms
  and invoices by position or highlighting a match.

It costs **$0.003 per page read**, with no start fee and nothing for files that fail. A 10-page scan costs $0.03. You
also need an [Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings > API &
Integrations).

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python ocr.py https://example.com/scan.pdf https://example.com/receipt.jpg
```

[`ocr.py`](ocr.py) starts the run with `ApifyClient.actor(...).call()`, waits for it, then reads the run's dataset:
one item per file, in the order you gave them.

```python
run = client.actor("wrentools/scanned-pdf-image-ocr").call(
    run_input={"fileUrls": urls, "languages": ["eng"], "pdfDpi": 300},
    max_total_charge_usd=Decimal("1.00"),
)
for item in client.dataset(run.default_dataset_id).iterate_items():
    print(item["fileName"], item["meanConfidence"], item["lowConfidencePages"])
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node ocr.mjs https://example.com/scan.pdf
```

[`ocr.mjs`](ocr.mjs) uses Apify's `run-sync-get-dataset-items` endpoint, which starts the run, waits for it and
returns the results in one HTTP call. That endpoint answers HTTP 408 if the run takes more than 300 seconds. For long
scans, start the run with `POST /v2/acts/wrentools~scanned-pdf-image-ocr/runs` and poll it, or use the Python client,
which waits for you.

## Output

For a 2-page scan of a sample report (a 300 dpi picture of each page, with no text layer), the example prints
`scanned-report.pdf: 2 pages, 80 words, confidence 96.3` and writes `scanned-report.txt`:

```text
Quarterly Field Report

1. Summary
The survey covered twelve sites over six weeks. Most sites met the target, and two were
re-measured after the storm in week four.

2. Findings

2.1 Water quality
Turbidity fell at nine of twelve sites.

- Site A: within limits
- Site B: within limits
- Site C: above limits

2.2 Equipment
Two probes were replaced. The spare kit is now stored at the north depot so field crews

can reach it within an hour.
```

The blank line before the last line is Tesseract's: the page was scanned slightly tilted, and it read that line as a
block of its own.

A file that fails has `"status": "error"` and an `error.code` such as `fetch-failed`, `unsupported-file`,
`password-required` or `ocr-timeout`, and is not charged.

## Options worth knowing

| Input | What it does |
|---|---|
| `languages` | 1 to 3 codes, e.g. `["eng", "deu"]`. Use the fewest that cover the text. |
| `pageSegmentation` | `auto`, `singleColumn`, `singleBlock` (receipts, labels) or `sparse` (forms, photos). |
| `includePages` | Adds each page's text, confidence and pixel size. |
| `includeWords` | Adds every word with its confidence and box (`left`, `top`, `width`, `height` in pixels). |
| `pdfDpi` | 72 to 600 (300 by default); raise it for small print. |
| `filesBase64` | Send files inline instead of as links. |

`max_total_charge_usd` (Python) and `maxTotalChargeUsd` (Node) cap what one run can cost you: the Actor stops before
a page it cannot pay for.

## Limits

- OCR can misread a letter, and nothing in the text marks where. Pages under 60 confidence are listed in
  `lowConfidencePages`; check those by eye, and use `includeWords` to find the individual words it was unsure of.
- The text keeps the page's lines but not its layout: tables come out as lines of text, without their cell structure.
- If your PDFs already have a text layer (made by a word processor, not a scanner), the
  [PDF to Text & Markdown Extractor](https://apify.com/wrentools/pdf-text-markdown-extractor) reads them faster and for
  less, and its `pagesWithoutText` field tells you which pages need OCR.
- PDF permissions are honoured: a PDF that needs a password, or whose owner forbids text extraction, is refused.
  Process only documents you have the right to use.
