"""Build disclosed salary summaries and supporting posting details by currency and period."""

import pandas as pd


COLUMN_NAMES = {
    "metadata.source": "source",
    "payload.identifier.value": "job_id",
    "payload.url": "posting_url",
    "payload.title": "title",
    "payload.hiringOrganization.name": "company_name",
    "payload.baseSalary.value.minValue": "salary_min",
    "payload.baseSalary.value.maxValue": "salary_max",
    "payload.baseSalary.currency": "currency",
    "payload.baseSalary.value.unitText": "salary_period",
}


def build_salary_datasets(silver):
    if silver.empty:
        raise ValueError("Cannot analyze an empty silver dataset.")

    required = [
        column
        for column in COLUMN_NAMES
        if not column.startswith("payload.baseSalary.")
    ]

    missing = [column for column in required if column not in silver]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Salary columns may be absent from a batch with no disclosed pay.
    jobs = (
        silver.reindex(columns=list(COLUMN_NAMES))
        .rename(columns=COLUMN_NAMES)
        .copy()
    )

    if jobs.duplicated(["source", "job_id"]).any():
        raise ValueError("Repeated posting identities in the silver batch.")

    disclosed = jobs[
        jobs["salary_min"].notna()
        | jobs["salary_max"].notna()
    ].copy()

    for column in ["currency", "salary_period"]:
        invalid = (
            disclosed[column].isna()
            | disclosed[column]
            .astype("string")
            .str.strip()
            .eq("")
            .fillna(False)
        )

        if invalid.any():
            raise ValueError(
                f"Disclosed salaries have missing or blank {column}."
            )

    summary = (
        disclosed
        .groupby(
            ["source", "currency", "salary_period"],
            as_index=False,
        )
        .agg(
            disclosed_posting_count=("job_id", "nunique"),
            lowest_salary_min=("salary_min", "min"),
            highest_salary_max=("salary_max", "max"),
        )
    )

    totals = (
        jobs.groupby("source", as_index=False)
        .agg(total_posting_count=("job_id", "nunique"))
    )

    summary = summary.merge(
        totals,
        on="source",
        how="left",
        validate="many_to_one",
    )

    summary["disclosure_percent_in_group"] = (
        summary["disclosed_posting_count"]
        / summary["total_posting_count"]
        * 100
    ).round(2)

    return summary, disclosed
