import datetime

from approck_sqlalchemy_utils.mixins.auto_now import MixinWithAutoNow
from approck_sqlalchemy_utils.model import Base
from sqlalchemy import TIMESTAMP, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column


class Person(MixinWithAutoNow, Base):
    """Someone who has signed in. Serves moderator selection and the names shown in requests and journals."""

    sub: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    #: Roles as of the latest token taken into account. Permissions are checked against the token, not this column.
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    token_issued_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True))
