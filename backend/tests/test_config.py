import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_auth_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.initial_username is None
    assert settings.initial_password is None
    assert settings.session_ttl_days == 7


def test_session_lifetime_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(session_ttl_days=0, _env_file=None)
