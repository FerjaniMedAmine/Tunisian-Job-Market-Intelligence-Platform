"""Run SQL against a Parquet object in MinIO and return a pandas DataFrame."""

from urllib.parse import urlsplit

import duckdb
from jobmarket_exploration.storage.connection import BUCKET, create_client
def _sql_literal(value):
    """Escape a string used as a SQL literal."""
    return "'" + value.replace("'", "''") + "'"


def query_parquet(session, key, sql):
    """
    Query a remote Parquet object using the supplied session.

    Reference the object as `dataset` in SQL.
    Return the result as a pandas DataFrame.
    """
    client = create_client(session)
    credentials = session.get_credentials().get_frozen_credentials()

    endpoint = urlsplit(client.meta.endpoint_url)
    uri = f"s3://{BUCKET}/{key}"

    with duckdb.connect(":memory:") as connection:
        connection.execute("INSTALL httpfs")
        connection.execute("LOAD httpfs")

        connection.execute(f"""
            CREATE SECRET minio_connection (
                TYPE s3,
                PROVIDER config,
                KEY_ID {_sql_literal(credentials.access_key)},
                SECRET {_sql_literal(credentials.secret_key)},
                REGION {_sql_literal(client.meta.region_name)},
                ENDPOINT {_sql_literal(endpoint.netloc)},
                URL_STYLE 'path',
                USE_SSL {str(endpoint.scheme == "https").lower()}
            )
        """)

        connection.read_parquet(uri).create_view("dataset")

        return connection.sql(sql).df()
