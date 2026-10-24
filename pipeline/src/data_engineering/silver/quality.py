"""Validate required silver fields, posting identities, and disclosed salary bounds."""

import pandas as pd


def validate_silver(silver):
    required_columns = [
        "metadata.source",
        "payload.identifier.value",
        "payload.url",
        "payload.title",
        "payload.description",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in silver.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    checks = {
        "empty_dataset": int(silver.empty),
    }

    for column in required_columns:
        values = silver[column].astype("string")

        invalid = (
            values.isna()
            | values.str.strip().eq("").fillna(False)
        )

        checks[f"missing_or_blank:{column}"] = int(invalid.sum())

    checks["duplicate_identity_rows"] = int(
        silver.duplicated(
            subset=["metadata.source", "payload.identifier.value"],
            keep=False,
        ).sum()
    )

    salary_columns = {
        "min": "payload.baseSalary.value.minValue",
        "max": "payload.baseSalary.value.maxValue",
    }

    salary_bounds = {}

    for bound, column in salary_columns.items():
        # The entire column may be absent in a batch without salaries.
        original = silver.reindex(columns=[column])[column]
        numeric = pd.to_numeric(original, errors="coerce")

        checks[f"salary_{bound}_not_numeric"] = int(
            (original.notna() & numeric.isna()).sum()
        )

        checks[f"salary_{bound}_not_finite"] = int(
            numeric.isin([float("inf"), float("-inf")]).sum()
        )

        checks[f"salary_{bound}_negative"] = int(
            numeric.lt(0).sum()
        )

        salary_bounds[bound] = numeric

    checks["salary_min_above_max"] = int(
        salary_bounds["min"].gt(salary_bounds["max"]).sum()
    )

    return checks
