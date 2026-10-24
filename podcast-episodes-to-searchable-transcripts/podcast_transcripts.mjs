// Turn a podcast's episodes into timestamped transcripts, then search them for the moment something was said.
// Node 18 or later, no packages.
//
// Usage:
//   APIFY_TOKEN=<your token> node podcast_transcripts.mjs <feed url> [--latest N]   transcribes the newest N episodes
//                                                                                  (default 3) into transcripts/
//   node podcast_transcripts.mjs --find <words>          prints each episode and time where <words> were said
//
// Two Actor runs: RSS Feed Reader reads the feed and returns each episode's audio link, and Audio & Video Transcription
// transcribes the episodes that are not in transcripts/ yet. Episodes already there are skipped, so running it again
// next week transcribes only the new ones, and --find reads the saved files, so searching costs nothing.
import { existsSync } from 'node:fs';
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const FEED_READER = 'wrentools~rss-feed-reader';
const TRANSCRIBER = 'wrentools~audio-video-transcription';
const OUT = 'transcripts';
const API = 'https://api.apify.com/v2';
const headers = { Authorization: `Bearer ${process.env.APIFY_TOKEN}`, 'Content-Type': 'application/json' };

const pad = (n) => String(n).padStart(2, '0');
function stamp(seconds) {
    const s = Math.floor(seconds);
    return s >= 3600 ? `${Math.floor(s / 3600)}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`
        : `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
}

function fileName(episode) {
    const slug = (episode.title || 'episode').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
    return `${(episode.published || 'undated').slice(0, 10)}-${slug}.md`;
}

async function api(path, init = {}) {
    const response = await fetch(`${API}${path}`, { headers, ...init });
    if (!response.ok) {
        console.error(`HTTP ${response.status} ${await response.text()}`);
        process.exit(1);
    }
    return response.json();
}

// Start a run, wait for it however long it takes (an hour of audio takes about half an hour), and return its items.
async function runActor(actor, input, maxUsd) {
    let { data: run } = await api(`/acts/${actor}/runs?maxTotalChargeUsd=${maxUsd}`, {
        method: 'POST', body: JSON.stringify(input) });
    while (!['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'].includes(run.status)) {
        ({ data: run } = await api(`/actor-runs/${run.id}?waitForFinish=60`));
    }
    if (run.status !== 'SUCCEEDED') {
        console.error(`${actor} run ${run.id}: ${run.status}`);
        process.exit(1);
    }
    return api(`/datasets/${run.defaultDatasetId}/items?clean=true`);
}

async function savedAudio() {
    const links = new Set();
    if (!existsSync(OUT)) return links;
    for (const name of (await readdir(OUT)).filter((n) => n.endsWith('.md'))) {
        const line = (await readFile(join(OUT, name), 'utf8')).split(/\r?\n/).slice(0, 5).find((l) => l.startsWith('Audio: '));
        if (line) links.add(line.slice('Audio: '.length));
    }
    return links;
}

async function transcribe(feedUrl, latest) {
    const episodes = [];
    for (const item of await runActor(FEED_READER, { feedUrls: [feedUrl], maxItemsPerFeed: latest }, '0.10')) {
        if (item.type === 'error') {
            console.error(`feed failed: ${item.error.code}: ${item.error.message}`);
            process.exit(1);
        }
        const audio = item.enclosures.find((e) => /^(audio|video)\//.test(e.type || ''))?.url;
        if (!audio) console.log(`no audio: ${item.title}`);
        else episodes.push({ ...item, audio });
    }
    const done = await savedAudio();
    const fresh = episodes.filter((e) => !done.has(e.audio));
    console.log(`${episodes.length} episodes in the feed's newest ${latest}; ${episodes.length - fresh.length} already transcribed`);
    if (fresh.length === 0) return;
    // $0.01 per started minute: $2.00 covers about three one-hour episodes
    const items = await runActor(TRANSCRIBER, { fileUrls: fresh.map((e) => e.audio), language: 'auto',
        includeSegments: true, subtitleFormats: [] }, '2.00');
    const results = new Map(items.map((item) => [item.url, item]));
    await mkdir(OUT, { recursive: true });
    for (const episode of fresh) {
        const item = results.get(episode.audio);
        if (!item || item.status !== 'ok') {
            console.log(`FAILED ${episode.title}: ${item ? item.error.code : 'not transcribed'}`);
            continue;
        }
        const lines = [`# ${episode.title}`, '', `${episode.feedTitle}, ${(episode.published || '').slice(0, 10)}`,
            `Audio: ${episode.audio}`, '', ...item.segments.map((s) => `[${stamp(s.start)}] ${s.text.trim()}`)];
        await writeFile(join(OUT, fileName(episode)), `${lines.join('\n')}\n`, 'utf8');
        console.log(`${episode.title}: ${stamp(item.durationSeconds)}, ${item.wordCount} words, `
            + `billed ${item.billedMinutes} min${item.truncated ? ', truncated' : ''}`);
    }
}

async function find(words) {
    const names = existsSync(OUT) ? (await readdir(OUT)).filter((n) => n.endsWith('.md')).sort() : [];
    let hits = 0;
    for (const name of names) {
        const text = (await readFile(join(OUT, name), 'utf8')).split(/\r?\n/);
        const found = text.filter((l) => l.startsWith('[') && l.toLowerCase().includes(words.toLowerCase()));
        for (const line of found) {
            const [time, said] = [line.slice(1, line.indexOf('] ')), line.slice(line.indexOf('] ') + 2)];
            console.log(`${text[0].slice(2)}, ${time}: ${said}`);
        }
        if (found.length) hits++;
    }
    console.log(`${hits} of ${names.length} episodes mention '${words}'`);
}

const args = process.argv.slice(2);
if (args.length === 2 && args[0] === '--find') await find(args[1]);
else if (args.length === 1) await transcribe(args[0], 3);
else if (args.length === 3 && args[1] === '--latest' && /^\d+$/.test(args[2])) await transcribe(args[0], Number(args[2]));
else {
    console.error('usage: node podcast_transcripts.mjs <feed url> [--latest N] | --find <words>');
    process.exit(2);
}
