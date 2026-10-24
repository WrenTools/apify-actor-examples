# Turn RSS feeds into a spreadsheet (Python and Node)

You follow a few blogs, newsletters or release notes. Each has a feed, but you would rather read every new post as
a row in one spreadsheet, newest first. This example sends your list of feeds to one run of
[RSS, Atom & JSON Feed Reader](https://apify.com/wrentools/rss-feed-reader) on Apify and writes `posts.csv`: one row
per post, the same columns whatever format each feed uses. Run it again and only posts that are not in the file yet
are added.

**Disclosure:** we built and sell the Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

## Try it on our test feeds

[`feeds.txt`](feeds.txt) lists three blogs about woodworking that we made up and host for this example. One publishes
RSS 2.0, one Atom and one a JSON Feed, and the second is listed by its home page rather than its feed: the Actor finds
the feed the page advertises. Every page says it was made up.

## Python

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python feeds_to_csv.py feeds.txt
```

Our first run:

```
3 feeds; posts.csv has 0 posts
reading 3 feeds in one run...
Shavings & Sawdust (RSS 2.0): 4 posts, 4 new
The Bench Log (Atom, found on the page you listed): 4 posts, 4 new
Grain Direction (JSON Feed): 4 posts, 4 new
12 new; posts.csv has 12 posts, newest first
```

Then The Bench Log published a new post, and the same command added just that one, at the top:

```
3 feeds; posts.csv has 12 posts
reading 3 feeds in one run...
Shavings & Sawdust (RSS 2.0): 4 posts, 0 new
The Bench Log (Atom, found on the page you listed): 5 posts, 1 new
Grain Direction (JSON Feed): 4 posts, 0 new
1 new; posts.csv has 13 posts, newest first
```

Options: `--csv <file>` writes another file than `posts.csv`; `--since <when>` reads only posts published after a date
or a period back from now (`2026-10-01`, `7 days`, `24 hours`).

[`feeds_to_csv.py`](feeds_to_csv.py) makes one run for the whole list and caps what it may spend:

```python
run = client.actor("wrentools/rss-feed-reader").call(
    run_input={"feedUrls": feeds, "maxItemsPerFeed": 100},
    max_total_charge_usd=Decimal("0.50"),
)
for item in client.dataset(run.default_dataset_id).iterate_items():
    # item["type"] is "item" (a post) or "error" (a URL that failed, with the reason)
    ...
```

## Node (18 or later, no packages)

```bash
APIFY_TOKEN=<your token> node feeds_to_csv.mjs feeds.txt [--csv posts.csv] [--since "7 days"]
```

[`feeds_to_csv.mjs`](feeds_to_csv.mjs) prints the same lines and writes the same file, so either version can carry on
a file the other started. In our test, Node starting from Python's 12-post file, and Node starting from nothing, both
wrote a file byte-identical to Python's.

## Output

`posts.csv`, newest first:

```
published (UTC),blog,title,link,author,summary,id
2026-10-24 22:00,The Bench Log,A bench hook from one board,https://api.apify.com/v2/key-value-stores/uM2zEXblvgf0s1cES/records/blog-benchlog.html#bench-hook,Tobias Fenn,"One board, two cleats and four screws. It holds small work steady for the saw, and it took an evening.",urn:wrentools-video:benchlog:bench-hook
...
```

- `published (UTC)` is the post's date as `YYYY-MM-DD HH:MM` in UTC, which sorts in date order even as text. A
  post with no date goes to the bottom.
- `id` is the feed's own id for the post (RSS `guid`, Atom `id`, JSON Feed `id`), or its link when it has none. It is
  how the script knows a post is already in the file, so keep that column.
- The file is UTF-8 with a byte-order mark, which is how Excel recognises a UTF-8 CSV
  ([Microsoft](https://support.microsoft.com/en-us/excel/opening-csv-utf-8-files-correctly-in-excel)),
  so accented names come through.
- Feeds are other people's text. A text cell that would start with `=`, `+`, `-` or `@` gets a leading `'`, as
  [OWASP](https://owasp.org/www-community/attacks/CSV_Injection) advises, so a spreadsheet treats it as text and not
  as a formula. Whitespace inside a cell is folded to single spaces.

A URL that fails is printed and not charged:

```
FAILED https://.../old-pricing.html: fetch-failed (HTTP 404), not charged
FAILED https://.../about.html: no-feed-found (the page is HTML and advertises no RSS, Atom or JSON feed), not charged
```

## What it costs

- $0.001 per feed read, plus $0.0003 per post returned. Our three test feeds cost $0.0066 a run (3 feeds, 12 posts).
- **Every run is charged for every post it reads, not only the new ones**: the feed is read whole each time, and the
  script then keeps what is new. For a large feed run on a schedule, pass `--since` (for a daily run, `--since
  "2 days"`), so a run reads only recent posts.
- Nothing for a URL that fails.
- The $0.50 cap covers about 1,600 posts. If a run reaches it, the script says so and names the feeds it returned
  no posts for. Running again would stop at the same place, so raise the cap in the script or use `--since`.

You also need an [Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings >
API & Integrations).

## Limits

- Only the URLs you list are read, plus the feeds a listed page advertises (up to 5). Nothing is crawled.
- Each site's robots.txt is read first and obeyed, and requests to one site are spaced 500 ms apart.
- Only public feeds: there is no field for a login or cookie.
- At most 100 posts per feed in this script (`maxItemsPerFeed`; the Actor allows up to 1,000). A feed holds only the
  posts its publisher keeps in it, often just the latest, so run it often enough not to miss any.
- The summary is plain text, at most 2,000 characters. The full post is at its link.
- Read only feeds you are allowed to use, and respect each publisher's terms for what you do with the content.
