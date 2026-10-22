"""Build all gold models from MinIO silver and publish the complete-run manifest last."""

import argparse
from datetime import datetime, timezone
from pathlib import PurePosixPath
from uuid import uuid4

from data_engineering.gold.companies import build_company_counts
from data_engineering.gold.governorates import build_governorate_counts
from data_engineering.gold.salaries import build_salary_datasets
from data_engineering.storage.connection import BUCKET, create_client
from data_engineering.storage.s3 import read_parquet, write_json, write_parquet





def run_gold(client, silver_key):
    """Build and publish gold datasets; return the published manifest key."""
    run_id = uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    batch_id = PurePosixPath(silver_key).stem
    batch_prefix = f"gold/keejob/{batch_id}"
    run_prefix = f"{batch_prefix}/runs/{run_id}"
    silver = read_parquet(client, silver_key)
    companies, excluded_companies = build_company_counts(silver)
    governorates = build_governorate_counts(silver)
    salary_summary, salary_postings = build_salary_datasets(silver)
    if int(companies["posting_count"].sum()) + excluded_companies != len(silver):
        raise ValueError("Company counts do not reconcile with silver.")
    if int(governorates["posting_count"].sum()) != len(silver):
        raise ValueError("Governorate counts do not reconcile with silver.")
    if int(salary_summary["disclosed_posting_count"].sum()) != len(salary_postings):
        raise ValueError("Salary summary does not reconcile with details.")
    datasets = {
        "company_posting_counts": companies,
        "governorate_posting_counts": governorates,
        "salary_summary": salary_summary,
        "salary_postings": salary_postings,
    }
    outputs = {}
    for name, dataframe in datasets.items():
        key = f"{run_prefix}/{name}.parquet"

        write_parquet(client, dataframe, key)

        outputs[name] = {
            "key": key,
            "row_count": len(dataframe),
        }

        print(f"Saved {name}: {len(dataframe)} rows", flush=True)
    manifest = {
        "run_id": run_id,
        "status": "complete",
        "bucket": BUCKET,
        "input_silver_key": silver_key,
        "input_count": len(silver),
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "company_ranking_excluded_count": excluded_companies,
        "datasets": outputs,
    }
    manifest_key = f"{batch_prefix}/manifest.json"
    write_json(client, manifest, manifest_key)
    print(f"\nPublished manifest: s3://{BUCKET}/{manifest_key}")
    return manifest_key

def main():
    """Run the gold stage from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "silver_key",
        help="Silver Parquet object key inside the MinIO bucket.",
    )
    args = parser.parse_args()

    client = create_client()
    run_gold(client, args.silver_key)


if __name__ == "__main__":
    main()



