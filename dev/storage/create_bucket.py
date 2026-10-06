"""Development only: create the attachments bucket in the local S3-compatible storage.

A production installation gets its bucket from whoever runs the storage; the server never creates one.
"""

import os

import boto3
from botocore.exceptions import ClientError

BUCKET_EXISTS_CODES = {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}


def main() -> None:
    bucket = os.environ["S3_BUCKET"]
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region_name=os.environ["S3_REGION"],
    )
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in BUCKET_EXISTS_CODES:
            raise
        print(f"Bucket {bucket!r} already exists")
        return
    print(f"Bucket {bucket!r} created")


if __name__ == "__main__":
    main()
