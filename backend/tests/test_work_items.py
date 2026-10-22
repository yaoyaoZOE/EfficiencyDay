from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from conftest import migrate_database
from fastapi.testclient import TestClient
from sqlalchemy import select


def _client(database_path: Path) -> TestClient:
    from app.core.config import Settings
    from app.main import create_app

    migrate_database(database_path)
    settings = Settings(
        database_path=database_path,
        initial_username="admin",
        initial_password="correct horse battery staple",
        session_ttl_days=1,
        public_origin="https://testserver",
        _env_file=None,
    )
    return TestClient(create_app(settings), base_url="https://testserver")


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct horse battery staple"},
        headers={"Origin": "https://testserver"},
    )
    assert response.status_code == 200
    return client.get("/api/v1/auth/me").json()["csrf_token"]


def _write_headers(csrf_token: str) -> dict[str, str]:
    return {"Origin": "https://testserver", "X-CSRF-Token": csrf_token}


def test_create_title_only_work_item_starts_pending(tmp_path: Path) -> None:
    from app.db.models import WorkItem

    with _client(tmp_path / "work-items.db") as client:
        csrf_token = _login(client)
        response = client.post(
            "/api/v1/work-items",
            json={"title": "Read the design"},
            headers=_write_headers(csrf_token),
        )
        assert response.status_code == 201
        work_item_id = response.json()["id"]
        with client.app.state.session_factory() as session:
            item = session.scalar(select(WorkItem).where(WorkItem.id == work_item_id))

    assert item is not None
    assert item.title == "Read the design"
    assert item.status == "pending"
    assert item.version == 1
    assert item.urgency is None
    assert item.importance is None
    assert item.completed_on is None


def test_create_and_read_classified_work_item_preserves_sql_date(tmp_path: Path) -> None:
    with _client(tmp_path / "work-items.db") as client:
        csrf_token = _login(client)
        created = client.post(
            "/api/v1/work-items",
            json={
                "title": "Submit the report",
                "urgency": True,
                "importance": False,
                "color_key": "blue",
                "due_on": "2026-10-31",
                "goal": "Send the final report",
            },
            headers=_write_headers(csrf_token),
        )
        assert created.status_code == 201

        detail = client.get(f"/api/v1/work-items/{created.json()['id']}")

    assert detail.status_code == 200
    assert detail.json()["due_on"] == "2026-10-31"
    assert detail.json()["urgency"] is True
    assert detail.json()["importance"] is False
    assert detail.json()["color_key"] == "blue"
    assert detail.json()["goal"] == "Send the final report"


@pytest.mark.parametrize(
    ("urgency", "importance"),
    [(None, None), (True, None), (None, False)],
)
def test_due_date_and_color_do_not_classify_unset_priority_flags(
    tmp_path: Path, urgency: bool | None, importance: bool | None
) -> None:
    with _client(tmp_path / "work-items.db") as client:
        csrf_token = _login(client)
        response = client.post(
            "/api/v1/work-items",
            json={
                "title": "Unclassified",
                "urgency": urgency,
                "importance": importance,
                "due_on": "2026-10-31",
                "color_key": "red",
            },
            headers=_write_headers(csrf_token),
        )

    assert response.status_code == 201
    assert response.json()["urgency"] is urgency
    assert response.json()["importance"] is importance
    assert response.json()["due_on"] == "2026-10-31"
    assert response.json()["color_key"] == "red"


def test_list_returns_only_current_users_work_items(tmp_path: Path) -> None:
    from app.db.models import User, WorkItem

    with _client(tmp_path / "work-items.db") as client:
        _login(client)
        with client.app.state.session_factory() as session:
            other_user = User(username="other", password_hash="unused")
            session.add(other_user)
            session.flush()
            session.add(
                WorkItem(user_id=other_user.id, title="Private item", status="pending")
            )
            session.commit()

        created = client.post(
            "/api/v1/work-items",
            json={"title": "My item"},
            headers=_write_headers(client.get("/api/v1/auth/me").json()["csrf_token"]),
        )
        response = client.get("/api/v1/work-items")

    assert created.status_code == 201
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["My item"]


def test_non_owned_and_missing_work_item_ids_have_same_not_found_response(
    tmp_path: Path,
) -> None:
    from app.db.models import User, WorkItem

    with _client(tmp_path / "work-items.db") as client:
        _login(client)
        with client.app.state.session_factory() as session:
            other_user = User(username="other", password_hash="unused")
            session.add(other_user)
            session.flush()
            item = WorkItem(user_id=other_user.id, title="Private item", status="pending")
            session.add(item)
            session.commit()
            other_id = item.id

        non_owned = client.get(f"/api/v1/work-items/{other_id}")
        missing = client.get(f"/api/v1/work-items/{other_id + 1000}")

    assert non_owned.status_code == missing.status_code == 404
    assert non_owned.json() == missing.json()


