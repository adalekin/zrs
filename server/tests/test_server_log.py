import pytest
from loguru import logger

from internal.app.http.app import create_app
from internal.config import settings


def reach(address: str) -> None:
    address.missing_attribute  # type: ignore[attr-defined]  # noqa: B018


def test_a_traceback_in_the_log_shows_the_code_without_the_values(capfd: pytest.CaptureFixture[str]) -> None:
    create_app()
    address = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

    try:
        reach(address)
    except AttributeError:
        logger.exception("A background pass failed")

    written = capfd.readouterr().err
    assert "A background pass failed" in written
    assert "address.missing_attribute" in written
    assert settings.TELEGRAM_BOT_TOKEN not in written
