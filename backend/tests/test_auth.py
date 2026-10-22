from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from conftest import migrate_database
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.time import utc_now
from app.db.models import SessionRecord
from app.main import create_app


def _client(
    database_path: Path,
    *,
    public_origin: str | None = "https://testserver",
    base_url: str = "https://testserver",
) -> TestClient:
    migrate_database(database_path)
    settings = Settings(
        database_path=database_path,
        initial_username="admin",
        initial_password="correct horse battery staple",
        session_ttl_days=1,
        public_origin=public_origin,
        _env_file=None,
    )
    return TestClient(create_app(settings), base_url=base_url)


def _login(client: TestClient):
    return client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct horse battery staple"},
        headers={"Origin": "https://testserver"},
    )


def test_password_hashing_verifies_only_the_original_password() -> None:
    from app.core.security import hash_password, verify_password

    password = "correct horse battery staple"
    encoded = hash_password(password)

    assert encoded != password
    assert verify_password(password, encoded)
    assert not verify_password("incorrect password", encoded)
    assert not verify_password(password, "not-a-valid-password-hash")


def test_login_sets_secure_cookie_and_persists_only_session_token_hash(
    tmp_path: Path,
) -> None:
    from app.core.security import hash_token

    with _client(tmp_path / "auth.db") as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
            headers={"Origin": "https://testserver"},
        )
        cookie = response.headers["set-cookie"]
        raw_token = client.cookies.get("efficiencyday_session")
        assert raw_token is not None

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "httponly" in cookie.lower()
        assert "secure" in cookie.lower()
        assert "samesite=lax" in cookie.lower()
        assert "path=/" in cookie.lower()

        with client.app.state.session_factory() as session:
            record = session.scalar(select(SessionRecord))
            assert record is not None
            assert record.token_hash == hash_token(raw_token)
            assert record.token_hash != raw_token
            assert record.csrf_token


def test_invalid_username_and_password_have_same_generic_error(tmp_path: Path) -> None:
    with _client(tmp_path / "auth.db") as client:
        unknown_user = client.post(
            "/api/v1/auth/login",
            json={"username": "missing", "password": "wrong"},
            headers={"Origin": "https://testserver"},
        )
        wrong_password = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
            headers={"Origin": "https://testserver"},
        )

    assert unknown_user.status_code == wrong_password.status_code == 401
    assert unknown_user.json() == wrong_password.json()


def test_me_returns_authenticated_user_timezone_and_csrf_token(tmp_path: Path) -> None:
    with _client(tmp_path / "auth.db") as client:
        login = _login(client)
        assert login.status_code == 200

        response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["timezone"] == "Asia/Shanghai"
    assert response.json()["id"] == 1
    assert response.json()["csrf_token"]


def test_logout_requires_csrf_and_same_origin(tmp_path: Path) -> None:
    with _client(tmp_path / "auth.db") as client:
        _login(client)
        with client.app.state.session_factory() as session:
            csrf_token = session.scalar(select(SessionRecord)).csrf_token

        missing_csrf = client.post(
            "/api/v1/auth/logout", headers={"Origin": "https://testserver"}
        )
        mismatched_csrf = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "https://testserver", "X-CSRF-Token": "wrong"},
        )
        invalid_origin = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "https://attacker.example", "X-CSRF-Token": csrf_token},
        )

    assert missing_csrf.status_code == 403
    assert mismatched_csrf.status_code == 403
    assert invalid_origin.status_code == 403


def test_logout_revokes_session_clears_cookie_and_prevents_reuse(tmp_path: Path) -> None:
    from app.core.security import hash_token

    with _client(tmp_path / "auth.db") as client:
        _login(client)
        raw_token = client.cookies.get("efficiencyday_session")
        with client.app.state.session_factory() as session:
            record = session.scalar(
                select(SessionRecord).where(SessionRecord.token_hash == hash_token(raw_token))
            )
            assert record is not None
            csrf_token = record.csrf_token

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "https://testserver", "X-CSRF-Token": csrf_token},
        )
        client.cookies.set("efficiencyday_session", raw_token, domain="testserver", path="/")
        after_logout = client.get("/api/v1/auth/me")

        assert logout.status_code == 200
        assert "efficiencyday_session=" in logout.headers["set-cookie"]
        assert "httponly" in logout.headers["set-cookie"].lower()
        assert "secure" in logout.headers["set-cookie"].lower()
        assert "samesite=lax" in logout.headers["set-cookie"].lower()
        assert after_logout.status_code == 401
        with client.app.state.session_factory() as session:
            record = session.scalar(select(SessionRecord))
            assert record is not None
            assert record.revoked_at is not None


def test_expired_and_revoked_sessions_cannot_authenticate(tmp_path: Path) -> None:
    from app.core.security import hash_token

    with _client(tmp_path / "auth.db") as client:
        _login(client)
        expired_token = client.cookies.get("efficiencyday_session")
        with client.app.state.session_factory.begin() as session:
            record = session.scalar(
                select(SessionRecord).where(
                    SessionRecord.token_hash == hash_token(expired_token)
                )
            )
            assert record is not None
            record.expires_at = utc_now() - timedelta(seconds=1)

        expired = client.get("/api/v1/auth/me")
        assert expired.status_code == 401

        _login(client)
        revoked_token = client.cookies.get("efficiencyday_session")
        with client.app.state.session_factory.begin() as session:
            record = session.scalar(
                select(SessionRecord).where(
                    SessionRecord.token_hash == hash_token(revoked_token)
                )
            )
            assert record is not None
            record.revoked_at = utc_now()

        revoked = client.get("/api/v1/auth/me")

    assert revoked.status_code == 401


def test_unsafe_request_fails_closed_when_public_origin_is_unset(tmp_path: Path) -> None:
    with _client(tmp_path / "auth.db", public_origin=None) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
            headers={"Origin": "https://testserver"},
        )
        logout_response = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "https://testserver"},
        )

    assert response.status_code == logout_response.status_code == 503
    assert response.json() == {"detail": "Public origin is not configured."}
    assert logout_response.json() == {"detail": "Public origin is not configured."}


def test_unsafe_request_rejects_origin_mismatch(tmp_path: Path) -> None:
    with _client(tmp_path / "auth.db") as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
            headers={"Origin": "https://attacker.example"},
        )

    assert response.status_code == 403


def test_external_origin_is_accepted_without_forwarded_headers(tmp_path: Path) -> None:
    with _client(
        tmp_path / "auth.db",
        public_origin="https://app.example:443",
        base_url="http://backend.internal:6931",
    ) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
            headers={"Origin": "https://APP.example"},
        )

    assert response.status_code == 200
