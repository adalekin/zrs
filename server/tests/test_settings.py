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
