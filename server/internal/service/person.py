import datetime
from collections.abc import Sequence
from typing import Any

from approck_fastapi_utils.exceptions import Unauthorized
from approck_services.fastapi import make_service_type
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from internal.entity.enums import Role
from internal.entity.person import Person
from internal.exceptions import IdentityProviderUnavailable
from internal.service.oidc import OIDCVerifier

NAME_MAX_LENGTH = 255


class PersonService(make_service_type(Person)):
    async def find_one(self, id_: int) -> Person | None:
        return await self._find_one(select(Person).where(Person.id == id_))

    async def find_by_sub(self, sub: str) -> Person | None:
        return await self._find_one(select(Person).where(Person.sub == sub))

    async def find_with_role(self, role: Role) -> Sequence[Person]:
        return await self._find(select(Person).where(Person.roles.contains([role.value])).order_by(Person.name))

    async def sync(
        self,
        payload: dict[str, Any],
        roles: frozenset[Role],
        token: str,
        verifier: OIDCVerifier,
    ) -> Person | None:
        """Bring the person's row up to date with a verified token.

        The row is rewritten once per issued token: roles come from the token, name and
        email from the provider's UserInfo Endpoint. A person who has no row and no role
        is not recorded. Returns ``None`` only in that case.
        """
        person = await self.find_by_sub(payload["sub"])
        issued_at = datetime.datetime.fromtimestamp(payload["iat"], tz=datetime.UTC)

        if person is not None and person.token_issued_at >= issued_at:
            return person
        if person is None and not roles:
            return None

        try:
            userinfo = await verifier.userinfo(token)
        except IdentityProviderUnavailable:
            if person is None:
                raise
            # Known person: keep the stored name and leave token_issued_at untouched,
            # so the next request asks the provider again.
            return person

        if userinfo.get("sub") != payload["sub"]:
            # OpenID Connect Core 5.3.2: a UserInfo response for another subject must not be used.
            raise Unauthorized("Invalid token")

        name = userinfo.get("name")
        if not isinstance(name, str) or not name.strip():
            if person is None:
                raise IdentityProviderUnavailable("The identity provider returned no name for this person")
            return person

        email = userinfo.get("email")
        values = {
            "name": name.strip()[:NAME_MAX_LENGTH],
            "email": email if isinstance(email, str) and email else None,
            "roles": sorted(role.value for role in roles),
            "token_issued_at": issued_at,
        }
        statement = (
            insert(Person)
            .values(sub=payload["sub"], **values)
            .on_conflict_do_update(index_elements=[Person.sub], set_={**values, "updated_at": func.now()})
            .returning(Person)
        )
        person = await self.session.scalar(statement, execution_options={"populate_existing": True})
        await self.session.commit()
        return person
