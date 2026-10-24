# Download every file from a list of links (Python and Node)

You have a list of links to files: manuals, reports, invoices, images, datasets. You want them all in one folder,
you want to know that each one arrived whole, and you want to know which links didn't work. This example sends the
list to one run of [Bulk File Downloader](https://apify.com/wrentools/bulk-file-downloader) on Apify, saves each file
under its own name, checks its SHA-256 against the one the Actor measured, and keeps a `manifest.csv` of what is in
the folder. Run it again after fixing a link, or adding new ones, and it downloads only those.

**Disclosure:** we built and sell the Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## Try it on our test links

[`links.txt`](links.txt) lists six one-page manuals for made-up tools, which we wrote and host for this example. Each
page says it was made up.

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python download_files.py links.txt
```

Our first run had an old link for the bandsaw manual in it, one that no longer exists:

```
6 links; 0 already in files/
downloading 6 in one run...
ok  manual-block-plane.pdf          54.4 KB  SHA-256 matches
ok  manual-bench-chisels.pdf        54.9 KB  SHA-256 matches
ok  manual-coping-saw.pdf           53.8 KB  SHA-256 matches
ok  manual-marking-gauge.pdf        51.1 KB  SHA-256 matches
FAILED https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/manual-bandsaw-2025.pdf: fetch-failed (HTTP 404), not charged
ok  manual-hand-drill.pdf           52.7 KB  SHA-256 matches
5 downloaded, 1 failed; 5 files listed in files/manifest.csv
```

With the link fixed, the same command downloads only that file:

```
6 links; 5 already in files/
downloading 1 in one run...
ok  manual-bandsaw.pdf              55.2 KB  SHA-256 matches
1 downloaded, 0 failed; 6 files listed in files/manifest.csv
```

And once everything is there, it starts no run at all: `6 links; 6 already in files/`. `--folder <name>` saves into
another folder than `files/`.

[`download_files.py`](download_files.py) makes one run for all the new links and caps what it may spend:

```python
run = client.actor("wrentools/bulk-file-downloader").call(
    run_input={"fileUrls": new, "maxFileSizeMb": 50},
    max_total_charge_usd=Decimal("0.50"),
)
store = client.key_value_store(run.default_key_value_store_id)
for item in client.dataset(run.default_dataset_id).iterate_items():
    body = store.get_record_as_bytes(item["key"])["value"]   # each file is a record of the run's store
    # ... compared with item["sha256"], then saved as item["fileName"]
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node download_files.mjs links.txt [--folder files]
```

[`download_files.mjs`](download_files.mjs) prints the same lines and writes the same `manifest.csv`, so either version
can carry on in a folder the other started. In our test the two wrote byte-identical files.

## Output

The files, under their own names (from the server's `Content-Disposition`, or the link), and `manifest.csv`:

```
url,file,bytes,sha256
https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/manual-block-plane.pdf,manual-block-plane.pdf,55747,9013d9719b69604cd2cb2490603aab0ac8e0c27d4e6de730cf93415005bd587c
...
```

The manifest is how the script knows a link is done. A link that failed is not written to it, so it is tried again
next time. If two links give files of the same name, the second is saved as `name-2.pdf`; nothing is overwritten.

## What it costs

- $0.002 per file downloaded, plus $0.001 per started megabyte of it (at least one). A 300 KB file costs $0.003.
- Nothing for a link that fails: a 404, a file over `maxFileSizeMb`, or a file the site's robots.txt disallows.
- The $0.50 cap covers about 160 files under a megabyte. When the cap is reached, the Actor stops before the next file,
  and the script says how many links it did not reach; run the same command again to fetch them.

You also need an [Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings >
API & Integrations).

## Limits

- Direct links to files only. It does not crawl a page for its files or follow links, so a link to a web page saves
  the page's HTML, not the files on it.
- Only public files: there is no field for a login, cookie or password. A link that needs one fails with HTTP 401 or
  403 (a signed link that already grants access works).
- Each site's robots.txt is read first and obeyed, and downloads from one site are spaced 500 ms apart.
- 50 MB per file in this script (`maxFileSizeMb`; the Actor allows up to 200).
- The files stay in the run's storage for as long as your Apify plan keeps it (7 days on the free plan); the copies
  in your folder are yours.
- Download only files you have the right to download and keep.
