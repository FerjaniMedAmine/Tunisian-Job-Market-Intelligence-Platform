"""Read bronze objects from MinIO, clean and validate jobs, and publish silver with a run report."""

import argparse
from datetime import datetime, timezone
from pathlib import PurePosixPath
from uuid import uuid4

import pandas as pd

from data_engineering.silver.quality import validate_silver
from data_engineering.silver.transform import transform_jobs
from data_engineering.storage.connection import BUCKET, create_client
from data_engineering.storage.s3 import read_json, write_json, write_parquet


def load_bronze(client, report_key):
    report = read_json(client, report_key)
    records = []

    for saved in report["saved_records"]:
        if "bronze_key" in saved:
            key = saved["bronze_key"]
        else:
            # Older reports reference local files migrated into MinIO.
            key = (
                PurePosixPath(saved["bronze_path"])
                .relative_to("data")
                .as_posix()
            )

        records.append(read_json(client, key))

    if not records:
        raise ValueError("The report references no saved records.")

    return pd.json_normalize(records, sep=".")


def run_silver(client, report_key):
    """Transform and validate bronze observations; return the silver key."""
    run_id = uuid4().hex
    batch_id = PurePosixPath(report_key).stem
    silver_key = f"silver/keejob/{batch_id}.parquet"
    execution_key = f"reports/transformation/keejob/{run_id}.json"
    run_report = {
        "run_id": run_id,
        "pipeline": "keejob_bronze_to_silver_minio",
        "bucket": BUCKET,
        "input_report_key": report_key,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "status": "running",
        "input_count": None,
        "excluded_country_count": None,
        "output_count": None,
        "output_key": None,
        "quality_checks": None,
        "error": None,
    }
    try:
        bronze = load_bronze(client, report_key)
        run_report["input_count"] = len(bronze)

        country = bronze["payload.jobLocation.address.addressCountry"]
        run_report["excluded_country_count"] = int(
            (~country.eq("TN")).sum()
        )

        silver = transform_jobs(bronze)

        checks = validate_silver(silver)
        run_report["quality_checks"] = checks

        failures = {
            name: count
            for name, count in checks.items()
            if count > 0
        }

        if failures:
            raise ValueError(f"Silver quality checks failed: {failures}")

        write_parquet(client, silver, silver_key)

        run_report["output_count"] = len(silver)
        run_report["output_key"] = silver_key
        run_report["status"] = "success"

        print("Input observations:", len(bronze))
        print("Silver rows:", len(silver))
        print(f"Saved to: s3://{BUCKET}/{silver_key}")

    except Exception as error:
        run_report["status"] = "failed"
        run_report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
        raise

    finally:
        run_report["completed_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

        write_json(client, run_report, execution_key)

        print(f"Run report: s3://{BUCKET}/{execution_key}")
    return silver_key


def main():
    """Run the silver stage from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report_key",
        help="Collection report object key inside the MinIO bucket.",
    )
    args = parser.parse_args()

    client = create_client()
    run_silver(client, args.report_key)


if __name__ == "__main__":
    main()


