"""Shared MinIO connection, bucket management, and JSON/Parquet object I/O."""

import json
from io import BytesIO
from pathlib import Path
from botocore.exceptions import ClientError
import pandas as pd

from jobmarket_exploration.storage.connection import BUCKET


def ensure_bucket(client):
    try:
        client.head_bucket(Bucket=BUCKET)

    except ClientError as error:
        status = error.response["ResponseMetadata"]["HTTPStatusCode"]

        if status != 404:
            raise

        client.create_bucket(Bucket=BUCKET)


def read_json(client, key):
    response = client.get_object(Bucket=BUCKET, Key=key)

    with response["Body"] as body:
        return json.load(body)


def write_json(client, value, key):
    client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def read_parquet(client, key):
    response = client.get_object(
        Bucket=BUCKET,
        Key=key,
    )

    with response["Body"] as body:
        content = body.read()

    return pd.read_parquet(
        BytesIO(content),
        engine="pyarrow",
    )


def write_parquet(client, dataframe, key):
    buffer = BytesIO()
    dataframe.to_parquet(buffer, engine="pyarrow", index=False)

    client.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream",
    )


def upload_file(client, path, key):
    """Upload an existing file and verify its stored length."""
    path = Path(path)
    local_size = path.stat().st_size
    client.upload_file(Filename=str(path), Bucket=BUCKET, Key=key)
    metadata = client.head_object(Bucket=BUCKET, Key=key)
    if metadata["ContentLength"] != local_size:
        raise ValueError(f"Stored size differs for object: {key}")
    return local_size
