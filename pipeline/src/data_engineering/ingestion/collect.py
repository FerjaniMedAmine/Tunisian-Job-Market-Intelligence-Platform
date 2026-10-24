"""Read a discovery manifest from MinIO and publish bronze observations and a collection report."""
import argparse
import time
from datetime import datetime, timezone
from uuid import uuid4

import requests

from data_engineering.ingestion.collector import (collect_job,save_record_to_minio,)
from data_engineering.storage.connection import BUCKET, create_client
from data_engineering.storage.s3 import ensure_bucket, write_json,read_json


def save_batch_report(
    client,
    manifest_key,
    started_at,
    saved_records,
    failures,
):
    report = {
        "source": "keejob",
        "manifest_key": manifest_key,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "successful_count": len(saved_records),
        "failed_count": len(failures),
        "saved_records": saved_records,
        "failures": failures,
    }

    key = f"reports/keejob/{uuid4().hex}.json"
    write_json(client, report, key)

    return key


def run_collection(client, manifest_key, limit=5):
    """Collect postings, save the batch report, and return its object key."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than zero or None.")

    manifest = read_json(client, manifest_key)

    started_at = datetime.now(timezone.utc)
    saved_records = []
    manifest_urls = manifest["job_urls"]

    if limit is None:
        job_urls = manifest_urls
    else:
        job_urls = manifest_urls[:limit]
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

        bronze_key = save_record_to_minio(client, record)

        successes += 1
        saved_records.append({
            "url": url,
            "bronze_key": bronze_key,
        })

        print("Title:", record["payload"].get("title"))
        print(f"Saved to: s3://{BUCKET}/{bronze_key}")
    report_key = save_batch_report(
        client,
        manifest_key,
        started_at,
        saved_records,
        failures,
    )

    print(f"\nBatch report saved to: s3://{BUCKET}/{report_key}")
    print("\nCollection finished")
    print("Successful:", successes)
    print("Failed:", len(failures))
    for failure in failures:
        print(failure)

    return report_key

def main():
    """Run collection from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest_key",
        help="Discovery manifest object key inside the MinIO bucket.",
    )

    batch_options = parser.add_mutually_exclusive_group()
    batch_options.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of postings to attempt (default: 5).",
    )
    batch_options.add_argument(
        "--all",
        action="store_true",
        help="Attempt every URL in the manifest.",
    )

    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than zero")

    client = create_client()
    ensure_bucket(client)

    run_collection(
        client,
        args.manifest_key,
        limit=None if args.all else args.limit,
    )
if __name__ == "__main__":
    main()
