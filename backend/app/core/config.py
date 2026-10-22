from pathlib import Path

from pydantic import PositiveInt, SecretStr, field_validator
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

    @field_validator("database_path")
    @classmethod
    def resolve_database_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            value = BACKEND_ROOT / value
        return value.resolve()
