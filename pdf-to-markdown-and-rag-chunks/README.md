# Turn PDFs into Markdown and RAG-ready chunks (Python and Node)

This example sends links to PDF files to the
[PDF to Text & Markdown Extractor](https://apify.com/wrenkit/pdf-text-markdown-extractor) Actor on Apify and
saves, for each PDF, its Markdown as `.md`, plus one `chunks.jsonl` with a chunk per line that you can load into a
vector store. It is about 50 lines in either language.

**Disclosure:** we built and sell that Actor (Apify account `wrenkit`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## What the Actor does

- Extracts text with [pdfminer.six](https://github.com/pdfminer/pdfminer.six) inside the run. No AI model reads your
  files, and the same file always gives the same result.
- Builds Markdown from the layout: clearly larger short lines become `#`, `##` and `###` headings, bullet lines become
  list items, and words hyphenated across a line break are joined again.
- Splits the Markdown into chunks at paragraph boundaries (`chunkSize`, with `chunkOverlap`), each with `pageStart`
  and `pageEnd`, so an answer can cite its page.
- Returns the document's metadata (title, author, dates) and lists pages that have no text layer
  (`pagesWithoutText`), so you can tell when a scan needs OCR.

It costs **$0.002 per PDF plus $0.0001 per page**, with no start fee and nothing for files that fail. A 10-page PDF
costs $0.003 and a 100-page PDF $0.012. You also need an [Apify account](https://console.apify.com/sign-up) and its
API token (Console > Settings > API & Integrations).

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python extract.py https://example.com/report.pdf https://example.com/manual.pdf
```

[`extract.py`](extract.py) starts the run with `ApifyClient.actor(...).call()`, waits for it, then reads the run's
dataset: one item per PDF, in the order you gave them.

```python
run = client.actor("wrenkit/pdf-text-markdown-extractor").call(
    run_input={"pdfUrls": urls, "outputFormat": "markdown", "chunkSize": 1500, "chunkOverlap": 200},
    max_total_charge_usd=Decimal("1.00"),
)
for item in client.dataset(run.default_dataset_id).iterate_items():
    for chunk in item["chunks"]:
        print(item["fileName"], chunk["pageStart"], chunk["pageEnd"], chunk["text"][:60])
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node extract.mjs https://example.com/report.pdf
```

[`extract.mjs`](extract.mjs) uses Apify's `run-sync-get-dataset-items` endpoint, which starts the run, waits for it
and returns the results in one HTTP call. That endpoint answers HTTP 408 if the run takes more than 300 seconds. That
is plenty for a few dozen typical PDFs; for hundreds, start the run with
`POST /v2/acts/wrenkit~pdf-text-markdown-extractor/runs` and poll it, or use the Python client, which waits for
you.

## Output

For a 3-page sample report, the example prints
`field-report.pdf: 3 pages, 80 words, 1 chunks, no text on pages [3]` and writes `field-report.md`:

```markdown
# Quarterly Field Report

## 1. Summary

The survey covered twelve sites over six weeks. Most sites met the target, and two were re-measured after the storm
in week four.

## 2. Findings

### 2.1 Water quality

Turbidity fell at nine of twelve sites.

- Site A: within limits
- Site B: within limits
- Site C: above limits
```

Each line of `chunks.jsonl` is one chunk:

```json
{"source": "https://example.com/field-report.pdf", "index": 0, "text": "# Quarterly Field Report\n\n## 1. Summary ...", "pageStart": 1, "pageEnd": 2, "charCount": 459}
```

A PDF that fails has `"status": "error"` and an `error.code` such as `fetch-failed`, `not-a-pdf`, `password-required`
or `extraction-not-permitted`, and is not charged.

## Options worth knowing

| Input | What it does |
|---|---|
| `outputFormat` | `both` (the default), `markdown` or `text`. |
| `includePages` | Adds the text of each page, for citing page numbers without chunks. |
| `chunkSize` / `chunkOverlap` | Characters per chunk (0 is off, otherwise at least 200) and the overlap (at most half). |
| `pdfBase64` | Send small files inline instead of as links. |
| `maxPagesPerPdf` | Stops long PDFs early (they are marked `truncated`). |

`max_total_charge_usd` (Python) and `maxTotalChargeUsd` (Node) cap what one run can cost you: the Actor stops before
a file it cannot pay for and extracts only the pages the remainder covers.

## Limits

- No OCR: scanned pages come back empty and are listed in `pagesWithoutText`. For those, the same publisher's
  [Scanned PDF & Image OCR](https://apify.com/wrenkit/scanned-pdf-image-ocr) Actor reads the page images.
- Tables come out as lines of text; their cell structure is not rebuilt. Multi-column layouts follow pdfminer's
  reading order, which is usually but not always right.
- Headings are inferred from font size, so a document that sets its headings in body-size bold reads as plain text.
- PDF permissions are honoured: a PDF that needs a password, or whose owner forbids text extraction, is refused.
  Process only documents you have the right to use.
