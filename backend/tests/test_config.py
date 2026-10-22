import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_auth_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.initial_username is None
    assert settings.initial_password is None
    assert settings.session_ttl_days == 7
    assert settings.public_origin is None


def test_session_lifetime_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(session_ttl_days=0, _env_file=None)


def test_blank_public_origin_is_treated_as_absent() -> None:
    settings = Settings(public_origin="  ", _env_file=None)

    assert settings.public_origin is None


def test_public_origin_cannot_include_path_query_or_fragment() -> None:
    for value in (
        "https://example.com/",
        "https://example.com/path",
        "https://example.com?query=value",
        "https://example.com?",
        "https://example.com#fragment",
        "https://example.com#",
    ):
        with pytest.raises(ValidationError):
            Settings(public_origin=value, _env_file=None)
