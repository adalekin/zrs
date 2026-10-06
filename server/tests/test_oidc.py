import datetime
import json
from typing import Any

import jwt
import pytest
from approck_fastapi_utils.exceptions import Unauthorized
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_httpx import HTTPXMock

from internal.exceptions import IdentityProviderUnavailable
from internal.service.oidc import OIDCVerifier

ISSUER = "https://idp.test/realms/zrs"
AUDIENCE = "zrs"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
JWKS_URL = f"{ISSUER}/keys"
USERINFO_URL = f"{ISSUER}/userinfo"


class SigningKey:
    def __init__(self, kid: str) -> None:
        self.kid = kid
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwk(self) -> dict[str, Any]:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self._private_key.public_key()))
        return {**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}

    def token(self, **overrides: Any) -> str:
        now = datetime.datetime.now(tz=datetime.UTC)
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "alice",
            "iat": now,
            "exp": now + datetime.timedelta(minutes=5),
            "roles": ["requester"],
        }
        claims.update(overrides)
        return jwt.encode(claims, self._private_key, algorithm="RS256", headers={"kid": self.kid})


@pytest.fixture(scope="module")
def key() -> SigningKey:
    return SigningKey("key-1")


def serve_discovery(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=DISCOVERY_URL, json={"jwks_uri": JWKS_URL, "userinfo_endpoint": USERINFO_URL})


def serve_keys(httpx_mock: HTTPXMock, *keys: SigningKey) -> None:
    httpx_mock.add_response(url=JWKS_URL, json={"keys": [key.jwk() for key in keys]})


async def test_a_token_signed_by_the_provider_for_this_installation_is_accepted(
    httpx_mock: HTTPXMock, key: SigningKey
) -> None:
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    payload = await verifier.verify(key.token())

    assert payload["sub"] == "alice"
    assert payload["roles"] == ["requester"]


async def test_keys_are_fetched_once_for_many_tokens(httpx_mock: HTTPXMock, key: SigningKey) -> None:
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    await verifier.verify(key.token())
    await verifier.verify(key.token(sub="bob"))

    assert len(httpx_mock.get_requests(url=JWKS_URL)) == 1


async def test_a_token_from_another_issuer_is_refused(httpx_mock: HTTPXMock, key: SigningKey) -> None:
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    with pytest.raises(Unauthorized):
        await verifier.verify(key.token(iss="https://other-idp.test"))


async def test_a_token_issued_for_another_application_is_refused(httpx_mock: HTTPXMock, key: SigningKey) -> None:
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    with pytest.raises(Unauthorized):
        await verifier.verify(key.token(aud="another-app"))


async def test_an_expired_token_is_refused(httpx_mock: HTTPXMock, key: SigningKey) -> None:
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)
    past = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=1)

    with pytest.raises(Unauthorized):
        await verifier.verify(key.token(iat=past, exp=past + datetime.timedelta(minutes=5)))


async def test_a_token_signed_with_a_rotated_key_triggers_one_reload_of_the_keys(
    httpx_mock: HTTPXMock, key: SigningKey
) -> None:
    rotated = SigningKey("key-2")
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    serve_keys(httpx_mock, key, rotated)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    await verifier.verify(key.token())
    payload = await verifier.verify(rotated.token(sub="bob"))

    assert payload["sub"] == "bob"
    assert len(httpx_mock.get_requests(url=JWKS_URL)) == 2


async def test_a_token_signed_with_a_key_the_provider_does_not_have_is_refused(
    httpx_mock: HTTPXMock, key: SigningKey
) -> None:
    stranger = SigningKey("stranger")
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    with pytest.raises(Unauthorized):
        await verifier.verify(stranger.token())

    assert len(httpx_mock.get_requests(url=JWKS_URL)) == 2


async def test_a_token_signed_with_a_forged_key_under_a_known_key_id_is_refused(
    httpx_mock: HTTPXMock, key: SigningKey
) -> None:
    forged = SigningKey(key.kid)
    serve_discovery(httpx_mock)
    serve_keys(httpx_mock, key)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    with pytest.raises(Unauthorized):
        await verifier.verify(forged.token())


async def test_text_that_is_not_a_jwt_is_refused() -> None:
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    with pytest.raises(Unauthorized):
        await verifier.verify("opaque-access-token")


async def test_userinfo_is_read_with_the_access_token(httpx_mock: HTTPXMock) -> None:
    serve_discovery(httpx_mock)
    httpx_mock.add_response(
        url=USERINFO_URL,
        match_headers={"Authorization": "Bearer the-token"},
        json={"sub": "alice", "name": "Alice Example", "email": "alice@example.test"},
    )
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    assert (await verifier.userinfo("the-token"))["name"] == "Alice Example"


async def test_a_failing_userinfo_endpoint_is_reported_as_provider_unavailable(httpx_mock: HTTPXMock) -> None:
    serve_discovery(httpx_mock)
    httpx_mock.add_response(url=USERINFO_URL, status_code=503)
    verifier = OIDCVerifier(ISSUER, AUDIENCE)

    with pytest.raises(IdentityProviderUnavailable):
        await verifier.userinfo("the-token")
