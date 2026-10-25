// Check every page your sitemap lists, and the sitemap itself, in one run; write the problems to a CSV.
// Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node check_sitemap.mjs <sitemap URL, or your site's address> [--csv sitemap-report.csv]
//
// Give it a sitemap or a sitemap index, or just your site's address: the Actor then reads the Sitemap: lines in your
// robots.txt, or tries /sitemap.xml. One run of Sitemap Validator checks each sitemap file against the sitemaps.org
// rules and requests every page it lists once. Pages that are broken or redirect, and entries that break a rule, are
// printed and written to the CSV, one row per problem. The exit code is 1 when there is any problem, so a scheduled
// job can tell you.
import { writeFile } from 'node:fs/promises';

const VALIDATOR = 'wrentools~sitemap-validator';
const FIELDS = ['page', 'problem', 'what is wrong', 'HTTP status', 'redirects to', 'sitemap'];
// A cell starting with one of these could be run as a formula by a spreadsheet; a leading ' keeps it text (OWASP,
// "CSV Injection"). A sitemap is whatever its site wrote, so every cell is treated this way.
const FORMULA_START = ['=', '+', '-', '@', '\t', '\r', '\n', '＝', '＋', '－', '＠'];
const FREQS = 'always, hourly, daily, weekly, monthly, yearly or never';
const RULES = { // the Actor's issue codes for the sitemaps.org rules, in words
    'invalid-lastmod': (e) => `lastmod "${e.lastmod}" is not a W3C date; write it YYYY-MM-DD`,
    'lastmod-in-future': (e) => `lastmod ${e.lastmod} is in the future`,
    'invalid-changefreq': (e) => `changefreq "${e.changefreq}" is not ${FREQS}`,
    'invalid-priority': (e) => `priority "${e.priority}" is not a number`,
    'priority-out-of-range': (e) => `priority ${e.priority} is not between 0.0 and 1.0`,
    'duplicate-loc': () => 'listed more than once',
    'loc-on-other-host': () => 'on another host than the sitemap, which the protocol does not allow',
    'loc-not-absolute-http-url': () => 'not a full http:// or https:// address',
    'loc-not-escaped': () => 'has characters that must be escaped (& as &amp;)',
    'missing-loc': () => 'an entry with no <loc>',
};
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

function asText(value) {
    const text = String(value ?? '').split(/\s+/).filter(Boolean).join(' ');
    return FORMULA_START.some((s) => text.startsWith(s)) ? `'${text}` : text;
}

// Quoted only when needed, as Python's csv module does.
const quote = (v) => (/[",\r\n]/.test(v) ? `"${v.replaceAll('"', '""')}"` : v);

// [label, issue code, what is wrong] for each issue the Actor reported on one entry.
function problemsOf(entry) {
    return entry.issues.map((code) => {
        if (code === 'url-not-ok') {
            const status = entry.httpStatus;
            return ['BROKEN', code, status ? `HTTP ${status}` : `no answer (${entry.statusError})`];
        }
        if (code === 'url-redirects') {
            return ['REDIRECT', code, `redirects to ${entry.redirectedTo}; list that address instead`];
        }
        if (code === 'url-blocked-by-robots-txt') {
            return ['BLOCKED', code, 'your robots.txt blocks it, so it was not requested'];
        }
        return ['RULE', code, RULES[code] ? RULES[code](entry) : code];
    });
}

async function check(target, sheet) {
    const input = /\.(xml|xml\.gz|gz)$/.test(target.toLowerCase().split('?')[0])
        ? { sitemapUrls: [target] }
        : { siteUrl: target }; // robots.txt Sitemap: lines, else /sitemap.xml
    Object.assign(input, { checkUrlStatus: true, maxUrls: 5000, maxSitemapFiles: 50 });
    console.log(`checking ${target} and every page it lists, in one run...`);
    // $0.002 a sitemap file + $0.0006 a page checked: about 830 pages
    const run = await runActor(VALIDATOR, input, '0.50');
    const items = await (await api(`/datasets/${run.defaultDatasetId}/items?clean=true&format=json`)).json();
    const rows = [];
    let [pages, works, broken, redirects, unchecked, ruleBreaking] = [0, 0, 0, 0, 0, 0];
    for (const item of items) {
        if (item.type === 'sitemap-file') {
            if (item.errors.length || item.httpStatus !== 200) {
                const what = item.errors.join(', ') || `HTTP ${item.httpStatus}`;
                console.log(`SITEMAP   ${item.url}  (${what})`);
                rows.push({ page: item.url, problem: 'sitemap-file', 'what is wrong': what,
                    'HTTP status': item.httpStatus, 'redirects to': '', sitemap: item.url });
            } else if (item.kind === 'sitemapindex') {
                console.log(`${item.url}: an index of ${item.entryCount} sitemaps`);
            } else {
                console.log(`${item.url}: ${item.entryCount} pages listed`);
            }
            continue;
        }
        pages += 1;
        const found = problemsOf(item);
        const labels = new Set(found.map(([label]) => label));
        if (labels.has('BROKEN')) broken += 1;
        if (labels.has('REDIRECT')) redirects += 1;
        if (!labels.has('BROKEN') && !labels.has('REDIRECT')) { // answered, or not requested (robots.txt, a bad <loc>)
            if (item.statusChecked) works += 1; else unchecked += 1;
        }
        if (labels.has('RULE')) ruleBreaking += 1;
        for (const [label, code, what] of found) {
            console.log(`${label.padEnd(9)} ${item.loc}  (${what})`);
            rows.push({ page: item.loc, problem: code, 'what is wrong': what, 'HTTP status': item.httpStatus,
                'redirects to': item.redirectedTo, sitemap: item.sitemap });
        }
    }
    const summary = await (await api(`/key-value-stores/${run.defaultKeyValueStoreId}/records/SUMMARY`)).json();
    const lines = [FIELDS, ...rows.map((r) => FIELDS.map((f) => asText(r[f])))].map((r) => r.map(quote).join(','));
    await writeFile(sheet, `﻿${lines.join('\n')}\n`); // the BOM tells Excel the file is UTF-8
    console.log(`${pages} pages: ${works} work, ${broken} broken, ${redirects} redirect`
        + (unchecked ? `, ${unchecked} not requested` : '') + `; ${ruleBreaking} `
        + `${ruleBreaking === 1 ? 'breaks' : 'break'} a sitemap rule; `
        + `${rows.length} ${rows.length === 1 ? 'problem' : 'problems'} in ${sheet}`);
    if (summary.stoppedReason) { // the charge cap, maxUrls or the time limit; the pages after it were not checked
        console.log(`the run stopped early (${summary.stoppedReason}); pages after that point were not checked`);
    }
    return rows.length || summary.stoppedReason ? 1 : 0;
}

const args = process.argv.slice(2);
const at = args.indexOf('--csv');
const sheet = at === -1 ? 'sitemap-report.csv' : args.splice(at, 2)[1];
if (args.length !== 1) {
    console.error('usage: node check_sitemap.mjs <sitemap URL, or your site\'s address> [--csv sitemap-report.csv]');
    process.exit(2);
}
process.exitCode = await check(args[0], sheet);
