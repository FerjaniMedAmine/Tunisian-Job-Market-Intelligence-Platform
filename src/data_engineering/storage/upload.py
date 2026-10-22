"""Upload one local file to MinIO and verify its stored length."""

import argparse
from pathlib import Path

from data_engineering.storage.connection import BUCKET, create_client
from data_engineering.storage.s3 import ensure_bucket, upload_file





def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("key")
    args = parser.parse_args()
    if not args.file.is_file():
        parser.error(f"File not found: {args.file}")
    client = create_client()
    ensure_bucket(client)
    size = upload_file(client, args.file, args.key)
    print(f"Uploaded to: s3://{BUCKET}/{args.key}")
    print("Stored size:", size, "bytes")


if __name__ == "__main__":
    main()
