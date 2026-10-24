"""Follow Keejob listing pagination and publish discovery manifests to MinIO."""

import argparse
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import requests
from bs4 import BeautifulSoup


from data_engineering.storage.connection import BUCKET, create_client
from data_engineering.storage.s3 import ensure_bucket, read_json, write_json


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


def save_discovery(client,job_urls,page_count,started_at,max_pages,stop_reason,):
    """Save a discovery manifest in MinIO and return its object key."""
    manifest = {
        "source": "keejob",
        "listing_url": LISTING_URL,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pages_inspected": page_count,
        "candidate_count": len(job_urls),
        "job_urls": sorted(job_urls),
        "max_pages": max_pages,
        "stop_reason": stop_reason,
    }

    key = f"discovery/keejob/{uuid4().hex}.json"
    write_json(client, manifest, key)

    return key

def fetch_listing_page(session, url, max_attempts=3):
    """Retry temporary connection failures without skipping the page."""
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than zero.")

    for attempt in range(1, max_attempts + 1):
        print(f"Fetching ({attempt}/{max_attempts}): {url}", flush=True)

        try:
            response = session.get(url, timeout=(10, 30))
            response.raise_for_status()
            return response

        except (requests.Timeout, requests.ConnectionError) as error:
            if attempt == max_attempts:
                raise

            delay = 2 ** attempt
            print(
                f"{type(error).__name__}; retrying in {delay} seconds.",
                flush=True,
            )
            time.sleep(delay)

def run_discovery(
    client,
    max_pages=None,
    checkpoint_key=None,
    resume_key=None,
):
    """Discover posting URLs, optionally limiting the number of listing pages."""
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be greater than zero or None.")

    if resume_key is None:
        started_at = datetime.now(timezone.utc)
        all_job_urls = set()
        visited_urls = set()
        next_url = LISTING_URL
        page_count = 0
        page_history = []

    else:
        checkpoint = read_json(client, resume_key)

        if checkpoint["source"] != "keejob":
            raise ValueError("This checkpoint does not belong to Keejob.")

        started_at = datetime.fromisoformat(checkpoint["started_at"])
        all_job_urls = set(checkpoint["job_urls"])
        visited_urls = set(checkpoint["visited_urls"])
        next_url = checkpoint["next_url"]
        page_count = checkpoint["pages_inspected"]
        page_history = list(checkpoint["pages"])

        if next_url is not None:
            parsed = urlsplit(next_url)

            if (
                parsed.scheme != "https"
                or parsed.hostname != "www.keejob.com"
                or parsed.path != "/offres-emploi/"
            ):
                raise ValueError(
                    "Checkpoint contains an unexpected next-page URL."
                )

            if max_pages is not None and max_pages <= page_count:
                raise ValueError(
                    "max_pages must exceed the checkpoint's pages_inspected."
                )

        print(f"Resuming after {page_count} completed pages.", flush=True)

    checkpoint_key = checkpoint_key or (
        f"checkpoints/discovery/keejob/{uuid4().hex}.json"
    )

    def save_checkpoint():
        write_json(client, {
            "source": "keejob",
            "started_at": started_at.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "max_pages": max_pages,
            "pages_inspected": page_count,
            "candidate_count": len(all_job_urls),
            "job_urls": sorted(all_job_urls),
            "visited_urls": sorted(visited_urls),
            "next_url": next_url,
            "pagination_exhausted": next_url is None,
            "pages": page_history,
            "resumed_from": resume_key,
        }, checkpoint_key)

    save_checkpoint()
    print(f"Discovery checkpoint: s3://{BUCKET}/{checkpoint_key}")
    with requests.Session() as session:
        session.headers.update(
            {"User-Agent": "TunisianJobMarketResearch/0.1"}
        )

        while (
            next_url is not None
            and (max_pages is None or page_count < max_pages)
        ):
            if next_url in visited_urls:
                raise RuntimeError(
                    f"Pagination repeated a URL: {next_url}"
                )

            if page_count > 0:
                time.sleep(2)

            response = fetch_listing_page(session, next_url)
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

            repeated_job_urls = page_job_urls & all_job_urls
            new_job_urls = page_job_urls - all_job_urls
            all_job_urls.update(page_job_urls)
            page_count += 1
            page_history.append({
                "page": page_count,
                "url": response.url,
                "candidate_count": len(page_job_urls),
                "new_count": len(new_job_urls),
                "repeated_urls": sorted(repeated_job_urls),
            })

            print(
                f"Page {page_count}: "
                f"{len(page_job_urls)} candidates, "
                f"{len(new_job_urls)} new, "
                f"{len(repeated_job_urls)} already seen — {response.url}",
                flush=True,
            )

            next_url = extract_next_page_url(
                response.content,
                response.url,
            )
            save_checkpoint()
        
    stop_reason = (
        "no_next_page"
        if next_url is None
        else "page_limit"
    )

    manifest_key = save_discovery(
        client,
        all_job_urls,
        page_count,
        started_at,
        max_pages=max_pages,
        stop_reason=stop_reason,
    )

    print(f"Discovery manifest saved to: s3://{BUCKET}/{manifest_key}")
    print("Discovery stopped:", stop_reason)
    print("Pages inspected:", page_count)
    print("Total unique candidate URLs:", len(all_job_urls))
    return manifest_key

def main():
    """Run discovery from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum listing pages to scan; omitted means all pages.",
    )
    parser.add_argument(
        "--resume-discovery",
        help="Discovery checkpoint object key to continue from.",
    )
    args = parser.parse_args()

    if args.max_pages is not None and args.max_pages <= 0:
        parser.error("--max-pages must be greater than zero")

    client = create_client()
    ensure_bucket(client)

    run_discovery(
        client,
        max_pages=args.max_pages,
        resume_key=args.resume_discovery,
    )


if __name__ == "__main__":
    main()
