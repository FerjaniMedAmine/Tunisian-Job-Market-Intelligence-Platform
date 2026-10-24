"""Count distinct source postings per source-reported governorate, retaining Unknown."""

import pandas as pd


def build_governorate_counts(silver):
    jobs = silver[
        [
            "metadata.source",
            "payload.identifier.value",
            "payload.jobLocation.address.addressRegion",
        ]
    ].rename(
        columns={
            "metadata.source": "source",
            "payload.identifier.value": "job_id",
            "payload.jobLocation.address.addressRegion": "governorate",
        }
    ).copy()

    jobs["governorate"] = (
        jobs["governorate"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("Unknown")
    )

    gold = (
        jobs
        .groupby(["source", "governorate"], as_index=False)
        .agg(posting_count=("job_id", "nunique"))
        .sort_values(
            ["posting_count", "governorate"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    return gold
