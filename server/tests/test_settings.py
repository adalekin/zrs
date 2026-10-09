import datetime
import re
from zoneinfo import ZoneInfo

import pytest

from internal.config import ConfigurationError, load_settings


@pytest.fixture(autouse=True)
def no_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Settings also read a .env file from the working directory; keep it out of these tests.
    monkeypatch.chdir(tmp_path)


def test_settings_load_from_the_environment() -> None:
    settings = load_settings()

    assert settings.CURRENCIES == ["RUB", "USD"]
    assert settings.database_url.database == "zrs_test"


def test_start_without_the_issuer_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OIDC_ISSUER")

    with pytest.raises(ConfigurationError, match="OIDC_ISSUER"):
        load_settings()


def test_start_without_the_payer_role_value_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROLE_PAYER")

    with pytest.raises(ConfigurationError, match="ROLE_PAYER"):
        load_settings()


def test_start_with_an_invalid_currency_code_names_the_setting_and_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURRENCIES", "RUB,EURO")

    with pytest.raises(ConfigurationError, match=r"CURRENCIES.*'EURO'"):
        load_settings()


def test_start_with_an_empty_currency_list_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURRENCIES", "")

    with pytest.raises(ConfigurationError, match="CURRENCIES"):
        load_settings()


def test_start_without_the_attachment_limit_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATTACHMENT_MAX_BYTES")

    with pytest.raises(ConfigurationError, match="ATTACHMENT_MAX_BYTES"):
        load_settings()


def test_the_payment_day_loads_as_a_time_in_a_timezone() -> None:
    settings = load_settings()

    assert settings.PAYMENT_DAY_ENDS_AT == datetime.time(16, 30)
    assert settings.TIMEZONE == ZoneInfo("Europe/Moscow")


def test_start_without_the_end_of_the_payment_day_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYMENT_DAY_ENDS_AT")

    with pytest.raises(ConfigurationError, match="PAYMENT_DAY_ENDS_AT"):
        load_settings()


@pytest.mark.parametrize("value", ["half past four", "16", "16:30:00", "24:00", "4:30 pm"])
def test_start_with_a_wrong_end_of_the_payment_day_names_the_setting_and_the_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("PAYMENT_DAY_ENDS_AT", value)

    with pytest.raises(ConfigurationError, match=rf"PAYMENT_DAY_ENDS_AT.*{re.escape(repr(value))}"):
        load_settings()


def test_start_without_the_timezone_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIMEZONE")

    with pytest.raises(ConfigurationError, match="TIMEZONE"):
        load_settings()


@pytest.mark.parametrize("value", ["Moscow", "Europe/Atlantis", "UTC+3", "../etc/passwd"])
def test_start_with_an_unknown_timezone_names_the_setting_and_the_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TIMEZONE", value)

    with pytest.raises(ConfigurationError, match=rf"TIMEZONE.*{re.escape(repr(value))}"):
        load_settings()


def test_notifications_load_with_the_bot_and_the_address_of_the_service() -> None:
    settings = load_settings()

    assert settings.NOTIFICATIONS == "telegram"
    assert settings.TELEGRAM_BOT_USERNAME == "zrs_test_bot"
    assert settings.AUTH_ORIGIN == "https://zrs.test"
    assert settings.TELEGRAM_PROXY_URL is None


def test_notifications_switched_off_need_no_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS", "off")
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME", "TELEGRAM_EGRESS", "AUTH_ORIGIN", "UI_LOCALE"):
        monkeypatch.delenv(name)

    assert load_settings().NOTIFICATIONS == "off"


def test_start_without_the_notifications_setting_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTIFICATIONS")

    with pytest.raises(ConfigurationError, match="NOTIFICATIONS"):
        load_settings()


def test_start_with_an_unknown_way_of_notifying_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS", "email")

    with pytest.raises(ConfigurationError, match="NOTIFICATIONS"):
        load_settings()


@pytest.mark.parametrize(
    "name", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME", "TELEGRAM_EGRESS", "AUTH_ORIGIN", "UI_LOCALE"]
)
def test_notifications_without_a_setting_of_the_bot_name_it(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ConfigurationError, match=name):
        load_settings()


def test_a_proxy_without_its_address_names_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_EGRESS", "proxy")

    with pytest.raises(ConfigurationError, match="TELEGRAM_PROXY_URL"):
        load_settings()


def test_a_proxy_with_its_address_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_EGRESS", "proxy")
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://proxy.test:1080")

    assert load_settings().TELEGRAM_PROXY_URL == "socks5://proxy.test:1080"


def test_a_proxy_address_with_direct_access_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://proxy.test:1080")

    with pytest.raises(ConfigurationError, match="TELEGRAM_PROXY_URL"):
        load_settings()
