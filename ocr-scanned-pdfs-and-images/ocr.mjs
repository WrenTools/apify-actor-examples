// Read the text in scanned PDFs and images with one Apify Actor run. Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node ocr.mjs https://example.com/scan.pdf [more links...]
//
// Writes <name>.txt for each file in the current folder and prints a one-line summary per file, naming any page read
// with low confidence, so you know which pages to check by eye.
import { writeFile } from 'node:fs/promises';
import { parse } from 'node:path';

const ACTOR = 'wrentools~scanned-pdf-image-ocr';
const urls = process.argv.slice(2);
if (urls.length === 0) {
    console.error('usage: node ocr.mjs <PDF or image URL> [...]');
    process.exit(2);
}

// run-sync-get-dataset-items starts the run, waits for it and returns its results in one call. It answers HTTP 408
// if the run takes more than 300 s; for long scans, start the run asynchronously (see the README).
const endpoint = new URL(`https://api.apify.com/v2/acts/${ACTOR}/run-sync-get-dataset-items`);
endpoint.searchParams.set('maxTotalChargeUsd', '1.00'); // the run stops before spending more than this

const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
        Authorization: `Bearer ${process.env.APIFY_TOKEN}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        fileUrls: urls,
        languages: ['eng'], // up to 3, e.g. ['eng', 'deu']; each one added slows every page
        pdfDpi: 300, // raise it for small print
    }),
});
if (!response.ok) {
    console.error(`run failed: HTTP ${response.status} ${await response.text()}`);
    process.exit(1);
}

for (const item of await response.json()) {
    if (item.status !== 'ok') {
        console.log(`FAILED ${item.source}: ${item.error.code}`);
        continue;
    }
    await writeFile(`${parse(item.fileName).name}.txt`, item.text, 'utf8');
    const check = item.lowConfidencePages.length ? `, check pages ${item.lowConfidencePages}` : '';
    console.log(`${item.fileName}: ${item.pagesProcessed} pages, ${item.wordCount} words, `
        + `confidence ${item.meanConfidence}${check}`);
}
