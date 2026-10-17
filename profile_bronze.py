"""Summarize field coverage in one completed collection batch."""

import argparse
import json
from collections import Counter
from pathlib import Path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    with args.report.open(encoding="utf-8") as file:
        report = json.load(file)

    field_counts = Counter()
    type_counts = Counter()
    job_ids = []
    missing_ids = 0

    for saved in report["saved_records"]:
        with Path(saved["bronze_path"]).open(encoding="utf-8") as file:
            record = json.load(file)

        job = record["payload"]

        for field, value in job.items():
            if value is not None and value != "" and value != [] and value != {}:
                field_counts[field] += 1

            type_counts[(field, type(value).__name__)] += 1

        identifier = job.get("identifier")
        job_id = (
            identifier.get("value")
            if isinstance(identifier, dict)
            else None
        )

        if job_id is None or job_id == "":
            missing_ids += 1
        else:
            job_ids.append(str(job_id))

    total = len(report["saved_records"])

    print("Records inspected:", total)
    print("Missing job IDs:", missing_ids)
    print("Unique job IDs:", len(set(job_ids)))
    print("Repeated job IDs:", len(job_ids) - len(set(job_ids)))

    print("\nTop-level field coverage:")
    for field, count in sorted(field_counts.items()):
        print(f"{field}: {count}/{total}")

    print("\nObserved Python types:")
    for (field, value_type), count in sorted(type_counts.items()):
        print(f"{field}: {value_type} — {count}")