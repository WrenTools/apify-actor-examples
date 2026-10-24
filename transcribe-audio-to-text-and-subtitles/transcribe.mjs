// Transcribe audio or video files to text and subtitles with one Apify Actor run. Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node transcribe.mjs https://example.com/interview.mp3 [more links...]
//
// Writes <name>.txt and <name>.srt in the current folder for each file, and prints a one-line summary per file.
import { writeFile } from 'node:fs/promises';
import { parse } from 'node:path';

const ACTOR = 'wrentools~audio-video-transcription';
const urls = process.argv.slice(2);
if (urls.length === 0) {
    console.error('usage: node transcribe.mjs <audio or video URL> [...]');
    process.exit(2);
}

// run-sync-get-dataset-items starts the run, waits for it (up to 300 s) and returns its results in one call.
// It answers HTTP 408 after 300 s, so for more than about 8 minutes of audio, start the run asynchronously (see the README).
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
        language: 'auto', // or "en", "de", "es", ...
        subtitleFormats: ['srt'],
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
    const stem = parse(item.fileName).name;
    await writeFile(`${stem}.txt`, item.text, 'utf8');
    if (item.subtitles?.srt) {
        const srt = await fetch(item.subtitles.srt);
        await writeFile(`${stem}.srt`, Buffer.from(await srt.arrayBuffer()));
    }
    console.log(`${item.fileName}: ${item.language}, ${Math.round(item.durationSeconds)} s, `
        + `${item.wordCount} words, billed ${item.billedMinutes} min`);
}