def test_list_pagination_defaults_to_50_caps_at_100_and_orders_by_id(
    tmp_path: Path,
) -> None:
    from app.db.models import User, WorkItem

    with _client(tmp_path / "work-items.db") as client:
        _login(client)
        with client.app.state.session_factory() as session:
            user = session.scalar(select(User).where(User.username == "admin"))
            assert user is not None
            created_at = datetime(2026, 10, 20, 12, tzinfo=UTC)
            session.add_all(
                [
                    WorkItem(
                        user_id=user.id,
                        title=f"Item {index}",
                        status="pending",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                    for index in range(105)
                ]
            )
            session.commit()

        default_page = client.get("/api/v1/work-items")
        largest_page = client.get("/api/v1/work-items?limit=100")
        too_large = client.get("/api/v1/work-items?limit=101")

    assert default_page.status_code == 200
    default_items = default_page.json()["items"]
    assert len(default_items) == 50
    assert [item["id"] for item in default_items] == sorted(
        (item["id"] for item in default_items), reverse=True
    )
    assert largest_page.status_code == 200
    assert len(largest_page.json()["items"]) == 100
    assert too_large.status_code == 422


@pytest.mark.parametrize("query", ["?limit=0", "?limit=-1", "?offset=-1"])
def test_list_rejects_non_positive_limit_and_negative_offset(
    tmp_path: Path, query: str
) -> None:
    with _client(tmp_path / "work-items.db") as client:
        _login(client)
        response = client.get(f"/api/v1/work-items{query}")

    assert response.status_code == 422


def test_create_requires_authentication_and_valid_csrf_origin(tmp_path: Path) -> None:
    with _client(tmp_path / "work-items.db") as client:
        unauthenticated = client.post(
            "/api/v1/work-items",
            json={"title": "No session"},
            headers={"Origin": "https://testserver", "X-CSRF-Token": "anything"},
        )
        unauthenticated_list = client.get("/api/v1/work-items")
        unauthenticated_detail = client.get("/api/v1/work-items/1")
        csrf_token = _login(client)
        no_csrf = client.post(
            "/api/v1/work-items",
            json={"title": "No token"},
            headers={"Origin": "https://testserver"},
        )
        wrong_origin = client.post(
            "/api/v1/work-items",
            json={"title": "Wrong origin"},
            headers={
                "Origin": "https://attacker.example",
                "X-CSRF-Token": csrf_token,
            },
        )
        wrong_csrf = client.post(
            "/api/v1/work-items",
            json={"title": "Wrong token"},
            headers=_write_headers("wrong"),
        )

    assert (
        unauthenticated.status_code
        == unauthenticated_list.status_code
        == unauthenticated_detail.status_code
        == 401
    )
    assert no_csrf.status_code == wrong_origin.status_code == wrong_csrf.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "x" * 501},
        {"title": "Invalid color", "color_key": "ultraviolet"},
        {"title": "Client status", "status": "completed"},
        {"title": "Client owner", "user_id": 999},
        {"title": "Client dates", "started_on": "2026-10-01", "completed_on": None},
    ],
)
def test_create_rejects_invalid_and_server_owned_fields(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    with _client(tmp_path / "work-items.db") as client:
        csrf_token = _login(client)
        response = client.post(
            "/api/v1/work-items",
            json=payload,
            headers=_write_headers(csrf_token),
        )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("pending", "in_progress"),
        ("pending", "completed"),
        ("pending", "cancelled"),
        ("in_progress", "pending"),
        ("in_progress", "completed"),
        ("in_progress", "cancelled"),
        ("completed", "pending"),
        ("completed", "in_progress"),
        ("cancelled", "pending"),
        ("cancelled", "in_progress"),
    ],
)
def test_status_transition_accepts_only_approved_edges(
    current: str, target: str
) -> None:
    from app.db.models import WorkItem
    from app.services.work_items import apply_status_transition

    item = WorkItem(user_id=1, title="Transition", status=current)
    apply_status_transition(item, target, "Asia/Shanghai")

    assert item.status == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("pending", "pending"),
        ("in_progress", "in_progress"),
        ("completed", "completed"),
        ("completed", "cancelled"),
        ("cancelled", "cancelled"),
        ("cancelled", "completed"),
        ("pending", "cancelled-invalid"),
        ("unknown", "pending"),
    ],
)
def test_status_transition_rejects_unapproved_edges(current: str, target: str) -> None:
    from app.db.models import WorkItem
    from app.services.work_items import apply_status_transition

    item = WorkItem(user_id=1, title="Transition", status=current)
    with pytest.raises(ValueError):
        apply_status_transition(item, target, "Asia/Shanghai")


def test_direct_completion_uses_account_local_date_without_start_date() -> None:
    from app.db.models import WorkItem
    from app.services.work_items import apply_status_transition

    item = WorkItem(user_id=1, title="Direct completion", status="pending")
    apply_status_transition(
        item,
        "completed",
        "Asia/Shanghai",
        now=datetime(2026, 10, 21, 16, 30, tzinfo=UTC),
    )

    assert item.status == "completed"
    assert item.started_on is None
    assert item.completed_on == date(2026, 10, 22)


def test_start_date_is_assigned_once_and_preserved_when_returning_to_pending() -> None:
    from app.db.models import WorkItem
    from app.services.work_items import apply_status_transition

    item = WorkItem(user_id=1, title="Start", status="pending", version=1)
    first_start = datetime(2026, 10, 21, 16, 30, tzinfo=UTC)
    apply_status_transition(item, "in_progress", "Asia/Shanghai", now=first_start)
    first_started_on = item.started_on
    apply_status_transition(item, "pending", "Asia/Shanghai")
    apply_status_transition(
        item,
        "in_progress",
        "Asia/Shanghai",
        now=datetime(2026, 10, 22, 16, 30, tzinfo=UTC),
    )

    assert first_started_on == date(2026, 10, 22)
    assert item.started_on == first_started_on
    assert item.completed_on is None
    assert item.version == 1


@pytest.mark.parametrize("target", ["pending", "in_progress"])
def test_reopening_completed_item_clears_completion_date(target: str) -> None:
    from app.db.models import WorkItem
    from app.services.work_items import apply_status_transition

    item = WorkItem(
        user_id=1,
        title="Reopen",
        status="completed",
        completed_on=date(2026, 10, 20),
        started_on=date(2026, 10, 19),
    )
    apply_status_transition(item, target, "Asia/Shanghai")

    assert item.status == target
    assert item.completed_on is None
    assert item.started_on == date(2026, 10, 19)
