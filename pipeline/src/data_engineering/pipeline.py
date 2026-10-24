"""Run the Keejob pipeline from discovery through gold publication."""

import argparse

from data_engineering.gold.pipeline import run_gold
from data_engineering.ingestion.collect import run_collection
from data_engineering.ingestion.discover import run_discovery
from data_engineering.silver.pipeline import run_silver
from data_engineering.storage.connection import BUCKET, create_client
from data_engineering.storage.s3 import ensure_bucket, write_json
import sys
from datetime import datetime, timezone
from uuid import uuid4

def run_pipeline(
    client,
    limit=5,
    manifest_key=None,
    max_pages=None,
    resume_key=None,
):
    """Run all stages, save an execution report, and return the gold manifest key."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than zero or None.")
    if max_pages is not None:
        if max_pages <= 0:
            raise ValueError("max_pages must be greater than zero.")

        if manifest_key is not None:
            raise ValueError(
                "max_pages cannot be used when reusing a discovery manifest."
            )
    if manifest_key is not None and resume_key is not None:
        raise ValueError(
            "Choose either a manifest or a discovery checkpoint."
        )
    run_id = uuid4().hex
    report_key = f"reports/pipeline/keejob/{run_id}.json"

    report = {
        "run_id": run_id,
        "pipeline": "keejob",
        "bucket": BUCKET,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "status": "running",
        "stage": None,
        "collection_limit": limit,
        "outputs": {
            "discovery_manifest_key": manifest_key,
            "collection_report_key": None,
            "silver_key": None,
            "gold_manifest_key": None,
        },
        "error": None,
        "discovery_max_pages": max_pages,
                "discovery_checkpoint_key": (
            f"checkpoints/discovery/keejob/{run_id}.json"
            if manifest_key is None
            else None
        ),
        "discovery_resume_key": resume_key,
    }

    try:
        if manifest_key is None:
            report["stage"] = "discovery"
            print("\nStarting discovery", flush=True)
            manifest_key = run_discovery(
                client,
                max_pages=max_pages,
                checkpoint_key=report["discovery_checkpoint_key"],
                resume_key=resume_key,
            )
            report["outputs"]["discovery_manifest_key"] = manifest_key

        report["stage"] = "collection"
        print("\nStarting collection", flush=True)
        collection_key = run_collection(client, manifest_key, limit=limit)
        report["outputs"]["collection_report_key"] = collection_key

        report["stage"] = "silver"
        print("\nStarting silver transformation", flush=True)
        silver_key = run_silver(client, collection_key)
        report["outputs"]["silver_key"] = silver_key

        report["stage"] = "gold"
        print("\nStarting gold publication", flush=True)
        gold_key = run_gold(client, silver_key)
        report["outputs"]["gold_manifest_key"] = gold_key

        report["status"] = "success"

    except Exception as error:
        report["status"] = "failed"
        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
        raise

    finally:
        report["completed_at"] = datetime.now(timezone.utc).isoformat()

        try:
            write_json(client, report, report_key)
            print(f"\nPipeline report: s3://{BUCKET}/{report_key}")

        except Exception as reporting_error:
            if report["status"] == "success":
                raise

            # Preserve the original pipeline exception if reporting also fails.
            print(
                f"Could not save the pipeline report: {reporting_error}",
                file=sys.stderr,
            )

    return gold_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-key",
        help="Reuse an existing discovery manifest instead of scanning listings.",
    )
    parser.add_argument(
        "--resume-discovery",
        help="Discovery checkpoint object key to continue from.",
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
        help="Attempt every posting in the discovery manifest.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum listing pages to scan during discovery.",
    )

    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than zero")

    if args.max_pages is not None:
        if args.max_pages <= 0:
            parser.error("--max-pages must be greater than zero")

        if args.manifest_key is not None:
            parser.error("--max-pages cannot be combined with --manifest-key")
    if args.manifest_key is not None and args.resume_discovery is not None:
        parser.error(
            "--manifest-key cannot be combined with --resume-discovery"
        )
    client = create_client()
    ensure_bucket(client)
    gold_manifest_key = run_pipeline(
        client,
        limit=None if args.all else args.limit,
        manifest_key=args.manifest_key,
        max_pages=args.max_pages,
        resume_key=args.resume_discovery,
    )

    print("\nPipeline completed successfully.")
    print(f"Gold manifest: s3://{BUCKET}/{gold_manifest_key}")


if __name__ == "__main__":
    main()