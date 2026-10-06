import asyncio
from typing import Any

import httpx
import jwt
from approck_fastapi_utils.exceptions import Unauthorized
from approck_services.base import BaseService
from loguru import logger

from internal.exceptions import IdentityProviderUnavailable

#: Asymmetric algorithms only: the keys come from the provider's public JWKS.
ALLOWED_ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"]
HTTP_TIMEOUT_SECONDS = 10.0


class OIDCVerifier(BaseService):
    """Checks access tokens against the installation's OpenID Connect provider and reads UserInfo.

    The discovery document and the key set are fetched over httpx and kept in memory.
    A token signed with an unknown key id triggers one reload of the key set.
    """

    def __init__(self, issuer: str, audience: str) -> None:
        super().__init__()
        self._issuer = issuer
        self._audience = audience
        self._configuration: dict[str, Any] | None = None
        self._keys: jwt.PyJWKSet | None = None
        self._lock = asyncio.Lock()

    async def _fetch_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Identity provider request to {} failed: {}", url, exc)
            raise IdentityProviderUnavailable("The identity provider is unavailable") from exc

    async def _get_configuration(self) -> dict[str, Any]:
        if self._configuration is None:
            async with self._lock:
                if self._configuration is None:
                    self._configuration = await self._fetch_json(f"{self._issuer}/.well-known/openid-configuration")
        return self._configuration

    async def _load_keys(self) -> jwt.PyJWKSet:
        configuration = await self._get_configuration()
        try:
            keys = jwt.PyJWKSet.from_dict(await self._fetch_json(configuration["jwks_uri"]))
        except (KeyError, jwt.PyJWKSetError) as exc:
            logger.warning("Identity provider returned an unusable key set: {}", exc)
            raise IdentityProviderUnavailable("The identity provider is unavailable") from exc
        self._keys = keys
        return keys

    async def _get_signing_key(self, kid: str) -> jwt.PyJWK:
        keys = self._keys if self._keys is not None else await self._load_keys()
        try:
            return keys[kid]
        except KeyError:
            pass

        async with self._lock:
            keys = await self._load_keys()
        try:
            return keys[kid]
        except KeyError as exc:
            logger.warning("Access token is signed with an unknown key id {!r}", kid)
            raise Unauthorized("Invalid token") from exc

    async def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            logger.warning("Access token is not a JWT: {}", exc)
            raise Unauthorized("Invalid token") from exc

        kid = header.get("kid")
        if not kid:
            logger.warning("Access token has no key id")
            raise Unauthorized("Invalid token")

        signing_key = await self._get_signing_key(kid)

        try:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.InvalidAudienceError as exc:
            received = jwt.decode(token, options={"verify_signature": False}).get("aud")
            logger.warning("Access token audience mismatch: expected {!r}, received {!r}", self._audience, received)
            raise Unauthorized("Invalid token") from exc
        except jwt.InvalidTokenError as exc:
            logger.warning("Access token rejected: {}", exc)
            raise Unauthorized("Invalid token") from exc

    async def userinfo(self, token: str) -> dict[str, Any]:
        configuration = await self._get_configuration()
        try:
            endpoint = configuration["userinfo_endpoint"]
        except KeyError as exc:
            logger.warning("Identity provider discovery document has no userinfo_endpoint")
            raise IdentityProviderUnavailable("The identity provider is unavailable") from exc
        return await self._fetch_json(endpoint, headers={"Authorization": f"Bearer {token}"})
