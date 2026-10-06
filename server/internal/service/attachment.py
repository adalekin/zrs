import uuid

from approck_fastapi_utils.exceptions import NotFound
from approck_services.fastapi import make_service_type
from approck_sqlalchemy_utils.mocks import get_session
from approck_sqlalchemy_utils.transaction import atomic
from fastapi import Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internal.config import settings
from internal.entity.expense_request import Attachment
from internal.exceptions import AttachmentTooLarge
from internal.service.actor import Actor
from internal.service.expense_request import ExpenseRequestService
from internal.service.storage import AttachmentStorage

READ_CHUNK_BYTES = 1024 * 1024
DEFAULT_CONTENT_TYPE = "application/octet-stream"
DEFAULT_FILENAME = "file"
#: The tail is kept when a name is longer: that is where the extension is.
FILENAME_MAX_LENGTH = 255


class AttachmentService(make_service_type(Attachment)):
    autocommit = False

    def __init__(self, session: AsyncSession = Depends(get_session)) -> None:
        super().__init__(session)
        self._request_service = ExpenseRequestService(session=session)

    async def _get(self, actor: Actor, request_id: int, attachment_id: int) -> Attachment:
        # Visibility of the request first: a file of a request the person may not see does not exist for them.
        await self._request_service.get(actor, request_id)
        attachment = await self._find_one(
            select(Attachment).where(Attachment.id == attachment_id, Attachment.request_id == request_id)
        )
        if attachment is None:
            raise NotFound("Attachment not found")
        return attachment

    @staticmethod
    async def _read_limited(file: UploadFile) -> bytes:
        limit = settings.ATTACHMENT_MAX_BYTES
        chunks: list[bytes] = []
        size = 0
        while chunk := await file.read(READ_CHUNK_BYTES):
            size += len(chunk)
            if size > limit:
                raise AttachmentTooLarge(limit)
            chunks.append(chunk)
        return b"".join(chunks)

    async def add(self, actor: Actor, request_id: int, file: UploadFile, storage: AttachmentStorage) -> Attachment:
        # Refuse early, before reading and storing the file. The same check runs again under the row lock.
        async with atomic(self.session):
            await self._request_service.lock_editable(actor, request_id)

        body = await self._read_limited(file)
        content_type = file.content_type or DEFAULT_CONTENT_TYPE
        storage_key = f"requests/{request_id}/{uuid.uuid4().hex}"
        # The object is stored before its row: the action transaction makes no network calls.
        await storage.upload_from_bytes(key=storage_key, body=body, content_type=content_type)

        async with atomic(self.session):
            await self._request_service.lock_editable(actor, request_id)
            attachment = Attachment(
                request_id=request_id,
                uploaded_by_id=actor.id,
                filename=(file.filename or DEFAULT_FILENAME)[-FILENAME_MAX_LENGTH:],
                content_type=content_type,
                size=len(body),
                storage_key=storage_key,
            )
            self.session.add(attachment)
            await self.session.flush()

        return attachment

    async def read(
        self, actor: Actor, request_id: int, attachment_id: int, storage: AttachmentStorage
    ) -> tuple[Attachment, bytes]:
        attachment = await self._get(actor, request_id, attachment_id)
        return attachment, await storage.download(attachment.storage_key)

    async def remove(self, actor: Actor, request_id: int, attachment_id: int, storage: AttachmentStorage) -> None:
        async with atomic(self.session):
            await self._request_service.lock_editable(actor, request_id)
            attachment = await self._get(actor, request_id, attachment_id)
            storage_key = attachment.storage_key
            await self.session.delete(attachment)

        await storage.delete(storage_key)
