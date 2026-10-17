# Fetch the current listing page.
# Extract its job URLs and add them to our set.
# Find its “Suivant” link.
# Wait two seconds before fetching that next page.
# Stop when no “Suivant” link exists.
import re
import time
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

LISTING_URL = "https://www.keejob.com/offres-emploi/"


def extract_job_urls(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    job_urls = set()

    for link in soup.find_all("a", href=True):
        absolute_url = urljoin(page_url, link["href"])
        parsed_url = urlsplit(absolute_url)

        if parsed_url.hostname != "www.keejob.com":
            continue

        if not re.fullmatch(
            r"/offres-emploi/\d+/[^/]+/",
            parsed_url.path,
        ):
            continue

        clean_url = parsed_url._replace(query="", fragment="").geturl()
        job_urls.add(clean_url)

    return job_urls

# def inspect_pagination(html, page_url):
#     soup = BeautifulSoup(html, "html.parser")
#     seen = set()

#     for link in soup.find_all("a", href=True):
#         absolute_url = urljoin(page_url, link["href"])
#         parsed_url = urlsplit(absolute_url)

#         if parsed_url.hostname != "www.keejob.com":
#             continue

#         if parsed_url.path != "/offres-emploi/":
#             continue

#         query = parse_qs(parsed_url.query)

#         if "page" not in query or absolute_url in seen:
#             continue

#         seen.add(absolute_url)

#         print({
#             "text": link.get_text(" ", strip=True),
#             "page": query["page"],
#             "rel": link.get("rel"),
#             "aria_label": link.get("aria-label"),
#             "url": absolute_url,
#         })


# def fetch_page_job_urls(session, page_number):
#     response = session.get(
#         LISTING_URL,
#         params={"page": page_number},
#         timeout=30,
#     )
#     response.raise_for_status()

#     print("Fetched:", response.url)
#     print("Fetched:", response.url)
#     inspect_pagination(response.content, response.url)

#     return extract_job_urls(response.content, response.url)


def extract_next_page_url(html, page_url):
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)

        if text != "Suivant":
            continue

        next_url = urljoin(page_url, link["href"])
        parsed_url = urlsplit(next_url)

        if (
            parsed_url.scheme == "https"
            and parsed_url.hostname == "www.keejob.com"
            and parsed_url.path == "/offres-emploi/"
        ):
            return parsed_url._replace(fragment="").geturl()

    return None


def save_discovery(job_urls, page_count, started_at):
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "source": "keejob",
        "listing_url": LISTING_URL,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "pages_inspected": page_count,
        "candidate_count": len(job_urls),
        "job_urls": sorted(job_urls),
    }

    directory = Path("data") / "discovery" / "keejob"
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{uuid4().hex}.json"

    with output_path.open("x", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return output_path


if __name__ == "__main__":
    started_at = datetime.now(timezone.utc)
if __name__ == "__main__":
    all_job_urls = set()
    visited_urls = set()
    next_url = LISTING_URL
    page_count = 0

    with requests.Session() as session:
        session.headers.update(
            {"User-Agent": "TunisianJobMarketResearch/0.1"}
        )

        while next_url is not None:
            if next_url in visited_urls:
                raise RuntimeError(
                    f"Pagination repeated a URL: {next_url}"
                )

            if page_count > 0:
                time.sleep(2)

            response = session.get(next_url, timeout=30)
            response.raise_for_status()

            if response.url in visited_urls:
                raise RuntimeError(
                    f"Pagination redirected to a visited URL: {response.url}"
                )

            visited_urls.update({next_url, response.url})

            page_job_urls = extract_job_urls(
                response.content,
                response.url,
            )

            if not page_job_urls:
                raise RuntimeError(
                    f"No candidate job URLs found: {response.url}"
                )

            new_job_urls = page_job_urls - all_job_urls
            all_job_urls.update(page_job_urls)
            page_count += 1

            print(
                f"Page {page_count}: "
                f"{len(page_job_urls)} candidates, "
                f"{len(new_job_urls)} new — {response.url}",
                flush=True,
            )

            next_url = extract_next_page_url(
                response.content,
                response.url,
            )
    output_path = save_discovery(
        all_job_urls,
        page_count,
        started_at,
    )

    print("Discovery manifest saved to:", output_path)

    print("\nNo 'Suivant' link found. Discovery stopped.")
    print("Pages inspected:", page_count)
    print("Total unique candidate URLs:", len(all_job_urls))