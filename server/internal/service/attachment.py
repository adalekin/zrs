from approck_fastapi_utils.exceptions import NotFound
from approck_services.fastapi import make_service_type
from approck_sqlalchemy_utils.mocks import get_session
from approck_sqlalchemy_utils.transaction import atomic
from fastapi import Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internal.entity.expense_request import Attachment
from internal.service.actor import Actor
from internal.service.expense_request import ExpenseRequestService
from internal.service.incoming_file import IncomingFile
from internal.service.storage import AttachmentStorage


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

    async def add(self, actor: Actor, request_id: int, file: UploadFile, storage: AttachmentStorage) -> Attachment:
        # Refuse early, before reading and storing the file. The same check runs again under the row lock.
        async with atomic(self.session):
            await self._request_service.lock_editable(actor, request_id)

        incoming = await IncomingFile.read(file)
        attachment = await incoming.store(request_id, actor.id, storage)

        async with atomic(self.session):
            await self._request_service.lock_editable(actor, request_id)
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
