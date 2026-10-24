// Download every file from a list of links into one folder, check each one arrived whole, and list what failed.
// Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node download_files.mjs <links file> [--folder files]
//
// The links file has one direct link to a file per line (blank lines and lines starting with # are skipped). One run
// of Bulk File Downloader fetches every link not downloaded yet. Each file is saved into the folder under its own name
// and its SHA-256 is compared with the one the Actor measured, so a file cut short in transit is caught. manifest.csv
// in the folder lists what is there. Links that failed are printed with the reason, are not charged, and are tried
// again next time, so after fixing a link you run the same command and only that file is downloaded.
import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const DOWNLOADER = 'wrentools~bulk-file-downloader';
const FIELDS = ['url', 'file', 'bytes', 'sha256'];
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

async function readLinks(path) {
    const links = [];
    for (const raw of (await readFile(path, 'utf8')).split(/\r?\n/)) {
        const line = raw.trim();
        if (line && !line.startsWith('#') && !links.includes(line)) links.push(line);
    }
    return links;
}

// manifest.csv, written and read the way Python's csv module does it, so either version can carry on the other's folder.
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

async function readManifest(folder) {
    const path = join(folder, 'manifest.csv');
    if (!existsSync(path)) return [];
    const [header, ...rows] = parseCsv(await readFile(path, 'utf8'));
    return rows.map((r) => Object.fromEntries(header.map((h, k) => [h, r[k]])));
}

// The file's own name, or name-2, name-3... when another link already saved a file by that name.
function freeName(folder, name, taken) {
    const dot = name.lastIndexOf('.');
    const [stem, ext] = dot >= 0 ? [name.slice(0, dot), name.slice(dot)] : [name, ''];
    let candidate = name;
    for (let n = 2; taken.has(candidate) || existsSync(join(folder, candidate)); n++) candidate = `${stem}-${n}${ext}`;
    return candidate;
}

async function download(linksFile, folder) {
    const links = await readLinks(linksFile);
    const rows = await readManifest(folder);
    const done = new Set(rows.map((r) => r.url));
    const fresh = links.filter((u) => !done.has(u));
    console.log(`${links.length} links; ${links.length - fresh.length} already in ${folder}/`);
    if (fresh.length === 0) return 0;
    console.log(`downloading ${fresh.length} in one run...`);
    // $0.002 a file + $0.001 a started MB: $0.50 covers about 160 files under 1 MB
    const run = await runActor(DOWNLOADER, { fileUrls: fresh, maxFileSizeMb: 50 }, '0.50');
    const items = await (await api(`/datasets/${run.defaultDatasetId}/items?clean=true`)).json();
    await mkdir(folder, { recursive: true });
    const taken = new Set(rows.map((r) => r.file));
    let [got, failed] = [0, 0];
    const reached = new Set(items.map((item) => item.url));
    for (const item of items) {
        if (item.status !== 'ok') {
            failed++;
            console.log(`FAILED ${item.url}: ${item.error.code} (${item.error.message}), not charged`);
            continue;
        }
        const key = encodeURIComponent(item.key);
        const body = Buffer.from(await (await api(`/key-value-stores/${run.defaultKeyValueStoreId}/records/${key}`))
            .arrayBuffer());
        if (createHash('sha256').update(body).digest('hex') !== item.sha256) {
            failed++;
            console.log(`FAILED ${item.url}: the copy's SHA-256 is not the one the Actor measured; run again`);
            continue;
        }
        const name = freeName(folder, item.fileName, taken);
        await writeFile(join(folder, name), body);
        taken.add(name);
        rows.push({ url: item.url, file: name, bytes: body.length, sha256: item.sha256 });
        got++;
        console.log(`ok  ${name.padEnd(28)} ${(body.length / 1024).toFixed(1).padStart(7)} KB  SHA-256 matches`);
    }
    const csv = [FIELDS, ...rows.map((r) => FIELDS.map((f) => r[f]))].map((r) => r.map(quote).join(',')).join('\n');
    await writeFile(join(folder, 'manifest.csv'), `${csv}\n`, 'utf8');
    console.log(`${got} downloaded, ${failed} failed; ${rows.length} files listed in ${folder}/manifest.csv`);
    const missed = fresh.filter((u) => !reached.has(u)); // the run stopped early, at its charge cap or time limit
    if (missed.length) {
        const summary = await (await api(`/key-value-stores/${run.defaultKeyValueStoreId}/records/SUMMARY`)).json();
        console.log(`${missed.length} links not reached (${summary.stoppedReason}); run the same command again to fetch them`);
    }
    return failed || missed.length ? 1 : 0;
}

const args = process.argv.slice(2);
if (args.length === 1) process.exitCode = await download(args[0], 'files');
else if (args.length === 3 && args[1] === '--folder') process.exitCode = await download(args[0], args[2]);
else {
    console.error('usage: node download_files.mjs <links file> [--folder files]');
    process.exit(2);
}
