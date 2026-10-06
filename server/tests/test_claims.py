from internal.entity.enums import Role
from internal.service.claims import ClaimsMapper

ROLE_VALUES = {
    Role.REQUESTER: "employees",
    Role.MODERATOR: "finance-approvers",
    Role.FINANCE_DIRECTOR: "finance-heads",
    Role.PAYER: "finance-heads",
}


def test_roles_listed_in_a_top_level_groups_claim() -> None:
    mapper = ClaimsMapper("groups", ROLE_VALUES)

    assert mapper.roles({"groups": ["finance-approvers", "something-else"]}) == {Role.MODERATOR}


def test_roles_listed_under_a_nested_path() -> None:
    mapper = ClaimsMapper("resource_access.zrs.roles", ROLE_VALUES)

    payload = {"resource_access": {"zrs": {"roles": ["employees"]}, "other-app": {"roles": ["finance-heads"]}}}

    assert mapper.roles(payload) == {Role.REQUESTER}


def test_roles_listed_under_a_namespaced_claim_with_dots_in_its_name() -> None:
    mapper = ClaimsMapper("https://example.com/roles", ROLE_VALUES)

    assert mapper.roles({"https://example.com/roles": ["employees"]}) == {Role.REQUESTER}


def test_one_provider_value_mapped_to_two_roles_gives_both() -> None:
    mapper = ClaimsMapper("groups", ROLE_VALUES)

    assert mapper.roles({"groups": ["finance-heads"]}) == {Role.FINANCE_DIRECTOR, Role.PAYER}


def test_values_outside_the_mapping_give_no_role() -> None:
    mapper = ClaimsMapper("groups", ROLE_VALUES)

    assert mapper.roles({"groups": ["admin", "moderator"]}) == frozenset()


def test_a_missing_claim_gives_no_role() -> None:
    mapper = ClaimsMapper("resource_access.zrs.roles", ROLE_VALUES)

    assert mapper.roles({"resource_access": {"other-app": {"roles": ["employees"]}}}) == frozenset()


def test_a_single_string_claim_is_read_as_one_value() -> None:
    mapper = ClaimsMapper("role", ROLE_VALUES)

    assert mapper.roles({"role": "employees"}) == {Role.REQUESTER}
