# Merge lead lists from CSV, JSON and Excel files and remove duplicates (Python and Node)

This example sends links to two or more files (CSV, TSV, JSON, JSON Lines or Excel) to the
[Merge & Dedup Datasets](https://apify.com/canopy_ne3/dataset-merge-dedup) Actor on Apify, which merges them, removes
the rows whose email is already in the list, and keeps the most complete copy of each. The example saves the result
as `merged.csv`. It is about 50 lines in either language.

**Disclosure:** we built and sell that Actor (Apify account `canopy_ne3`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## What the Actor does

- Merges any mix of up to 100 Apify datasets, up to 100 file URLs and rows pasted as JSON, and finds duplicates
  across all of them.
- Deduplicates on one or more fields (dotted paths such as `address.city` work) or whole rows. By default it ignores
  surrounding spaces and upper/lower case; it can also treat URL variants (`http`/`https`, `www.`, trailing slash,
  `utm_*` and other tracking parameters) as the same.
- Keeps the first, the last, or the most complete duplicate.
- Filters rows (16 operators), picks, drops and renames fields, and records which source each row came from.
- Writes a `SUMMARY` with, per source, the rows read, removed as duplicates and written.

It costs **$0.0002 per row written**, with no start fee. Duplicates and filtered rows are not charged as written.
Rows read from your own Apify datasets add $0.001 per started 1,000; rows from file URLs add nothing. Merging 50,000
rows from files into 35,000 unique ones costs $7.00. You also need an
[Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings > API & Integrations).

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python dedup.py https://example.com/crm-export.csv https://example.com/signups.jsonl
```

[`dedup.py`](dedup.py) starts the run, downloads the run's dataset as CSV, and prints the counts from the run's
`SUMMARY` record:

```python
run = client.actor("canopy_ne3/dataset-merge-dedup").call(
    run_input={"fileUrls": urls, "dedupFields": ["email"], "keep": "mostComplete", "addSourceField": "_source"},
    max_total_charge_usd=Decimal("1.00"),
)
csv = client.dataset(run.default_dataset_id).get_items_as_bytes(item_format="csv")
summary = client.key_value_store(run.default_key_value_store_id).get_record("SUMMARY")["value"]
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node dedup.mjs https://example.com/crm-export.csv https://example.com/signups.jsonl
```

[`dedup.mjs`](dedup.mjs) uses Apify's `run-sync-get-dataset-items` endpoint with `format=csv`, which starts the run,
waits for it and returns the merged rows as CSV in one HTTP call. That endpoint answers HTTP 408 if the run takes more
than 300 seconds; for very large merges, start the run with `POST /v2/acts/canopy_ne3~dataset-merge-dedup/runs` and
poll it, or use the Python client, which waits for you.

## Output

For a 5-row CRM export (CSV) and 4 newsletter sign-ups (JSON Lines), in which 3 rows repeat an email already seen, written in
different case and with stray spaces, the Python example prints:

```
.../leads-crm.csv: ok, read 5, duplicates 1, written 4
.../leads-signups.jsonl: ok, read 4, duplicates 2, written 2
total: read 9, removed 3 duplicates, wrote 6 rows to merged.csv
```

and `merged.csv` starts:

```csv
"_source","company","country","email","name","website"
".../leads-crm.csv","Harbor Supply","US","ann.lee@example.com","Ann Lee","https://www.harbor-supply.example/"
".../leads-crm.csv","Alder Works","CA","BO.CHEN@example.com ","Bo Chen","http://alder-works.example"
```

Rows are written exactly as read: matching ignores case and spaces, but the kept row keeps its own spelling.

## Options worth knowing

| Input | What it does |
|---|---|
| `datasetIds` | Merge your own Apify datasets (for example several scraper runs) instead of, or as well as, files. |
| `dedupFields` | Fields that together identify a duplicate; `["*"]` compares whole rows; empty merges only. |
| `keep` | `first`, `last` or `mostComplete` (the most non-empty fields). |
| `normalizeUrls` | Treat URL variants as the same value (useful for deduplicating by website). |
| `filters` / `filterMode` | For example `[{"field": "country", "op": "in", "value": ["US", "CA"]}]`, combined with AND or OR. |
| `fields` / `omitFields` / `renameFields` | Shape the output columns. |

`max_total_charge_usd` (Python) and `maxTotalChargeUsd` (Node) cap what one run can cost you: the Actor reads and
writes only what the cap covers, then stops, and the `SUMMARY` says it was truncated.

## Limits

- Excel files: the first sheet only, with the first row as the header. CSV values stay text.
- The Actor reads only the datasets you pick (it runs with Apify's limited permissions) and only the file links you
  give it, and it obeys each site's robots.txt. Use files and data you have the right to process.
