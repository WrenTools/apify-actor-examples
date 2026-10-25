# Check a sitemap for broken links (Python and Node)

Your sitemap is the list of pages you hand to search engines. After a redesign it can still list pages you took
down. This example sends your sitemap, or just your site's address, to one run of
[Sitemap Validator](https://apify.com/wrentools/sitemap-validator) on Apify. The run checks each sitemap file against
the [sitemaps.org](https://www.sitemaps.org/protocol.html) rules and requests every page it lists once. The script
prints what is broken or redirects, and which entries break a rule, and writes them to `sitemap-report.csv`.

**Disclosure:** we built and sell the Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## Try it on our test sitemap

Oakline Joinery is a woodworking shop we made up for this example; every page says so. Its
[sitemap](https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/shop-sitemap.xml) lists seven pages.
Five exist. The spring sale and gift card pages were taken down in the shop's redesign, and the sitemap still lists
them. The chairs page's date is written `03/10/2026`.

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python check_sitemap.py https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/shop-sitemap.xml
```

Our run (the store's address cut to `.../` here):

```
checking .../shop-sitemap.xml and every page it lists, in one run...
.../shop-sitemap.xml: 7 pages listed
RULE      .../shop-chairs.html  (lastmod "03/10/2026" is not a W3C date; write it YYYY-MM-DD)
BROKEN    .../shop-spring-sale.html  (HTTP 404)
BROKEN    .../shop-gift-cards.html  (HTTP 404)
7 pages: 5 work, 2 broken, 0 redirect; 1 breaks a sitemap rule; 3 problems in sitemap-report.csv
```

On your own site, pass the sitemap's address, a sitemap index (each sitemap it lists is checked too), or just
`https://www.your-site.com`: the Actor then reads the `Sitemap:` lines in your robots.txt, or tries `/sitemap.xml`.
`--csv <file>` writes another file than `sitemap-report.csv`.

[`check_sitemap.py`](check_sitemap.py) makes one run and caps what it may spend:

```python
run = client.actor("wrentools/sitemap-validator").call(
    run_input={"sitemapUrls": [sitemap], "checkUrlStatus": True, "maxUrls": 5000, "maxSitemapFiles": 50},
    max_total_charge_usd=Decimal("0.50"),
)
for item in client.dataset(run.default_dataset_id).iterate_items():
    # item["type"] is "sitemap-file" (one per sitemap) or "url-entry" (one per page, with its "issues")
    ...
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node check_sitemap.mjs <sitemap URL, or your site's address> [--csv sitemap-report.csv]
```

[`check_sitemap.mjs`](check_sitemap.mjs) prints the same lines and writes the same file. In our test, both wrote a
byte-identical `sitemap-report.csv`.

## Output

`sitemap-report.csv`, one row per problem, in the sitemap's order:

```
page,problem,what is wrong,HTTP status,redirects to,sitemap
https://.../shop-chairs.html,invalid-lastmod,"lastmod ""03/10/2026"" is not a W3C date; write it YYYY-MM-DD",200,,https://.../shop-sitemap.xml
https://.../shop-spring-sale.html,url-not-ok,HTTP 404,404,,https://.../shop-sitemap.xml
https://.../shop-gift-cards.html,url-not-ok,HTTP 404,404,,https://.../shop-sitemap.xml
```

- **BROKEN**: the page answered 4xx or 5xx, or did not answer. **REDIRECT**: it redirects, so the sitemap should list
  the address it ends at. **BLOCKED**: your robots.txt blocks it, so it was not requested. **RULE**: the entry breaks
  a sitemaps.org rule (a date not in the W3C format, a page listed twice, a page on another host, a `changefreq` or
  `priority` that is not allowed, and so on). **SITEMAP**: the sitemap file itself could not be read, or is not a
  valid sitemap.
- `problem` is the Actor's own code for it, so you can filter the file.
- **The exit code is 1 when there is any problem**, and 0 when there is none, so a scheduled job (cron, a CI step)
  can tell you when a page you list breaks.
- The file is UTF-8 with a byte-order mark, which is how Excel recognises a UTF-8 CSV
  ([Microsoft](https://support.microsoft.com/en-us/excel/opening-csv-utf-8-files-correctly-in-excel)). A cell that
  would start with `=`, `+`, `-` or `@` gets a leading `'`, as [OWASP](https://owasp.org/www-community/attacks/CSV_Injection)
  advises, so a spreadsheet treats it as text and not as a formula.

A sitemap that cannot be read is reported the same way:

```
SITEMAP   .../no-such-sitemap.xml  (fetch-failed: 404)
0 pages: 0 work, 0 broken, 0 redirect; 0 break a sitemap rule; 1 problem in sitemap-report.csv
```

## What it costs

- $0.002 per sitemap file, plus $0.0006 per page checked (the rule check and one request for its status). Our test
  sitemap costs $0.0062 a run (1 file, 7 pages).
- The $0.50 cap covers about 830 pages. A larger sitemap stops there; the script then says the run stopped early and
  that the pages after that point were not checked. Raise the cap in the script for a larger site.

You also need an [Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings >
API & Integrations).

## Limits

- Each page is requested once. A page that is down for a moment shows as broken; run it again before you remove it.
- Robots.txt is obeyed for every request, and requests are spaced 500 ms apart, so 1,000 pages take at least 8 minutes.
- Only public addresses are requested: a sitemap or redirect into a private network is refused.
- At most 5,000 pages and 50 sitemap files per run in this script (`maxUrls`, `maxSitemapFiles`).
- Image, video and news sitemap tags are read as ordinary entries; their extra tags are not checked.
