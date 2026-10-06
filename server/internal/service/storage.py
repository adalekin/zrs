from approck_services.integrations.upload import BaseUploadService


class AttachmentStorage(BaseUploadService):
    """Adapter over an S3-compatible object store. Adds reading and deleting to the upload base."""

    async def download(self, key: str) -> bytes:
        async with self.session.client("s3", endpoint_url=self.endpoint_url) as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            async with response["Body"] as body:
                return await body.read()

    async def delete(self, key: str) -> None:
        async with self.session.client("s3", endpoint_url=self.endpoint_url) as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)
