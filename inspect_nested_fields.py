"""Inspect nested field structures in one collection batch."""

import argparse
import json
from collections import Counter
from pathlib import Path


FIELDS = (
    "hiringOrganization",
    "jobLocation",
    "baseSalary",
    "jobLocationType",
    "applicantLocationRequirements",
)


def describe_structure(value):
    """Describe keys and types without including actual field values."""
    if isinstance(value, dict):
        return {
            key: describe_structure(item)
            for key, item in sorted(value.items())
        }

    if isinstance(value, list):
        # Describe distinct item structures, regardless of list length.
        item_shapes = {
            json.dumps(describe_structure(item), sort_keys=True)
            for item in value
        }
        return {
            "list_item_structures": [
                json.loads(shape)
                for shape in sorted(item_shapes)
            ]
        }

    return type(value).__name__


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    with args.report.open(encoding="utf-8") as file:
        report = json.load(file)

    structures = {field: Counter() for field in FIELDS}
    examples = {}

    for saved in report["saved_records"]:
        with Path(saved["bronze_path"]).open(encoding="utf-8") as file:
            job = json.load(file)["payload"]

        for field in FIELDS:
            if field not in job:
                continue

            value = job[field]
            shape = json.dumps(
                describe_structure(value),
                sort_keys=True,
            )

            structures[field][shape] += 1
            examples.setdefault((field, shape), value)

    for field in FIELDS:
        print(f"\n--- {field} ---")

        for shape, count in structures[field].most_common():
            print(f"\nStructure found in {count} records:")
            print(json.dumps(json.loads(shape), indent=2))

            print("Example:")
            print(json.dumps(
                examples[(field, shape)],
                ensure_ascii=False,
                indent=2,
            ))