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
