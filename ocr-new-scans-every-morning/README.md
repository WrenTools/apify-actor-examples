# Read the text in every new scan in a folder, each morning (Python)

This example is a script you leave to run on a schedule. Each time it runs, it finds the PDF scans in one folder that
it has not read yet, sends them to the
[Image & Scanned PDF OCR](https://apify.com/wrentools/scanned-pdf-image-ocr) Actor on Apify in one run, saves the text
of each beside its scan as `.txt`, and adds every page read with low confidence to `review.csv` for a person to check.
It is about 95 lines of Python, with no packages to install.

**Disclosure:** we built and sell that Actor (Apify account `wrentools`), and this example was written with AI
assistance and then run against the live Actor before publishing.

For a one-off list of files, the shorter [OCR example](../ocr-scanned-pdfs-and-images/) is simpler.

## How it knows which scans are new

A file's name can't tell it. Someone copies a scan back into the folder, and the same scan is there twice under two
names; a page is scanned again, and new contents arrive under an old name. So the script remembers each scan by its
**fingerprint**, the SHA-256 of its bytes, kept in `done.json` beside the scans:

- A copy has the same fingerprint as the scan it copies, so it is not sent again.
- A file that changes gets a new fingerprint, so it is sent, even under the old name.
- A scan's fingerprint goes into `done.json` only after its text is saved. A scan that fails is not recorded, so the
  next run tries it again.
- `done.json` is written to `done.tmp` first and then renamed over the old file, so a crash while writing it leaves the
  old list as it was.

## Run it

You need Python 3 (we ran it with Python 3.14 on Windows 11), an
[Apify account](https://console.apify.com/sign-up) and its API token (Console > Settings > API & Integrations). The
token goes in an environment variable, `APIFY_TOKEN`, never in the script.

```bash
export APIFY_TOKEN=<your token>          # PowerShell: $env:APIFY_TOKEN = "<your token>"
python ocr_new_scans.py ~/Scans          # Windows: py ocr_new_scans.py C:\Scans
```

It prints one line for each scan that failed, then a summary: `3 new: 3 read, 0 failed, 1 to check`, or
`no new scans` (when nothing is new it sends no request at all, so it costs nothing).

## Run it every weekday morning

**Windows (Task Scheduler).** Store the token once for your Windows user, then create the task. Put
`ocr_new_scans.py` in the folder, or anywhere and change the path:

```bat
setx APIFY_TOKEN "<your token>"
schtasks /create /tn "OCR new scans" /tr "py C:\Scans\ocr_new_scans.py C:\Scans" /sc weekly /d MON,TUE,WED,THU,FRI /st 07:00
```

That runs it at 7:00, Monday to Friday, while you are signed in. `setx` stores the variable for your user; programs
started afterwards, the task among them, can read it, but a window that was already open cannot.

To keep each morning's summary in a log, run it through `cmd`:

```bat
schtasks /create /tn "OCR new scans" /tr "cmd /c py C:\Scans\ocr_new_scans.py C:\Scans >> C:\Scans\ocr.log 2>&1" /sc weekly /d MON,TUE,WED,THU,FRI /st 07:00
```

**macOS and Linux (cron).** cron does not read your shell profile, so set the token in the crontab itself
(`crontab -e`). The five fields are the minute, the hour, the day of the month, the month and the day of the week, so
`0 7 * * 1-5` is 7:00, Monday to Friday:

```text
APIFY_TOKEN=<your token>
0 7 * * 1-5 cd ~/Scans && python3 ocr_new_scans.py . >> ocr.log 2>&1
```

## What it did over four mornings

We ran it against the live Actor (build 0.1.9) on a made-up office's scan folder, morning by morning: one-page scans of
invoices, a receipt, a statement, and a remittance advice that came through as a faint copy. This is
the log the four runs left:

```text
3 new: 3 read, 0 failed, 1 to check
no new scans
scan-0005.pdf: failed (unreadable-pdf), tried again next time
2 new: 1 read, 1 failed, 0 to check
1 new: 1 read, 0 failed, 0 to check
```

- **Monday:** three scans, all read. The faint copy (scan 3) scored 47.9 and went on the review list:

  ```text
  file,page,confidence
  scan-0003.pdf,1,47.9
  ```

- **Monday, run again:** nothing new, and no request sent.
- **Tuesday:** six files. One was a copy of scan 2 (`scan-0002 - Copy.pdf`), skipped by its fingerprint, so two were
  sent. Scan 5 had been cut off by the scanner while it wrote the file, and the Actor answered `unreadable-pdf`.
- **Wednesday:** scan 5 had been scanned again under the same name. Its fingerprint was new, so it was sent, and read.

After Wednesday the folder held five `.txt` files, one per distinct scan, beside `done.json` and `review.csv`.

## What it costs

The Actor charges **$0.003 per page read**, with no start fee, and nothing for a file that fails. The four mornings
above read 5 pages, which is $0.015. A morning with nothing new sends no request, so it costs nothing.

## Limits

- It reads files ending in `.pdf`. On Windows that matches `.PDF` too; on macOS and Linux, Python matches the case
  exactly, so rename `.PDF` files or change the pattern in `main`.
- Every new scan goes inside one run's input, as base64 (about a third larger than the file). We ran it on mornings of
  one to three one-page scans. On a first morning with a large backlog, give it part of the backlog at a time.
- The Actor reads at most 100 pages of each file unless told otherwise (`maxPagesPerFile`), and the script does not
  change that: a longer scan's later pages are not read, and the scan is still marked done.
- A file that fails the same way each morning (a scan that stays cut off) is tried every morning until it is replaced.
  Failed files are not charged.
- OCR can misread a letter, and nothing in the text marks where. Check the pages in `review.csv` by eye; the
  [OCR example](../ocr-scanned-pdfs-and-images/) shows the Actor's options for harder pages.
- Process only documents you have the right to use.
