"""Pure Keejob bronze-to-silver cleaning rules established in the exploration notebook."""

import pandas as pd
from bs4 import BeautifulSoup


DROP_COLUMNS = [
    "payload.@context",
    "payload.@type",
    "payload.identifier.@type",
    "payload.hiringOrganization.@type",
    "payload.jobLocation.@type",
    "payload.jobLocation.address.@type",
    "payload.baseSalary.@type",
    "payload.baseSalary.value.@type",
    "payload.applicantLocationRequirements.@type",
    "payload.applicantLocationRequirements.name",
    "payload.hiringOrganization.logo",
    "metadata.requested_url",
    "metadata.response_url",
    "metadata.http_status",
    "metadata.content_type",
]


def extract_description_text(html):
    if pd.isna(html):
        return pd.NA

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    return " ".join(text.split())


def transform_jobs(bronze):
    country_column = "payload.jobLocation.address.addressCountry"

    # Select the intended market before applying the remaining rules.
    silver = bronze.loc[
        bronze[country_column].eq("TN")
    ].copy()

    # Optional fields may be absent from an entire future batch.
    silver = silver.drop(columns=DROP_COLUMNS, errors="ignore")

    date_formats = {
        "payload.datePosted": "%Y-%m-%d",
        "payload.validThrough": "%Y-%m-%dT%H:%M:%S",
    }

    for column, date_format in date_formats.items():
        silver[column] = pd.to_datetime(
            silver[column],
            format=date_format,
            errors="raise",
        )

    silver["metadata.collected_at"] = pd.to_datetime(
        silver["metadata.collected_at"],
        utc=True,
        errors="raise",
    )

    date_columns = list(date_formats) + ["metadata.collected_at"]

    if silver[date_columns].isna().any().any():
        raise ValueError("Required date fields contain missing values.")

    invalid_dates = (
        silver["payload.validThrough"]
        < silver["payload.datePosted"]
    )

    if invalid_dates.any():
        job_ids = silver.loc[
            invalid_dates,
            "payload.identifier.value",
        ].tolist()

        raise ValueError(
            f"Expiry earlier than publication for job IDs: {job_ids}"
        )

    silver["payload.description"] = silver[
        "payload.description"
    ].map(extract_description_text)

    return silver.reset_index(drop=True)
