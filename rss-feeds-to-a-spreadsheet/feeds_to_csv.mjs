// Turn the RSS, Atom and JSON feeds you follow into one spreadsheet of posts, newest first.
// Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node feeds_to_csv.mjs <feeds file> [--csv posts.csv] [--since "7 days"]
//
// The feeds file has one feed URL per line, or a blog's home page, whose feed is then found (blank lines and lines
// starting with # are skipped). One run of RSS, Atom & JSON Feed Reader reads them all. Posts not yet in the CSV are
// added to it, and the CSV is written newest first, so running the same command again adds only what is new. --since
// reads only posts published after a date or a period back from now ("2026-10-01", "7 days").
import { existsSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';

const READER = 'wrentools~rss-feed-reader';
const FIELDS = ['published (UTC)', 'blog', 'title', 'link', 'author', 'summary', 'id'];
const FORMATS = { rss20: 'RSS 2.0', rss10: 'RSS 1.0', atom10: 'Atom', jsonfeed: 'JSON Feed' };
// A cell starting with one of these could be run as a formula by a spreadsheet; a leading ' keeps it text (OWASP,
// "CSV Injection"). Feeds are other people's text, so the text columns are treated this way.
const FORMULA_START = ['=', '+', '-', '@', '\t', '\r', '\n', '＝', '＋', '－', '＠'];
const API = 'https://api.apify.com/v2';
const auth = { Authorization: `Bearer ${process.env.APIFY_TOKEN}` };

async function api(path, init = {}) {
    const response = await fetch(`${API}${path}`, { ...init, headers: { ...auth, ...init.headers } });
    if (!response.ok) {
        console.error(`HTTP ${response.status} ${await response.text()}`);
        process.exit(1);
    }
    return response;
}

// Start a run and wait for it however long it takes.
async function runActor(actor, input, maxUsd) {
    let { data: run } = await (await api(`/acts/${actor}/runs?maxTotalChargeUsd=${maxUsd}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) })).json();
    while (!['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'].includes(run.status)) {
        ({ data: run } = await (await api(`/actor-runs/${run.id}?waitForFinish=60`)).json());
    }
    if (run.status !== 'SUCCEEDED') {
        console.error(`${actor} run ${run.id}: ${run.status}`);
        process.exit(1);
    }
    return run;
}

const posts = (n) => (n === 1 ? `${n} post` : `${n} posts`);

async function readFeeds(path) {
    const feeds = [];
    for (const raw of (await readFile(path, 'utf8')).split(/\r?\n/)) {
        const line = raw.trim();
        if (line && !line.startsWith('#') && !feeds.includes(line)) feeds.push(line);
    }
    return feeds;
}

// The CSV, written and read the way Python's csv module does it, so either version can carry on the other's file.
const quote = (v) => (/[",\r\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));

function parseCsv(text) {
    const rows = [];
    let row = [];
    let field = '';
    let quoted = false;
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (quoted) {
            if (c === '"' && text[i + 1] === '"') { field += '"'; i++; } else if (c === '"') quoted = false;
            else field += c;
        } else if (c === '"') quoted = true;
        else if (c === ',') { row.push(field); field = ''; } else if (c === '\n' || c === '\r') {
            if (c === '\r' && text[i + 1] === '\n') i++;
            row.push(field); rows.push(row); row = []; field = '';
        } else field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    return rows;
}

async function readSheet(path) {
    if (!existsSync(path)) return [];
    const [header, ...rows] = parseCsv((await readFile(path, 'utf8')).replace(/^﻿/, ''));
    return rows.map((r) => Object.fromEntries(header.map((h, i) => [h, r[i] ?? ''])));
}

function asText(value) {
    const text = String(value ?? '').split(/\s+/).filter(Boolean).join(' ');
    return FORMULA_START.some((s) => text.startsWith(s)) ? `'${text}` : text;
}

function rowOf(item) {
    const published = item.published || item.updated || '';
    return { 'published (UTC)': published.replaceAll('T', ' ').slice(0, 16), blog: asText(item.feedTitle),
        title: asText(item.title), link: item.link || '', author: asText(item.author), summary: asText(item.summary),
        id: item.id || item.link || '' };
}

const order = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

async function update(feedsFile, sheet, since) {
    const feeds = await readFeeds(feedsFile);
    const rows = await readSheet(sheet);
    const seen = new Set(rows.map((r) => r.id));
    console.log(`${feeds.length} feeds; ${sheet} has ${posts(rows.length)}`);
    console.log(`reading ${feeds.length} feeds in one run...`);
    const input = { feedUrls: feeds, maxItemsPerFeed: 100 };
    if (since) input.publishedAfter = since;
    const maxUsd = '0.50'; // $0.001 a feed + $0.0003 a post: about 1,600 posts
    const run = await runActor(READER, input, maxUsd);
    const found = new Map(feeds.map((url) => [url, { feeds: new Map(), failed: null }]));
    let added = 0;
    const items = await (await api(`/datasets/${run.defaultDatasetId}/items?clean=true&format=json`)).json();
    for (const item of items) {
        if (!found.has(item.requestedUrl)) found.set(item.requestedUrl, { feeds: new Map(), failed: null });
        const got = found.get(item.requestedUrl);
        if (item.type === 'error') {
            got.failed = item.error;
            continue;
        }
        if (!got.feeds.has(item.feedUrl)) {
            got.feeds.set(item.feedUrl, { title: item.feedTitle || item.feedUrl, format: item.feedFormat, posts: 0,
                new: 0 });
        }
        const feed = got.feeds.get(item.feedUrl);
        feed.posts += 1;
        const row = rowOf(item);
        if (row.id && !seen.has(row.id)) {
            seen.add(row.id);
            rows.push(row);
            feed.new += 1;
            added += 1;
        }
    }
    const summary = await (await api(`/key-value-stores/${run.defaultKeyValueStoreId}/records/SUMMARY`)).json();
    let failed = 0;
    for (const [url, got] of found) {
        if (got.failed) {
            failed += 1;
            console.log(`FAILED ${url}: ${got.failed.code} (${got.failed.message}), not charged`);
        }
        for (const [feedUrl, feed] of got.feeds) {
            let kind = FORMATS[feed.format] || feed.format || 'feed';
            if (feedUrl !== url) kind += ', found on the page you listed';
            console.log(`${feed.title} (${kind}): ${posts(feed.posts)}, ${feed.new} new`);
        }
        if (!got.failed && !got.feeds.size) {
            console.log(summary.stoppedReason ? `${url}: no posts returned before the run stopped`
                : `${url}: no posts${since ? ` since ${since}` : ''}`);
        }
    }
    // newest first; undated posts last
    rows.sort((a, b) => order(b['published (UTC)'], a['published (UTC)']) || order(a.blog, b.blog)
        || order(a.title, b.title));
    const lines = [FIELDS, ...rows.map((r) => FIELDS.map((f) => r[f] ?? ''))].map((r) => r.map(quote).join(','));
    await writeFile(sheet, `﻿${lines.join('\n')}\n`); // the BOM tells Excel the file is UTF-8
    console.log(`${added} new; ${sheet} has ${posts(rows.length)}, newest first`);
    if (summary.stoppedReason) { // at its charge cap or time limit; a re-run reads every feed again from the start
        console.log(`the run stopped early (${summary.stoppedReason}); raise maxUsd in this script, `
            + 'or read fewer posts with --since');
    }
    return failed || summary.stoppedReason ? 1 : 0;
}

const args = process.argv.slice(2);
const option = (name, fallback) => {
    const at = args.indexOf(name);
    if (at === -1) return fallback;
    const [, value] = args.splice(at, 2);
    return value;
};
const sheet = option('--csv', 'posts.csv');
const since = option('--since', null);
if (args.length !== 1) {
    console.error('usage: node feeds_to_csv.mjs <feeds file> [--csv posts.csv] [--since "7 days"]');
    process.exit(2);
}
process.exitCode = await update(args[0], sheet, since);
