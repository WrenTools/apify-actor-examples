// Pull the text out of a folder of screenshots or photos with Apify Actor runs. Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node ocr_folder.mjs <folder>                  reads every image into <folder>-text.csv
//   APIFY_TOKEN=<your token> node ocr_folder.mjs <folder> --find <words>   prints each screenshot whose text holds
//                                                                          <words>, and the line
//
// The files are on your computer, not online, so they are sent inline as base64, a few megabytes per run. --find
// reads the CSV if it is already there, so searching again costs nothing; delete the CSV to read the folder again.
import { existsSync } from 'node:fs';
import { readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { basename, extname, join, resolve } from 'node:path';

const ACTOR = 'wrentools~scanned-pdf-image-ocr';
const IMAGES = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff']);
const BATCH_BYTES = 4_000_000; // image bytes per run; base64 makes the input a third larger

const [folder, flag, words] = process.argv.slice(2);
if (!folder || (flag !== undefined && (flag !== '--find' || !words))) {
    console.error('usage: node ocr_folder.mjs <folder> [--find <words>]');
    process.exit(2);
}
const out = `${basename(resolve(folder))}-text.csv`;

const quote = (value) => `"${String(value).replaceAll('"', '""')}"`;

// A small CSV reader for the file this script writes: quoted fields may hold commas, quotes and line breaks.
function parseCsv(text) {
    const rows = [];
    let row = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (quoted) {
            if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
            else if (c === '"') quoted = false;
            else field += c;
        } else if (c === '"') quoted = true;
        else if (c === ',') { row.push(field); field = ''; }
        else if (c === '\n') { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
        else field += c;
    }
    if (field || row.length) rows.push([...row, field]);
    const [header, ...body] = rows;
    return body.map((cells) => Object.fromEntries(header.map((name, k) => [name, cells[k]])));
}

async function readFolder() {
    const names = (await readdir(folder)).filter((n) => IMAGES.has(extname(n).toLowerCase())).sort();
    if (names.length === 0) {
        console.error(`no images in ${folder}`);
        process.exit(1);
    }
    const batches = [[]];
    let size = 0;
    for (const name of names) {
        const bytes = (await stat(join(folder, name))).size;
        if (batches.at(-1).length && size + bytes > BATCH_BYTES) {
            batches.push([]);
            size = 0;
        }
        batches.at(-1).push(name);
        size += bytes;
    }

    const lines = ['file,confidence,words,text'];
    for (const batch of batches) {
        // run-sync-get-dataset-items starts the run, waits for it and returns its results in one call. It answers
        // HTTP 408 if the run takes more than 300 s; for a large folder, lower BATCH_BYTES.
        const endpoint = new URL(`https://api.apify.com/v2/acts/${ACTOR}/run-sync-get-dataset-items`);
        endpoint.searchParams.set('maxTotalChargeUsd', '1.00'); // the run stops before spending more than this
        const filesBase64 = await Promise.all(batch.map(async (name) => (
            { name, data: (await readFile(join(folder, name))).toString('base64') })));
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { Authorization: `Bearer ${process.env.APIFY_TOKEN}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filesBase64,
                languages: ['eng'], // up to 3, e.g. ['eng', 'deu']; each one added slows every page
            }),
        });
        if (!response.ok) {
            console.error(`run failed: HTTP ${response.status} ${await response.text()}`);
            process.exit(1);
        }
        for (const item of await response.json()) {
            if (item.status !== 'ok') {
                console.log(`FAILED ${item.fileName}: ${item.error.code}`);
                continue;
            }
            lines.push([item.fileName, item.meanConfidence, item.wordCount, item.text].map(quote).join(','));
        }
    }
    // The byte order mark lets Excel read the file as UTF-8.
    await writeFile(out, `﻿${lines.join('\r\n')}\r\n`, 'utf8');
    console.log(`${lines.length - 1} of ${names.length} images read into ${out}`);
}

if (!words || !existsSync(out)) await readFolder();
if (words) {
    const rows = parseCsv((await readFile(out, 'utf8')).replace(/^﻿/, ''));
    let hits = 0;
    for (const row of rows) {
        const found = row.text.split('\n').map((l) => l.trim()).filter((l) => l.toLowerCase().includes(words.toLowerCase()));
        for (const line of found) console.log(`${row.file}: ${line}`);
        if (found.length) hits++;
    }
    console.log(`${hits} of ${rows.length} screenshots mention '${words}'`);
}
