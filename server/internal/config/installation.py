import re
from typing import Annotated

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")


class ConfigurationError(RuntimeError):
    """An installation setting is missing or invalid; the message names every such setting."""


class Settings(BaseSettings):
    """Installation settings.

    None of them has a default: a value substituted silently for access or money
    is worse than a refused start.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OIDC_ISSUER: str = Field(min_length=1)
    OIDC_AUDIENCE: str = Field(min_length=1)
    OIDC_ROLES_CLAIM: str = Field(min_length=1)

    ROLE_REQUESTER: str = Field(min_length=1)
    ROLE_MODERATOR: str = Field(min_length=1)
    ROLE_FINANCE_DIRECTOR: str = Field(min_length=1)
    ROLE_PAYER: str = Field(min_length=1)

    CURRENCIES: Annotated[list[str], NoDecode]
    ATTACHMENT_MAX_BYTES: int = Field(gt=0)

    S3_ENDPOINT_URL: str = Field(min_length=1)
    S3_BUCKET: str = Field(min_length=1)
    S3_ACCESS_KEY_ID: str = Field(min_length=1)
    S3_SECRET_ACCESS_KEY: str = Field(min_length=1)
    S3_REGION: str = Field(min_length=1)

    DB_HOST: str = Field(min_length=1)
    DB_PORT: int = Field(gt=0)
    DB_USER: str = Field(min_length=1)
    DB_PASSWORD: str = Field(min_length=1)
    DB_NAME: str = Field(min_length=1)

    @field_validator("OIDC_ISSUER")
    @classmethod
    def strip_issuer_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("CURRENCIES", mode="before")
    @classmethod
    def split_currencies(cls, value: object) -> object:
        if isinstance(value, str):
            return [code.strip() for code in value.split(",") if code.strip()]
        return value

    @field_validator("CURRENCIES")
    @classmethod
    def check_currencies(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one currency code is required")
        for code in value:
            if not CURRENCY_CODE_RE.fullmatch(code):
                raise ValueError(f"{code!r} is not a three-letter ISO 4217 code")
        if len(set(value)) != len(value):
            raise ValueError("currency codes must not repeat")
        return value

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
        )
        raise ConfigurationError(f"Invalid installation settings: {problems}") from exc
