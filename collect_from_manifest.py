"""
Collect up to five Keejob postings from a saved discovery manifest.

Preserve each posting's JobPosting JSON-LD data with collection metadata
in a separate bronze JSON file. Report collection failures and stop on
access restrictions, rate limiting, or file-saving errors.

Usage:
    uv run python collect_from_manifest.py path/to/manifest.json
"""
import argparse
import json
import time
from pathlib import Path

import requests

from collect_job import collect_job, save_record
from datetime import datetime, timezone
from uuid import uuid4


def save_batch_report(manifest_path, started_at, saved_records, failures):
    report = {
        "source": "keejob",
        "manifest_path": str(manifest_path),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "successful_count": len(saved_records),
        "failed_count": len(failures),
        "saved_records": saved_records,
        "failures": failures,
    }

    directory = Path("data") / "reports" / "keejob"
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{uuid4().hex}.json"

    with output_path.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)

    batch_options = parser.add_mutually_exclusive_group()

    batch_options.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of postings to collect (default: 5).",
    )

    batch_options.add_argument(
        "--all",
        action="store_true",
        help="Collect every URL in the manifest.",
    )

    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than zero")




    with args.manifest.open(encoding="utf-8") as file:
        manifest = json.load(file)
    started_at = datetime.now(timezone.utc)
    saved_records = []

    manifest_urls = manifest["job_urls"]

    if args.all:
        job_urls = manifest_urls
    else:
        job_urls = manifest_urls[:args.limit]

    print(f"Selected {len(job_urls)} candidate URLs.",  flush=True )

    successes = 0
    failures = []

    for index, url in enumerate(job_urls, start=1):
        if index > 1:
            time.sleep(2)

        print(f"\n[{index}/{len(job_urls)}] Collecting: {url}", flush=True)

        try:
            record = collect_job(url)
        except requests.HTTPError as error:
            status = error.response.status_code

            # Stop the batch on access restrictions or rate limiting.
            if status in {401, 403, 429}:
                raise

            failures.append({"url": url, "error": str(error)})
            print("HTTP failure:", error)
            continue

        except (requests.RequestException, ValueError) as error:
            failures.append({"url": url, "error": str(error)})
            print("Collection failure:", error)
            continue

        output_path = save_record(record)
        successes += 1
        saved_records.append({
            "url": url,
            "bronze_path": str(output_path),
        })

        print("Title:", record["payload"].get("title"))
        print("Saved to:", output_path)
    report_path = save_batch_report(
        args.manifest,
        started_at,
        saved_records,
        failures,
    )

    print("\nBatch report saved to:", report_path)
    print("\nCollection finished")
    print("Successful:", successes)
    print("Failed:", len(failures))

    for failure in failures:
        print(failure)