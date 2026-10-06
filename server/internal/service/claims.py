from typing import Any

from approck_services.base import BaseService

from internal.entity.enums import Role


class ClaimsMapper(BaseService):
    """Anti-corruption layer: translates the provider's token claims into the service's own roles.

    ``roles_claim`` names where the provider lists roles. It is first looked up as a
    top-level claim under its exact name (which covers namespaced claims such as
    ``https://example.com/roles``), then as a dot-separated path into nested objects
    (``resource_access.zrs.roles``). The claim holds a list of strings or one string.
    """

    def __init__(self, roles_claim: str, role_values: dict[Role, str]) -> None:
        super().__init__()
        self._roles_claim = roles_claim
        self._role_values = role_values

    def _provider_values(self, payload: dict[str, Any]) -> set[str]:
        if self._roles_claim in payload:
            node: Any = payload[self._roles_claim]
        else:
            node = payload
            for part in self._roles_claim.split("."):
                if not isinstance(node, dict) or part not in node:
                    return set()
                node = node[part]

        if isinstance(node, str):
            return {node}
        if isinstance(node, list):
            return {value for value in node if isinstance(value, str)}
        return set()

    def roles(self, payload: dict[str, Any]) -> frozenset[Role]:
        provider_values = self._provider_values(payload)
        return frozenset(role for role, value in self._role_values.items() if value in provider_values)
