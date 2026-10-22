"""Extract Keejob JobPosting objects and preserve bronze observations in MinIO."""
import json
from datetime import datetime, timezone
from uuid import uuid4

import requests
from bs4 import BeautifulSoup

from data_engineering.storage.s3 import write_json


def save_record_to_minio(client, record):
    """Save a bronze observation in MinIO and return its object key."""
    source = record["metadata"]["source"]
    collection_date = record["metadata"]["collected_at"][:10]

    key = (
        f"bronze/{source}/"
        f"collection_date={collection_date}/"
        f"{uuid4().hex}.json"
    )

    write_json(client, record, key)

    return key


def extract_job_posting(html):
    soup = BeautifulSoup(html, "html.parser")

    blocks = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    )

    for block in blocks:
        data = json.loads(block.get_text())

        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data

    raise ValueError("No JobPosting object found in the page.")


def collect_job(url):
    response = requests.get(
        url,
        headers={"User-Agent": "TunisianJobMarketResearch/0.1"},
        timeout=30,
    )
    response.raise_for_status()

    collected_at = datetime.now(timezone.utc)
    job = extract_job_posting(response.content)

    return {
        "metadata": {
            "source": "keejob",
            "requested_url": url,
            "response_url": response.url,
            "collected_at": collected_at.isoformat(),
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type"),
        },
        "payload": job,
    }


