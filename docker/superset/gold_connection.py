"""Expose a published MinIO gold batch as DuckDB SQL views."""

import json
import os
from urllib.parse import urlsplit

from duckdb_engine import ConnectionWrapper


GOLD_DATASETS = (
    "company_posting_counts",
    "governorate_posting_counts",
    "salary_summary",
    "salary_postings",
)


def sql_literal(value):
    """Quote a string embedded in SQL."""
    return "'" + value.replace("'", "''") + "'"


def configure_gold_connection(connection, connection_record):
    """Initialize DuckDB connections; leave PostgreSQL connections untouched."""
    if not isinstance(connection, ConnectionWrapper):
        return

    bucket = os.environ["MINIO_BUCKET"]
    endpoint = urlsplit(os.environ["MINIO_ENDPOINT"])
    manifest_key = os.environ["GOLD_MANIFEST_KEY"]

    connection.execute("SET threads = 2")
    connection.execute("SET memory_limit = '1GB'")
    connection.execute("INSTALL httpfs")
    connection.execute("LOAD httpfs")

    connection.execute(f"""
        CREATE OR REPLACE SECRET minio_connection (
            TYPE s3,
            PROVIDER config,
            KEY_ID {sql_literal(os.environ["MINIO_ROOT_USER"])},
            SECRET {sql_literal(os.environ["MINIO_ROOT_PASSWORD"])},
            REGION 'us-east-1',
            ENDPOINT {sql_literal(endpoint.netloc)},
            URL_STYLE 'path',
            USE_SSL {str(endpoint.scheme == "https").lower()},
            SCOPE {sql_literal(f"s3://{bucket}/")}
        )
    """)

    manifest_uri = f"s3://{bucket}/{manifest_key}"
    row = connection.execute(
        "SELECT to_json(manifest) FROM read_json_auto(?) AS manifest",
        [manifest_uri],
    ).fetchone()

    if row is None:
        raise ValueError("The gold manifest is empty.")

    manifest = json.loads(row[0])

    if manifest["status"] != "complete":
        raise ValueError("The gold publication is incomplete.")

    if manifest["bucket"] != bucket:
        raise ValueError("The gold manifest references a different bucket.")

    for name in GOLD_DATASETS:
        key = manifest["datasets"][name]["key"]
        uri = sql_literal(f"s3://{bucket}/{key}")

        connection.execute(
            f'CREATE OR REPLACE VIEW "{name}" '
            f"AS SELECT * FROM read_parquet({uri})"
        )