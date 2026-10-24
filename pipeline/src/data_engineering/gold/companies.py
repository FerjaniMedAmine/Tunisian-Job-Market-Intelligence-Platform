"""Count distinct source postings per identifiable company."""

import pandas as pd


def build_company_counts(silver):
    jobs = silver[
        [
            "metadata.source",
            "payload.identifier.value",
            "payload.hiringOrganization.name",
            "payload.hiringOrganization.sameAs",
        ]
    ].rename(
        columns={
            "metadata.source": "source",
            "payload.identifier.value": "job_id",
            "payload.hiringOrganization.name": "company_name",
            "payload.hiringOrganization.sameAs": "company_url",
        }
    ).copy()

    jobs["company_name"] = jobs["company_name"].str.strip()

    identifiable = (
        jobs["company_url"].notna()
        & jobs["company_url"].str.strip().ne("").fillna(False)
        & jobs["company_name"].notna()
        & jobs["company_name"].ne("")
        & jobs["company_name"].str.casefold().ne("entreprise anonyme")
    )

    eligible_jobs = jobs.loc[identifiable].copy()

    gold = (
        eligible_jobs
        .groupby(["source", "company_url"], as_index=False)
        .agg(
            company_name=("company_name", "first"),
            posting_count=("job_id", "nunique"),
        )
        .sort_values(
            ["posting_count", "company_name", "company_url"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )

    return gold, int((~identifiable).sum())
