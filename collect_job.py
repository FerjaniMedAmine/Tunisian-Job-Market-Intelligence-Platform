# Parse the HTML.
# Find the JSON-LD script blocks.
# Convert each block’s text into a Python object.
# Return the object whose type is JobPosting.
# Raise an error if none matches.

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.keejob.com/offres-emploi/"
    "248502/analyste-fonctionnel-erp/"
)


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


def save_record(record):
    collection_date = record["metadata"]["collected_at"][:10]

    directory = (
        Path("data")
        / "bronze"
        / "keejob"
        / f"collection_date={collection_date}"
    )
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{uuid4().hex}.json"

    with output_path.open("x", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return output_path


if __name__ == "__main__":
    record = collect_job(URL)
    output_path = save_record(record)

    print("Collected:", record["payload"].get("title"))
    print("Saved to:", output_path)