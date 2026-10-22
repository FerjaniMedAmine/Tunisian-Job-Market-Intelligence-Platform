"""Read a MinIO Parquet object and display a preview."""

import argparse

from data_engineering.storage.connection import create_client
from data_engineering.storage.s3 import read_parquet





def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("key")
    args = parser.parse_args()
    client = create_client()
    dataframe = read_parquet(client, args.key)
    print("Rows and columns:", dataframe.shape)
    print("\nFirst 10 rows:")
    print(dataframe.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
