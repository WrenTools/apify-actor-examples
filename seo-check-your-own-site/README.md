# Run an SEO check on your own site (Python and Node)

You built your website yourself, and before you tell people about it you want to see it the way a search engine
reads it. This example sends your home page to one run of
[Own-Site SEO Audit](https://apify.com/wrentools/own-site-seo-audit) on Apify. The run follows the links on your site
(obeying your robots.txt) and checks every page it reaches: the title, the meta description, the headings, images
without alt text, structured data that does not parse, links to pages that are broken, and titles or descriptions
that two pages share. The script prints each page's score out of 100 with its problems underneath, and writes them to
`seo-report.csv`.

**Disclosure:** we built and sell the Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

Use it on sites you own or are authorized to audit.

## Try it on our test site

Kettle Hill Cycles is a bike workshop we made up for this example; every page says so. Its
[home page](https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/bikes.html) links to four more pages,
built by hand with four mistakes in them: the services page still links to a winter service page that was taken down,
the prices page was copied from the services page and kept its title, the gallery's photos have no alt text, and the
opening hours on the contact page, written as structured data, end with a stray comma.

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python seo_check.py https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/bikes.html
```

Our run (the site's address cut to `.../` here):

```
auditing .../bikes.html and the pages it links to on the same site, in one run...
100  .../bikes.html
 78  .../bikes-services.html
     HIGH    links to 1 broken page on your site: .../bikes-winter-service.html
     MEDIUM  the same title as .../bikes-prices.html
 93  .../bikes-prices.html
     MEDIUM  the same title as .../bikes-services.html
 93  .../bikes-gallery.html
     MEDIUM  3 images without alt text
 85  .../bikes-contact.html
     HIGH    1 structured data (JSON-LD) block does not parse
 85  .../bikes-winter-service.html
     HIGH    HTTP 404
6 pages, average score 89.0: 3 high, 3 medium, 0 low; 6 problems in seo-report.csv
```

The removed page is listed too: it is linked from your site, so the run requested it, and it answered 404.

On your own site, pass your home page (`https://www.your-site.com`). Only pages on that exact host are audited
(`www.your-site.com` and `your-site.com` are different hosts). `--max-pages <n>` audits at most n pages (50 by
default), and `--csv <file>` writes another file than `seo-report.csv`.

[`seo_check.py`](seo_check.py) makes one run and caps what it may spend:

```python
run = client.actor("wrentools/own-site-seo-audit").call(
    run_input={"startUrl": start, "maxPages": 50},
    max_total_charge_usd=Decimal("0.50"),
)
for page in client.dataset(run.default_dataset_id).iterate_items():
    # one item per page reached: its "url", "score" and "issues" (each with a "code", "severity" and "detail")
    ...
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node seo_check.mjs <your home page> [--max-pages 50] [--csv seo-report.csv]
```

[`seo_check.mjs`](seo_check.mjs) prints the same lines and writes the same file. In our test, both wrote a
byte-identical `seo-report.csv`.

## Output

`seo-report.csv`, one row per problem, in the order the pages were reached:

```
page,score,severity,problem,what is wrong
https://.../bikes-services.html,78,high,broken-internal-links,links to 1 broken page on your site: https://.../bikes-winter-service.html
https://.../bikes-services.html,78,medium,duplicate-title,the same title as https://.../bikes-prices.html
https://.../bikes-prices.html,93,medium,duplicate-title,the same title as https://.../bikes-services.html
https://.../bikes-gallery.html,93,medium,images-missing-alt,3 images without alt text
https://.../bikes-contact.html,85,high,invalid-json-ld,1 structured data (JSON-LD) block does not parse
https://.../bikes-winter-service.html,85,high,http-error,HTTP 404
```

- Each page starts at 100 and loses 15 for each high problem, 7 for each medium and 3 for each low one. The score is
  for tracking your own progress; it is not a search engine's ranking signal.
- `problem` is the Actor's own code for it, so you can filter the file. The Actor's
  [Store page](https://apify.com/wrentools/own-site-seo-audit) lists every check and its severity.
- **The exit code is 1 when any problem is rated high** (a broken link or page, a missing title, structured data that
  does not parse), and 0 otherwise, so a scheduled job (cron, a CI step) can tell you.
- The file is UTF-8 with a byte-order mark, which is how Excel recognises a UTF-8 CSV
  ([Microsoft](https://support.microsoft.com/en-us/excel/opening-csv-utf-8-files-correctly-in-excel)). A cell that
  would start with `=`, `+`, `-` or `@` gets a leading `'`, as [OWASP](https://owasp.org/www-community/attacks/CSV_Injection)
  advises, so a spreadsheet treats it as text and not as a formula.

## What it costs

- $0.005 per page audited, a page that answers with an error included. Our test site costs $0.03 a run (6 pages).
- `--max-pages` 50 costs at most $0.25. The $0.50 cap in the script covers 100 pages; raise it in the script, with
  `--max-pages`, for a larger site. A run that stops at either says so, and the pages after that point were not
  audited.

You also need an [Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings >
API & Integrations).

## Limits

- Plain HTTP, no browser: a page that builds its content with JavaScript is audited as the server sends it.
- Outbound links are not checked by this script (the Actor can, with `checkExternalLinks`).
- Robots.txt is obeyed, and requests are spaced 500 ms apart, so 100 pages take at least 50 seconds.
- Only public addresses are requested: a link or redirect into a private network is refused.
- It does not check your sitemap; our [sitemap example](../check-a-sitemap-for-broken-links) does.
