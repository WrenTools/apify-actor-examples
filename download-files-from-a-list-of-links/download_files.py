"""Download every file from a list of links into one folder, check each one arrived whole, and list what failed.

Usage:
    pip install -r requirements.txt
    set APIFY_TOKEN=<your token>            (PowerShell: $env:APIFY_TOKEN = "<your token>")
    python download_files.py <links file> [--folder files]

The links file has one direct link to a file per line (blank lines and lines starting with # are skipped). One run of
Bulk File Downloader fetches every link not downloaded yet. Each file is saved into the folder under its own name and
its SHA-256 is compared with the one the Actor measured, so a file cut short in transit is caught. manifest.csv in the
folder lists what is there. Links that failed are printed with the reason, are not charged, and are tried again next
time, so after fixing a link you run the same command and only that file is downloaded.
"""
import csv
import hashlib
import os
import sys
from decimal import Decimal
from pathlib import Path

from apify_client import ApifyClient

DOWNLOADER = "wrentools/bulk-file-downloader"
FIELDS = ["url", "file", "bytes", "sha256"]


def read_links(path: Path) -> list[str]:
    links = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line not in links:
            links.append(line)
    return links


def read_manifest(folder: Path) -> list[dict]:
    manifest = folder / "manifest.csv"
    if not manifest.exists():
        return []
    with manifest.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def free_name(folder: Path, name: str, taken: set[str]) -> str:
    """The file's own name, or name-2, name-3... when another link already saved a file by that name."""
    stem, dot, ext = name.rpartition(".") if "." in name else (name, "", "")
    candidate, n = name, 1
    while candidate in taken or (folder / candidate).exists():
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    return candidate


def download(links_file: Path, folder: Path) -> int:
    links = read_links(links_file)
    rows = read_manifest(folder)
    done = {r["url"] for r in rows}
    new = [u for u in links if u not in done]
    print(f"{len(links)} links; {len(links) - len(new)} already in {folder}/")
    if not new:
        return 0
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    print(f"downloading {len(new)} in one run...")
    run = client.actor(DOWNLOADER).call(
        run_input={"fileUrls": new, "maxFileSizeMb": 50},
        max_total_charge_usd=Decimal("0.50"),  # $0.002 a file + $0.001 a started MB: about 160 files under 1 MB
    )
    store = client.key_value_store(run.default_key_value_store_id)
    folder.mkdir(exist_ok=True)
    taken = {r["file"] for r in rows}
    got, failed, reached = 0, 0, set()
    for item in client.dataset(run.default_dataset_id).iterate_items():
        reached.add(item["url"])
        if item["status"] != "ok":
            failed += 1
            print(f"FAILED {item['url']}: {item['error']['code']} ({item['error']['message']}), not charged")
            continue
        body = store.get_record_as_bytes(item["key"])["value"]
        if hashlib.sha256(body).hexdigest() != item["sha256"]:
            failed += 1
            print(f"FAILED {item['url']}: the copy's SHA-256 is not the one the Actor measured; run again")
            continue
        name = free_name(folder, item["fileName"], taken)
        (folder / name).write_bytes(body)
        taken.add(name)
        rows.append({"url": item["url"], "file": name, "bytes": len(body), "sha256": item["sha256"]})
        got += 1
        print(f"ok  {name:<28} {len(body) / 1024:7.1f} KB  SHA-256 matches")
    with (folder / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")  # the same file on every system
        writer.writeheader()
        writer.writerows(rows)
    print(f"{got} downloaded, {failed} failed; {len(rows)} files listed in {folder}/manifest.csv")
    if missed := [u for u in new if u not in reached]:  # the run stopped early, at its charge cap or time limit
        stopped = store.get_record("SUMMARY")["value"]["stoppedReason"]
        print(f"{len(missed)} links not reached ({stopped}); run the same command again to fetch them")
    return 1 if failed or missed else 0


def main(args: list[str]) -> int:
    if len(args) == 1:
        return download(Path(args[0]), Path("files"))
    if len(args) == 3 and args[1] == "--folder":
        return download(Path(args[0]), Path(args[2]))
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
