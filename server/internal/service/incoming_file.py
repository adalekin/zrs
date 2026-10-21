import uuid
from dataclasses import dataclass
from typing import Self

from fastapi import UploadFile

from internal.config import settings
from internal.entity.expense_request import Attachment
from internal.exceptions import AttachmentTooLarge
from internal.service.storage import AttachmentStorage

READ_CHUNK_BYTES = 1024 * 1024
DEFAULT_CONTENT_TYPE = "application/octet-stream"
DEFAULT_FILENAME = "file"
#: The tail is kept when a name is longer: that is where the extension is.
FILENAME_MAX_LENGTH = 255


@dataclass(frozen=True)
class IncomingFile:
    """A payment document read from an upload within the installation limit, not stored yet."""

    filename: str
    content_type: str
    body: bytes

    @classmethod
    async def read(cls, file: UploadFile) -> Self:
        limit = settings.ATTACHMENT_MAX_BYTES
        chunks: list[bytes] = []
        size = 0
        while chunk := await file.read(READ_CHUNK_BYTES):
            size += len(chunk)
            if size > limit:
                raise AttachmentTooLarge(limit)
            chunks.append(chunk)
        return cls(
            filename=(file.filename or DEFAULT_FILENAME)[-FILENAME_MAX_LENGTH:],
            content_type=file.content_type or DEFAULT_CONTENT_TYPE,
            body=b"".join(chunks),
        )

    async def store(self, request_id: int, uploaded_by_id: int, storage: AttachmentStorage) -> Attachment:
        """Put the object into the store and return its row, which the caller adds inside its transaction.

        The object is stored before its row: the transaction that writes the row makes no network calls.
        """
        storage_key = f"requests/{request_id}/{uuid.uuid4().hex}"
        await storage.upload_from_bytes(key=storage_key, body=self.body, content_type=self.content_type)
        return Attachment(
            request_id=request_id,
            uploaded_by_id=uploaded_by_id,
            filename=self.filename,
            content_type=self.content_type,
            size=len(self.body),
            storage_key=storage_key,
        )
