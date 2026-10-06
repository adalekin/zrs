from approck_sqlalchemy_utils.mixins.auto_now import MixinWithAutoNow
from approck_sqlalchemy_utils.model import Base
from sqlalchemy import Boolean, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column


class ReferenceItem(MixinWithAutoNow, Base):
    """A value of one of the reference lists: operation types, payment forms, priorities."""

    __table_args__ = (UniqueConstraint("kind", "name", name="uq_reference_item_kind_name"),)

    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
