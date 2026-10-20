// Turn PDFs into Markdown and RAG-ready chunks with one Apify Actor run. Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node extract.mjs https://example.com/report.pdf [more links...]
//
// Writes <name>.md for each PDF and one chunks.jsonl (a chunk per line, with its source and page range) in the
// current folder, and prints a one-line summary per PDF.
import { writeFile } from 'node:fs/promises';
import { parse } from 'node:path';

const ACTOR = 'canopy_ne3~pdf-text-markdown-extractor';
const urls = process.argv.slice(2);
if (urls.length === 0) {
    console.error('usage: node extract.mjs <PDF URL> [...]');
    process.exit(2);
}

// run-sync-get-dataset-items starts the run, waits for it and returns its results in one call. It answers HTTP 408
// if the run takes more than 300 s; for hundreds of PDFs, start the run asynchronously (see the README).
const endpoint = new URL(`https://api.apify.com/v2/acts/${ACTOR}/run-sync-get-dataset-items`);
endpoint.searchParams.set('maxTotalChargeUsd', '1.00'); // the run stops before spending more than this

const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
        Authorization: `Bearer ${process.env.APIFY_TOKEN}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        pdfUrls: urls,
        outputFormat: 'markdown',
        chunkSize: 1500, // characters per chunk, split at paragraph boundaries; 0 turns chunking off
        chunkOverlap: 200,
    }),
});
if (!response.ok) {
    console.error(`run failed: HTTP ${response.status} ${await response.text()}`);
    process.exit(1);
}

const lines = [];
for (const item of await response.json()) {
    if (item.status !== 'ok') {
        console.log(`FAILED ${item.source}: ${item.error.code}`);
        continue;
    }
    await writeFile(`${parse(item.fileName).name}.md`, item.markdown, 'utf8');
    const chunks = item.chunks ?? [];
    for (const chunk of chunks) lines.push(JSON.stringify({ source: item.source, ...chunk }));
    const scanned = item.pagesWithoutText.length ? `, no text on pages ${item.pagesWithoutText}` : '';
    console.log(`${item.fileName}: ${item.pagesExtracted} pages, ${item.wordCount} words, `
        + `${chunks.length} chunks${scanned}`);
}
await writeFile('chunks.jsonl', lines.map((line) => `${line}\n`).join(''), 'utf8');
