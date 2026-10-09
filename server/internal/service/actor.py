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

    @classmethod
    def as_last_signed_in(cls, person: Person) -> "Actor":
        """The person with the roles their latest sign-in gave them.

        For an action that comes without a token, from the chat with the bot: the service
        has nothing fresher to go by there.
        """
        return cls(person=person, roles=frozenset(Role(role) for role in person.roles))
