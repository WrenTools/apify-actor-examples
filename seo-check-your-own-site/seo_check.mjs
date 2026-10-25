// Audit your own website's on-page SEO in one run: every page's score and problems, printed and written to a CSV.
// Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node seo_check.mjs <your home page> [--max-pages 50] [--csv seo-report.csv]
//
// One run of Own-Site SEO Audit starts at your home page, follows the links on the same site (obeying your robots.txt)
// and checks every page it reaches the way a search engine reads it: the title, the meta description, the headings,
// images without alt text, structured data that does not parse, links to pages that are broken, and titles or
// descriptions that two pages share. Each page gets a score out of 100. The problems are printed under each page and
// written to the CSV, one row per problem. The exit code is 1 when any problem is rated high, so a scheduled job can
// tell you.
import { writeFile } from 'node:fs/promises';

const AUDIT = 'wrentools~own-site-seo-audit';
const FIELDS = ['page', 'score', 'severity', 'problem', 'what is wrong'];
// A cell starting with one of these could be run as a formula by a spreadsheet; a leading ' keeps it text (OWASP,
// "CSV Injection"). Titles and links are whatever the site wrote, so every cell is treated this way.
const FORMULA_START = ['=', '+', '-', '@', '\t', '\r', '\n', '＝', '＋', '－', '＠'];
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const WORDS = { // the Actor's issue codes, in words; d is the issue's detail, p the page
    'missing-title': () => 'no <title>',
    'title-too-long': (d) => `the title is ${d} characters; search results cut it after about 60`,
    'title-too-short': (d) => `the title is only ${d} characters`,
    'multiple-title-tags': (d) => `${d} <title> tags`,
    'missing-meta-description': () => 'no meta description',
    'meta-description-length': (d) => `the meta description is ${d} characters; aim for 50 to 160`,
    'missing-h1': () => 'no <h1> heading',
    'multiple-h1': (d) => `${d} <h1> headings`,
    'images-missing-alt': (d) => `${plural(d, 'image', 'images')} without alt text`,
    noindex: () => 'marked noindex, so search engines are asked not to list it',
    'canonical-points-elsewhere': (d) => `its canonical address is another page: ${d}`,
    'missing-html-lang': () => 'no lang on <html>',
    'missing-viewport': () => 'no mobile viewport tag',
    'invalid-json-ld': (d) => `${plural(d, 'structured data (JSON-LD) block does',
        'structured data (JSON-LD) blocks do')} not parse`,
    redirected: (d) => `redirects to ${d}`,
    'http-error': (d) => (Number.isInteger(d) ? `HTTP ${d}` : `no answer (${d})`),
    'broken-internal-links': (d, p) => `links to ${plural(d, 'broken page', 'broken pages')} on your site: `
        + p.brokenInternalLinks.join(', '),
    'broken-external-links': (d, p) => `links to ${plural(d, 'broken page', 'broken pages')} on other sites: `
        + p.brokenExternalLinks.join(', '),
    'duplicate-title': (d) => `the same title as ${d.join(', ')}`,
    'duplicate-meta-description': (d) => `the same meta description as ${d.join(', ')}`,
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

const words = (issue, page) => (WORDS[issue.code] ? WORDS[issue.code](issue.detail, page) : issue.code);

async function audit(start, maxPages, sheet) {
    console.log(`auditing ${start} and the pages it links to on the same site, in one run...`);
    const run = await runActor(AUDIT, { startUrl: start, maxPages }, '0.50'); // $0.005 a page audited: at most 100
    const pages = await (await api(`/datasets/${run.defaultDatasetId}/items?clean=true&format=json`)).json();
    const rows = [];
    const counts = { high: 0, medium: 0, low: 0, info: 0 };
    for (const page of pages) { // in the order the pages were reached
        console.log(`${String(page.score).padStart(3)}  ${page.url}`);
        for (const issue of page.issues) {
            const what = words(issue, page);
            counts[issue.severity] += 1;
            console.log(`     ${issue.severity.toUpperCase().padEnd(7)} ${what}`);
            rows.push({ page: page.url, score: page.score, severity: issue.severity, problem: issue.code,
                'what is wrong': what });
        }
    }
    const summary = await (await api(`/key-value-stores/${run.defaultKeyValueStoreId}/records/SUMMARY`)).json();
    const lines = [FIELDS, ...rows.map((r) => FIELDS.map((f) => asText(r[f])))].map((r) => r.map(quote).join(','));
    await writeFile(sheet, `﻿${lines.join('\n')}\n`); // the BOM tells Excel the file is UTF-8
    const average = summary.averageScore;
    console.log(`${plural(summary.pagesAudited, 'page', 'pages')}, average score `
        + (average === null ? 'none' : average.toFixed(1)) + `: ${counts.high} high, ${counts.medium} medium, `
        + `${counts.low} low` + (counts.info ? `, ${counts.info} info` : '')
        + `; ${plural(rows.length, 'problem', 'problems')} in ${sheet}`);
    if (summary.urlsBlockedByRobotsTxt) {
        console.log(`${summary.urlsBlockedByRobotsTxt} linked pages were not audited, because your robots.txt blocks them`);
    }
    if (summary.stoppedReason) { // max pages, the charge cap or the time limit; pages after it were not audited
        console.log(`the run stopped early (${summary.stoppedReason})`);
    }
    return counts.high ? 1 : 0;
}

const args = process.argv.slice(2);
const option = (name, fallback) => {
    const at = args.indexOf(name);
    return at === -1 ? fallback : args.splice(at, 2)[1];
};
const sheet = option('--csv', 'seo-report.csv');
const maxPages = Number(option('--max-pages', '50'));
if (args.length !== 1 || !Number.isInteger(maxPages) || maxPages < 1) {
    console.error('usage: node seo_check.mjs <your home page> [--max-pages 50] [--csv seo-report.csv]');
    process.exit(2);
}
process.exitCode = await audit(args[0], maxPages, sheet);
