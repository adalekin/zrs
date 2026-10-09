import datetime
import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")
TIME_OF_DAY_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


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

    #: Where the people who make the payments work: a name of the IANA time zone database.
    TIMEZONE: ZoneInfo
    #: The time of day, HH:MM in that zone, after which a payment is not made the same day.
    PAYMENT_DAY_ENDS_AT: datetime.time

    #: Whether people are told about requests outside the service, and through what.
    #: The rest of this block is required once it is ``telegram`` and unused while it is ``off``.
    NOTIFICATIONS: Literal["telegram", "off"]
    TELEGRAM_BOT_TOKEN: str | None = None
    #: The name of the bot without the at sign: links that start it are built from it.
    TELEGRAM_BOT_USERNAME: str | None = None
    #: How the server reaches the Telegram Bot API: straight or through the proxy of the installation.
    TELEGRAM_EGRESS: Literal["direct", "proxy"] | None = None
    TELEGRAM_PROXY_URL: str | None = None
    #: Whether a person may decide on a request from the chat with the bot, without signing in.
    TELEGRAM_DECISIONS: Literal["on", "off"] | None = None
    #: The public address of the web app, as the web app itself is given it: messages link to requests.
    AUTH_ORIGIN: str | None = None
    #: The language of the interface, as the web app is given it: messages are written in it.
    UI_LOCALE: Literal["ru", "en"] | None = None

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

    @field_validator("TIMEZONE", mode="before")
    @classmethod
    def find_timezone(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            return ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"{value!r} is not a time zone of the IANA database") from exc

    @field_validator("PAYMENT_DAY_ENDS_AT", mode="before")
    @classmethod
    def read_time_of_day(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if not TIME_OF_DAY_RE.fullmatch(value):
            raise ValueError(f"{value!r} is not a time of day written as HH:MM")
        return datetime.time.fromisoformat(value)

    @field_validator(
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BOT_USERNAME",
        "TELEGRAM_EGRESS",
        "TELEGRAM_PROXY_URL",
        "TELEGRAM_DECISIONS",
        "AUTH_ORIGIN",
        "UI_LOCALE",
        mode="before",
    )
    @classmethod
    def empty_is_not_set(cls, value: object) -> object:
        # A compose file hands an unset variable over as an empty string.
        return None if value == "" else value

    @field_validator("AUTH_ORIGIN")
    @classmethod
    def strip_origin_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value is not None else None

    @model_validator(mode="after")
    def check_notifications(self) -> "Settings":
        if self.NOTIFICATIONS == "off":
            return self
        needed = [
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_BOT_USERNAME",
            "TELEGRAM_EGRESS",
            "TELEGRAM_DECISIONS",
            "AUTH_ORIGIN",
            "UI_LOCALE",
        ]
        if self.TELEGRAM_EGRESS == "proxy":
            needed.append("TELEGRAM_PROXY_URL")
        missing = [name for name in needed if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{', '.join(missing)}: required while NOTIFICATIONS is 'telegram'")
        if self.TELEGRAM_EGRESS == "direct" and self.TELEGRAM_PROXY_URL is not None:
            raise ValueError("TELEGRAM_PROXY_URL: set while TELEGRAM_EGRESS is 'direct'; one of the two is wrong")
        return self

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
