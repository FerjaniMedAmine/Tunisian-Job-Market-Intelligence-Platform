import json

import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.keejob.com/offres-emploi/"
    "248502/analyste-fonctionnel-erp/"
)

response = requests.get(
    URL,
    headers={"User-Agent": "TunisianJobMarketResearch/0.1"},
    timeout=30,
)

print("HTTP status:", response.status_code)
response.raise_for_status()

print("Final URL:", response.url)
print("Content type:", response.headers.get("Content-Type"))

soup = BeautifulSoup(response.content, "html.parser")

heading = soup.find("h1")
print("Page heading:", heading.get_text(" ", strip=True) if heading else None)

structured_blocks = soup.find_all(
    "script",
    attrs={"type": "application/ld+json"},
)

print("JSON-LD blocks:", len(structured_blocks))

for index, block in enumerate(structured_blocks, start=1):
    try:
        data = json.loads(block.get_text())
    except json.JSONDecodeError:
        print(f"Block {index}: invalid JSON")
        continue

    print(f"\nBlock {index}:")
    print(json.dumps(data, ensure_ascii=False, indent=2))