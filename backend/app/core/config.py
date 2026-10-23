from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="EFFICIENCYDAY_",
        extra="forbid",
    )

    database_path: Path = BACKEND_ROOT / "data" / "efficiencyday.db"
    initial_username: str | None = None
    initial_password: SecretStr | None = None
    session_ttl_days: PositiveInt = 7
    session_cookie_secure: bool = True
    public_origin: AnyHttpUrl | None = None

    @field_validator("public_origin", mode="before")
    @classmethod
    def blank_public_origin_is_absent(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            parsed = urlsplit(value)
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("public_origin must not include userinfo")
            if parsed.path or "?" in value or "#" in value:
                raise ValueError("public_origin must not include a path, query, or fragment")
        return value

    @field_validator("public_origin")
    @classmethod
    def public_origin_must_be_an_origin(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (value.username is not None or value.password is not None):
            raise ValueError("public_origin must not include userinfo")
        if value is not None and (
            value.path not in ("", "/") or value.query is not None or value.fragment is not None
        ):
            raise ValueError("public_origin must not include a path, query, or fragment")
        return value

    @field_validator("database_path")
    @classmethod
    def resolve_database_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            value = BACKEND_ROOT / value
        return value.resolve()
