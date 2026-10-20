// Merge CSV, JSON, JSON Lines or Excel files into one list without duplicates, with one Apify Actor run.
// Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node dedup.mjs https://example.com/crm-export.csv https://example.com/signups.jsonl
//
// Rows are duplicates when their email matches (ignoring case and surrounding spaces); of each group, the row with
// the most non-empty fields is kept. Writes merged.csv in the current folder.
import { writeFile } from 'node:fs/promises';

const ACTOR = 'canopy_ne3~dataset-merge-dedup';
const urls = process.argv.slice(2);
if (urls.length === 0) {
    console.error('usage: node dedup.mjs <file URL> [...]');
    process.exit(2);
}

// run-sync-get-dataset-items starts the run, waits for it and returns its dataset in one call, here as CSV.
// It answers HTTP 408 if the run takes more than 300 s; for very large merges, start the run asynchronously.
const endpoint = new URL(`https://api.apify.com/v2/acts/${ACTOR}/run-sync-get-dataset-items`);
endpoint.searchParams.set('format', 'csv');
endpoint.searchParams.set('maxTotalChargeUsd', '1.00'); // the run stops before spending more than this

const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
        Authorization: `Bearer ${process.env.APIFY_TOKEN}`,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        fileUrls: urls, // or datasetIds: [...] to merge your own Apify datasets
        dedupFields: ['email'], // several fields together, dotted paths, or ['*'] for whole rows
        keep: 'mostComplete', // or 'first', 'last'
        addSourceField: '_source', // which file each row came from
    }),
});
if (!response.ok) {
    console.error(`run failed: HTTP ${response.status} ${await response.text()}`);
    process.exit(1);
}
const csv = await response.text();
await writeFile('merged.csv', csv, 'utf8');
console.log(`wrote merged.csv (${csv.length} characters)`);
