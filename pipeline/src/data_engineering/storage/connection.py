import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv


load_dotenv()

BUCKET = os.environ["MINIO_BUCKET"]

def create_session():
    """Load our storage credentials and region into a Boto3 session."""
    return boto3.Session(
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
    )


def create_client(session=None):
    """Create an S3 client, optionally using an existing session."""
    if session is None:
        session = create_session()

    return session.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )