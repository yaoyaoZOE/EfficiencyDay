from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from app.core.config import Settings


def test_auth_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.initial_username is None
    assert settings.initial_password is None
    assert settings.session_ttl_days == 7
    assert settings.public_origin is None
    assert settings.session_cookie_secure is True


@pytest.mark.parametrize("value, expected", [("true", True), ("false", False)])
def test_session_cookie_security_is_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("EFFICIENCYDAY_SESSION_COOKIE_SECURE", value)

    assert Settings(_env_file=None).session_cookie_secure is expected


@pytest.mark.parametrize("value", ["", "invalid"])
def test_invalid_session_cookie_security_is_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("EFFICIENCYDAY_SESSION_COOKIE_SECURE", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_compose_forwards_session_cookie_security_with_secure_default() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert (
        '      EFFICIENCYDAY_SESSION_COOKIE_SECURE: "${EFFICIENCYDAY_SESSION_COOKIE_SECURE:-true}"'
        in compose.split("  frontend:", 1)[0]
    )


@pytest.mark.parametrize("relative_path", [".env.example", "backend/.env.example"])
def test_env_examples_document_secure_cookie_default(relative_path: str) -> None:
    root = Path(__file__).resolve().parents[2]
    example = (root / relative_path).read_text(encoding="utf-8")

    assert "EFFICIENCYDAY_SESSION_COOKIE_SECURE=true" in example.splitlines()


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


@pytest.mark.parametrize(
    "value",
    [
        "https://user@example.com",
        "https://user:password@example.com",
        "https://:password@example.com",
        "https://user:@example.com",
        "https://@example.com",
        "https://:@example.com",
        AnyHttpUrl("https://user@example.com"),
        AnyHttpUrl("https://user:password@example.com"),
    ],
)
def test_public_origin_cannot_include_userinfo(value: str | AnyHttpUrl) -> None:
    with pytest.raises(ValidationError, match="userinfo"):
        Settings(public_origin=value, _env_file=None)


def test_session_lifetime_is_loaded_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EFFICIENCYDAY_SESSION_TTL_DAYS", "3")

    assert Settings(_env_file=None).session_ttl_days == 3


def test_compose_forwards_session_lifetime_with_seven_day_default() -> None:
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")

    assert (
        "      EFFICIENCYDAY_SESSION_TTL_DAYS: ${EFFICIENCYDAY_SESSION_TTL_DAYS:-7}"
        in compose.split("  frontend:", 1)[0]
    )


@pytest.mark.parametrize("relative_path", [".env.example", "backend/.env.example"])
def test_env_examples_document_session_lifetime(relative_path: str) -> None:
    root = Path(__file__).resolve().parents[2]
    example = (root / relative_path).read_text(encoding="utf-8")

    assert "EFFICIENCYDAY_SESSION_TTL_DAYS=7" in example.splitlines()
