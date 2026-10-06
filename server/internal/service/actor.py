from dataclasses import dataclass

from internal.entity.enums import Role
from internal.entity.person import Person


@dataclass(frozen=True)
class Actor:
    """The signed-in person together with the roles carried by the current token."""

    person: Person
    roles: frozenset[Role]

    @property
    def id(self) -> int:
        return self.person.id

    def has(self, role: Role) -> bool:
        return role in self.roles
